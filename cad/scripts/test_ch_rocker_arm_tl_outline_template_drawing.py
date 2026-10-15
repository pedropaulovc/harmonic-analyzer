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
from _printed_tolerance import printed_deviations

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
    assert spec.ROCKER_NUMBER == parent


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
    assert top == [8.23, 8.27]
    assert bottom == [7.73, 7.77]
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


def test_locator_play_and_edge_band_fit_a_quarter_of_the_rocker_zone() -> None:
    """The pin's worst-case play in BOTH bores (template and rocker, each at
    its largest, the pin at its smallest) moves the template off the arm's
    pivot; with the edge acceptance about the template's own hole it stays
    inside the quarter of the rocker's arc zone the gauge may spend, centred
    on the aim: half of that quarter either side."""
    hole = _features()["pivot_hole"]
    assert hole["dia"] == [6.5, 6.515]
    rocker_bore = (
        rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1],
        rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0],
    )
    assert spec.PIN_GAUGE_MAX < hole["dia"][0]
    assert spec.PIN_GAUGE_MAX < rocker_bore[0]
    registration = (hole["dia"][1] - spec.PIN_GAUGE_MIN) / 2.0 + (
        rocker_bore[1] - spec.PIN_GAUGE_MIN
    ) / 2.0
    zone = rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
    assert spec.LOW_POINT_BAND[0] + registration <= 0.25 * zone / 2.0 + 1e-9
    assert spec.LOCATOR_REGISTRATION_MAX >= registration


def test_pivot_callout_names_the_bought_locating_pin() -> None:
    inches = f"{spec.PIN_GAUGE_IN:.4f}"
    assert spec.PIN_GAUGE_MAX == pytest.approx(float(inches) * 25.4)
    assert f"{inches} IN, CLASS X MINUS" in spec.PIVOT_CALLOUT
    assert "PIN GAUGE" in spec.PIVOT_CALLOUT
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    pin = inventory["gauges"]["vermont-class-x-2558-minus"]
    assert pin["kind"] == "pin_gauge" and pin["make"] == "Vermont Gage"
    assert pin["dia_in"]["value"] == spec.PIN_GAUGE_IN
    assert "Class X minus" in pin["name"] + pin["note"]


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


def _dti_acceptance() -> float:
    """The inventory record's profile acceptance, DTI stations about the pivot."""
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    note = inventory["gauges"]["arm-outline-template"]["note"]
    match = re.search(
        r"DTI within \+/-(\d+\.\d+) of nominal about the pivot at (\d+) stations", note
    )
    assert match, note
    return float(match.group(1))


def test_end_stations_hold_the_dti_acceptance_under_the_title_block_radii() -> None:
    """The arcs' centre sits on the pivot centreline and each low point is
    held by its band, so a radius error dR at the title block's band moves
    the edge at station x by dR x^2 / (2 R^2): at the end stations that drift
    plus the low-point band stays inside the inventory's DTI acceptance."""
    acceptance = _dti_acceptance()
    features = _features()
    for feature, low_point, radius_name in (
        ("top_edge", "height_above_pivot", "TopRadius"),
        ("bottom_edge", "depth", "BottomRadius"),
    ):
        edge = features[feature]
        radius = edge["radius_nominal"]
        lower, upper = printed_deviations(
            radius, spec.DRAWING_PRECISION_BY_NAME[radius_name]
        )
        drift = max(-lower, upper) * edge["station_nominal"] ** 2 / (2.0 * radius**2)
        low, high = edge[low_point]
        assert drift + (high - low) / 2.0 <= acceptance + 1e-9, (feature, drift)
        assert edge["radius"] == pytest.approx([radius + lower, radius + upper])
    assert spec.DTI_ACCEPTANCE == acceptance


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
