"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

import math
from pathlib import Path

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
    assert spec.BORE_PAIR_CALLOUT.startswith("PAIR-REAM WITH THE MATING MHA-CH-007")
    pair_ream = " ".join(spec.BORE_PAIR_CALLOUT.split())
    assert "AT INSTALLED SPACING; THE MHA-CH-004 SHAFT SLIDES THROUGH BOTH" in pair_ream


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
    assert spec.FOOT_TIP_WALL_MM >= 1.5
    assert spec.FOOT_SIDE_WALL_MM >= 1.5
    assert round(spec.SET_SCREW_WEB_MM, 3) == 1.813
    assert round(spec.FOOT_TIP_WALL_MM, 3) == 2.37
    assert round(spec.FOOT_SCREW_ENGAGEMENT_D, 2) == 1.79
    # The native counterbore callout prints the template's .XX; the engagement
    # and bottoming stacks take that printed depth (2.11), not 2.1082.
    assert spec.FOOT_COUNTERBORE_DEPTH_PLACES == 2
    # The web is only met with the lug and tap station at three places.
    assert spec.DRAWING_PRECISION["LugBody"]["LugThickness"] == 3
    assert spec.DRAWING_PRECISION["SetScrewReference"]["SetScrewLocation"] == 3
    # GPT review F4 / ruling (d): plain .XXX coordinate dims locate the foot
    # hole; the frame's transferred tap takes the side-station band.
    assert spec.DRAWING_PRECISION["FootScrewReference"]["ScrewFromLug"] == 3
    assert spec.DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"] == 3
    assert spec.KEEPER_SCREW_TRANSVERSE_BAND_MM == spec._BAND_BY_PLACES[3]


def test_tap_and_foot_hole_station_reference_sketches() -> None:
    spec = ch_fulcrum_keeper_spec
    assert part.REFERENCE_SKETCHES == spec.REFERENCE_SKETCHES
    assert [row[0] for row in part.REFERENCE_LINES] == [
        "SetScrewReference",
        "FootScrewReference",
        "FootScrewSideReference",
    ]
    rows = {row[0]: row for row in part.REFERENCE_LINES}
    _, plane, dimension, start, end, _, value, _ = rows["SetScrewReference"]
    assert (plane, dimension) == ("Front", "SetScrewLocation")
    # From the outer lug face to the tap axis, on the crown top.
    assert start == (spec.LUG_HALF_T, spec.CROWN_TOP_Y)
    assert end == (0.0, spec.CROWN_TOP_Y)
    assert value == spec.LUG_HALF_T
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewReference"]
    assert (plane, dimension) == ("Top", "ScrewFromLug")
    assert start == (spec.LUG_HALF_T, 0.0) and end == (spec.SCREW_X, 0.0)
    assert value == spec.SCREW_X - spec.LUG_HALF_T
    _, plane, dimension, start, end, _, value, _ = rows["FootScrewSideReference"]
    assert (plane, dimension) == ("Top", "ScrewFromSide")
    # One keeper part: the foot hole on the width centreline.
    assert start == (spec.SCREW_X, 0.0)
    assert end == (spec.SCREW_X, spec.KEEPER_WIDTH / 2.0)
    assert value == spec.KEEPER_WIDTH / 2.0


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
    assert "STAKE MOUTH 2 PLACES" in " ".join(drawing.SET_SCREW_PROCESS.split())
    assert steps.step_ref(steps.SET_SCREWS_STAKED_KEY) in drawing.SET_SCREW_PROCESS


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


def test_tap_callout_stands_inside_the_border_clear_of_the_plan() -> None:
    # Machinist review r13: the tap/staking block ran 5.70 mm past the left
    # inner border (x 12.7 mm). Reflowed to rows of at most 24 characters,
    # the whole block and its leader shoulder stand inside with air, clear of
    # the plan, of LugThickness's text and of the foot-hole callout.
    from _layout_audit import _segment_crossing
    from _layout_geometry import Box, Segment, point_segment_distance

    spec = ch_fulcrum_keeper_spec
    rows = ["Ø 1.51 THRU", *drawing.SET_SCREW_PROCESS.splitlines(), "1-72 UNF - 2B THRU"]
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
    lug_thickness_text = Box(0.0924, 0.1752, 0.1066, 0.1787)  # r13 printed
    foot_hole = Box(0.1035, 0.1964, 0.1469, 0.2055)  # r13 printed
    for other in (plan, lug_thickness_text, foot_hole):
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


def test_notes_cover_the_grade_the_tap_and_the_screw() -> None:
    notes = ch_fulcrum_keeper_spec.DRAWING_NOTES
    assert "AISI 1018" in notes
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
    assert config["material"] == "Plain Carbon Steel"
    assert "black oxide" in str(config["finish"])
    assert int(config["quantity"]) == 2
