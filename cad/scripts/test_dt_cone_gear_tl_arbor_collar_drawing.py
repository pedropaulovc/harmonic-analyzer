"""Offline contracts for the keyed arbor's backing collars (MHA-DT-03-TL-04)."""

from __future__ import annotations

import math
import sys

import pytest

import _buildgraph as bg
import _config
import build_dt_cone_gear_tl_arbor_collar as part
import draw_dt_cone_gear_tl_arbor_collar as drawing
import dt_cone_gear_tl_arbor_collar_spec as spec
import dt_cone_gear_tl_keyed_arbor_spec as arbor
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")


def test_registry_row_is_three_tooling_members_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-04"
    assert row["drawing_unit"] == "in"
    assert row["default_configuration"] == spec.CONFIGURATIONS[0]
    quantities = row["configuration_quantities"]
    assert tuple(quantities) == spec.CONFIGURATIONS
    assert sum(int(q) for q in quantities.values()) == int(row["quantity"]) == 3
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_arbor_collar"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    stem = "dt_cone_gear_tl_arbor_collar"
    assert bg.is_shop_fixture(stem)
    assert stem in bg.references_of("dt_cone_gear_tl_arbor")
    for machine in bg.MACHINE_ASSEMBLIES:
        assert stem not in bg.references_of(machine)


def test_each_member_is_named_for_its_diameter_and_backs_its_gears() -> None:
    assert sorted(spec.OD_BY_CONFIGURATION.values()) == sorted(arbor.COLLAR_DIAS)
    for name, od in spec.OD_BY_CONFIGURATION.items():
        assert name == f"C{round(od / INCH * 100):03d}"
        assert spec.GEARS_BY_CONFIGURATION[name], name
    backed = [tag for tags in spec.GEARS_BY_CONFIGURATION.values() for tag in tags]
    assert sorted(backed) == sorted(blank.tag for blank in arbor.KEYED_GEARS)


def test_every_member_slides_over_the_pilot_and_the_thread() -> None:
    assert spec.BORE - (arbor.PILOT_DIA + XXX) > 0.0
    assert spec.BORE > arbor.THREAD_MAJOR
    # The nut's flats cover the bore's widest drilled limit.
    assert arbor.NUT_ACROSS_FLATS > spec.BORE + drilled_oversize_mm(unit="in")


def test_each_member_stands_under_the_root_of_every_gear_it_backs() -> None:
    roots = {blank.tag: blank.root_min_dia for blank in arbor.KEYED_GEARS}
    for name, tags in spec.GEARS_BY_CONFIGURATION.items():
        reach = spec.OD_BY_CONFIGURATION[name] / 2.0 + XX + arbor.COLLAR_FLOAT
        for tag in tags:
            assert reach + arbor.AIR_MIN <= roots[tag] / 2.0, (name, tag)


def test_member_volumes_and_dimensions_are_the_disc_and_bore() -> None:
    for name in spec.CONFIGURATIONS:
        od = spec.OD_BY_CONFIGURATION[name]
        expected = math.pi / 4.0 * (od**2 - spec.BORE**2) * spec.LENGTH
        assert spec.V_BY_CONFIGURATION[name] == pytest.approx(expected)
        assert spec.CONFIGURATION_FEATURES[name] == (spec.disc_feature(name),)
        marked = (
            spec.DRAWING_DIMENSIONS[spec.disc_sketch(name)]
            | (spec.DRAWING_DIMENSIONS[spec.disc_feature(name)])
        )
        assert marked == {
            spec.od_name(name),
            spec.bore_name(name),
            spec.length_name(name),
        }
    features = [f for fs in spec.CONFIGURATION_FEATURES.values() for f in fs]
    assert len(features) == len(set(features))


def test_each_member_sheet_carries_only_its_caption_and_the_kit_says_what_it_backs() -> None:
    """Which blanks a member backs is assembly information: the kit's step 2
    lists it by item number, and a part-sheet note repeating it was narration
    (rule 7, machinist review of farm 20261113T042822797Z)."""
    import dt_cone_gear_tl_arbor_assembly_spec as kit

    assert tuple(drawing.MEMBER_SHEETS.values()) == spec.CONFIGURATIONS
    assert len(set(spec.SHEET_NAMES)) == len(spec.SHEET_NAMES)
    labels = {name: spec.member_label(name) for name in spec.CONFIGURATIONS}
    assert len(set(labels.values())) == len(spec.CONFIGURATIONS)
    for name, label in labels.items():
        assert label == (
            f"{spec.CONFIGURATION_DESCRIPTIONS[name]} OF {spec.PART_NUMBER}, "
            f"QTY {spec.QUANTITY_BY_CONFIGURATION[name]}"
        )
        assert "\n" not in label
        item = kit.BOM_ITEMS[kit.member(name)]
        cones = [int(t[1:]) for t in spec.GEARS_BY_CONFIGURATION[name] if t[0] == "T"]
        assert f"ITEM {item} {cones[0]}T-{cones[-1]}T" in kit.ASSEMBLY_STEPS


def test_the_bore_callout_names_its_process() -> None:
    """Rule 12: a plain drilled size under DRILLED HOLES says DRILL."""
    assert spec.BORE_CALLOUT == "DRILL THRU"
    assert spec.BORE == pytest.approx(arbor.COLLAR_BORE)


def test_the_largest_member_fits_the_sheet_at_its_scale() -> None:
    largest = max(spec.OD_BY_CONFIGURATION.values())
    half = largest * drawing.VIEW_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + half + drawing.BORE_RUN < drawing.SIDE_CENTER[0]
    assert drawing.END_CENTER[1] + half + drawing.OD_DONOR_RISE < 0.2667
    assert drawing.END_CENTER[0] - half > 0.0127


def test_the_outside_diameter_reads_on_the_side_view_clear_of_the_isometric() -> None:
    """Rule 11: the OD stands right of the side view, its two-line text
    (about 20 mm wide at 2:1) between the collar and the largest isometric."""
    text_half = 0.010
    side_right = drawing.SIDE_CENTER[0] + spec.LENGTH * drawing.VIEW_SCALE[0] / 2000.0
    iso_left = (
        drawing.ISO_CENTER[0] - max(spec.OD_BY_CONFIGURATION.values()) / 2000.0 * 1.25
    )
    assert drawing.OD_ON_SIDE[1] == drawing.SIDE_CENTER[1]
    assert side_right < drawing.OD_ON_SIDE[0] - text_half
    assert drawing.OD_ON_SIDE[0] + text_half < iso_left


def test_the_isometric_and_its_label_stand_clear_of_the_title_block() -> None:
    """Title block top 0.066 m; the 1:1 isometric of the largest disc stands
    above its label, which stands above the title block."""
    title_top = 0.066
    largest = max(spec.OD_BY_CONFIGURATION.values()) / 1000.0
    assert drawing.ISO_NOTE_XY[1] - 0.005 > title_top
    assert drawing.ISO_CENTER[1] - largest / 2.0 * 1.25 > drawing.ISO_NOTE_XY[1]
    side_right = drawing.SIDE_CENTER[0] + spec.LENGTH * drawing.VIEW_SCALE[0] / 2000.0
    assert drawing.ISO_CENTER[0] - largest / 2.0 * 1.25 > side_right


def test_each_disc_is_authored_alone_in_its_own_member(monkeypatch) -> None:
    """A disc extruded into another member's solid merges with it and makes
    that disc its parent, so unsuppressing it brings the foreign disc back
    (farm run 20261112T203156536Z). Each disc is authored with its member
    active and every disc before it suppressed there, and its volume checked
    alone."""
    import asyncio

    state = {"active": None, "suppressed": set(), "existing": []}
    authored: list[tuple[str, str, tuple[str, ...]]] = []
    volumes: list[tuple[str, float]] = []

    async def noop(*_args, **_kwargs):
        return None

    def sync_noop(*_args, **_kwargs):
        return None

    async def activate(_adapter, configuration):
        state["active"] = configuration

    def suppress(_adapter, names, *, suppressed):
        for name in names:
            key = (state["active"], name)
            if suppressed:
                state["suppressed"].add(key)
            else:
                state["suppressed"].discard(key)

    async def add_disc(_adapter, jobs, configuration):
        present = tuple(
            name
            for name in state["existing"]
            if (state["active"], name) not in state["suppressed"]
        )
        authored.append((state["active"], configuration, present))
        state["existing"].append(spec.disc_feature(configuration))
        jobs.append((spec.length_name(configuration), '"CollarLength"'))

    async def volume(_adapter, label, expected, _tol):
        volumes.append((label, expected))
        return expected

    async def save(*_args, **_kwargs):
        return {}

    class _Adapter:
        async def create_part(self):
            from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

            return AdapterResult(status=AdapterResultStatus.SUCCESS, data="ok")

    for name, value in {
        "apply_package_model_units": sync_noop,
        "part_drawing_unit": lambda _stem: "in",
        "create_member_configurations": noop,
        "set_global": noop,
        "activate_member": activate,
        "set_member_suppression": suppress,
        "_add_disc": add_disc,
        "volume_check": volume,
        "force_rebuild": noop,
        "drive_dimension": noop,
        "apply_drawing_precision": sync_noop,
        "clear_dimensions_for_drawing": sync_noop,
        "mark_dimensions_for_drawing": sync_noop,
        "apply_drawing_properties": sync_noop,
        "select_member_features": noop,
        "apply_material": noop,
        "apply_member_properties": sync_noop,
        "report_mass_properties": noop,
        "save_member_part": save,
    }.items():
        monkeypatch.setattr(part, name, value)
    asyncio.run(part.build(_Adapter()))
    assert [(active, disc) for active, disc, _ in authored] == [
        (name, name) for name in spec.CONFIGURATIONS
    ]
    assert all(present == () for _active, _disc, present in authored)
    for name in spec.CONFIGURATIONS:
        checked = [v for label, v in volumes if name in label]
        assert checked and all(
            v == pytest.approx(spec.V_BY_CONFIGURATION[name]) for v in checked
        )


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
