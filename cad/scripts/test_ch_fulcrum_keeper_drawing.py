"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_ch_fulcrum_keeper as part
import draw_ch_fulcrum_keeper as drawing
import ch_fulcrum_keeper_notes
import ch_fulcrum_keeper_spec
import _config
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_shaft_h import SHAFT_H
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import inside_corner_radius_mm
from ch_vn_frame_side_screw_spec import HEAD_DIA as FRAME_SIDE_HEAD_DIA
from ch_vn_frame_side_screw_spec import HEAD_H as FRAME_SIDE_HEAD_H
from ch_vn_frame_side_screw_spec import SHANK_DIA as FRAME_SIDE_SHANK_DIA


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-fulcrum-keeper.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-fulcrum-keeper.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-fulcrum-keeper_drawing.png")
    assert DRAWINGS_BY_NAME["ch_fulcrum_keeper"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS
    marked = set().union(*ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_geometry_matches_the_top_frame_contract() -> None:
    from channel_frame_geom import LEVER_FULCRUM_XY
    from top_frame_plane import FULCRUM_KEEPER_SEAT_Y, TOP_FRAME_RAIL_TOP_Y

    spec = ch_fulcrum_keeper_spec
    assert spec.SHAFT_AXIS_H == 25.2
    assert LEVER_FULCRUM_XY[1] - spec.SHAFT_AXIS_H == pytest.approx(
        FULCRUM_KEEPER_SEAT_Y, abs=1e-9
    )
    assert FULCRUM_KEEPER_SEAT_Y - TOP_FRAME_RAIL_TOP_Y == pytest.approx(
        0.0002, abs=1e-9
    )
    assert 2.0 * spec.CROWN_R == spec.KEEPER_WIDTH == 13.97
    assert 2.0 * spec.LUG_HALF_T == 8.128
    assert spec.FOOT_UNSTEPPED_H == 7.874
    assert spec.FOOT_H == pytest.approx(spec.FOOT_UNSTEPPED_H - FRAME_SIDE_HEAD_H)
    assert spec.FOOT_H == pytest.approx(5.7658)
    assert spec.FOOT_TIP_X == pytest.approx(spec.LUG_HALF_T + spec.FOOT_L)
    assert spec.FOOT_TIP_X == 12.446
    assert spec.SCREW_X == pytest.approx(spec.FOOT_TIP_X - spec.SCREW_FROM_TIP)
    assert spec.SCREW_X == pytest.approx(7.874)
    assert spec.KEEPER_Z_OFF == 80.772
    assert spec.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(153.416)
    assert spec.KEEPER_SCREW_Z_OFF == pytest.approx(spec.KEEPER_Z_OFF + spec.SCREW_X)
    assert spec.KEEPER_SCREW_Z_OFF == pytest.approx(88.646)
    from _hole_spec import LETTER_DRILL_MM

    assert spec.BORE_HOLE_SPEC.size == "F"
    assert spec.BORE_DIA == LETTER_DRILL_MM["F"]
    assert spec.BORE_DIA_BAND == pytest.approx((0.1016, 0.0))
    assert spec.DRAWING_PRECISION["ShaftBoreProfile"]["BoreDia"] == 3
    assert not hasattr(spec, "BORE_REAMER_DIA_RANGE_MM")


def test_crown_set_screw_tap_stops_at_the_bore() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_THREAD == "#1-72"
    assert spec.SET_SCREW_HOLE_SPEC.kind == "tapped"
    assert spec.SET_SCREW_HOLE_SPEC.end == "through_next"
    assert spec.CROWN_TOP_Y == spec.SHAFT_AXIS_H + spec.CROWN_R


def test_rule_12_worst_case_walls_and_thread() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.FOOT_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.SET_SCREW_WEB_MM >= WALL_TARGET_MM
    assert spec.FOOT_TIP_WALL_MM >= WALL_TARGET_MM
    assert spec.FOOT_SIDE_WALL_MM >= WALL_TARGET_MM
    assert spec.BORE_SIDE_WALL_MM >= WALL_TARGET_MM
    assert round(spec.BORE_SIDE_WALL_MM, 3) == 3.238
    assert round(spec.SET_SCREW_WEB_MM, 3) == 2.629
    assert round(spec.FOOT_TIP_WALL_MM, 3) == 3.073
    assert round(spec.FOOT_SIDE_WALL_MM, 3) == 5.359
    assert spec.FOOT_HEAD_LUG_CLEARANCE_MM == pytest.approx(1.1174, abs=1e-4)
    assert round(spec.FOOT_SCREW_ENGAGEMENT_D, 2) == 2.39
    assert spec.FOOT_HOLE_PLACES == 3
    assert spec.FOOT_HOLE_CALLOUT_PRECISION == {"hw-diam": 3}
    assert spec.DRAWING_PRECISION["LugBody"]["LugThickness"] == 2
    assert spec.DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] == 2
    assert spec.DRAWING_PRECISION["OverallLengthReference"]["OverallLength"] == 2
    assert spec.DRAWING_PRECISION["FootProfile"] == {"FootRise": 3}
    assert spec.DRAWING_PRECISION["FootScrewReference"]["ScrewFromTip"] == 2
    assert spec.DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] == 3
    assert spec.KEEPER_SCREW_TRANSVERSE_BAND_MM == spec._BAND_BY_PLACES[3]


def test_open_foot_step_eliminates_counterbore_and_rv04() -> None:
    spec = ch_fulcrum_keeper_spec
    for retired in (
        "CBORE_DIA_MM",
        "CBORE_DEPTH_MM",
        "CBORE_DIA_BAND",
        "CBORE_DEPTH_BAND",
        "FOOT_COUNTERBORE_DEPTH_PLACES",
        "FOOT_TIP_WALL_TEXT",
    ):
        assert not hasattr(spec, retired)
    assert spec.FOOT_TIP_WALL_MM / 25.4 == pytest.approx(0.1210, abs=5e-5)
    assert spec.FOOT_TIP_WALL_MM >= WALL_TARGET_MM
    rows = _config.parts("ch-fulcrum-keeper")["machinist_exceptions"]
    assert {row["id"] for row in rows} == {"RV-01", "RV-02", "RV-03"}


def test_side_station_names_the_frame_tap_and_the_web_needs_xx() -> None:
    spec = ch_fulcrum_keeper_spec
    frame = _config.parts("fr-top-frame")["number"]
    assert frame in ch_fulcrum_keeper_notes.FOOT_HOLE_MATE
    assert frame in ch_fulcrum_keeper_notes.FOOT_RISE_CALLOUT
    bands = spec._BAND_BY_PLACES
    assert spec.SET_SCREW_WEB_MM + 2.0 * (bands[2] - bands[1]) < 1.5


def test_corner_round_prints_r_02_max_clearing_the_fillister_head() -> None:
    spec = ch_fulcrum_keeper_spec
    ceiling = inside_corner_radius_mm(unit=spec.UNIT)
    assert spec.CORNER_R_MAX == pytest.approx(0.508)
    assert spec.CORNER_R_MAX < ceiling
    assert spec.CORNER_R_BAND == (0.0, -spec.CORNER_R_MAX)
    assert spec.CORNER_R_TOL_TYPE == 6
    assert 0.0 < spec.CORNER_R_MAX <= spec.FOOT_HEAD_LUG_CLEARANCE_MM
    assert spec.DRAWING_DIMENSIONS["CornerFillet"] == {"CornerRadius"}
    assert spec.DRAWING_PRECISION["CornerFillet"] == {"CornerRadius": 2}
    assert "CornerRadius" in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["CornerRadius"] == "CLEARS HEAD OF\nMHA-CH-VN-52"
    assert (
        part.V_CORNER
        == (1.0 - math.pi / 4.0) * spec.CORNER_R_MAX**2 * spec.KEEPER_WIDTH
    )


def test_drawing_enforces_machinist_review() -> None:
    from _machinist_review_mode import MachinistReviewMode

    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_overall_length_is_real_and_the_bore_centred_on_the_width() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.REFERENCE_DIMENSIONS == ("OverallHeight", "BoreFromSide")
    assert "FootLength" not in drawing.FRONT_KEEP
    assert "FootLength" not in set().union(*spec.DRAWING_DIMENSIONS.values())
    assert spec.DRAWING_PRECISION["BoreSideReference"] == {"BoreFromSide": 3}
    assert spec.BORE_FROM_SIDE == spec.KEEPER_WIDTH / 2.0
    assert spec.BORE_CENTRE_BAND_MM == 0.3048
    assert spec.BORE_CENTRE_CALLOUT == (
        "ON WIDTH CENTER \u00b1.012,\nHOLDS MHA-CH-VN-55\nTHREAD ENGAGEMENT"
    )
    assert drawing.DIMENSION_CALLOUTS["BoreFromSide"] is spec.BORE_CENTRE_CALLOUT
    assert spec.DRAWING_PRECISION["OverallHeightReference"] == {"OverallHeight": 2}
    assert spec.DRAWING_PRECISION["OverallLengthReference"] == {"OverallLength": 2}
    assert spec.OVERALL_LENGTH == pytest.approx(2.0 * spec.LUG_HALF_T + spec.FOOT_L)
    assert spec.OVERALL_LENGTH == pytest.approx(16.51)
    assert "BoreFromSide" in drawing.RIGHT_KEEP
    assert "OverallLength" in drawing.FRONT_KEEP


def test_each_keeper_is_drilled_alone_and_the_pair_still_lines_up() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.DRAWING_PRECISION["LugProfile"]["LugRise"] == 2
    assert spec.DRAWING_PRECISION["LugBody"]["LugThickness"] == 2
    mismatch = 2.0 * 0.254 + spec.KEEPER_SEAT_FLATNESS_BUDGET_MM
    assert spec.BORE_HEIGHT_MISMATCH_MM == pytest.approx(mismatch)
    lug_max = 2.0 * spec.LUG_HALF_T + 0.254
    assert spec.LUG_THICKNESS_MAX_MM == pytest.approx(lug_max)
    allowance = lug_max * (
        spec.KEEPER_SEAT_FLATNESS_BUDGET_MM / spec.KEEPER_SEAT_LENGTH_MM
        + mismatch / (2.0 * spec.KEEPER_Z_OFF)
    ) + lug_max * math.tan(math.radians(0.3))
    assert spec.BORE_ALIGNMENT_ALLOWANCE_MM == pytest.approx(allowance)
    least = spec.BORE_DIA + spec.BORE_DIA_BAND[1] - (6.35 + SHAFT_H[0])
    assert least >= spec.BORE_RUNNING_MIN_CLEARANCE_MM + allowance
    assert "SupplyHeightReference" not in spec.REFERENCE_SKETCHES
    assert "SupplyHeight" not in set().union(*spec.DRAWING_DIMENSIONS.values())
    assert "SupplyHeight" not in drawing.FRONT_KEEP
    for text in (
        ch_fulcrum_keeper_notes.BORE_CALLOUT,
        ch_fulcrum_keeper_notes.CROWN_CALLOUT,
        ch_fulcrum_keeper_notes.SET_SCREW_QUALIFIER,
    ):
        assert "ASSEMBLY" not in text
    assert ch_fulcrum_keeper_notes.BORE_CALLOUT.splitlines()[0] == "F DRILL THRU"
    assert "REAM" not in ch_fulcrum_keeper_notes.BORE_CALLOUT
    assert not any(
        ch.isdigit()
        for ch in ch_fulcrum_keeper_notes.BORE_CALLOUT.replace("MHA-CH-04", "")
    )


def test_crown_prints_a_full_round_reference_radius() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.DRAWING_DIMENSIONS["LugCrownProfile"] == {"CrownRadius"}
    assert spec.DRAWING_PRECISION["LugCrownProfile"] == {"CrownRadius": 3}
    assert spec.DRAWING_PRECISION["Foot"] == {"Depth": 2}
    assert spec.CROWN_R == spec.KEEPER_WIDTH / 2.0 == 6.985
    assert spec.CROWN_LEAST_R == pytest.approx(6.858)
    assert spec.CROWN_MOST_R == pytest.approx(7.112)
    major = 1.8542
    at_x_band = sum(
        spec.set_screw_wall_terms(spec.CROWN_R - spec._BAND_BY_PLACES[1], 0.0).values()
    )
    assert at_x_band / major < 1.5
    assert not hasattr(spec, "CROWN_R_MIN")
    half_width_band = spec._BAND_BY_PLACES[2] / 2.0
    off_side = spec.set_screw_wall_terms(
        spec.CROWN_LEAST_R, half_width_band + spec._BAND_BY_PLACES[1]
    )
    assert sum(off_side.values()) / major < 1.5
    terms = spec.set_screw_wall_terms(spec.CROWN_LEAST_R, spec.BORE_CENTRE_BAND_MM)
    assert sum(terms.values()) == pytest.approx(spec.SET_SCREW_FULL_THREAD_MM)
    assert terms["least crown over the bore axis"] == pytest.approx(
        math.sqrt(6.858**2 - 0.3048**2)
    )
    assert terms["least crown over the bore axis"] + terms[
        "crown fall across the thread"
    ] == pytest.approx(spec.crown_least_height(spec._THREAD_HALF_MAJOR))
    assert round(spec.SET_SCREW_ENGAGEMENT_D, 3) == 1.589
    assert "CrownRadius" not in drawing.NEAR_SIDE_DIAMETERS
    assert "CrownRadius" not in spec.REFERENCE_DIMENSIONS


def test_front_reference_lines_draw_in_the_outline_black() -> None:
    spec = ch_fulcrum_keeper_spec
    rows = {row[0]: row for row in part.REFERENCE_LINES}
    assert drawing.REFERENCE_WITNESS_COLOR == 0
    assert set(drawing.FRONT_REFERENCE_WITNESSES) == {
        name for name, row in rows.items() if row[1] == "Front"
    }
    for name, length in drawing.FRONT_REFERENCE_WITNESSES.items():
        _, _, _, start, end, _, value, _ = rows[name]
        assert math.dist(start, end) == pytest.approx(length) == value
        assert start == (-spec.LUG_HALF_T, 0.0)


def test_tap_and_foot_hole_station_reference_sketches() -> None:
    spec = ch_fulcrum_keeper_spec
    assert part.REFERENCE_SKETCHES == spec.REFERENCE_SKETCHES
    assert [row[0] for row in part.REFERENCE_LINES] == [
        "SetScrewReference",
        "FootScrewReference",
        "FootScrewSideReference",
        "BoreSideReference",
        "OverallHeightReference",
        "OverallLengthReference",
    ]
    rows = {row[0]: row for row in part.REFERENCE_LINES}
    _, plane, dimension, start, end, _, value, _ = rows["SetScrewReference"]
    assert (plane, dimension) == ("Top", "SetScrewLocation")
    assert start == (-spec.LUG_HALF_T, 0.0)
    assert end == (0.0, 0.0)
    assert value == spec.LUG_HALF_T
    corner = (spec.FOOT_TIP_X, spec.KEEPER_WIDTH / 2.0)
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewReference"]
    assert (plane, dimension) == ("Top", "ScrewFromTip")
    assert start == corner and end == (spec.SCREW_X, corner[1])
    assert value == pytest.approx(spec.FOOT_TIP_X - spec.SCREW_X)
    assert value == spec.SCREW_FROM_TIP == 4.572
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewSideReference"]
    assert (plane, dimension) == ("Top", "ScrewFromSide")
    assert start == corner and end == (spec.FOOT_TIP_X, 0.0)
    assert value == spec.KEEPER_WIDTH / 2.0
    _, plane, dimension, start, end, _, value, _ = rows["BoreSideReference"]
    assert (plane, dimension) == ("Right", "BoreFromSide")
    assert start == (spec.KEEPER_WIDTH / 2.0, spec.SHAFT_AXIS_H)
    assert end == (0.0, spec.SHAFT_AXIS_H)
    _, plane, dimension, start, end, _, value, _ = rows["OverallHeightReference"]
    assert (plane, dimension) == ("Front", "OverallHeight")
    assert start == (-spec.LUG_HALF_T, 0.0)
    assert end == (-spec.LUG_HALF_T, spec.CROWN_TOP_Y)
    assert value == spec.CROWN_TOP_Y
    _, plane, dimension, start, end, _, value, _ = rows["OverallLengthReference"]
    assert (plane, dimension) == ("Front", "OverallLength")
    assert start == (-spec.LUG_HALF_T, 0.0)
    assert end == (spec.FOOT_TIP_X, 0.0)
    assert value == spec.OVERALL_LENGTH


def test_keeper_tap_spec_for_the_frame() -> None:
    spec = ch_fulcrum_keeper_spec
    tap = spec.KEEPER_TAP_SPEC
    assert (tap.kind, tap.size, tap.end) == ("tapped", "#2-56", "blind")
    assert tap.size == spec.FOOT_SCREW_THREAD
    assert tap.overrides_mm["ThreadDepth"] == spec.KEEPER_TAP_THREAD_DEPTH_MM == 7.6
    assert tap.depth_mm == 11.5


def test_fitup_exports_for_the_top_frame() -> None:
    from _cone_axis_constants import FRAME_FRONT_COLUMN_Z
    from channel_frame_geom import LEVER_FULCRUM_XY
    from frame_column_stations import COLUMN_X

    spec = ch_fulcrum_keeper_spec
    import ch_channel_assembly_spec as asm

    assert spec.KEEPER_FITUP_PLACES == 3
    assert (
        asm.DRAWING_PRECISION[asm.KEEPER_PLAN_FEATURE][asm.KEEPER_X_DIMENSION]
        == spec.KEEPER_FITUP_PLACES
    )
    assert COLUMN_X + spec.KEEPER_FITUP_X_FROM_WEB_MM == pytest.approx(
        LEVER_FULCRUM_XY[0]
    )
    assert spec.KEEPER_FITUP_X_BAND_MM == 0.1016
    front, rear = spec.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    inner = spec.KEEPER_Z_OFF - spec.LUG_HALF_T
    assert front == pytest.approx(
        spec.FULCRUM_KEEPER_CENTRE_Z - inner - FRAME_FRONT_COLUMN_Z
    )
    assert rear == pytest.approx(
        spec.FULCRUM_KEEPER_CENTRE_Z + inner - FRAME_FRONT_COLUMN_Z
    )


def test_print_carries_no_datums_or_frames_and_no_assembly_steps() -> None:
    assert not hasattr(ch_fulcrum_keeper_spec, "GEOMETRIC_TOLERANCES_MM")
    printed = " ".join((
        *drawing.DIMENSION_CALLOUTS.values(),
        drawing.SET_SCREW_QUALIFIER,
        ch_fulcrum_keeper_notes.FOOT_HOLE_MATE,
        ch_fulcrum_keeper_notes.DRAWING_NOTES,
    ))
    assert "MHA-CH-00" not in printed and "STEP" not in printed
    assert drawing.SET_SCREW_EXTENT == "TO BORE"
    for rows in (
        *drawing.DIMENSION_CALLOUTS.values(),
        drawing.SET_SCREW_QUALIFIER,
        ch_fulcrum_keeper_notes.FOOT_HOLE_MATE,
    ):
        assert len(rows.splitlines()) <= 3
    for key in ("BoreDia", "CrownRadius", "FootRise", "CornerRadius"):
        assert len(drawing.DIMENSION_CALLOUTS[key].splitlines()) <= 2


_NATIVE_TAP = {
    5: "<hw-threaddesc> - <hw-threadclass> <hw-thru>",
    6: "",
    7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
    8: "",
}


def test_tap_callout_says_to_bore_and_closes_with_mate_and_stage() -> None:
    updated = drawing.set_screw_callout_definitions(dict(_NATIVE_TAP))
    assert updated[7] == "<MOD-DIAM><hw-thrutapdrldia> TO BORE"
    assert updated[5] == f"<hw-threaddesc> TO BORE\n{drawing.SET_SCREW_QUALIFIER}"
    assert updated[6] == updated[8] == ""
    blind = {**_NATIVE_TAP, 7: "<MOD-DIAM><hw-thrutapdrldia> <hw-deep>"}
    with pytest.raises(RuntimeError, match="two native extents"):
        drawing.set_screw_callout_definitions(blind)


def test_screw_hole_is_plain_close_clearance_on_the_open_step() -> None:
    hole = ch_fulcrum_keeper_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is hole
    assert hole is ch_fulcrum_keeper_spec.SCREW_CLEARANCE_SPEC
    assert (hole.kind, hole.size, hole.fit) == ("clearance", "#2", "close")
    assert FRAME_SIDE_SHANK_DIA < ch_fulcrum_keeper_spec.HOLE_DIA_MM < FRAME_SIDE_HEAD_DIA
    assert ch_fulcrum_keeper_spec.FOOT_UNSTEPPED_H - ch_fulcrum_keeper_spec.FOOT_H == pytest.approx(
        FRAME_SIDE_HEAD_H
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert ch_fulcrum_keeper_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"


def test_foot_hole_leader_routes_clear_of_the_crown_tap() -> None:
    from _layout_audit import _segment_crossing
    from _layout_geometry import (
        Segment,
        point_segment_distance,
        segment_circle_distance,
    )

    spec = ch_fulcrum_keeper_spec
    tap_leader = Segment(0.0997, 0.2295, 0.0993, 0.2265)
    assert _segment_crossing(Segment(0.1122, 0.2283, 0.0624, 0.2324), tap_leader)
    x, _ = drawing.FOOT_HOLE_CALLOUT_XY
    cy = drawing.TOP_CENTER[1]
    leader = _foot_hole_leader()
    tip = (leader.x1, leader.y1)
    assert _segment_crossing(leader, tap_leader) is None
    tap = (drawing.TAP_X_SHEET, cy, drawing.TAP_R_SHEET)
    assert segment_circle_distance(leader, tap) >= 0.003
    scale = drawing.SHEET_SCALE[0] / 1000.0
    corner = (drawing._front_x(spec.FOOT_TIP_X), cy - spec.KEEPER_WIDTH / 2.0 * scale)
    assert point_segment_distance(corner, leader) >= 0.003
    assert tip[1] <= cy - 0.0015
    assert x >= 0.1082 + 0.003


_CAP = 0.0035
_PITCH = 0.00556
_STACK = 0.00453
_CHAR = 0.0028
_PLACEMENT_SLACK = 0.0011
_SHOULDER_RUN = 0.0016
_AIR = 0.003 + _PLACEMENT_SLACK


def _text_block(xy, rows, *, stack=False):
    from _layout_geometry import Box

    width = max(map(len, rows)) * _CHAR
    height = (len(rows) - 1) * _PITCH + _CAP + (_STACK if stack else 0.0)
    return Box(xy[0] - width / 2, xy[1] - height / 2, xy[0] + width / 2, xy[1] + height / 2)


def _box_gap(a, b) -> float:
    return math.hypot(
        max(b.xmin - a.xmax, a.xmin - b.xmax, 0.0), max(b.ymin - a.ymax, a.ymin - b.ymax, 0.0)
    )


def _shoulder_leader(block, target, radius):
    """Bend (shoulder end facing ``target``) to the rim point toward it."""
    from _layout_geometry import Segment

    facing_right = (block.xmin + block.xmax) / 2.0 < target[0]
    bend = (block.xmax + _SHOULDER_RUN if facing_right else block.xmin - _SHOULDER_RUN, block.ymin)
    reach = math.dist(bend, target)
    rim = (
        target[0] + radius * (bend[0] - target[0]) / reach,
        target[1] + radius * (bend[1] - target[1]) / reach,
    )
    return Segment(*rim, *bend)


def test_end_view_callouts_stand_clear_of_the_part_and_each_other() -> None:
    from _layout_audit import _segment_crossing
    from _layout_geometry import Box, Segment, segment_box_distance

    spec = ch_fulcrum_keeper_spec
    scale = drawing.SHEET_SCALE[0] / 1000.0
    cx = drawing.RIGHT_CENTER[0]
    bottom = drawing.RIGHT_CENTER[1] - spec.CROWN_TOP_Y * scale / 2.0
    centre = (cx, bottom + spec.SHAFT_AXIS_H * scale)
    half = spec.KEEPER_WIDTH * scale / 2.0
    crown_r = spec.CROWN_R * scale
    body = Box(cx - half, bottom, cx + half, centre[1])
    assert drawing.NEAR_SIDE_DIAMETERS == ("BoreDia",)
    keep = drawing.RIGHT_KEEP
    callouts = drawing.DIMENSION_CALLOUTS
    blocks = {
        "CrownRadius": _text_block(
            keep["CrownRadius"], ["(R.275)", *callouts["CrownRadius"].splitlines()]
        ),
        "BoreDia": _text_block(
            keep["BoreDia"], ["Ø.257", *callouts["BoreDia"].splitlines()]
        ),
        "Depth": _text_block(keep["Depth"], [".55"]),
        "BoreFromSide": _value_block(
            keep["BoreFromSide"], "(.275)", callouts["BoreFromSide"]
        ),
    }
    leaders = {
        "CrownRadius": _shoulder_leader(blocks["CrownRadius"], centre, crown_r),
        "BoreDia": _shoulder_leader(blocks["BoreDia"], centre, spec.BORE_DIA * scale / 2.0),
    }
    assert leaders["CrownRadius"].y0 > centre[1] + 0.003
    neighbours = {
        "iso note": Box(0.3098, 0.1459, 0.3694, 0.1502),
        "iso view": Box(0.3136, 0.165, 0.3464, 0.215),
        "foot-hole callout": _foot_hole_block(),
        "corner radius": _value_block(
            drawing.FRONT_KEEP["CornerRadius"], "R.02 MAX", callouts["CornerRadius"]
        ),
        "foot rise": _value_block(
            drawing.FOOT_RISE_TEXT_XY, ".227", callouts["FootRise"]
        ),
        "25.20": Box(0.1889, 0.1232, 0.2031, 0.1267),
        "title block": Box(0.216, 0.0, 0.4318, 0.066),
    }
    for name, block in blocks.items():
        assert 0.0127 + 0.003 <= block.xmin and block.xmax <= 0.4318 - 0.0127 - 0.003, name
        assert block.ymax <= 0.2794 - 0.0127 - 0.003, name
        assert _box_gap(block, body) >= _AIR, name
        nearest = (
            min(max(centre[0], block.xmin), block.xmax),
            min(max(centre[1], block.ymin), block.ymax),
        )
        assert math.dist(nearest, centre) - crown_r >= _AIR, name
        for other, box in neighbours.items():
            assert _box_gap(block, box) >= _AIR, (name, other)
        for other, box in blocks.items():
            if other != name:
                assert _box_gap(block, box) >= _AIR, (name, other)
        for other, leader in leaders.items():
            if other != name:
                assert segment_box_distance(leader, block) >= 0.003, (other, name)
    assert _segment_crossing(leaders["CrownRadius"], leaders["BoreDia"]) is None
    depth_line = keep["Depth"][1] - 0.0028
    lug_rise_x = keep["LugRise"][0]
    lines = [
        Segment(cx - half, depth_line, cx + half, depth_line),
        Segment(cx - half, bottom - 0.001, cx - half, depth_line - 0.001),
        Segment(cx + half, bottom - 0.001, cx + half, depth_line - 0.001),
        Segment(lug_rise_x, bottom, lug_rise_x, centre[1]),
        Segment(lug_rise_x - 0.001, bottom, cx + half - 0.001, bottom),
        Segment(lug_rise_x - 0.001, centre[1], cx + half - 0.001, centre[1]),
    ]
    for name, leader in leaders.items():
        for line in lines:
            assert _segment_crossing(leader, line) is None, (name, line)
    assert blocks["Depth"].ymax <= bottom - _AIR
    bore_side = blocks["BoreFromSide"]
    assert bore_side.ymin >= bottom + spec.CROWN_TOP_Y * scale + _AIR
    assert bore_side.xmin >= cx + half + 0.003
    assert segment_box_distance(leaders["CrownRadius"], bore_side) >= 0.003


def _value_block(xy, value, callout):
    from _layout_geometry import Box

    rows = [value, *callout.splitlines()] if callout else [value]
    block = _text_block(xy, rows)
    return Box(
        block.xmin,
        block.ymin - _PLACEMENT_SLACK,
        block.xmax,
        block.ymax + _PLACEMENT_SLACK,
    )


def _tap_rows() -> list[str]:
    extent = drawing.SET_SCREW_EXTENT
    return [
        f"Ø .060 {extent}",
        f"1-72 UNF {extent}",
        *drawing.SET_SCREW_QUALIFIER.splitlines(),
    ]


def _foot_hole_rows() -> list[str]:
    return [
        f"Ø .094 {drawing.FOOT_HOLE_THRU}",
        *ch_fulcrum_keeper_notes.FOOT_HOLE_MATE.splitlines(),
    ]


def test_function_callouts_stand_clear_of_the_views_and_each_other() -> None:
    from _layout_geometry import Box, Segment, segment_box_distance

    spec = ch_fulcrum_keeper_spec
    scale = drawing.SHEET_SCALE[0] / 1000.0
    seat = drawing.FRONT_CENTER[1] - spec.CROWN_TOP_Y * scale / 2.0
    lug = Box(
        drawing._front_x(-spec.LUG_HALF_T),
        seat,
        drawing._front_x(spec.LUG_HALF_T),
        seat + spec.CROWN_TOP_Y * scale,
    )
    foot_top = seat + spec.FOOT_H * scale
    foot = Box(lug.xmax, seat, drawing._front_x(spec.FOOT_TIP_X), foot_top)
    cy = drawing.TOP_CENTER[1]
    plan = Box(
        lug.xmin,
        cy - spec.KEEPER_WIDTH * scale / 2.0,
        foot.xmax,
        cy + spec.KEEPER_WIDTH * scale / 2.0,
    )
    crown_block = _text_block(
        drawing.RIGHT_KEEP["CrownRadius"],
        ["(R.275)", *drawing.DIMENSION_CALLOUTS["CrownRadius"].splitlines()],
    )
    notes_top = drawing.NOTES_TOP
    notes = Box(0.020, notes_top - 2 * _PITCH, 0.120, notes_top)
    overall_length = _text_block(drawing.FRONT_KEEP["OverallLength"], [".65"])
    foot_hole = _foot_hole_block()
    tap = _text_block(drawing.SET_SCREW_CALLOUT_XY, _tap_rows())
    keeps = {**drawing.FRONT_KEEP, **drawing.TOP_KEEP, "FootRise": drawing.FOOT_RISE_TEXT_XY}
    callouts = drawing.DIMENSION_CALLOUTS
    values = {
        "SetScrewLocation": ".16",
        "LugThickness": ".32",
        "ScrewFromSide": ".275",
        "FootRise": ".227",
        "CornerRadius": "R.02 MAX",
    }
    blocks = {
        name: _value_block(keeps[name], value, callouts.get(name, ""))
        for name, value in values.items()
    }
    side = blocks["ScrewFromSide"]
    shift = keeps["ScrewFromSide"][0] - side.xmin
    blocks["ScrewFromSide"] = Box(side.xmin + shift, side.ymin, side.xmax + shift, side.ymax)
    neighbours = {
        "lug": lug,
        "foot": foot,
        "plan": plan,
        "crown block": crown_block,
        "notes": notes,
        "foot-hole callout": foot_hole,
        "tap callout": tap,
        "overall length": overall_length,
        "overall height": _text_block(drawing.FRONT_KEEP["OverallHeight"], ["(1.27)"]),
        "screw from tip": _text_block(drawing.TOP_KEEP["ScrewFromTip"], [".18"]),
        "title block": Box(0.216, 0.0, 0.4318, 0.066),
    }
    for name, block in blocks.items():
        assert 0.0127 + _AIR <= block.xmin, name
        assert block.xmax <= 0.4318 - 0.0127 - _AIR, name
        assert block.ymax <= 0.2794 - 0.0127 - _AIR, name
        for other, box in {**neighbours, **blocks}.items():
            if other != name:
                assert _box_gap(block, box) >= _AIR, (name, other)
    assert blocks["SetScrewLocation"].xmax <= plan.xmin - _AIR
    assert blocks["SetScrewLocation"].ymin >= plan.ymax + 0.003
    assert blocks["LugThickness"].xmax <= lug.xmin - _AIR
    assert blocks["ScrewFromSide"].ymax <= cy - _AIR
    assert blocks["ScrewFromSide"].xmin >= plan.xmax + _AIR
    assert blocks["CornerRadius"].xmin >= lug.xmax + _AIR
    assert blocks["CornerRadius"].ymin >= foot_top + _AIR
    assert blocks["FootRise"].xmin >= drawing.FRONT_KEEP["FootRise"][0] + 0.001
    assert blocks["FootRise"].ymax <= seat - _AIR
    assert blocks["LugThickness"].ymin - (overall_length.ymax + 0.003) >= _AIR
    assert overall_length.ymin - 0.003 - notes_top >= _AIR
    length_y = drawing.FRONT_KEEP["OverallLength"][1]
    for x in (lug.xmin, foot.xmax):
        line = Segment(x, seat, x, length_y - 0.003)
        for name in ("LugThickness", "FootRise"):
            assert segment_box_distance(line, blocks[name]) >= 0.003, (name, line)
        assert segment_box_distance(line, notes) >= 0.003, line


def test_tap_callout_stands_inside_the_border_clear_of_the_plan() -> None:
    from _layout_audit import _segment_crossing
    from _layout_geometry import Box, Segment, point_segment_distance

    spec = ch_fulcrum_keeper_spec
    rows = _tap_rows()
    assert max(map(len, rows)) <= 24
    block = _text_block(drawing.SET_SCREW_CALLOUT_XY, rows)
    assert block.xmin >= 0.0127 + _AIR
    scale = drawing.SHEET_SCALE[0] / 1000.0
    cy = drawing.TOP_CENTER[1]
    plan = Box(
        drawing._front_x(-spec.LUG_HALF_T),
        cy - spec.KEEPER_WIDTH * scale / 2.0,
        drawing._front_x(spec.FOOT_TIP_X),
        cy + spec.KEEPER_WIDTH * scale / 2.0,
    )
    station = "SetScrewLocation"
    set_screw_location = _value_block(drawing.TOP_KEEP[station], ".16", "")
    foot_hole = _foot_hole_block()
    for other in (plan, set_screw_location, foot_hole):
        assert _box_gap(block, other) >= _AIR, other
    bend = (block.xmax + _SHOULDER_RUN, block.ymin)
    leader = Segment(*bend, drawing.TAP_X_SHEET, cy - drawing.TAP_R_SHEET)
    assert _segment_crossing(leader, _foot_hole_leader()) is None
    assert point_segment_distance((foot_hole.xmin, foot_hole.ymin), leader) >= 0.003
    assert point_segment_distance((plan.xmin, plan.ymin), leader) >= 0.003


def _foot_hole_block():
    return _text_block(drawing.FOOT_HOLE_CALLOUT_XY, _foot_hole_rows())


def _foot_hole_leader():
    from _layout_geometry import Segment

    block = _foot_hole_block()
    bend = (block.xmin - _SHOULDER_RUN, block.ymin)
    centre = (drawing.HOLE_X_SHEET, drawing.TOP_CENTER[1])
    dx, dy = bend[0] - centre[0], bend[1] - centre[1]
    scale = drawing.HOLE_R_SHEET / math.hypot(dx, dy)
    return Segment(*bend, centre[0] + dx * scale, centre[1] + dy * scale)


def test_foot_hole_leader_climbs_left_of_its_own_upper_rows() -> None:
    from _layout_geometry import Box, segment_box_distance

    rows = _foot_hole_rows()
    assert len(rows) <= 4
    block = _foot_hole_block()
    leader = _foot_hole_leader()
    for index, row in enumerate(rows[:-1]):
        top = block.ymax - index * _PITCH
        half = len(row) * _CHAR / 2.0
        cx = drawing.FOOT_HOLE_CALLOUT_XY[0]
        box = Box(cx - half, top - _CAP, cx + half, top)
        assert segment_box_distance(leader, box) >= 0.001, row


def test_the_auto_tapped_hole_note_is_removed() -> None:
    assert "tapped hole" not in ch_fulcrum_keeper_notes.DRAWING_NOTES.lower()


def test_foot_hole_callout_says_size_drill_thru_and_its_mates_below() -> None:
    native = {
        5: "<MOD-DIAM><hw-diam> <hw-thru>",
        6: "",
        7: "",
        8: "",
    }
    updated = drawing.foot_hole_callout_definitions(native)
    assert updated == {
        **native,
        5: "<MOD-DIAM><hw-diam> DRILL THRU",
        8: ch_fulcrum_keeper_notes.FOOT_HOLE_MATE,
    }
    with pytest.raises(RuntimeError, match="THRU row"):
        drawing.foot_hole_callout_definitions({**native, 7: native[5]})


def test_notes_and_callouts_name_each_mate_once() -> None:
    notes = ch_fulcrum_keeper_notes.DRAWING_NOTES
    assert "MATERIAL" not in notes and "1018" not in notes
    assert "BLACK OXIDE" not in notes.upper()
    assert "REAM" not in notes
    assert "MHA-CH-VN-55" in drawing.SET_SCREW_QUALIFIER
    assert "MHA-CH-VN-52" in drawing.DIMENSION_CALLOUTS["CornerRadius"]
    assert "MHA-CH-VN-52" not in ch_fulcrum_keeper_notes.FOOT_HOLE_MATE
    assert "MHA-FR-02" in ch_fulcrum_keeper_notes.FOOT_HOLE_MATE
    assert "MHA-FR-02" in drawing.DIMENSION_CALLOUTS["FootRise"]
    assert "MHA-CH-04" in drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "MHA-CH-VN-55" not in notes and "MHA-CH-VN-52" not in notes
    assert notes == "1. 2 REQUIRED, IDENTICAL."
    assert "TIP WALL" not in notes
    assert "RULING" not in notes and "EXCEPTION" not in notes
    assert part.DRAWING_NOTES is notes


def test_keeper_is_one_body_with_no_ball() -> None:
    assert not hasattr(ch_fulcrum_keeper_spec, "BALL_DIA")


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "FootScrewHole" not in part.DRAWING_DIMENSIONS
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_parts_registry_row() -> None:
    config = _config.parts("ch-fulcrum-keeper")
    assert config["number"] == "MHA-CH-07"
    assert config["material"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    finish = str(config["finish"])
    assert "black oxide" in finish and "oil" in finish
    assert "pair-ream" not in finish
    assert int(config["quantity"]) == 2


def _in(value: float) -> float:
    return value * 25.4


def test_the_keeper_declares_one_owner_per_face() -> None:
    import export_features
    from _gtol_face import FaceGeometry

    spec = ch_fulcrum_keeper_spec

    def plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
        point = tuple(value * offset_mm / 1000 for value in normal)
        return FaceGeometry(None, 4001, (*normal, *point), normal, ())

    def cylinder(dia_mm: float, box_mm: tuple[float, ...]) -> FaceGeometry:
        box = tuple(value / 1000 for value in box_mm)
        return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, 0, 0, 1, dia_mm / 2000), None, box)

    manifest = export_features.requirement_manifest("ch_fulcrum_keeper")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == {
        "seat": "face",
        "foot_top": "face",
        "inner_face": "face",
        "lug_outer_face": "face",
        "foot_tip": "face",
        "near_side": "face",
        "far_side": "face",
        "inside_corner": "fillet",
        "crown": "arc",
        "bore": "hole",
        "crown_tap": "threaded_hole",
        "foot_hole": "hole",
    }
    half_w, half_t = spec.KEEPER_WIDTH / 2, spec.LUG_HALF_T
    x = spec.SCREW_X
    tap_r = drawing._TAP_DRILL / 2
    r_c = spec.CORNER_R_MAX
    faces = {
        "seat": plane((0.0, -1.0, 0.0), 0.0),
        "foot_top": plane((0.0, 1.0, 0.0), spec.FOOT_H),
        "inner_face": plane((-1.0, 0.0, 0.0), half_t),
        "lug_outer_face": plane((1.0, 0.0, 0.0), half_t),
        "foot_tip": plane((1.0, 0.0, 0.0), spec.FOOT_TIP_X),
        "near_side": plane((0.0, 0.0, -1.0), half_w),
        "far_side": plane((0.0, 0.0, 1.0), half_w),
        "inside_corner": cylinder(2 * r_c, (half_t, spec.FOOT_H, -half_w, half_t + r_c, spec.FOOT_H + r_c, half_w)),
        "crown": cylinder(2 * spec.CROWN_R, (-half_t, spec.SHAFT_AXIS_H, -half_w, half_t, spec.CROWN_TOP_Y, half_w)),
        "bore": cylinder(spec.BORE_DIA, (-half_t, 21.9, -3.3, half_t, 28.5, 3.3)),
        "crown_tap": cylinder(drawing._TAP_DRILL, (-tap_r, 28.0, -tap_r, tap_r, spec.CROWN_TOP_Y, tap_r)),
        "foot_hole": cylinder(spec.HOLE_DIA_MM, (x - 1.2, 0.0, -1.2, x + 1.2, spec.FOOT_H, 1.2)),
    }
    selectors = export_features.feature_selectors("ch_fulcrum_keeper")
    for name, face in faces.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_keeper_feature_bands_are_the_printed_ones() -> None:
    import export_features

    features = export_features.requirement_manifest("ch_fulcrum_keeper")["features"]
    assert features["foot_top"]["height"] == pytest.approx([_in(0.222), _in(0.232)])
    assert features["lug_outer_face"]["thickness"] == pytest.approx([_in(0.31), _in(0.33)])
    assert features["foot_tip"]["length"] == pytest.approx([_in(0.64), _in(0.66)])
    assert features["far_side"]["width"] == pytest.approx([_in(0.54), _in(0.56)])
    assert features["inside_corner"]["radius"] == pytest.approx([0.0, _in(0.02)])
    bore = features["bore"]
    assert bore["dia"] == pytest.approx([6.528, 6.6296])
    assert bore["process"] == "drill" and bore["drill"] == "F" and bore["thru"] is True
    assert bore["height"] == pytest.approx([_in(0.98), _in(1.00)])
    assert bore["off_centre"] == pytest.approx([_in(-0.012), _in(0.012)])
    tap = features["crown_tap"]
    assert tap["thread"] == "#1-72 UNF-2B" and tap["into"] == "bore"
    assert tap["station"] == pytest.approx([_in(0.15), _in(0.17)])
    hole = features["foot_hole"]
    assert hole["dia"] == pytest.approx([_in(0.094), _in(0.098)], abs=1e-3)
    assert "cbore_dia" not in hole and "cbore_depth" not in hole and "tip_wall_min" not in hole
    assert hole["station"] == pytest.approx([_in(0.17), _in(0.19)])
    assert hole["lateral"] == pytest.approx([_in(0.270), _in(0.280)])
