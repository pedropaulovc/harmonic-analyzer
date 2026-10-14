"""Offline contracts for the rocker arm outline template (MHA-CH-006-TL-13)."""

from __future__ import annotations

import math
import re
import tomllib

import pytest

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_outline_template_spec as spec
import draw_ch_rocker_arm_tl_outline_template as drawing
import export_features
from _paths import CAD_ROOT

STEM = "ch_rocker_arm_tl_outline_template"
# The template frame is the rocker build frame moved down to the pivot and
# raised by the aim offset.
_AIM_OFFSET = spec.TOP_ABOVE_PIVOT - rocker.TOP_EDGE_ABOVE_PIVOT


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {name for _feature, name in spec.DRAWING_BANDS} <= marked
    assert set(drawing.CALLOUTS_BELOW) <= marked


def test_number_is_the_parent_number_plus_tool_suffix_thirteen() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    assert (
        _config.parts("ch-rocker-arm-tl-outline-template")["number"]
        == f"{parent}-TL-13"
    )


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"SCRIBE THE|FILE TO|SAW|TRAMMEL", spec.DRAWING_NOTES.upper())


def test_apex_bands_sit_mid_zone_inside_the_rocker_arc_zone() -> None:
    """Both arcs of the rocker may come out 0..+0.5 high; the template's
    printed apex limits sit in the middle quarter of that zone."""
    features = _features()
    top = features["top_edge"]["height_above_pivot"]
    bottom = features["bottom_edge"]["depth"]
    assert top == [8.22, 8.28]
    assert bottom == [7.72, 7.78]
    zone_top = (
        rocker.TOP_EDGE_ABOVE_PIVOT,
        rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[0],
    )
    zone_bottom = (rocker.ARM_DEPTH - zone_top[1], rocker.ARM_DEPTH - zone_top[0])
    for (low, high), (zone_low, zone_high) in ((top, zone_top), (bottom, zone_bottom)):
        assert zone_low < low < high < zone_high
        assert math.isclose(
            (low + high) / 2.0, (zone_low + zone_high) / 2.0, abs_tol=1e-9
        )
        assert high - low <= 0.25 * (zone_high - zone_low) + 1e-9


_ROCKER_BOT_END_Y = rocker.CENTER_Y - rocker.R_BOTTOM * math.cos(rocker._ALPHA_BOT)
_ROCKER_TIP_Y = rocker.TOP_END_Y - rocker.TIP_FACE * math.cos(rocker._ALPHA_TOP)


@pytest.mark.parametrize(
    ("template", "rocker_point"),
    [
        ((spec.TOP_END_X, spec.TOP_END_Y), (rocker.TOP_END_X, rocker.TOP_END_Y)),
        ((spec.BOT_END_X, spec.BOT_END_Y), (rocker.BOT_END_X, _ROCKER_BOT_END_Y)),
        ((spec.TIP_X, spec.TIP_Y), (rocker.ROD_TIP_X, _ROCKER_TIP_Y)),
    ],
)
def test_outline_corners_are_the_rockers_raised_by_the_aim(
    template, rocker_point
) -> None:
    expected = (rocker_point[0], rocker_point[1] - rocker.PIVOT_MID_Y + _AIM_OFFSET)
    assert math.dist(template, expected) < 1e-3


def test_outline_corners_lie_on_their_arcs() -> None:
    def radius(x: float, y: float) -> float:
        return math.hypot(x, y - spec.CENTER_Y)

    assert math.isclose(
        radius(spec.TOP_END_X, spec.TOP_END_Y), spec.R_TOP, abs_tol=1e-9
    )
    assert math.isclose(
        radius(spec.BOT_END_X, spec.BOT_END_Y), spec.R_BOTTOM, abs_tol=1e-9
    )
    # The tip land is radial, so its foot lies TIP_FACE beyond the top arc.
    assert math.isclose(
        radius(spec.TIP_X, spec.TIP_Y), spec.R_TOP + spec.TIP_FACE, abs_tol=1e-9
    )
    # The tapered end runs inward and down from the tip to the bottom arc's end.
    assert spec.BOT_END_X < spec.TIP_X and spec.BOT_END_Y < spec.TIP_Y


def test_pin_gauge_locates_both_bores_inside_the_apex_band() -> None:
    hole = _features()["pivot_hole"]
    assert hole["dia"] == [6.5, 6.515]
    assert spec.PIN_GAUGE_MAX < hole["dia"][0]
    assert spec.PIN_GAUGE_MAX < rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]
    assert (hole["dia"][1] - spec.PIN_GAUGE_MIN) / 2.0 < spec.APEX_BAND[0]


def test_prechips_envelope_is_the_outline_extents_with_the_pivot_void() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    plate, hole = spec.PRECHIPS_SOLIDS
    xs, ys = zip(*spec.outline_points(), strict=True)
    low = (min(xs), min(ys), 0.0)
    high = (max(xs), max(ys), spec.THICK)
    assert plate["shape"] == "box" and plate["supply"] == "made"
    for axis in range(3):
        assert math.isclose(plate["at_mm"][axis], low[axis], abs_tol=1e-3)
        assert math.isclose(
            plate["at_mm"][axis] + plate["size_mm"][axis], high[axis], abs_tol=1e-3
        )
    assert hole["void"] is True and hole["shape"] == "cylinder"
    assert hole["at_mm"] == [0.0, 0.0, 0.0] and hole["axis"] == [0.0, 0.0, 1.0]
    assert hole["dia_mm"] == spec.PIVOT_HOLE_DIA and hole["length_mm"] == spec.THICK


def test_inventory_record_binds_this_part_without_hand_solids() -> None:
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    records = [
        record
        for table in inventory.values()
        if isinstance(table, dict)
        for record in table.values()
        if isinstance(record, dict) and record.get("cad") == STEM
    ]
    assert len(records) == 1
    assert "solids" not in records[0]


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked
