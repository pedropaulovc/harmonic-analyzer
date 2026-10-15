"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_ch_fulcrum_keeper as part
import ch_channel_assembly_steps as steps
import draw_ch_fulcrum_keeper as drawing
import ch_fulcrum_keeper_spec
import _config
from _drawing_registry import DRAWINGS_BY_NAME
from vn_frame_side_screw_spec import HEAD_H as FRAME_SIDE_HEAD_H


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-fulcrum-keeper.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-fulcrum-keeper.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-fulcrum-keeper_drawing.png")
    assert DRAWINGS_BY_NAME["ch_fulcrum_keeper"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set
    # are BOTH the shared spec's map.
    assert part.DRAWING_DIMENSIONS is ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS
    marked = set().union(*ch_fulcrum_keeper_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_geometry_matches_the_top_frame_contract() -> None:
    # The keeper exists to hold the fulcrum shaft 25.2 above the rail top
    # face (1061.4 - 1036.2, the 2026-08-02 rederive contract) on a flat
    # seat: a 6.0 lug with a straight foot running OUTBOARD to x = 13.5.
    spec = ch_fulcrum_keeper_spec
    assert spec.SHAFT_AXIS_H == 25.2
    assert spec.CROWN_DIA == spec.KEEPER_WIDTH == 14.0
    assert 2.0 * spec.LUG_HALF_T == 6.0
    assert spec.FOOT_TIP_X == spec.LUG_HALF_T + spec.FOOT_L == 13.5
    assert spec.SCREW_X == 8.25
    assert spec.KEEPER_SCREW_Z_OFF == spec.KEEPER_Z_OFF + spec.SCREW_X == 82.25
    # Plain reamed bore on the plain Ø6.35 shaft: a running band, cut by one
    # made-to-order 0.2514 in reamer through both keepers at their installed
    # spacing, that covers the faced rail seats' flatness (ch_fulcrum_shaft_spec).
    assert spec.BORE_DIA == 6.35
    assert spec.BORE_DIA_BAND == (0.050, 0.035)  # (upper, lower)
    # The mate is the OTHER keeper of the pair, which the quantity note states.
    # MR-fleet r1: the supply condition -- no bore until the pair-ream, the
    # crown rounded after it -- is on the two callouts.
    pair_ream = " ".join(spec.BORE_PAIR_CALLOUT.split())
    assert pair_ream.startswith(
        "SUPPLIED UNDRILLED; PAIR-REAM WITH THE OTHER MHA-CH-007"
    )
    assert f"(NOTE {spec.QUANTITY_NOTE}) AT INSTALLED SPACING" in pair_ream
    assert "AT INSTALLED SPACING; THE MHA-CH-004 SHAFT SLIDES THROUGH BOTH" in pair_ream
    assert spec.CROWN_ABOUT_BORE_CALLOUT == "ROUND ABOUT THE BORE AFTER REAMING"
    notes = spec.DRAWING_NOTES.splitlines()
    quantity = [line for line in notes if "2 REQUIRED" in line]
    assert len(quantity) == 1 and quantity[0].startswith(f"{spec.QUANTITY_NOTE}. ")


def test_crown_set_screw_tap_stops_at_the_bore() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_THREAD == "#1-72"
    assert spec.SET_SCREW_HOLE_SPEC.kind == "tapped"
    assert spec.SET_SCREW_HOLE_SPEC.end == "through_next"
    assert spec.CROWN_TOP_Y == spec.SHAFT_AXIS_H + spec.CROWN_DIA / 2.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="SetScrewTap"' in source
    # through_next stops at the bore only if the bore is already cut.
    assert source.index('"cut bore"') < source.index('name="SetScrewTap"')


def test_rule_12_worst_case_walls_and_thread() -> None:
    # Worst case of the printed bands (drawing-guidelines.md rule 18 (thread engagement)): >= 1.5D of full
    # crown thread and of foot-screw engagement in the frame, >= 1.5 web from
    # the crown thread major to each lug face and from the foot counterbore
    # to the foot tip and sides.
    spec = ch_fulcrum_keeper_spec
    assert spec.SET_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.FOOT_SCREW_ENGAGEMENT_D >= 1.5
    assert spec.SET_SCREW_WEB_MM >= 1.5
    assert spec.FOOT_TIP_WALL_MM >= 2.0
    assert spec.FOOT_SIDE_WALL_MM >= 2.0
    assert round(spec.SET_SCREW_WEB_MM, 3) == 1.813
    assert round(spec.FOOT_TIP_WALL_MM, 3) == 2.79
    assert round(spec.FOOT_CBORE_LUG_CLEARANCE_MM, 3) == 1.99
    assert round(spec.FOOT_SCREW_ENGAGEMENT_D, 2) == 1.79
    # The native counterbore callout prints the template's .XX; the engagement
    # and bottoming stacks take that printed depth (2.11), not 2.1082.
    assert spec.FOOT_COUNTERBORE_DEPTH_PLACES == 2
    # The web is only met with the lug and tap station at three places.
    assert spec.DRAWING_PRECISION["LugBody"]["LugThickness"] == 3
    assert spec.DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] == 3
    # Off the foot tip the hole's station holds the tip wall at .XX; the
    # frame's transferred tap takes the .XXX side-station band.
    assert spec.DRAWING_PRECISION["FootScrewReference"]["ScrewFromTip"] == 2
    assert spec.DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] == 3
    assert spec.KEEPER_SCREW_TRANSVERSE_BAND_MM == spec._BAND_BY_PLACES[3]


def test_three_place_sizes_state_their_function() -> None:
    # Machinist review baseline (rule 3/4): 6.000, 3.000 and 7.000 printed
    # with neither a band nor a function. Each now names what it holds; MR-fleet
    # r1: the station alone sets the screw on its flat, from the inner face,
    # and the lug thickness holds the tap's outer web.
    spec = ch_fulcrum_keeper_spec
    three_place = {
        name
        for places in spec.DRAWING_PRECISION.values()
        for name, value in places.items()
        if value == 3
    } - {"BoreDia"}  # the reamed bore carries its own band
    callouts = {**drawing.FRONT_CALLOUTS, **drawing.TOP_CALLOUTS}
    # The supplied height's callout names what it is, not a function.
    assert set(callouts) - {"SupplyHeight"} == three_place
    assert " ".join(drawing.FRONT_CALLOUTS["LugThickness"].split()) == (
        "HOLDS CROWN TAP OUTER WALL"
    )
    assert drawing.TOP_CALLOUTS["SetScrewLocation"] == spec.SET_SCREW_STATION_CALLOUT
    shaft = _config.parts("ch-fulcrum-shaft")["number"]
    frame = _config.parts("fr-top-frame")["number"]
    assert shaft in spec.SET_SCREW_STATION_CALLOUT
    assert frame in drawing.TOP_CALLOUTS["ScrewFromSide"]
    # At .X (+-0.8 for .XXX's +-0.13) the lug would leave the outer web, the
    # thinner one, under the 1.5 floor.
    bands = spec._BAND_BY_PLACES
    assert spec.SET_SCREW_WEB_MM + bands[3] - bands[1] < 1.5


def test_corner_round_prints_its_max_limit_in_the_open_corner() -> None:
    # MR-fleet r1: the foot-to-lug inside corner was sharp and unstated. The
    # part models it at its single limit, which keeps the round's tangent
    # line off the counterbore, and the front view prints "R1.0 MAX" up in
    # the open corner on the round's bisector, clear of the views.
    from _layout_geometry import Box

    spec = ch_fulcrum_keeper_spec
    assert spec.DRAWING_DIMENSIONS["CornerFillet"] == {"CornerRadius"}
    assert spec.DRAWING_PRECISION["CornerFillet"] == {"CornerRadius": 1}
    assert spec.CORNER_R_BAND == (0.0, -spec.CORNER_R_MAX)
    assert spec.CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert 0.0 < spec.CORNER_R_MAX < spec.FOOT_CBORE_LUG_CLEARANCE_MM
    assert (
        part.V_CORNER
        == (1.0 - math.pi / 4.0) * spec.CORNER_R_MAX**2 * spec.KEEPER_WIDTH
    )
    scale = drawing.SHEET_SCALE[0] / 1000.0
    seat = drawing.FRONT_CENTER[1] - spec.CROWN_TOP_Y * scale / 2.0
    corner = (drawing._front_x(spec.LUG_HALF_T), seat + spec.FOOT_H * scale)
    x, y = drawing.FRONT_KEEP["CornerRadius"]
    assert math.isclose(x - corner[0], y - corner[1], abs_tol=0.001)
    block = _text_block((x, y), ["R1.0 MAX"])
    lug = Box(
        drawing._front_x(-spec.LUG_HALF_T),
        seat,
        corner[0],
        seat + spec.CROWN_TOP_Y * scale,
    )
    foot = Box(corner[0], seat, drawing._front_x(spec.FOOT_TIP_X), corner[1])
    crown_block = _text_block(
        drawing.RIGHT_KEEP["CrownDia"],
        ["Ø14.0", *drawing.DIMENSION_CALLOUTS["CrownDia"].splitlines()],
    )
    for other in (
        lug,
        foot,
        crown_block,
        _text_block(drawing.FRONT_KEEP["FootRise"], ["8.0"]),
    ):
        assert _box_gap(block, other) >= _AIR, other


def test_overall_sizes_and_bore_station_print_as_references() -> None:
    spec = ch_fulcrum_keeper_spec
    assert spec.REFERENCE_DIMENSIONS == (
        "BoreFromSide",
        "OverallHeight",
        "OverallLength",
    )
    assert spec.DRAWING_PRECISION["BoreSideReference"] == {"BoreFromSide": 1}
    assert spec.DRAWING_PRECISION["OverallHeightReference"] == {"OverallHeight": 1}
    assert spec.DRAWING_PRECISION["OverallLengthReference"] == {"OverallLength": 1}
    assert spec.OVERALL_LENGTH == 2.0 * spec.LUG_HALF_T + spec.FOOT_L == 16.5
    assert "BoreFromSide" in drawing.RIGHT_KEEP
    assert "OverallLength" in drawing.FRONT_KEEP
    # MR-fleet r4: the finished height stands beside the supplied one, the
    # larger outermost.
    assert (
        drawing.FRONT_KEEP["SupplyHeight"][0]
        < drawing.FRONT_KEEP["OverallHeight"][0]
        < drawing._front_x(-spec.LUG_HALF_T)
    )


def test_supply_height_prints_the_blank_minimum() -> None:
    # MR-fleet r3: supplied undrilled and square-topped, the blank's height
    # was printed nowhere. It must reach the crown apex of a bore at the top
    # of the .XX LugRise band; the part models it AT that limit.
    spec = ch_fulcrum_keeper_spec
    assert spec.DRAWING_DIMENSIONS["SupplyHeightReference"] == {"SupplyHeight"}
    assert spec.SUPPLY_HEIGHT_PLACES == 1
    assert spec.SUPPLY_HEIGHT_TOL_TYPE == 5  # swTolMIN
    assert spec.DRAWING_PRECISION["LugProfile"]["LugRise"] == 2
    apex = spec.SHAFT_AXIS_H + 0.51 + spec.CROWN_DIA / 2.0
    assert apex <= spec.SUPPLY_HEIGHT_MIN < apex + 0.1
    assert spec.SUPPLY_HEIGHT_MIN == 32.8
    assert "SupplyHeight" not in spec.REFERENCE_DIMENSIONS
    assert drawing.FRONT_CALLOUTS["SupplyHeight"] == spec.SUPPLY_HEIGHT_CALLOUT
    # The builder sets the MIN type on the line's own dimension (no upper
    # deviation: any taller blank rounds down to the crown).
    source = " ".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert re.search(
        r'_single_limit\( adapter, "SupplyHeightReference", "SupplyHeight", '
        r"SUPPLY_HEIGHT_MIN, SUPPLY_HEIGHT_TOL_TYPE, 0\.0, 0\.0, \)",
        source,
    )


def test_tap_and_foot_hole_station_reference_sketches() -> None:
    spec = ch_fulcrum_keeper_spec
    assert part.REFERENCE_SKETCHES == spec.REFERENCE_SKETCHES
    assert [row[0] for row in part.REFERENCE_LINES] == [
        "SetScrewReference",
        "FootScrewReference",
        "FootScrewSideReference",
        "BoreSideReference",
        "OverallHeightReference",
        "SupplyHeightReference",
        "OverallLengthReference",
    ]
    rows = {row[0]: row for row in part.REFERENCE_LINES}
    _, plane, dimension, start, end, _, value, _ = rows["SetScrewReference"]
    assert (plane, dimension) == ("Top", "SetScrewLocation")
    # From the inner lug face (the face the fit-up sets) to the tap axis, on
    # the seat along the mid-width.
    assert start == (-spec.LUG_HALF_T, 0.0)
    assert end == (0.0, 0.0)
    assert value == spec.LUG_HALF_T
    # The foot hole: off the foot tip and off the -Z side face, both lines
    # leaving the plan's tip/side corner.
    corner = (spec.FOOT_TIP_X, spec.KEEPER_WIDTH / 2.0)
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewReference"]
    assert (plane, dimension) == ("Top", "ScrewFromTip")
    assert start == corner and end == (spec.SCREW_X, corner[1])
    assert value == spec.FOOT_TIP_X - spec.SCREW_X == 5.25
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewSideReference"]
    assert (plane, dimension) == ("Top", "ScrewFromSide")
    # One keeper part: the foot hole on the width centreline.
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
    _, plane, dimension, start, end, _, value, _ = rows["SupplyHeightReference"]
    assert (plane, dimension) == ("Front", "SupplyHeight")
    assert start == (-spec.LUG_HALF_T, 0.0)
    assert end == (-spec.LUG_HALF_T, spec.SUPPLY_HEIGHT_MIN)
    assert value == spec.SUPPLY_HEIGHT_MIN
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
    # The pair is set by DRO (KEEPERS_SET_KEY): X off the rail web under
    # each lug, Z off the front socket line; the frame taps are transferred.
    spec = ch_fulcrum_keeper_spec
    assert spec.KEEPER_FITUP_LOCATION_BAND_MM == 0.02
    assert spec.KEEPER_FITUP_PLACES == 2
    assert spec.KEEPER_FITUP_X_FROM_WEB_MM == 2.9
    front, rear = spec.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    assert (round(front, 2), round(rear, 2)) == (40.5, 182.5)
    assert rear - front == 2.0 * (spec.KEEPER_Z_OFF - spec.LUG_HALF_T)


def test_print_carries_no_datums_or_frames_and_cites_the_fitup_steps() -> None:
    # Policy: brackets carry no GD&T; the bore pair's coaxiality is a named
    # step (F5) and the set-screw lock is a staked mouth (F6).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature" not in source
    assert "add_feature_control_frame" not in source
    assert not hasattr(ch_fulcrum_keeper_spec, "GEOMETRIC_TOLERANCES_MM")
    pair_ream = steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].endswith(f"PER {pair_ream}")
    assert drawing.DIMENSION_CALLOUTS["CrownDia"].endswith(f"PER {pair_ream}")
    assert steps.step_ref(steps.SET_SCREWS_STAKED_KEY) in drawing.SET_SCREW_QUALIFIER
    # MR-fleet r2/r3: supplied undrilled, the crown tap that stops at the bore
    # is cut after the pair-ream, on the bore's axis; the native sizes lead.
    assert drawing.SET_SCREW_EXTENT == "TO BORE"
    assert drawing.SET_SCREW_QUALIFIER.splitlines()[0] == "ON BORE AXIS AFTER REAM;"
    assert "STAKE AT ASSEMBLY PER" in drawing.SET_SCREW_QUALIFIER


_NATIVE_TAP = {
    5: "<hw-threaddesc> - <hw-threadclass> <hw-thru>",
    6: "",
    7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
    8: "",
}


def test_tap_callout_says_to_bore_and_closes_with_place_and_staking() -> None:
    updated = drawing.set_screw_callout_definitions(dict(_NATIVE_TAP))
    assert updated[7] == "<MOD-DIAM><hw-thrutapdrldia> TO BORE"
    assert updated[5] == f"<hw-threaddesc> TO BORE\n{drawing.SET_SCREW_QUALIFIER}"
    assert updated[6] == updated[8] == ""
    blind = {**_NATIVE_TAP, 7: "<MOD-DIAM><hw-thrutapdrldia> <hw-deep>"}
    with pytest.raises(RuntimeError, match="two native extents"):
        drawing.set_screw_callout_definitions(blind)


def test_screw_hole_seats_the_frame_side_screw() -> None:
    hole = ch_fulcrum_keeper_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is hole
    assert hole.kind == "counterbore_fillister"
    assert hole.size == "#2"
    assert hole.overrides_mm == {
        "HoleDiameter": ch_fulcrum_keeper_spec.HOLE_DIA_MM,
        "CounterBoreDiameter": ch_fulcrum_keeper_spec.CBORE_DIA_MM,
        "CounterBoreDepth": ch_fulcrum_keeper_spec.CBORE_DEPTH_MM,
    }
    assert ch_fulcrum_keeper_spec.HOLE_DIA_MM > part.FRAME_SIDE_SHANK_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DIA_MM > part.FRAME_SIDE_HEAD_DIA
    assert ch_fulcrum_keeper_spec.CBORE_DEPTH_MM == FRAME_SIDE_HEAD_H
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="FootScrewHole"' in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert ch_fulcrum_keeper_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "add_native_hole_callout(" in source


def test_foot_hole_leader_routes_clear_of_the_crown_tap() -> None:
    # Farm run r8 (HEAD c126e34b): with its text left of the plan, the
    # foot-hole callout's leader ran across the plan at y ~229 mm and through
    # the crown tap's end-on circle, crossing the tap callout's leader at
    # (99.7, 229.3) mm (leader-crosses-leader).  The leaders are r8's printed
    # ones; r8 printed the text end 5.6 mm under its position (238 -> 232.4)
    # and the tip on the counterbore rim toward it.
    from _layout_audit import _segment_crossing
    from _layout_geometry import (
        Segment,
        point_segment_distance,
        segment_circle_distance,
    )

    spec = ch_fulcrum_keeper_spec
    tap_leader = Segment(0.0997, 0.2295, 0.0993, 0.2265)
    assert _segment_crossing(Segment(0.1122, 0.2283, 0.0624, 0.2324), tap_leader)
    x, y = drawing.FOOT_HOLE_CALLOUT_XY
    end = (x, y - 0.0056)
    cx, cy = drawing.HOLE_X_SHEET, drawing.TOP_CENTER[1]
    reach = math.dist(end, (cx, cy))
    tip = (
        cx + drawing.CBORE_R_SHEET * (end[0] - cx) / reach,
        cy + drawing.CBORE_R_SHEET * (end[1] - cy) / reach,
    )
    leader = Segment(*tip, *end)
    assert _segment_crossing(leader, tap_leader) is None
    tap = (drawing.TAP_X_SHEET, cy, drawing.TAP_R_SHEET)
    assert segment_circle_distance(leader, tap) >= 0.003
    # It leaves the plan through the bottom edge >= 3 mm from the foot-tip
    # corner, its tip >= 3 mm under ScrewFromSide's extension on the screw
    # axis, and the text stands right of r8's SetScrewLocation text box.
    scale = drawing.SHEET_SCALE[0] / 1000.0
    corner = (drawing._front_x(spec.FOOT_TIP_X), cy - spec.KEEPER_WIDTH / 2.0 * scale)
    assert point_segment_distance(corner, leader) >= 0.003
    assert tip[1] <= cy - 0.003
    assert x >= 0.1082 + 0.003


# Printed text metrics of farm run r13 (20261011T024120388Z, layout audit):
# 3.5 mm capitals on a 5.56 mm pitch, a tolerance stack's upper row 4.53 mm
# over the value, 2.48-2.76 mm a character (2.8 bounds it), each block within
# 1.1 mm of its requested centre. A diametric's shoulder runs under its last
# row and 1.6 mm past the end facing the centre; its leader runs from there
# straight at the centre (r13: 30.1 and 32.0 deg, the bend-to-centre bearing).
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
    # Machinist review r13: the Ø14 crown callout, the 14.0 width, the Ø6.350
    # limits and the pair-ream note overprinted one another and the crown and
    # bore, and the Ø14 leader crossed the 14.0 line. Each now stands in its
    # own clear paper with a near-side leader, the width under the foot.
    from _layout_audit import _segment_crossing
    from _layout_geometry import Box, Segment, segment_box_distance

    spec = ch_fulcrum_keeper_spec
    scale = drawing.SHEET_SCALE[0] / 1000.0
    cx = drawing.RIGHT_CENTER[0]
    bottom = drawing.RIGHT_CENTER[1] - spec.CROWN_TOP_Y * scale / 2.0
    centre = (cx, bottom + spec.SHAFT_AXIS_H * scale)
    half = spec.KEEPER_WIDTH * scale / 2.0
    crown_r = spec.CROWN_DIA * scale / 2.0
    body = Box(cx - half, bottom, cx + half, centre[1])
    assert drawing.NEAR_SIDE_DIAMETERS == ("CrownDia", "BoreDia")
    keep = drawing.RIGHT_KEEP
    callouts = drawing.DIMENSION_CALLOUTS
    blocks = {
        "CrownDia": _text_block(
            keep["CrownDia"], ["Ø14.0", *callouts["CrownDia"].splitlines()]
        ),
        "BoreDia": _text_block(
            keep["BoreDia"], ["Ø6.350 +0.035", *callouts["BoreDia"].splitlines()], stack=True
        ),
        "Depth": _text_block(keep["Depth"], ["14.0"]),
    }
    leaders = {
        "CrownDia": _shoulder_leader(blocks["CrownDia"], centre, crown_r),
        "BoreDia": _shoulder_leader(blocks["BoreDia"], centre, spec.BORE_DIA * scale / 2.0),
    }
    # The crown is a half round: its leader lands on the arc above the axis.
    assert leaders["CrownDia"].y0 > centre[1] + 0.003
    # Neighbours, r13's printed extents (mm): the isometric note and view,
    # the foot-hole callout, the 25.20 text; the inner border and title block.
    neighbours = {
        "iso note": Box(0.3098, 0.1459, 0.3694, 0.1502),
        "iso view": Box(0.3136, 0.165, 0.3464, 0.215),
        "foot-hole callout": Box(0.1035, 0.1964, 0.1469, 0.2055),
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
    assert _segment_crossing(leaders["CrownDia"], leaders["BoreDia"]) is None
    # Neither leader meets the width or LugRise dimension lines or their
    # extension lines (r13: extension lines 1 mm off the outline).
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
    # The width stands under the foot, its text clear of the outline.
    assert blocks["Depth"].ymax <= bottom - _AIR
    # The bore's (7.0) reference stands above the crown, between the bore
    # axis and the sheet-right side face, clear of the crown block and leader.
    bore_side = _text_block(keep["BoreFromSide"], ["(7.0)"])
    assert bore_side.ymin >= bottom + spec.CROWN_TOP_Y * scale + _AIR
    assert cx < keep["BoreFromSide"][0] < cx + half
    assert _box_gap(bore_side, blocks["CrownDia"]) >= _AIR
    assert segment_box_distance(leaders["CrownDia"], bore_side) >= 0.003


def _value_block(xy, value, callout):
    """A dimension's value with its callout rows under it, the whole block
    centred on ``xy`` (farm run r1, 991a56e: the 3.000 block's middle row sat
    on its requested centre, the dimension line under its last row)."""
    from _layout_geometry import Box

    block = _text_block(xy, [value, *callout.splitlines()])
    return Box(
        block.xmin,
        block.ymin - _PLACEMENT_SLACK,
        block.xmax,
        block.ymax + _PLACEMENT_SLACK,
    )


def _tap_rows() -> list[str]:
    """The crown-tap callout as printed: native drill and thread rows (TO
    BORE, no class), then the place, stage and staking rows."""
    extent = drawing.SET_SCREW_EXTENT
    return [
        f"Ø 1.51 {extent}",
        f"1-72 UNF {extent}",
        *drawing.SET_SCREW_QUALIFIER.splitlines(),
    ]


def test_function_callouts_stand_clear_of_the_views_and_each_other() -> None:
    # The three-place sizes' function rows: 3.000 above the plan out to the
    # left (MR-fleet r1), 6.000 left of the seat over the notes, 7.000 under
    # its extension lines right of the plan; the supplied height's MIN left
    # of the lug (MR-fleet r3). None may touch a view, a neighbour, its own
    # extension lines, the supplied height's lines or the border.
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
        drawing.RIGHT_KEEP["CrownDia"],
        ["Ø14.0", *drawing.DIMENSION_CALLOUTS["CrownDia"].splitlines()],
    )
    notes_top = drawing.NOTES_TOP
    notes = Box(0.020, notes_top - 5 * _PITCH, 0.182, notes_top)
    overall_length = _text_block(drawing.FRONT_KEEP["OverallLength"], ["(16.5)"])
    foot_hole = Box(0.1035, 0.1964, 0.1469, 0.2055)  # r13 printed
    tap = _text_block(drawing.SET_SCREW_CALLOUT_XY, _tap_rows())
    keeps = {**drawing.FRONT_KEEP, **drawing.TOP_KEEP}
    callouts = {**drawing.FRONT_CALLOUTS, **drawing.TOP_CALLOUTS}
    values = {
        "SetScrewLocation": "3.000",
        "LugThickness": "6.000",
        "ScrewFromSide": "7.000",
        "SupplyHeight": "32.8 MIN",
    }
    blocks = {
        name: _value_block(keeps[name], value, callouts[name])
        for name, value in values.items()
    }
    neighbours = {
        "lug": lug,
        "foot": foot,
        "plan": plan,
        "crown block": crown_block,
        "notes": notes,
        "foot-hole callout": foot_hole,
        "tap callout": tap,
        "overall length": overall_length,
        "overall height": _text_block(drawing.FRONT_KEEP["OverallHeight"], ["(32.2)"]),
        "foot length": _text_block(drawing.FRONT_KEEP["FootLength"], ["10.5"]),
        "screw from tip": _text_block(drawing.TOP_KEEP["ScrewFromTip"], ["5.25"]),
        "corner radius": _text_block(drawing.FRONT_KEEP["CornerRadius"], ["R1.0 MAX"]),
    }
    for name, block in blocks.items():
        assert 0.0127 + _AIR <= block.xmin, name
        assert block.xmax <= 0.4318 - 0.0127 - _AIR, name
        assert block.ymax <= 0.2794 - 0.0127 - _AIR, name
        for other, box in {**neighbours, **blocks}.items():
            if other != name:
                assert _box_gap(block, box) >= _AIR, (name, other)
    # Each text stands outside its own extension lines: 3.000's left of the
    # plan's inner-face edge and over the plan (its line runs above the
    # outline), 6.000's left of the inner lug face, 7.000's below the screw
    # axis.
    assert blocks["SetScrewLocation"].xmax <= plan.xmin - _AIR
    assert blocks["SetScrewLocation"].ymin >= plan.ymax + 0.003
    assert blocks["LugThickness"].xmax <= lug.xmin - _AIR
    assert blocks["ScrewFromSide"].ymax <= cy - _AIR
    assert blocks["ScrewFromSide"].xmin >= plan.xmax + _AIR
    assert blocks["SupplyHeight"].xmax <= lug.xmin - 0.008
    # The supplied height's dimension line and its seat and blank-top
    # extension lines (1 mm overshoot) run from the lug out to its block; the
    # overall length's extension lines drop from the seat to its value.
    height_x = drawing.FRONT_KEEP["SupplyHeight"][0]
    supply_top = seat + spec.SUPPLY_HEIGHT_MIN * scale
    height_lines = (
        Segment(height_x - 0.001, lug.ymin, lug.xmin - 0.001, lug.ymin),
        Segment(height_x - 0.001, supply_top, lug.xmin - 0.001, supply_top),
    )
    for line in height_lines:
        for name in ("SetScrewLocation", "LugThickness"):
            assert segment_box_distance(line, blocks[name]) >= 0.003, (name, line)
        assert segment_box_distance(line, tap) >= 0.003, line
    # r4: SolidWorks drew the (16.5)'s line ~2.7 mm off its text, onto the
    # 6.000's arrows under that block's last row; either side, it stays clear
    # of the 6.000's line and of the notes.
    assert blocks["LugThickness"].ymin - (overall_length.ymax + 0.003) >= _AIR
    assert overall_length.ymin - 0.003 - notes_top >= _AIR
    length_y = drawing.FRONT_KEEP["OverallLength"][1]
    for x in (lug.xmin, foot.xmax):
        line = Segment(x, seat, x, length_y - 0.003)
        for name in ("LugThickness",):
            assert segment_box_distance(line, blocks[name]) >= 0.003, (name, line)
        assert segment_box_distance(line, notes) >= 0.003, line


def test_tap_callout_stands_inside_the_border_clear_of_the_plan() -> None:
    # Machinist review r13: the tap/staking block ran 5.70 mm past the left
    # inner border (x 12.7 mm). Reflowed to rows of at most 24 characters,
    # the whole block and its leader shoulder stand inside with air, clear of
    # the plan, of the 3.000 text and its function and of the foot-hole callout.
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
    set_screw_location = _value_block(
        drawing.TOP_KEEP[station], "3.000", drawing.TOP_CALLOUTS[station]
    )
    foot_hole = Box(0.1035, 0.1964, 0.1469, 0.2055)  # r13 printed
    for other in (plan, set_screw_location, foot_hole):
        assert _box_gap(block, other) >= _AIR, other
    bend = (block.xmax + _SHOULDER_RUN, block.ymin)
    leader = Segment(*bend, drawing.TAP_X_SHEET, cy - drawing.TAP_R_SHEET)
    foot_hole_leader = Segment(0.1035592, 0.1963903, 0.1146083, 0.224464)  # r13 printed
    assert _segment_crossing(leader, foot_hole_leader) is None
    assert point_segment_distance((foot_hole.xmin, foot_hole.ymin), leader) >= 0.003
    assert point_segment_distance((plan.xmin, plan.ymin), leader) >= 0.003


def test_the_auto_tapped_hole_note_is_removed() -> None:
    # Farm run r8: SolidWorks' own "#1-72 Tapped Hole" note restated the tap
    # callout's thread and its leader ran 4.07 mm through the SetScrewLocation
    # text (leader-through-text); finalize deletes exactly that one note.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=1" in source
    assert "tapped hole" not in ch_fulcrum_keeper_spec.DRAWING_NOTES.lower()


def test_notes_cover_the_tap_the_screw_and_the_quantity() -> None:
    notes = ch_fulcrum_keeper_spec.DRAWING_NOTES
    # The material is the title block's MATERIAL cell (rule 2; baseline
    # review: a material note restated it).
    assert "MATERIAL" not in notes and "1018" not in notes
    # The finish is the title block's Finish field; the note does not restate it.
    assert "BLACK OXIDE" not in notes.upper()
    # The pair ream is on the bore callout (KEEPERS_PAIR_REAMED_KEY), not a note.
    assert "REAM" not in notes
    assert "MHA-CH-004" in notes
    assert "MHA-VN-055" in notes
    assert "MHA-VN-022 #2-56 FILLISTER" in notes
    assert "2 REQUIRED" in notes
    assert len(notes.splitlines()) <= 6


def test_keeper_is_one_body_with_no_ball() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" not in source
    assert "Ball" not in source
    assert not hasattr(ch_fulcrum_keeper_spec, "BALL_DIA")


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "FootScrewHole" not in part.DRAWING_DIMENSIONS
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_parts_registry_row() -> None:
    config = _config.parts("ch-fulcrum-keeper")
    assert config["number"] == "MHA-CH-007"
    # The MATERIAL cell names the family (rule 2): a staked tap mouth wants a
    # ductile low-carbon steel; 1018 CF is an example, not a requirement.
    assert config["material"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    # Rule 2: the Finish field also protects the metal the pair-ream and the
    # crown tap after it leave bare after finishing (baseline review blocker,
    # MR-fleet r2).
    finish = str(config["finish"])
    assert "black oxide" in finish
    assert "oil the bore and crown and the crown tap" in finish
    assert int(config["quantity"]) == 2
