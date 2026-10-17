"""Offline contracts for the oblique-trammel jig's nut bracket (MHA-CH-006-TL-29)."""

from __future__ import annotations

from collections.abc import Iterator
import importlib
import inspect
import math
import re
from pathlib import Path

import pytest

import _config
from _drawing_contract import model_toleranced_dimensions
from _paths import CAD_ROOT
from _printed_limits import limits
from _printed_tolerance import printed_band_mm
import build_ch_rocker_arm_tl_oblique_nut_bracket as part
import ch_rocker_arm_tl_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_nut_bracket_spec as spec
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import draw_ch_rocker_arm_tl_oblique_nut_bracket as drawing
import export_features
from machinist_exceptions import load_exceptions

STEM = "ch_rocker_arm_tl_oblique_nut_bracket"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_block_taps_sit_on_the_pivot_block_screws() -> None:
    features = _features()
    for index, x in enumerate(leadscrew.BLOCK_SCREW_X, start=1):
        tap = features[f"block_tap_{index}"]
        assert tap["at"] == pytest.approx([x, 0.0, leadscrew.NUT_BRACKET_BLOCK_HOLES_Z])
        # Spotted from TL-22 at assembly: the model's nominal station from
        # the real -X face, not the mid-air origin; no printed station.
        assert tap["station_nominal"] == pytest.approx(x - leadscrew.NUT_BRACKET_X[0])
        assert "station" not in tap and "height" not in tap
        assert tap["note"].startswith(
            f"SPOT FROM {spec.PIVOT_BLOCK_NUMBER} AT ASSEMBLY;"
        )
        assert tap["thread"] == "#8-32 UNC-2B"
    assert spec.BLOCK_TAP_THREAD_DEPTH == leadscrew.NUT_BRACKET_TAP_DEPTH


def test_nut_seat_and_m3_taps_sit_on_the_screw_axis_and_bolt_circle() -> None:
    features = _features()
    seat_y, seat_z = leadscrew.NUT_BORE_YZ
    assert features["nut_seat"]["at"] == pytest.approx(
        [leadscrew.NUT_BRACKET_X[0], seat_y, seat_z]
    )
    radii = []
    for index in range(1, 5):
        tap = features[f"nut_tap_{index}"]
        x, y, z = tap["at"]
        assert x == pytest.approx(leadscrew.NUT_BRACKET_X[0])
        radii.append(math.hypot(y - seat_y, z - seat_z))
        # Metric (Main's ruling): the bought nut's M3, no inch class.
        assert tap["thread"] == f"{leadscrew.NUT_SCREW}x0.5"
    assert radii == pytest.approx([leadscrew.NUT_HOLE_PCD / 2.0] * 4, abs=0.001)
    # The spigot seats in the counterbore; the screw passes the THRU.
    counterbore = features["nut_seat_counterbore"]
    assert counterbore["dia_nominal"] == pytest.approx(leadscrew.NUT_BORE_DIA)
    assert counterbore["dia"][0] > leadscrew.NUT_BODY_DIA
    assert counterbore["depth"][0] > leadscrew.NUT_BODY_SHORT
    assert features["nut_seat"]["dia"][0] > leadscrew.SCREW_MAJOR_DIA


def test_nut_flange_lands_on_the_nut_face_at_worst_case() -> None:
    assert spec.NUT_FLANGE_MARGINS == pytest.approx(
        {"to the -Y side": 2.0, "to the bottom face": 2.0}
    )
    # The seat at its two-place band, the nut at its float, the depth at one.
    assert spec.WORST_FLANGE_MARGINS == pytest.approx(
        {"to the -Y side": 0.44, "to the bottom face": 1.24}, abs=0.005
    )


def test_nut_pattern_fits_its_mate_only_at_three_places() -> None:
    assert spec.NUT_PATTERN_ALLOWANCE > 0.0
    two_place = math.hypot(printed_band_mm(2), printed_band_mm(2))
    assert two_place > max(spec.NUT_SCREW_FLOAT, spec.SPIGOT_FLOAT)
    # The offsets from the seat's axis carry the fit; the seat's own stations
    # from the edges carry walls only (c4 review).
    assert spec.PATTERN_PLACES == 3
    assert spec.SEAT_PLACES == 2
    assert not hasattr(spec, "HOLE_PLACES")
    # The #8 taps print no station: their pattern is TL-22's, spotted.
    assert not hasattr(spec, "BLOCK_PATTERN_ALLOWANCE")
    assert not {"ScrewX1", "ScrewX2", "ScrewZ"} & set(spec.DRAWING_VALUES)


_PATTERN_DIMS = ("NutPatternY1", "NutPatternY2", "NutPatternZ1", "NutPatternZ2")


def test_m3_pattern_prints_from_the_seat_axis_not_the_edges() -> None:
    assert spec.DRAWING_PRECISION["NutSeat"] == {"BoreY": 2, "BoreZ": 2}
    assert spec.DRAWING_PRECISION[spec.NUT_PATTERN_REFERENCE] == dict.fromkeys(
        _PATTERN_DIMS, 3
    )
    assert spec.DRAWING_DIMENSIONS[spec.NUT_PATTERN_REFERENCE] == set(_PATTERN_DIMS)
    assert {spec.DRAWING_VALUES[name] for name in _PATTERN_DIMS} == {
        spec.NUT_HOLE_OFFSET
    }
    assert spec.NUT_HOLE_OFFSET == 5.657
    assert {spec.DIMENSION_PREFIXES[name] for name in _PATTERN_DIMS} == {"2X "}
    assert set(spec.DIMENSION_PREFIXES) == set(_PATTERN_DIMS)
    # The wizard's edge placements stay driven but unprinted.
    edge = {"NutHoleY1", "NutHoleY2", "NutHoleZ1", "NutHoleZ2"}
    assert "NutTaps" not in spec.DRAWING_DIMENSIONS
    assert not edge & set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not edge & set(spec.DRAWING_VALUES)
    assert spec.REFERENCE_SKETCHES == (spec.NUT_PATTERN_REFERENCE,)
    features = _features()
    seat = features["nut_seat"]
    assert list(seat["width"]) == pytest.approx([34.49, 35.51])
    assert list(seat["height"]) == pytest.approx([12.49, 13.51])
    assert list(seat["width"]) == pytest.approx(list(limits(spec.BORE_Y, 2)))
    for index in range(1, 5):
        tap = features[f"nut_tap_{index}"]
        for key in ("width", "height"):
            assert list(tap[key]) == pytest.approx([5.527, 5.787]), (index, key)
            assert tap[f"{key}_nominal"] == spec.NUT_HOLE_OFFSET
            # prechips measures a height_from across the two parallel axes.
            assert f"{key}_from" not in tap, (index, key)


def test_m3_pattern_lives_on_a_blanked_sketch_of_points() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "name_last_feature(adapter, NUT_PATTERN_REFERENCE)" in source
    assert "reference.apply(adapter, NUT_PATTERN_REFERENCE)" in source
    assert "blank_reference_sketches(adapter, REFERENCE_SKETCHES)" in source
    body = inspect.getsource(part._nut_pattern_reference)
    assert 'create_sketch("Right")' in body
    assert body.count("_add_reference_point(") == 2  # the seat, then the taps
    # Points only: a construction line printed as a diagonal on TL-22.
    assert "add_line_chain" not in body
    assert "create_line" not in body
    # Every dimension follows the part's globals, never a literal.
    drives = re.findall(r"dims\.record\(([^)]*)\)", body)
    assert drives == [
        '"PatternSeatZ", \'"BoreZ"\'',
        '"PatternSeatY", \'"BoreY"\'',
        "name, '\"NutHoleOffset\"'",
    ]
    # The nut face shows the part-hidden sketch to import its dimensions.
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions(" in draw_source


def test_walls_and_margins_stack_the_seat_and_pattern_bands() -> None:
    walls = spec.WORST_WALLS
    assert walls["M3 tap to nut-seat counterbore"] == pytest.approx(0.916, abs=0.001)
    assert walls["M3 tap to screw clearance"] == pytest.approx(1.766, abs=0.001)
    assert walls["M3 tap to bottom face"] == pytest.approx(5.203, abs=0.001)
    assert walls["M3 tap to -Y side"] == pytest.approx(4.403, abs=0.001)
    assert walls["counterbore to bottom face"] == pytest.approx(7.09, abs=0.001)
    assert walls["counterbore to -Y side"] == pytest.approx(6.29, abs=0.001)
    assert f"{spec.NUT_WALL_MIN:.2f}" == "0.92"


def test_x_set_centres_the_bracket_on_the_pivot_block_side_holes() -> None:
    near, far = pivot_block.SIDE_STATIONS_X
    assert spec.X_SET_MID == pytest.approx((near + far) / 2.0)
    assert spec.X_SET_FAR_END == pytest.approx(59.25)
    assert spec.X_SET_NUT_FACE == pytest.approx(40.75)
    assert pivot_block.DATUM_X + spec.X_SET_FAR_END == pytest.approx(
        leadscrew.NUT_BRACKET_X[1]
    )
    # A 3/16 transfer punch floats in TL-22's #8 clearance hole.
    assert 0.0 < spec.SPOT_FLOAT < spec.X_SET_BAND + printed_band_mm(3)


def test_walls_hold_rule_17_but_the_owner_accepted_one() -> None:
    under_floor = {
        name for name, wall in spec.WORST_WALLS.items() if wall < spec.WALL_FLOOR
    }
    assert under_floor == spec.RULE_17_FLOOR_EXCEPTIONS
    assert under_floor == {"M3 tap to nut-seat counterbore"}
    # Set centred on TL-22's side holes, the milled length holds each end
    # wall over the floor at its two places, the spots' TL-22 band, the X
    # set's title-block .XXX band and the punch's float (Main's ruling (a)).
    assert spec.WORST_WALLS["#8 tap to -X face"] == pytest.approx(
        spec.WORST_WALLS["#8 tap to +X face"]
    )
    assert spec.X_SET_PLACES == 3
    assert spec.X_SET_BAND == printed_band_mm(3) == pytest.approx(0.13)
    chain = printed_band_mm(pivot_block.SIDE_STATION_PLACES) + spec.X_SET_BAND
    chain += spec.SPOT_FLOAT
    half_pitch = (spec.SCREW_X[1] - spec.SCREW_X[0]) / 2.0
    length_min = spec.BRACKET_LENGTH - printed_band_mm(spec.LENGTH_PLACES)
    wall = length_min / 2.0 - half_pitch - chain - spec._BLOCK_R
    assert spec.WORST_WALLS["#8 tap to +X face"] == pytest.approx(wall)
    assert wall == pytest.approx(1.544, abs=0.001)
    assert wall >= spec.WALL_FLOOR
    assert not hasattr(spec, "END_WALL_RULED_MIN")
    assert spec.LENGTH_PLACES == 2
    assert spec.BRACKET_LENGTH == leadscrew.NUT_BRACKET_LENGTH
    # The +X end is always cut, even at the longest finished length.
    assert spec.LENGTH_CLEANUP - printed_band_mm(spec.LENGTH_PLACES) > 0.0


def test_bracket_centres_on_the_pivot_block_screws() -> None:
    near, far = spec.SCREW_X
    assert near == pytest.approx(spec.BRACKET_LENGTH - far)
    assert sum(leadscrew.NUT_BRACKET_X) / 2.0 == pytest.approx(
        sum(leadscrew.BLOCK_SCREW_X) / 2.0
    )
    assert spec.SCREW_X == pytest.approx((4.25, 14.25))
    assert spec.DRAWING_VALUES["BracketLength"] == round(
        spec.BRACKET_LENGTH, spec.LENGTH_PLACES
    )


def test_every_shortfall_is_stated_on_the_sheet() -> None:
    assert set(spec.RULE_20_SHORTFALLS) == {
        "M3 tap to nut-seat counterbore",
        "M3 tap to screw clearance",
        "#8 tap to -X face",
        "#8 tap to +X face",
    }
    assert spec.END_WALL_MIN == pytest.approx(1.544, abs=0.001)
    seat_rows = spec.NUT_SEAT_MATE_CALLOUT.splitlines()
    assert seat_rows == [
        "LOCATES NUT SPIGOT ON M3 PATTERN",
        "FOR fixtures.trammel-tr8-flange-nut",
        f"WALL TO M3 TAPS {spec.NUT_WALL_MIN:.2f} MIN",
    ]
    assert spec.NUT_WALL_MIN == min(
        spec.RULE_20_SHORTFALLS["M3 tap to nut-seat counterbore"],
        spec.RULE_20_SHORTFALLS["M3 tap to screw clearance"],
    )
    # The end wall is the #8 callout's last row, not text on the length's
    # extension lines (c4-r3).
    assert spec.BLOCK_TAP_WALL_CALLOUT == (
        f"WALL TO EACH END FACE {spec.END_WALL_MIN:.2f} MIN"
    )
    assert not hasattr(spec, "CALLOUTS_BELOW")
    note = _features()["block_tap_2"]["note"]
    assert note.endswith(spec.BLOCK_TAP_WALL_CALLOUT)


def test_owner_exceptions_match_the_stated_walls() -> None:
    exceptions = load_exceptions(CAD_ROOT / "config", STEM, "part")
    assert [(e.id, e.kind) for e in exceptions] == [
        ("RV-01", "minor"),
        ("RV-02", "minor"),
    ]
    exception, end_walls = exceptions
    assert f"{spec.NUT_WALL_MIN:.2f} min" in exception.finding
    assert f"{leadscrew.NUT_HOLE_PCD:.1f} bolt circle" in exception.reason
    assert f"{spec.CBORE_DEPTH:.2f} counterbore depth" in exception.reason
    clearance = spec.WORST_WALLS["M3 tap to screw clearance"]
    assert f"{clearance:.2f} min" in exception.reason
    assert f"Ø{spec.CBORE_DIA:.2f} x {spec.CBORE_DEPTH:.2f}" in exception.where
    # RV-02: the #8 taps' end walls, under the target at the stated X set.
    assert f"{spec.END_WALL_MIN:.2f} min" in end_walls.finding
    assert f"{spec.X_SET_MID:.{spec.X_SET_PLACES}f}" in end_walls.reason
    assert f"±{spec.X_SET_BAND:.2f}" in end_walls.reason
    assert "±0.10" not in end_walls.reason
    assert f"{spec.BRACKET_LENGTH:.2f} length" in end_walls.reason
    assert spec.BLOCK_TAP_PROCESS.strip().rstrip(";") in end_walls.where


def test_rule_18_engagement_and_no_screw_bottoms() -> None:
    for thread, engagement, depth in (
        (
            spec.BLOCK_THREAD,
            leadscrew.BLOCK_SCREW_ENGAGEMENT,
            spec.BLOCK_TAP_THREAD_DEPTH,
        ),
        (spec.NUT_THREAD, leadscrew.NUT_SCREW_ENGAGEMENT, spec.NUT_TAP_THREAD_DEPTH),
    ):
        assert engagement >= 1.5 * spec.THREAD_MAJOR_MM[thread]
        assert depth - printed_band_mm(2) > engagement


def test_only_the_counterbore_carries_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("NutSeat", "_cbore_diameter_name(adapter)"): "CBORE_BAND[1], CBORE_BAND[0]"
    }
    assert spec.CBORE_BAND == (0.10, 0.0)
    assert _features()["nut_seat_counterbore"]["dia"] == pytest.approx(
        [spec.CBORE_DIA, spec.CBORE_DIA + 0.10]
    )


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.FRONT_KEEP, drawing.TOP_KEEP, drawing.LEFT_KEEP)
    assert set().union(*map(set, views)) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DIMENSION_PREFIXES) <= marked


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                assert abs(nominal - round(nominal, places)) < 1e-9
            checked += 1
    assert checked


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-nut-bracket")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-006-TL-29" == spec.NUMBER


def test_sheet_carries_no_notes_and_cites_inventory_ids_only() -> None:
    assert spec.DRAWING_NOTES == ""
    texts = (
        spec.BLOCK_TAP_PROCESS,
        spec.NUT_TAP_PROCESS,
        spec.NUT_SEAT_MATE_CALLOUT,
        spec.BLOCK_TAP_WALL_CALLOUT,
    )
    for text in texts:
        assert not re.search(r"\b\d{4,5}[A-Z]\d+\b", text), text  # no McMaster SKU
        assert "ISO 2768" not in text


def test_nut_seat_callout_puts_drill_in_the_thru_row_and_the_mate_below() -> None:
    definitions = {
        5: "<MOD-DIAM><HOLE-DIA> THRU ALL",
        6: "<HOLE-SYMB-CBORE> <MOD-DIAM><CBORE-DIA> <HOLE-SYMB-DEPTH> <CBORE-DEPTH>",
        7: "",
        8: "",
    }
    updated = drawing.nut_seat_callout_definitions(definitions)
    assert updated[5].startswith("DRILL")
    assert updated[6] == definitions[6]
    assert updated[8] == spec.NUT_SEAT_MATE_CALLOUT
    with pytest.raises(RuntimeError):
        drawing.nut_seat_callout_definitions({**definitions, 8: "ALREADY"})
    with pytest.raises(RuntimeError):
        drawing.nut_seat_callout_definitions({5: "THRU", 6: "", 7: ""})


def test_block_tap_callout_ends_with_the_end_wall_row() -> None:
    definitions = {
        5: "SPOT FROM MHA-CH-006-TL-22 AT ASSEMBLY;\n8-32 UNC",
        6: "",
        7: "2X",
        8: "",
    }
    updated = drawing.block_tap_callout_definitions(definitions)
    assert updated == {**definitions, 8: spec.BLOCK_TAP_WALL_CALLOUT}
    # A native row already below stays above the wall row.
    native_below = drawing.block_tap_callout_definitions({**definitions, 8: "ROW\n"})
    assert native_below[8] == f"ROW\n{spec.BLOCK_TAP_WALL_CALLOUT}"
    with pytest.raises(RuntimeError):
        drawing.block_tap_callout_definitions(updated)
    with pytest.raises(RuntimeError):
        drawing.block_tap_callout_definitions({5: "", 6: "", 7: ""})
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_set_block_tap_wall_row(block_taps)" in source
    assert "set_dimension_callouts" not in source


# --- Sheet layout (sheet mm; 2 sheet mm per model mm) ------------------------------
_S = 2.0
_LEFT_BORDER = 12.4
_TOP_BORDER = 267.0
_GAP = 2.5  # text to a foreign line
_TEXT_HALF_HIGH = 1.75  # 3.5 mm dimension text
_TEXT_DROP = 2.7  # dimension line under a one-line text's centre
_EXT_OVERSHOOT = 1.0
_CHAR = 2.3  # c4-r3: "2X 29.343" 20.6, "35.000" 13.9, "4.525" 11.3 wide
# c4-r3 callout blocks (text and shelf), width x height; the #8 block adds
# its wall row: four 5.56 mm rows. The seat adds its locating row (five), and
# the #8 block's spot row is 39 characters to the 30 of c4-r3's mate row.
# c4-r9: the M3 block's widest row is the mate's 31-character inventory id
# (69 scaled from the seat's 78 for 35 characters; taken at _CHAR).
_M3_BLOCK = (31 * _CHAR, 4 * 5.56)
_SEAT_BLOCK = (78.0, 24.2 + 5.56)
_BLOCK_TAP_BLOCK = (79.3 * 39.0 / 30.0, 3 * 5.56 + 3.5)
# c4-r3 render: an M3 tap's centre-mark arms reach this far from its centre.
_MARK_REACH = 7.4
_PATTERN_TEXT = "2X 5.657"
# A hung text's near edge stands this far off its line (draw_fr_harmonic_base).
_HANG_GAP = 1.3


def _left(y: float, z: float) -> tuple[float, float]:
    """Nut face (model Y, Z) -> sheet mm: +Z right, +Y up."""
    cx, cy = (c * 1000.0 for c in drawing.LEFT_CENTER)
    return (
        cx + _S * (z - spec.BRACKET_HEIGHT / 2.0),
        cy + _S * (y + spec.BRACKET_DEPTH / 2.0),
    )


def _top(x: float, z: float) -> tuple[float, float]:
    """Block face (model X, Z) -> sheet mm: +X up, its Z on the nut face's."""
    return _left(0.0, z)[0], drawing.TOP_CENTER[1] * 1000.0 + _S * x


def _text_half(text: str) -> float:
    return len(text) * _CHAR / 2.0


def test_block_face_view_stands_in_projection_over_the_nut_face() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_project_block_face_view(adapter, left, top)" in source
    assert drawing.TOP_CENTER[0] == drawing.LEFT_CENTER[0]
    # Symmetric about X 0, so the pinned origin is the view's centre.
    assert spec.FACE_X + spec.BRACKET_LENGTH / 2.0 == pytest.approx(0.0)
    _, bottom = _top(spec.FACE_X, 0.0)
    _, top_edge = _top(spec.FACE_X + spec.BRACKET_LENGTH, 0.0)
    # The block face's hung height clears the nut face's top Z station.
    z_text_top = _left(max(y for _x, y, _z in drawing.LEFT_KEEP.values()), 0.0)[1]
    z_text_top += _TEXT_HALF_HIGH
    hung = drawing.TOP_KEEP["BracketHeight"][0]
    assert _top(hung, 0.0)[1] - _TEXT_DROP - _EXT_OVERSHOOT >= z_text_top + _GAP
    assert _top(hung, 0.0)[1] + _TEXT_HALF_HIGH <= bottom - _GAP
    assert top_edge > bottom
    # Spotted at assembly, the #8 taps print no station or row.
    assert set(drawing.TOP_KEEP) == {"BracketHeight", "BracketLength"}


def test_block_face_length_sits_between_its_extension_lines() -> None:
    right_edge = _top(0.0, spec.BRACKET_HEIGHT)[0]
    x, _y, z = drawing.TOP_KEEP["BracketLength"]
    sx, sy = _top(x, z)
    assert _top(spec.FACE_X, 0.0)[1] + _GAP <= sy - _TEXT_HALF_HIGH
    assert (
        sy + _TEXT_HALF_HIGH <= _top(spec.FACE_X + spec.BRACKET_LENGTH, 0.0)[1] - _GAP
    )
    assert sx - _text_half("18.50") >= right_edge + _GAP


def test_block_tap_callout_rides_over_the_view_inside_the_border() -> None:
    cx, cy = (c * 1000.0 for c in drawing.BLOCK_TAP_CALLOUT_XY)
    width, height = _BLOCK_TAP_BLOCK
    _, top_edge = _top(spec.FACE_X + spec.BRACKET_LENGTH, 0.0)
    assert cy - height / 2.0 >= top_edge + _GAP
    assert cy + height / 2.0 <= _TOP_BORDER - 5.0
    assert cx - width / 2.0 >= _LEFT_BORDER + 5.0
    # The leader leaves the shelf's right end for the far tap, up-right of
    # it, so it never runs down the station column.
    hole_x, hole_y = _top(spec.BLOCK_SCREW_POINTS[1][0], spec.SCREW_Z)
    assert cx + width / 2.0 > hole_x + 3.0
    assert drawing.BLOCK_TAP_EDGE_MODEL[0] > spec.BLOCK_SCREW_POINTS[1][0]
    # The block face's X stations stand right of the view, past the shelf.
    assert cx + width / 2.0 < _top(0.0, spec.BRACKET_HEIGHT)[0]
    assert hole_y < top_edge


def test_nut_face_seat_stations_stand_outside_the_view() -> None:
    left_edge, top_edge = _left(0.0, 0.0)
    bore_x, bore_y = _left(-spec.BORE_Y, spec.BORE_Z)
    # Z from the bottom face: in the lane over the view, between its lines,
    # and right of the left M3 column's extension line, which ends at the -Z
    # offset's lane under it (c4-r9).
    _x, y, z = drawing.LEFT_KEEP["BoreZ"]
    sx, sy = _left(y, z)
    assert sy - _TEXT_HALF_HIGH >= top_edge + _GAP
    assert sx - _text_half("13.00") >= left_edge + _GAP
    assert sx + _text_half("13.00") <= bore_x - _GAP
    left_col = _left(0.0, spec.NUT_HOLE_Z[0])[0]
    if sx - _text_half("13.00") < left_col < sx + _text_half("13.00"):
        z1_line = _left(drawing.LEFT_KEEP["NutPatternZ1"][1], 0.0)[1] - _TEXT_DROP
        assert sy - _TEXT_HALF_HIGH >= z1_line + _EXT_OVERSHOOT + _GAP
    # Y from the Y = 0 face: left of the view, between its lines.
    _x, y, z = drawing.LEFT_KEEP["BoreY"]
    sx, sy = _left(y, z)
    assert sx + _text_half("35.00") <= left_edge - _GAP
    assert sx - _text_half("35.00") >= _LEFT_BORDER + 2.0
    assert sy - _TEXT_HALF_HIGH >= bore_y + _GAP
    assert sy + _TEXT_HALF_HIGH <= top_edge - _GAP


def test_nut_face_pattern_offsets_stand_outside_the_outline() -> None:
    """c4-r8/r9 (rule 14): all four 2X 5.657 texts and lines sat inside the
    nut face. The Z offsets ride lanes over it, the Y offsets a line left of
    it, each clear of the seat's stations, the side view and the 48.0."""
    half = _text_half(_PATTERN_TEXT)
    bore_x, _bore_y = _left(-spec.BORE_Y, spec.BORE_Z)
    left_col = _left(0.0, spec.NUT_HOLE_Z[0])[0]
    right_col = _left(0.0, spec.NUT_HOLE_Z[1])[0]
    upper_row = _left(-spec.NUT_HOLE_Y[0], 0.0)[1]
    lower_row = _left(-spec.NUT_HOLE_Y[1], 0.0)[1]
    left_edge, top_edge = _left(0.0, 0.0)
    bottom_edge = _left(-spec.BRACKET_DEPTH, 0.0)[1]
    keep = drawing.LEFT_KEEP
    text = {name: _left(*keep[name][1:]) for name in (*_PATTERN_DIMS, "BoreZ", "BoreY")}

    def line(name: str) -> float:  # a horizontal dimension's line, under its text
        return text[name][1] - _TEXT_DROP

    # Z lanes over the view: -Z, the seat's 13.00, +Z, each line clearing the
    # text under it, so each extension line ends under the next lane's text.
    lanes = ("NutPatternZ1", "BoreZ", "NutPatternZ2")
    assert line("NutPatternZ1") >= top_edge + _GAP
    for low, high in zip(lanes, lanes[1:], strict=False):
        assert line(high) >= text[low][1] + _TEXT_HALF_HIGH + _GAP
    # -Z: its text left of the left edge (the 13.00's extension line there),
    # beyond its span's left column.
    z1_x, _ = text["NutPatternZ1"]
    assert z1_x + half <= left_edge - _GAP
    assert z1_x - half >= _LEFT_BORDER + 5.0
    assert z1_x + half <= left_col
    # +Z: right of the right column's extension line, inside the face's width.
    z2_x, _ = text["NutPatternZ2"]
    assert z2_x - half >= right_col + _GAP
    assert z2_x + half <= _left(0.0, spec.BRACKET_HEIGHT)[0]
    # Every Z text crosses only extension lines that end under it: the
    # seat's (bore) line runs to the +Z lane, the right column's too.
    for name in ("NutPatternZ1", "BoreZ"):
        sx, _ = text[name]
        for x in (bore_x, right_col):
            assert not sx - half - _GAP < x < sx + half + _GAP, name
    # The Y offsets share one line left of the view, arrows inside (c4-r4:
    # outside, each one's tails ran into the other's span); each text beyond
    # its span hangs west of it (away from the taps), clear of the left edge
    # and of the 35.00's text further out.
    assert keep["NutPatternY1"][2] == keep["NutPatternY2"][2]
    assert set(drawing.ARROWS_INSIDE) == {"NutPatternY1", "NutPatternY2"}
    line_x = text["NutPatternY1"][0]
    assert line_x <= left_edge - _GAP
    hung_left = line_x - _HANG_GAP - 2.0 * half
    bore_y_x, _ = text["BoreY"]
    assert hung_left >= bore_y_x + _text_half("35.00") + _GAP
    # The 35.00's line stays west of the Y offsets' extension lines' ends.
    assert bore_y_x + _text_half("35.00") < line_x - _EXT_OVERSHOOT
    _, upper_y = text["NutPatternY1"]
    assert upper_y - _TEXT_HALF_HIGH >= upper_row + _GAP
    assert upper_y + _TEXT_HALF_HIGH <= top_edge - _GAP
    _, lower_y = text["NutPatternY2"]
    assert lower_y + _TEXT_HALF_HIGH <= lower_row - _GAP
    assert lower_y - _TEXT_HALF_HIGH >= bottom_edge + _GAP
    # Nothing of the pattern's dimensions inside the outline.
    right_edge = _left(0.0, spec.BRACKET_HEIGHT)[0]
    for name in _PATTERN_DIMS:
        sx, sy = text[name]
        inside_x = left_edge < sx < right_edge
        inside_y = bottom_edge < sy < top_edge
        assert not (inside_x and inside_y), name


def test_nut_face_callouts_stay_inside_the_border_and_off_the_lines() -> None:
    m3_x, m3_y = (c * 1000.0 for c in drawing.NUT_TAP_CALLOUT_XY)
    seat_x, seat_y = (c * 1000.0 for c in drawing.NUT_SEAT_CALLOUT_XY)
    bottom_edge = _left(-spec.BRACKET_DEPTH, 0.0)[1]
    assert seat_x - _SEAT_BLOCK[0] / 2.0 >= _LEFT_BORDER + 5.0
    assert seat_y + _SEAT_BLOCK[1] / 2.0 <= bottom_edge - 5.0
    # c4-r9 (rule 4): the M3 callout names the bought nut by its inventory
    # id, as the seat's does, on a row of its own.
    rows = spec.NUT_TAP_PROCESS.split("\n")
    assert spec.NUT_ID == "fixtures.trammel-tr8-flange-nut"
    assert rows == ["MATCHES FLANGE HOLES OF", spec.NUT_ID, ""]
    assert spec.NUT_ID in spec.NUT_SEAT_MATE_CALLOUT
    assert "NUT\n" not in spec.NUT_TAP_PROCESS
    # Its block, the id its widest row, rides over the plan, right of the
    # nut face and under the block face's hung height.
    m3_left = m3_x - _M3_BLOCK[0] / 2.0
    m3_low, m3_high = m3_y - _M3_BLOCK[1] / 2.0, m3_y + _M3_BLOCK[1] / 2.0
    right_edge, top_edge = _left(0.0, spec.BRACKET_HEIGHT)
    assert len(spec.NUT_ID) == 31
    assert m3_left >= right_edge + 5.0
    assert m3_low >= top_edge + 5.0  # the plan's top edge is the face's
    hung = _top(drawing.TOP_KEEP["BracketHeight"][0], 0.0)[1]
    assert m3_high <= hung - _TEXT_DROP - _GAP
    assert m3_x + _M3_BLOCK[0] / 2.0 <= 216.0 - _GAP  # left of the title block
    # Its leader: from the shelf's left end (the bottom row) down-left to the
    # upper-right tap's upper-right edge, right of the +Z offset's extension
    # line (the right column), so it never rises through the rows (c4-r7).
    edge_y, edge_z = -drawing.NUT_TAP_EDGE_MODEL[1], drawing.NUT_TAP_EDGE_MODEL[2]
    assert edge_y < spec.NUT_HOLE_Y[0] and edge_z > spec.NUT_HOLE_Z[1]
    tap_x, tap_y = _left(-edge_y, edge_z)
    right_col = _left(0.0, spec.NUT_HOLE_Z[1])[0]
    assert tap_x > right_col and tap_y < m3_low
    # It enters through the face's right edge, under the top edge.
    at_edge = m3_low + (tap_y - m3_low) * (right_edge - m3_left) / (tap_x - m3_left)
    assert tap_y < at_edge < top_edge
    # The seat leader: shelf left end to the bore centre, crossing the lower
    # M3 row right of the seat's axis and left of the lower-right tap (whose
    # Y offset's extension line runs right from it).
    bore_x, bore_y = _left(-spec.BORE_Y, spec.BORE_Z)
    sx, sy = seat_x - _SEAT_BLOCK[0] / 2.0, seat_y - _SEAT_BLOCK[1] / 2.0
    row_y = _left(-spec.NUT_HOLE_Y[1], 0.0)[1]
    cross_x = bore_x + (sx - bore_x) * (row_y - bore_y) / (sy - bore_y)
    assert cross_x >= bore_x + 1.5
    m3_right, _ = _left(0.0, spec.NUT_HOLE_Z[1])
    assert cross_x <= m3_right - _S * spec.NUT_TAP_DRILL / 2.0 - 2.0
    assert seat_x + _SEAT_BLOCK[0] / 2.0 <= 210.0  # short of the title block


def test_prechips_solids_are_valid_fixture_solids() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    names = {solid["name"] for solid in spec.PRECHIPS_SOLIDS}
    assert names == {
        "nut bracket",
        "screw clearance",
        "nut seat",
        *(f"nut tap {index}" for index in range(1, 5)),
        "block tap 1",
        "block tap 2",
    }


# --- A vendor swap of the bought nut is a number-only change in leadscrew ------


@pytest.fixture
def respec(monkeypatch: pytest.MonkeyPatch) -> Iterator:
    """Reload the spec against patched leadscrew numbers; restore after."""

    def reload(**numbers: float):
        for name, value in numbers.items():
            assert hasattr(leadscrew, name), name
            monkeypatch.setattr(leadscrew, name, value)
        return importlib.reload(spec)

    try:
        yield reload
    finally:
        monkeypatch.undo()
        importlib.reload(spec)


def test_spec_follows_the_nut_bolt_circle(respec) -> None:
    reloaded = respec(NUT_HOLE_PCD=16.1)
    assert reloaded.NUT_HOLE_OFFSET == round(16.1 / 2.0 * math.sqrt(0.5), 3)
    assert reloaded.NUT_HOLE_Y == pytest.approx((35.0 - 5.692, 35.0 + 5.692))
    # The offsets print at three places, so the circle holds to 0.001.
    assert reloaded.WALLS_MM["M3 tap to nut-seat counterbore"] == pytest.approx(
        8.05 - reloaded.CBORE_DIA / 2.0 - 1.5, abs=0.001
    )


def test_spec_follows_the_nut_spigot(respec) -> None:
    reloaded = respec(NUT_BODY_DIA=10.0, NUT_BORE_DIA=10.5, NUT_BODY_SHORT=2.0)
    assert reloaded.CBORE_DIA == 10.5
    assert reloaded.SPIGOT_FLOAT == pytest.approx(0.25)
    # ceil0.1(spigot 2.0 + the 0.51 band + 0.05 end clearance)
    assert reloaded.CBORE_DEPTH == pytest.approx(2.6)
    assert reloaded.NUT_SEAT_SPEC.overrides_mm["CounterBoreDiameter"] == 10.5


def test_spec_follows_the_nut_screw_holes(respec) -> None:
    reloaded = respec(NUT_HOLE_DIA=3.4)
    assert reloaded.NUT_SCREW_FLOAT == pytest.approx(0.2)
    assert reloaded.NUT_PATTERN_ALLOWANCE == pytest.approx(
        0.2 - reloaded.POSITION_RADIUS
    )


def test_spec_refuses_a_flange_that_overhangs(respec) -> None:
    with pytest.raises(AssertionError, match="overhangs"):
        respec(NUT_FLANGE_DIA=24.0)
