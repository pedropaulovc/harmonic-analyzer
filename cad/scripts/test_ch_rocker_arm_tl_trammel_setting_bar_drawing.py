"""Offline contracts for the rocker trammel setting bar (MHA-CH-006-TL-17)."""

from __future__ import annotations

import math
import re

from prechips.model import FixtureSolid

import _config
import ch_rocker_arm_tl_trammel_setting_bar_spec as spec
import draw_ch_rocker_arm_tl_trammel_setting_bar as drawing
from _drawing_registry import DRAWING_TEMPLATES
import export_features

STEM = "ch_rocker_arm_tl_trammel_setting_bar"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    top, section = set(drawing.TOP_OFFSETS), {*drawing.SECTION_OFFSETS, "BarThickness"}
    assert top | section == marked
    assert not top & section
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {name for _feature, name in spec.DRAWING_BANDS} <= marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_stations_are_the_trammel_radii_from_h0() -> None:
    features = _features()
    assert features["seat_h800"]["station"] == [799.95, 800.05]
    assert features["seat_h816"]["station"] == [815.95, 816.05]
    for name in ("seat_h0", "seat_h800", "seat_h816"):
        assert features[name]["axis"] == [0.0, -1.0, 0.0]


def test_seat_takes_both_trammel_points() -> None:
    seat = _features()["seat_h0"]
    pilot = _features()["seat_h0_pilot"]
    # The cone lies inside the #2 centre drill's body and outside the pilot.
    assert seat["dia"][1] < spec.CENTRE_DRILL_BODY_DIA
    assert seat["dia"][0] > pilot["dia"][1]
    assert pilot["thru"] is True
    # The 1/4 point bodies never enter; the pivot apex stays inside the bar.
    assert spec.TRAMMEL_POINT_DIA > seat["dia"][1]
    half = math.radians(spec.PIVOT_POINT_HALF_ANGLE_DEG - 1.0)
    assert seat["dia"][1] / 2.0 / math.tan(half) < spec.BAR_THICKNESS
    # Face-to-flank angle of a 60 deg included seat.
    assert seat["land_angle_nominal_deg"] == 90.0 - spec.SEAT_HALF_ANGLE_DEG == 60.0
    assert seat["land_angle_deg"] == [59.0, 61.0]


def test_bar_is_the_supply_stock_with_h0_and_h816_equally_in_from_the_ends() -> None:
    assert (spec.BAR_LENGTH, spec.BAR_WIDTH, spec.BAR_THICKNESS) == (914.4, 25.4, 6.35)
    assert math.isclose(
        spec.H0_FROM_END, spec.BAR_LENGTH - spec.H816 - spec.H0_FROM_END
    )


def test_supply_dimensions_read_as_stock_not_machined() -> None:
    """The bar is used at its supply length and thickness; only the seat
    stations are machined, so neither stock size takes the title-block band."""
    for name in ("BarLength", "BarThickness"):
        assert drawing.CALLOUTS_BELOW[name] == "STOCK"


def test_prechips_solids_are_valid_fixture_solids() -> None:
    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    bar, *seats = spec.PRECHIPS_SOLIDS
    assert bar["size_mm"] == [spec.BAR_LENGTH, spec.BAR_THICKNESS, spec.BAR_WIDTH]
    assert [seat["at_mm"][0] for seat in seats] == [0.0, 800.0, 816.0]
    assert all(seat["void"] for seat in seats)


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-setting-bar")["number"]
    assert number == f"{parent}-TL-17"


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    # Callouts carry counts and mate part numbers, never a dimension.
    for callout in (*drawing.CALLOUTS_ABOVE.values(), *drawing.CALLOUTS_BELOW.values()):
        bare = re.sub(r"MHA-CH-006-TL-\d\d\b", "", callout)
        assert not re.search(r"\d(?!X\b)", bare), callout


# Measured on run 20261015T092257793Z (layout audit, sheet m): a value's
# dimension line sits this far under its text position, and the 3X 12.7
# arrow's outside tail ends this far above H0's centre line.
_LINE_BELOW_TEXT = {"H0FromEnd": 0.0056, "H800X": 0.0073, "H816X": 0.0073}
_HOLE_HEIGHT_TAIL = 0.0063
# The 1:10 isometric's ink half-extents and GetOutline's padding on that run.
_ISO_INK_HALF_AT_1_10 = (0.0331, 0.0193)
_ISO_PADDING = 0.006


def test_top_view_rows_clear_the_bar_and_the_hole_height_tail() -> None:
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    edge = spec.BAR_WIDTH / 2.0 * scale / 1000.0
    line = {
        name: drawing.TOP_OFFSETS[name][1] - below
        for name, below in _LINE_BELOW_TEXT.items()
    }
    # The first row has 8 mm of air over the bar (round-5 review: 800.00 sat
    # on the edge); 816.00 keeps its pitch above it.
    assert line["H800X"] - edge >= 0.008 - 1e-9
    assert abs(line["H816X"] - line["H800X"] - 0.019) < 1e-9
    # 49.2 chains into 800.00's row, clear above the 12.7 tail it crossed.
    assert abs(line["H0FromEnd"] - line["H800X"]) < 1e-4
    assert line["H0FromEnd"] - _HOLE_HEIGHT_TAIL >= 0.004


def test_flank_angle_text_sits_in_the_wedge_above_the_face() -> None:
    scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    vertex = spec.SEAT_DIA / 2.0 * scale / 1000.0
    dx, dy = drawing.SECTION_OFFSETS["SeatFlankAngle"]
    u = dx - vertex
    assert 0.0 < math.degrees(math.atan2(dy, u)) < spec.SEAT_FLANK_ANGLE_DEG
    assert math.hypot(u, dy) >= 0.018
    assert all(
        drawing.SECTION_OFFSETS[name][0] < 0.0 for name in ("PilotDia", "SeatDia")
    )
    assert set(drawing.INSIDE_ARROW_DIMENSIONS) <= set(drawing.SECTION_OFFSETS)


def test_isometric_note_and_outline_follow_its_scale() -> None:
    num, den = drawing.ISO_SCALE
    assert spec.ISOMETRIC_VIEW_NOTE == f"ISOMETRIC VIEW SCALE {num}:{den}"
    grow = (num / den) / (1 / 10)
    half_w, half_h = (ink * grow + _ISO_PADDING for ink in _ISO_INK_HALF_AT_1_10)
    cx, cy = drawing.ISO_CENTER
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    assert (
        cx + half_w < template.title_block_left_m
        or cy - half_h > template.title_block_top_m
    )
    # Below the edge view's outline (run 20261015T092257793Z: y 158.6 mm).
    assert cy + half_h < 0.1586
    assert cx - half_w > 0.0127


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """One fact: a band applied to an unrounded model nominal exports limits
    the sheet never prints."""
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
