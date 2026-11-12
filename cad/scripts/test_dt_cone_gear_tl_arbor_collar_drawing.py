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


def test_each_member_sheet_names_only_its_own_gears() -> None:
    assert tuple(drawing.MEMBER_SHEETS.values()) == spec.CONFIGURATIONS
    assert len(set(spec.SHEET_NAMES)) == len(spec.SHEET_NAMES)
    notes = {name: spec.member_note(name) for name in spec.CONFIGURATIONS}
    for name, note in notes.items():
        assert len(note.splitlines()) == 1
        assert arbor.PART_NUMBER in note
    crank_tag = arbor.KEYED_GEARS[-1].tag
    holders = [
        n for n, tags in spec.GEARS_BY_CONFIGURATION.items() if crank_tag in tags
    ]
    assert len(holders) == 1
    assert "MHA-DT-07" in notes[holders[0]]
    assert sum("MHA-DT-07" in note for note in notes.values()) == 1


def test_the_largest_member_fits_the_sheet_at_its_scale() -> None:
    largest = max(spec.OD_BY_CONFIGURATION.values())
    half = largest * drawing.VIEW_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + half + drawing.BORE_RUN < drawing.SIDE_CENTER[0]
    assert drawing.END_CENTER[1] + half + drawing.OD_RISE < 0.2667
    assert drawing.END_CENTER[0] - half > 0.0127


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
