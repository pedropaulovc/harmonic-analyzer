"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_sm_knife_mount as part
import draw_sm_knife_mount as drawing
import sm_knife_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_knife_seat_bore_finish_is_part_owned_and_consumed_by_key() -> None:
    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the knife SEAT carries MACHINED_UM (1.6); GROUND_UM (0.8)
    # is for the knife edge itself, which is the lever trunnion's ridge.  The
    # top seat, datum A, a static mating face, carries SEAT_UM (3.2;
    # 2026-10-10 ruling).
    control, top_seat = sm_knife_mount_spec.SURFACE_FINISHES
    assert control.key == "knife_bore"
    assert control.roughness_um == sm_knife_mount_spec.MACHINED_UM == 1.6
    assert control.face.diameter_mm == 2.0 * sm_knife_mount_spec.R_BORE
    assert top_seat.key == "top_seat"
    assert top_seat.roughness_um == sm_knife_mount_spec.SEAT_UM == 3.2
    assert top_seat.face.normal == (0.0, 1.0, 0.0)
    assert top_seat.face.offset_mm == sm_knife_mount_spec.BLK_TOP
    # The built top (14.866) is inside the face match.
    assert abs(part.BLK_TOP - top_seat.face.offset_mm) < top_seat.face.tolerance_mm
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "knife_bore")' in drawing_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "top_seat")' in drawing_source
    assert "roughness_ra=" not in drawing_source
    # The fleet's finish height (62 of 75 finish symbols print at 2.5 mm):
    # at the document default the Ra 1.6 printed 6.35 mm, twice the sheet's
    # 3.5 mm notes (farm run 20261009T171439353Z).
    import ast

    finishes = [
        call
        for call in ast.walk(ast.parse(drawing_source))
        if isinstance(call, ast.Call)
        and getattr(call.func, "id", "") == "add_surface_finish"
    ]
    keywords = [
        {
            keyword.arg: ast.literal_eval(keyword.value)
            for keyword in finish.keywords
            if keyword.arg in {"label", "char_height"}
        }
        for finish in finishes
    ]
    assert keywords == [
        {"label": "knife bore finish", "char_height": 0.0025},
        {"label": "top seat finish", "char_height": 0.0025},
    ]
    # The seat's symbol stands over the right view's top edge, its leader
    # landing on that edge.
    edge_x, edge_y = drawing.TOP_SEAT_FINISH_EDGE_XY
    symbol_x, symbol_y = drawing.TOP_SEAT_FINISH_XY
    assert edge_y == pytest.approx(drawing._front_y(sm_knife_mount_spec.BLK_TOP))
    assert abs(edge_x - drawing.RIGHT_CENTER[0]) < drawing.RIGHT_HALF_Z
    assert abs(symbol_x - drawing.RIGHT_CENTER[0]) < drawing.RIGHT_HALF_Z
    assert symbol_y > edge_y


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/sm-knife-mount.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/sm-knife-mount.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sm-knife-mount_drawing.png")
    assert DRAWINGS_BY_NAME["sm_knife_mount"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is sm_knife_mount_spec.DRAWING_DIMENSIONS
    marked = set().union(*sm_knife_mount_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.RIGHT_KEEP)
        | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # Every marked dimension carries part-authored places (the block's .X
    # overall size, the reamed bore's .XX band, the dowel hole's); the
    # pair's span, the block depth and the pattern's face locations are
    # sheet-added, their places the spec's.
    assert set(sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME) == {
        "BlockWidth",
        "BlockHeight",
        "BoreDia",
        "PinHoleDia",
        "PinHoleDepth",
    }
    assert sm_knife_mount_spec.DRAWING_REFERENCE_PRECISION == {
        "dowel hole span": 3,
        "dowel hole from tap axis": 3,
        "knife-bore centre from top seat": 3,
        "block-depth overall": 1,
        "dowel hole from side face": 2,
        "hole row from front face": 1,
    }
    for feature, names in sm_knife_mount_spec.DRAWING_PRECISION.items():
        assert set(names) <= sm_knife_mount_spec.DRAWING_DIMENSIONS[feature]


def test_dowel_hole_depth_is_dimensioned_on_the_section_not_a_hidden_edge() -> None:
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): the blind dowel hole's floor is a hidden edge in the
    # front view, so its depth rides section A-A, cut on z = 0 through the
    # tap axis (the origin) and both dowel axes, and only there.
    assert set(drawing.SECTION_KEEP) == {"PinHoleDepth"}
    assert "PinHoleDepth" not in drawing.FRONT_KEEP
    assert "PinHoleDepth" not in drawing.TOP_KEEP
    (start, end) = drawing.SECTION_LINE_MODEL_MM
    assert start[2] == end[2] == 0.0
    assert start[0] < -sm_knife_mount_spec.BLK_HALF_X
    assert end[0] > sm_knife_mount_spec.BLK_HALF_X
    assert start[0] < -sm_knife_mount_spec.PIN_HOLE_X < 0.0 < sm_knife_mount_spec.PIN_HOLE_X < end[0]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("create_section_view(") == 1
    assert "_look_section_along_minus_z(adapter, section)" in source
    assert "set_hidden_lines_removed(adapter, section)" in source
    # Section before top: the MHA-PD-018 import order.
    assert source.index("keep=SECTION_KEEP") < source.index("keep=TOP_KEEP")
    # The depth text stands right of the cut block, level with the hole.
    x, y = drawing.SECTION_KEEP["PinHoleDepth"]
    scale = drawing.SHEET_SCALE[0] / 1000.0
    assert x > drawing.SECTION_CENTER[0] + sm_knife_mount_spec.BLK_HALF_X * scale
    top_y = drawing._section_y(sm_knife_mount_spec.BLK_TOP)
    floor_y = drawing._section_y(
        sm_knife_mount_spec.BLK_TOP - sm_knife_mount_spec.PIN_HOLE_DEPTH
    )
    assert floor_y < y < top_y


def test_dowel_callout_is_parked_clear_of_the_top_view() -> None:
    # drawing-guidelines.md rule 14 (keep text off the part) (dda9a33a8 render): the three callout lines ran through both
    # holes and the leader shoulder crossed the view.  The block now hangs
    # wholly right of the block's +X face, and the shoulder's near end stands
    # below the hole centre so the leader climbs to the hole rim.
    x, y = drawing.TOP_KEEP["PinHoleDia"]
    face_x = drawing._sheet_x(sm_knife_mount_spec.BLK_HALF_X)
    shoulder_x, shoulder_y = drawing.PIN_CALLOUT_SHOULDER_START
    assert shoulder_x > face_x
    shoulder_start_x = (
        x - drawing.PIN_CALLOUT_HALF_WIDTH - drawing.PIN_CALLOUT_SHOULDER_OVERHANG
    )
    assert shoulder_start_x == pytest.approx(shoulder_x)
    assert y - drawing.PIN_CALLOUT_SHOULDER_DROP == pytest.approx(shoulder_y)
    assert shoulder_y < drawing.TOP_CENTER[1]
    # Right edge clear of the right view's column and on the sheet.
    right_edge = x + drawing.PIN_CALLOUT_HALF_WIDTH
    assert right_edge < drawing.ISO_CENTER[0] - 0.050
    # Above the right view's box (front row, 2:1 block height).
    assert shoulder_y > drawing.RIGHT_CENTER[1] + drawing.RIGHT_HALF_Y + 0.040


def test_the_tap_is_stated_once_on_its_hole_callout() -> None:
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the tap rides one native Hole Wizard callout (thread, full
    # thread depth, drill and drill depth stay associative); SolidWorks' raw
    # "#10-24 Tapped Hole" note would restate it, so it is deleted and
    # finalize proves none is left at export.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 1
    assert "process=TAP_CALLOUT_PROCESS" in source
    assert drawing.TAP_CALLOUT_PROCESS is sm_knife_mount_spec.TAP_CALLOUT_PROCESS
    assert drawing.TAP_CALLOUT_PROCESS == "BOTTOMING TAP FOR MHA-VN-024\n"
    assert drawing.TAPPED_HOLE_NOTE == "Tapped Hole"
    assert "remove_notes_matching(adapter, TAPPED_HOLE_NOTE)" in source
    assert "redundant_note_substrings=(TAPPED_HOLE_NOTE,)" in source
    assert "expected_redundant_notes=0" in source
    assert source.index("remove_notes_matching(adapter, TAPPED_HOLE_NOTE)") > (
        source.index("keep=TOP_KEEP")
    )


# The ASME B landscape sheet's inner border, left edge.
SHEET_INNER_BORDER_LEFT = 0.0127


# Farm build 20261013T225639.450330Z (c673e62ee, re-run at e5ad7dcdd): the
# five-row block at anchor (58.6, 209.0) mm printed x 20.0..97.1 with its top
# ('+0.10') row 213.8..217.4, and the 7.0's (RD4's) outside tail ran
# (77.6, 221.0)->(77.6, 214.7) through that row.
RUN_CALLOUT_XY = (0.0586, 0.2090)
RUN_CALLOUT_SPAN_X = (0.0200, 0.0971)
RUN_CALLOUT_TOP = 0.2174
RUN_RD4_TAIL = ((0.0776, 0.2210), (0.0776, 0.2147))


def test_tap_callout_moves_clear_of_the_row_dimension_tail() -> None:
    # drawing-guidelines.md rule 14 (keep text off the part): the three rows
    # stand inside the five-row run's envelope, moved down with the anchor,
    # whichever way SolidWorks restacks them, so their top clears RD4's tail by
    # more than the gating arrow-to-text clearance.
    from _layout_audit import ARROW_TAIL_M
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M

    x, y = drawing.TAP_CALLOUT_XY
    assert x == pytest.approx(RUN_CALLOUT_XY[0])
    assert RUN_CALLOUT_XY[1] + drawing.TAP_CALLOUT_TOP_REACH == pytest.approx(
        RUN_CALLOUT_TOP
    )
    # The run's tail, from the drawing's own placement: the 7.0's line at its
    # text's x, its outside tail one ARROW_TAIL_M under the view's lower edge.
    top_view_bottom = drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    tail_x = drawing.ROW_FACE_TEXT_XY[0]
    tail_end = top_view_bottom - ARROW_TAIL_M
    assert (tail_x, top_view_bottom) == pytest.approx(RUN_RD4_TAIL[0], abs=1e-4)
    assert (tail_x, tail_end) == pytest.approx(RUN_RD4_TAIL[1], abs=1e-4)
    # The run's top row ran across the tail; the three rows' top stays 1 mm
    # more than the gating clearance under its end, the block spanning it.
    assert RUN_CALLOUT_SPAN_X[0] < tail_x < RUN_CALLOUT_SPAN_X[1]
    assert RUN_CALLOUT_TOP > tail_end
    top = y + drawing.TAP_CALLOUT_TOP_REACH
    assert top == pytest.approx(0.2114)
    assert top <= tail_end - ARROW_TEXT_CLEARANCE_M - 0.001
    # The frame moves with the anchor, so it stands where the run printed it
    # under the block (no finding between them; its top at 209.0 - 8.6 - 7.0
    # = 193.4 mm), the block a row shorter.
    assert RUN_CALLOUT_XY[1] - drawing.TAP_FRAME_DROP == pytest.approx(0.1934)
    assert drawing.TAP_FRAME_XY[1] == pytest.approx(y - drawing.TAP_FRAME_DROP)


def test_tap_callout_prints_three_rows_with_its_bands_and_drill_point() -> None:
    # Tall-block (the 4-row limit): the c673e62ee seat's definitions, the
    # pilot's stacked upper deviation a row of its own, printed five rows with
    # the mate below the thread.  Now the mate rides the process, the pilot
    # takes the title block's DRILLED HOLES row (no band, no stacked row) and
    # the thread prints no class (the title block's thread row): three.  The
    # symmetric bands, the drill point and the thread's native depth stay.
    from _layout_audit import TEXT_ROW_LIMIT

    drill_row = "<MOD-DIAM> <hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>"
    thread_row = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"
    seat = {5: f"{drawing.TAP_CALLOUT_PROCESS}{thread_row}", 6: "", 7: drill_row, 8: ""}
    # A bilateral band stacks its deviations a row of their own.
    stacked_band_rows = sum(
        1
        for _, band in drawing.TAP_CALLOUT_BANDS.values()
        if band is not None
        and drawing.tap_callout_tolerance(band)[0] != drawing._TOL_SYMMETRIC
    )

    def printed_rows(definitions: dict[int, str], stacked: int) -> int:
        lines = [
            line
            for part in (7, 5, 6, 8)
            for line in definitions[part].splitlines()
            if line.strip()
        ]
        return stacked + len(lines)

    run = {
        **seat,
        5: f"BOTTOMING TAP - FULL THREAD\n{thread_row}",
        7: f"{drill_row} X <hw-drlang>",
        8: "FOR MHA-VN-024 HEX BOLT",
    }
    assert printed_rows(run, 1) == TEXT_ROW_LIMIT + 1
    assert stacked_band_rows == 0
    wanted = drawing.tap_callout_definitions(seat)
    assert printed_rows(wanted, stacked_band_rows) == 3 <= TEXT_ROW_LIMIT
    assert wanted[7] == f"{drill_row} X <hw-drlang>"
    assert wanted[5] == (
        f"{drawing.TAP_CALLOUT_PROCESS}<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
    )
    assert "threadclass" not in "".join(wanted.values())
    assert wanted[8] == ""
    assert drawing.TAP_CALLOUT_BANDS["hw-tapdrldia"] == (
        sm_knife_mount_spec.STUD_TAP_DIA,
        None,
    )
    assert drawing.TAP_CALLOUT_BANDS["hw-tapdrldepth"][1] == (
        sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH_BAND,
        -sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH_BAND,
    )
    assert drawing.TAP_CALLOUT_BANDS["hw-threaddepth"] == (
        sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH,
        (
            sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_BAND,
            -sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_BAND,
        ),
    )


def test_tap_callout_parks_between_the_top_view_and_the_front_view() -> None:
    # drawing-guidelines.md rule 14 (keep text off the part): the three rows
    # stand in the band under the top view, left of the front view's datum-A
    # tag, their frame under them and over the front view.
    x, y = drawing.TAP_CALLOUT_XY
    top_view_bottom = drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    assert y + drawing.TAP_CALLOUT_TOP_REACH < top_view_bottom
    assert x + drawing.TAP_CALLOUT_HALF_WIDTH < drawing.FRONT_CENTER[0] - 0.0035 - 0.005
    # The frame (7 mm tall) stays over the 29.6 height line's upper witness
    # line (y at the block top), not beside it.
    frame_bottom = drawing.TAP_FRAME_XY[1] - 0.007
    assert frame_bottom > drawing._front_y(sm_knife_mount_spec.BLK_TOP) + 0.010
    # Rule 13: the block stays inside the inner border.
    assert x - drawing.TAP_CALLOUT_HALF_WIDTH > SHEET_INNER_BORDER_LEFT + 0.001
    # The widest row is now the process, "BOTTOMING TAP FOR MHA-VN-024":
    # 16.58 em of Century Gothic at the 4.83 mm an em the run's drill row gave
    # (15.97 em printed 77.1 mm), ~80 mm, inside the half width's 88.
    run_width = RUN_CALLOUT_SPAN_X[1] - RUN_CALLOUT_SPAN_X[0]
    assert run_width == pytest.approx(0.0771)
    process_width = 16.58 * run_width / 15.97
    assert process_width == pytest.approx(0.0801, abs=1e-4)
    assert 2.0 * drawing.TAP_CALLOUT_HALF_WIDTH >= process_width + 0.005


def test_tap_frame_leader_lands_clear_of_the_tap_callout_leader() -> None:
    # Farm run 20261009T164113078Z: both leaders landed on the tap's
    # lower-left rim and the frame's, climbing from the frame's right end,
    # crossed the callout's 2 mm short of the tip (leader-crosses-leader,
    # enforced in report mode).  The leader ends below are that run's
    # printed ones (the 25-wide block, the #6-32 tap's Ø2.705 drill); the
    # frame now lands on the lower-right rim instead.
    from _layout_audit import TEXT_CLEARANCE_HEIGHTS, _segment_crossing
    from _layout_geometry import Segment

    callout_shoulder_end, run_callout_tip = (0.0947, 0.1986), (0.1137, 0.2326)
    frame_end, old_frame_tip = (0.1103, 0.1900), (0.1130, 0.2332)
    callout = Segment(*callout_shoulder_end, *run_callout_tip)
    assert _segment_crossing(callout, Segment(*frame_end, *old_frame_tip)) is not None

    def lower_rim(x_side: float, tap_drill_dia: float) -> tuple[float, float]:
        rim = tap_drill_dia / 2.0 / 2.0**0.5 * drawing.SHEET_SCALE[0] / 1000.0
        return (drawing._sheet_x(0.0) + x_side * rim, drawing.TOP_CENTER[1] - rim)

    run_tap_drill_dia, run_blk_half_x = 2.705, 12.5
    run_rim = lower_rim(drawing.TAP_CALLOUT_RIM_SIDE, run_tap_drill_dia)
    assert math.dist(run_rim, run_callout_tip) < 0.001
    assert drawing.TAP_FRAME_RIM_SIDE == -drawing.TAP_CALLOUT_RIM_SIDE
    # That run's frame stood at (face - 0.022, 0.1935): its leader left its
    # right end, 3.5 mm under its top.  The frame keeps that shape wherever
    # TAP_FRAME_XY puts it; the tips land on the #10-24 drill's lower rims.
    run_frame_xy = (drawing._sheet_x(-run_blk_half_x) - 0.022, 0.1935)
    frame_root = (
        drawing.TAP_FRAME_XY[0] + frame_end[0] - run_frame_xy[0],
        drawing.TAP_FRAME_XY[1] + frame_end[1] - run_frame_xy[1],
    )
    frame_tip = lower_rim(drawing.TAP_FRAME_RIM_SIDE, drawing.STUD_TAP_DIA)
    frame = Segment(*frame_root, *frame_tip)
    callout_tip = lower_rim(drawing.TAP_CALLOUT_RIM_SIDE, drawing.STUD_TAP_DIA)
    # The callout's leader leaves its block's right end, under its last row:
    # at most the half width right of the anchor, anywhere from a text
    # clearance over the frame's top up to the anchor.
    callout_right = drawing.TAP_CALLOUT_XY[0] + drawing.TAP_CALLOUT_HALF_WIDTH
    lowest = drawing.TAP_FRAME_XY[1] + TEXT_CLEARANCE_HEIGHTS * 0.0035
    for root_y in (lowest, drawing.TAP_CALLOUT_XY[1]):
        callout = Segment(callout_right, root_y, *callout_tip)
        assert _segment_crossing(callout, frame) is None
        # The callout's root stays left of the frame's.
        assert callout.x0 < frame.x0
    # The frame's leader passes left of the datum-A tag's 7 mm box (x
    # 111.5..118.5, top 195.1 mm) over the front view's top seat.
    tag_left = drawing.FRONT_CENTER[0] - 0.0035
    tag_top = drawing._front_y(sm_knife_mount_spec.BLK_TOP) + 0.018 + 0.0075
    assert frame_root[1] < tag_top < frame_tip[1]
    x_at_tag_top = frame_root[0] + (frame_tip[0] - frame_root[0]) * (
        (tag_top - frame_root[1]) / (frame_tip[1] - frame_root[1])
    )
    assert x_at_tag_top < tag_left - 0.001
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "tap_rim = _tap_lower_rim(adapter, top, TAP_CALLOUT_RIM_SIDE)" in source
    assert "edge_xy=_tap_lower_rim(adapter, top, TAP_FRAME_RIM_SIDE)" in source


def test_dowel_frame_leader_lands_apart_from_the_dowel_diameter_leader() -> None:
    # Blind machinist review R3 (farm run 20261014T010316127Z): the 2X Ø's
    # arrowhead and datum B's frame's landed on the +X hole's lower-right rim
    # 0.10 mm apart, so the two leaders read as one.  The points below are
    # that run's printed ones (sheet metres); the frame's elbow stands
    # 6.35 mm left of its left end, at its middle height.
    from _layout_audit import _segment_crossing
    from _layout_geometry import Segment

    run_dia_tip, run_dia_shoulder = (0.13275, 0.23301), (0.14640, 0.22221)
    run_frame_tip, run_frame_elbow = (0.13268, 0.23294), (0.14164, 0.21548)
    assert math.dist(run_dia_tip, run_frame_tip) < 0.0002
    frame_left, frame_top = drawing.PIN_FRAME_XY
    elbow = (frame_left - 0.00635, frame_top - drawing.PIN_FRAME_SIZE[1] / 2.0)
    assert math.dist(elbow, run_frame_elbow) < 0.0003
    centre = (drawing._sheet_x(sm_knife_mount_spec.PIN_HOLE_X), drawing.TOP_CENTER[1])
    rim = sm_knife_mount_spec.PIN_HOLE_DIA / 2.0 * drawing.SHEET_SCALE[0] / 1000.0
    assert math.dist(centre, run_dia_tip) == pytest.approx(rim, abs=0.0002)
    angle = math.radians(drawing.PIN_FRAME_RIM_DEG)
    tip = (centre[0] + rim * math.cos(angle), centre[1] + rim * math.sin(angle))
    # Its own point: an arrowhead's width and more round the rim from the
    # Ø's, below the cutting line, right of the centre mark's vertical arm.
    assert math.dist(tip, run_dia_tip) >= 0.0015
    assert tip[1] < centre[1]
    assert tip[0] - centre[0] >= 0.0006
    # The frame's leader stays under the Ø's, crossing neither it nor the
    # centre mark's vertical arm (x = centre, down to 226.83 mm).
    frame = Segment(*elbow, *tip)
    assert _segment_crossing(Segment(*run_dia_tip, *run_dia_shoulder), frame) is None
    assert min(frame.x0, frame.x1) > centre[0]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("    pin_frame_angle = math.radians(PIN_FRAME_RIM_DEG)") :]
    body = body[: body.index("    add_frame_datum_feature(")]
    assert "        edge_xy=pin_frame_rim,\n        leader_attach_xy=pin_frame_rim,\n" in body


def test_bore_callout_stands_between_the_height_line_and_the_block() -> None:
    # 5ff8fba5d render: the 29.6 dimension line ran 3.62 mm through the
    # Ø12.00 THRU text, and the Ø line crossed the bore and the view to a
    # shoulder left of it.  The text now sits in the band between the height
    # line and the block's -X face, at least 5 mm clear of each, and the Ø
    # is drawn as one arrow on the near rim.
    height_x, _ = drawing.FRONT_KEEP["BlockHeight"]
    x, y = drawing.FRONT_KEEP["BoreDia"]
    face_x = drawing._sheet_x(-sm_knife_mount_spec.BLK_HALF_X)
    assert x - drawing.BORE_DIA_TEXT_HALF_WIDTH > height_x + 0.005
    assert x + drawing.BORE_DIA_TEXT_HALF_WIDTH < face_x - 0.005
    # Above the bore centre, so the leader descends to the upper-left rim.
    assert y > drawing._front_y(sm_knife_mount_spec.BORE_CY)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(bore_dia[0], "knife-bore diameter")' in source


def test_the_template_alone_centre_marks_the_bore() -> None:
    # #913 on this sheet: the template marks the bore as the front view is
    # placed, and an explicit auto-insert printed a second mark over it.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" not in source
    assert "expected one knife-bore centre mark" in source


def test_spec_geometry_mirrors_the_build_source() -> None:
    # The drawing's view math reads the spec's mirrored nominals for placement
    # only (the marks carry the exact values); assert they track the build's
    # actual (assembly-derived) geometry to <0.05 mm so they cannot drift.
    assert sm_knife_mount_spec.R_BORE == part.R_BORE
    assert sm_knife_mount_spec.SUPPORT_Z_THICK == part.SUPPORT_Z_THICK
    # The block's width is the spec's alone: the build imports it.
    assert sm_knife_mount_spec.BLK_HALF_X == part.BLK_HALF_X == 12.7
    assert abs(sm_knife_mount_spec.BLK_TOP - part.BLK_TOP) < 0.005
    assert abs(sm_knife_mount_spec.BLK_BOT - part.BLK_BOT) < 0.05
    assert abs(sm_knife_mount_spec.BORE_CY - part.BORE_CY) < 0.05
    # The seat is clamped to the casting underside by the #10-24 bolt.
    assert part.MOUNT_GAP == 0.0
    assert abs(part.BLK_TOP - 14.866) < 1e-3
    assert sm_knife_mount_spec.BLK_TOP == 14.87
    # The build owns no tap constants: they are the spec's (consumers import
    # them there).
    assert not hasattr(part, "STUD_TAP_DEPTH")
    assert part.STUD_TAP_SPEC is sm_knife_mount_spec.STUD_TAP_SPEC
    assert part.STUD_TAP_DIA == sm_knife_mount_spec.STUD_TAP_DIA
    # Dowel holes: one each side of the tap at +/-7.632 (the printed BASIC
    # span 15.264), printed places and the volume the build's gate expects.
    assert sm_knife_mount_spec.PIN_HOLE_X == 7.632
    assert sm_knife_mount_spec.PIN_HOLE_XS == (-7.632, 7.632)
    assert sm_knife_mount_spec.PIN_HOLE_SPAN == 15.264
    assert sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME == {
        "BlockWidth": 1,
        "BlockHeight": 1,
        "BoreDia": 2,
        "PinHoleDia": 3,
        "PinHoleDepth": 1,
    }
    import math

    assert abs(part.V_PIN - math.pi * (3.175 / 2.0) ** 2 * 9.5) < 1e-9
    assert part.V_PINS == 2 * part.V_PIN
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH)" in source
    assert "\nBLK_HALF_X = " not in source
    assert "    BLK_HALF_X,\n" in source
    assert 'for pin_dia_name in ("PinHoleDia", "PinHole2Dia"):' in source
    # The band prints at the nominal's places, +0.000/-0.010 under Ø3.175,
    # not "0.00 / -0.01" (farm run 20261009T171439353Z).
    assert (
        '            "PinHoleProfile",\n'
        "            pin_dia_name,\n"
        "            *deviations(PIN_HOLE_DIA_BAND),\n"
        "            places=PIN_HOLE_DIA_PLACES,\n"
    ) in source
    assert (
        sm_knife_mount_spec.PIN_HOLE_DIA_PLACES
        == sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME["PinHoleDia"]
        == 3
    )
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_the_sheet_carries_no_notes_block() -> None:
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): every fact the notes held now rides a callout or a field --
    # the bore's location its BASICs and position frame, the tap its hole
    # callout, the heat treatment the Finish field -- and the design-intent
    # prose (knife-edge bearing, screw clamp, two blocks) is gone.
    assert not hasattr(sm_knife_mount_spec, "DRAWING_NOTES")
    assert not hasattr(sm_knife_mount_spec, "STUD_SCREW_NUMBER")
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in part_source
    assert "Manufacturing Notes" not in drawing_source
    assert drawing_source.count("add_property_linked_note(") == 1
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in drawing_source
    # The dowel holes' count rides above their Ø and the press below it
    # (MHA-PD-018 precedent); their position frame hangs under the callout.
    assert drawing.CALLOUTS_ABOVE == {"PinHoleDia": "2X"}
    assert sm_knife_mount_spec.PIN_HOLE_CALLOUT.splitlines() == [
        "BLIND FLAT-BOTTOM REAM",
        "PRESS MHA-VN-051 DOWEL TO FLOOR",
        "0.0025/0.0177 INTERFERENCE",
    ]


def test_datum_b_hangs_under_its_frame_clear_of_the_bore_frame() -> None:
    # The B symbol's box (its bottom middle at PIN_DATUM_B_XY) sits under the
    # dowel-pattern frame's printed box, within its width, with stem room to
    # it and clear of the bore frame's top (DetailItem355, 188.62 mm) below.
    frame_left, frame_top = drawing.PIN_FRAME_XY
    frame_w, frame_h = drawing.PIN_FRAME_SIZE
    box = drawing.DATUM_TAG_BOX
    x, y = drawing.PIN_DATUM_B_XY
    assert frame_left + box / 2 <= x <= frame_left + frame_w - box / 2
    assert (frame_top - frame_h) - (y + box) >= 0.004
    assert y - drawing.BORE_FRAME_XY[1] >= 0.004


def test_native_gdt_and_bore_geometry() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Datum A the top seat (a tag on its edge); datum B the dowel pair, its
    # symbol on the pair's position frame: a tag on the 2X Ø attaches to
    # nothing (farm run 20261009T155421516Z, count=0), and the frame's datum
    # identifier read "B" back but printed nothing (20261009T171439353Z).
    assert source.count("add_datum_feature(") == 1
    assert "add_dimension_datum_feature" not in source
    assert "datum_identifier" not in source
    assert source.count("add_frame_datum_feature(") == 1
    frame_datum = source[source.index("pin_frame = add_feature_control_frame(") :]
    frame_datum = frame_datum[: frame_datum.index("# The bore:")]
    assert "        pin_frame,\n        datum=\"B\",\n" in frame_datum
    assert 'datum="A"' in source
    # The sheet fails unless every frame's datum is printed, over every view
    # a frame or tag stands in.
    assert (
        "assert_frame_datums_defined(\n        (front, right, top, section),"
    ) in source
    assert source.index("assert_frame_datums_defined(") > source.index(
        "add_frame_datum_feature("
    )
    # The pair's frame to A, the bore's and the tap's frames to A|B; under
    # the bore's position, a stacked (not composite) ⊥Ø0.05 to B
    # (2026-10-10 ruling: one Ø zone bounds the yaw the rock budget takes).
    assert source.count("add_feature_control_frame(") == 3
    assert source.count('characteristic="position"') == 3
    assert source.count('datums=("A",)') == 1
    assert source.count('datums=("A", "B")') == 2
    assert "composite_lower" not in source
    bore_frame = source[source.index("# The bore: Ø0.20 located to A|B") :]
    bore_frame = bore_frame[: bore_frame.index("bore_basic = ")]
    assert (
        "        lower_frame=(\n"
        '            "perpendicularity",\n'
        '            GEOMETRIC_TOLERANCES_MM["knife-bore perpendicularity"],\n'
        '            ("B",),\n'
        "        ),\n"
    ) in bore_frame
    assert 'GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"]' in source
    assert sm_knife_mount_spec.GEOMETRIC_TOLERANCES_MM == {
        "knife-bore position": "0.20",
        "knife-bore perpendicularity": "0.05",
        "knife-hanger tap position": "0.10",
        "dowel hole pattern position": "0.13",
    }
    assert sm_knife_mount_spec.KNIFE_BORE_ORIENTATION_TOL == 0.05
    # Sheet-added: the block depth, the dowel span, the tap axis's station
    # from a dowel axis and the bore centre's height under A (all BASIC), and
    # the pattern's two face locations; the
    # dowel holes' Ø and depth are marked model dimensions
    # (DRAWING_DIMENSIONS).
    assert source.count("add_edge_dimension(") == 6
    assert source.count("set_basic_dimension(") == 3
    assert 'set_basic_dimension(adapter, span, label="dowel hole span")' in source
    assert (
        'set_basic_dimension(adapter, station, label="dowel hole from tap axis")'
        in source
    )


@pytest.mark.parametrize(
    ("label", "basic"),
    (
        ("knife-bore centre from top seat", part.BORE_CENTRE_DEPTH),
        ("dowel hole span", sm_knife_mount_spec.PIN_HOLE_SPAN),
        ("dowel hole from tap axis", sm_knife_mount_spec.PIN_HOLE_X),
    ),
)
def test_each_basic_prints_the_modelled_value_unrounded(label: str, basic: float) -> None:
    # A BASIC is exact: the sheet measures it off the model (1e-5 gate) and
    # its places must print that value, not a rounding of it.  48ad988c6
    # checked the bore height against the spec's 14.87 mirror (20.62) at
    # .XX; the model measures 14.866 + 5.75 = 20.616, and the leaf failed.
    places = sm_knife_mount_spec.DRAWING_REFERENCE_PRECISION[label]
    assert abs(round(basic, places) - basic) < 1e-9
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from build_sm_knife_mount import BORE_CENTRE_DEPTH" in source
    assert not hasattr(sm_knife_mount_spec, "BORE_CENTRE_DEPTH")


def test_bore_basic_is_the_built_geometry() -> None:
    assert part.BORE_CENTRE_DEPTH == part.BLK_TOP - part.BORE_CY
    assert part.BORE_CENTRE_DEPTH == pytest.approx(20.616, abs=1e-9)
    assert f"{part.BORE_CENTRE_DEPTH:.3f}" == "20.616"
    # The spec's mirror would print a BASIC 0.004 off the part.
    mirror = sm_knife_mount_spec.BLK_TOP - sm_knife_mount_spec.BORE_CY
    assert abs(mirror - part.BORE_CENTRE_DEPTH) > 1e-5


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("sm-knife-mount")
    # ch18 p.42 (2026-09-02): unpainted heat-treated steel, not brass.
    assert part.MATERIAL == "Plain Carbon Steel"
    assert config["material"] == "Plain Carbon Steel"
    assert config["material_specification"] == "AISI O1 tool steel"
    # drawing-guidelines.md rule 2 (the title block is the general specification): the heat treatment and the bare surface are the Finish field's,
    # stated once there (the sheet has no notes block).
    assert config["finish"] == "hardened and tempered 58-60 HRC, unpainted"
    assert "Brass" not in config["material_specification"]
    assert int(config["quantity"]) == 2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_color(adapter, HARDENED_STEEL)" in source
    assert part.HARDENED_STEEL == (0.30, 0.30, 0.31)


def test_close_bore_clears_the_hex_trunnion_only_at_the_ridge() -> None:
    import math

    from sm_summing_lever_spec import HEX_H, HEX_W

    assert part.R_BORE == 6.0
    assert abs(part.BLK_BOT - (-14.75)) < 1e-9
    assert abs(part.BORE_CY - (-5.75)) < 1e-9
    # Top vertex hangs TOP_CLEAR under the crown; the across-corners bottom
    # vertex and the two widest shoulders clear the bore wall.
    hex_centre_y = -HEX_H / 2.0
    assert abs((part.BORE_CY + part.R_BORE) - part.TOP_CLEAR) < 1e-9
    bottom_clear = part.R_BORE - abs(hex_centre_y - HEX_H / 2.0 - part.BORE_CY)
    assert bottom_clear > 0.5
    for sy in (hex_centre_y + HEX_H / 4.0, hex_centre_y - HEX_H / 4.0):
        d = math.hypot(HEX_W / 2.0, sy - part.BORE_CY)
        assert d < part.R_BORE - 0.5


def test_tap_callout_bands_its_full_thread_and_drill_depth_with_a_pitch_of_runout() -> None:
    # Machinist review B2: the bottoming tap needs drill past the full
    # thread.  The #10-24 full thread prints 9.65 with its own native +/-0.13
    # (R3: no third place; bare, the .XX row's +/-0.51 would give a 9.14
    # shallowest thread under the bolt's 9.4856 reach) and its shallowest
    # 9.52 still holds 1.5 D; the drill runs 1.5 pitch past it nominally and
    # carries the explicit +/-0.05 the 2.0 crown web leaves, 11.24, on the
    # native callout (the summing-lever bracket-tap precedent), still one
    # 1.058 pitch past the deepest thread at worst.  Rule 3: the #25 pilot
    # carries no band of its own, so the DRILLED HOLES row governs it (R3:
    # its native +0.10/0 restated that row).
    assert drawing.TAP_CALLOUT_BANDS == {
        "hw-tapdrldia": (3.797, None),
        "hw-threaddepth": (9.65, (0.13, -0.13)),
        "hw-tapdrldepth": (11.24, (0.05, -0.05)),
    }
    assert drawing.TAP_CALLOUT_BAND_PLACES == 2
    # swTolType_e: both bands symmetric (4), each (lower, upper) as
    # SolidWorks takes it; a one-sided band would write bilateral (2).
    assert drawing.tap_callout_tolerance((0.13, -0.13)) == (4, -0.13, 0.13)
    assert drawing.tap_callout_tolerance((0.05, -0.05)) == (4, -0.05, 0.05)
    assert drawing.tap_callout_tolerance((0.10, 0.0)) == (2, 0.0, 0.10)
    assert drawing.TAP_CALLOUT_PLACES == {
        "hw-tapdrldia": 3,
        "hw-threaddepth": 2,
        "hw-tapdrldepth": 2,
    }
    from build_sm_summing_assembly import HANGER_REACH_MAX

    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_MIN > HANGER_REACH_MAX
    assert (
        sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH - sm_knife_mount_spec._XX
        < HANGER_REACH_MAX
    )
    assert sm_knife_mount_spec.STUD_THREAD == "#10-24"
    assert sm_knife_mount_spec.STUD_TAP_DIA == pytest.approx(3.797)
    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_BAND == pytest.approx(0.13)
    pitch = sm_knife_mount_spec.STUD_PITCH
    assert pitch == pytest.approx(25.4 / 24.0)
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT == pytest.approx(1.59)
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT >= 1.5 * pitch
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT_MIN == pytest.approx(1.41)
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT_MIN >= pitch
    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.52)
    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_MIN >= (
        1.5 * sm_knife_mount_spec.STUD_THREAD_MAJOR
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "tap_callout = add_native_hole_callout(" in source
    assert (
        "    _write_tap_callout_definitions(adapter, tap_callout)\n"
        "    _band_tap_callout(tap_callout)\n"
    ) in source
    assert "        TAP_CALLOUT_PLACES,\n" in source
    body = source[source.index("def _band_tap_callout(") :]
    body = body[: body.index("\ndef ")]
    assert "kind, lower, upper = tap_callout_tolerance(band)" in body
    assert "variable.ToleranceType = kind" in body
    assert "variable.ToleranceMin = lower / 1000.0" in body
    assert "variable.ToleranceMax = upper / 1000.0" in body
    assert "length.TolerancePrecision = TAP_CALLOUT_BAND_PLACES" in body
    assert "variable.ToleranceType = _TOL_NONE" in body
    assert "if required:" in body
    assert "_prove_tap_point(points[0])" in body


def test_tap_crown_web_charges_a_pilot_wider_than_accepted_at_its_sharpest_point() -> None:
    # The pilot, under the title block's DRILLED HOLES row, accepts
    # Ø3.797-3.897.  The crown web charges more, Ø3.927 (the printed Ø3.797
    # plus the larger of that row and the general .XXX): a conservative
    # envelope, charged, not accepted.
    # The point, dimensioned 118° on the callout, takes the title block's
    # angular +/-1: its sharpest, 117°, stands tallest.
    from _printed_tolerance import angular_band_deg, drilled_oversize_mm

    spec = sm_knife_mount_spec
    assert spec.STUD_TAP_DIA_PLACES == 3
    assert drilled_oversize_mm() == pytest.approx(0.10)
    assert spec.STUD_TAP_DIA_BAND == (drilled_oversize_mm(), 0.0)
    assert spec.STUD_TAP_DIA_ACCEPTED == pytest.approx((3.797, 3.897))
    assert spec.STUD_TAP_DIA_MAX == pytest.approx(3.927)
    assert spec.STUD_TAP_DIA_MAX - max(spec.STUD_TAP_DIA_ACCEPTED) == pytest.approx(0.03)
    assert spec.STUD_TAP_DIA_OVERSIZE == pytest.approx(0.13)
    assert angular_band_deg() == pytest.approx(1.0)
    assert spec.STUD_TAP_POINT_ANGLE_DEG == 118.0
    assert spec.STUD_TAP_POINT_ANGLE_PLACES == 0
    assert spec.STUD_TAP_POINT_ANGLE_TOL_DEG == angular_band_deg()
    assert spec.STUD_TAP_POINT_ANGLE_MIN_DEG == pytest.approx(117.0)
    assert spec.STUD_TAP_POINT_H == pytest.approx(
        3.927 / 2.0 / math.tan(math.radians(117.0 / 2.0))
    )
    assert spec.STUD_TAP_POINT_H == pytest.approx(1.2032343475, abs=1e-9)
    assert spec.STUD_TAP_DRILL_DEPTH_MAX == pytest.approx(11.29)
    assert spec.STUD_TAP_WEB_WORST == pytest.approx(2.0117656525, abs=1e-9)
    assert part._TAP_WEB_WORST == pytest.approx(2.0077656525, abs=1e-9)
    assert part._TAP_WEB_WORST >= spec.STUD_TAP_WEB_MIN == 2.0
    # The nominal pilot at an exact 118 deg overstated the web.
    assert spec.tap_web_worst(
        part.BLK_TOP,
        spec.STUD_TAP_DRILL_DEPTH,
        spec.STUD_TAP_DIA,
        drill_dia_oversize=0.0,
        point_angle_deg=118.0,
    ) > part._TAP_WEB_WORST


def test_tap_point_rides_the_native_definitions_and_the_process_names_the_mate() -> None:
    # The installed calloutformat.txt's blind tap, behind the process prefix.
    drill_row = "<MOD-DIAM> <hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>"
    thread_row = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"
    before = {
        5: f"{drawing.TAP_CALLOUT_PROCESS}{drill_row}\n{thread_row}",
        6: "",
        7: "",
        8: "",
    }
    wanted = drawing.tap_callout_definitions(before)
    # The class rides the title block's thread row: the variable and its
    # separator go, the description and the full thread stay.
    assert wanted == {
        **before,
        5: (
            f"{drawing.TAP_CALLOUT_PROCESS}{drill_row} X <hw-drlang>\n"
            "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
        ),
    }
    assert drawing.tap_callout_definitions(
        {**before, 5: before[5].replace(" <hw-threadclass>", "-<hw-threadclass>")}
    ) == wanted
    # Rule 4: the full thread names its mate, the registry's bolt, on the
    # process row the prefix already prints; the below definition stays empty.
    assert sm_knife_mount_spec.BOLT_NUMBER == _config.parts("vn-knife-hanger-stud")[
        "number"
    ]
    assert sm_knife_mount_spec.TAP_CALLOUT_PROCESS == (
        f"BOTTOMING TAP FOR {sm_knife_mount_spec.BOLT_NUMBER}\n"
    )
    assert drawing._CALLOUT_BELOW_DEFINITION == 8
    assert drawing._CALLOUT_DEFINITION_PARTS[8] == 4
    assert drawing.TAP_POINT_ANGLE_VARIABLE == "hw-drlang"
    assert drawing._CALLOUT_ANGLE_VARIABLE == 2
    assert drawing._DRILL_ANGLE_VARIABLE == 16
    for bad in (
        {**before, 5: thread_row},
        {**before, 6: drill_row},
        {**before, 6: drawing.TAP_CALLOUT_PROCESS},
        {**before, 8: "FOR MHA-VN-024 HEX BOLT"},
        {**before, 6: "<hw-threadclass>"},
        {**before, 5: before[5].replace(" <hw-threadclass>", "")},
        wanted,
    ):
        with pytest.raises(RuntimeError, match="knife-hanger tap callout"):
            drawing.tap_callout_definitions(bad)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _write_tap_callout_definitions(") :]
    body = body[: body.index("\ndef ")]
    assert "callout.SetText(_CALLOUT_DEFINITION_PARTS[part], text)" in body
    assert "if after != wanted:" in body
    body = source[source.index("def _prove_tap_point(") :]
    body = body[: body.index("\n# ")]
    assert 'angle = _early_bound(raw, "ICalloutAngleVariable")' in body
    assert "STUD_TAP_POINT_ANGLE_DEG" in body
    assert "variable.ToleranceType = _TOL_NONE" in body
    assert "angle.Precision = STUD_TAP_POINT_ANGLE_PLACES" in body


def test_hidden_threads_and_restated_hidden_lines_are_gone() -> None:
    # Machinist review: the right view's dashed tap, dowel and bore restated
    # the front view and A-A, and A-A printed the tap's thread dashed; the
    # top view's dashed cross-bore and the front view's dashed blind holes
    # restated the front view, the callouts and A-A (2026-10-10 ruling).
    # Every view is hidden-lines-removed, the front and right views' thread
    # annotations on a hidden layer; A-A's thread on a visible thin
    # continuous layer, and none moved there fails the build.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for view in (iso, right, front, top):\n"
        "        set_hidden_lines_removed(adapter, view)"
    ) in source
    assert "set_hidden_lines_visible" not in source
    assert drawing.SECTION_THREAD_LAYER != drawing.HIDDEN_THREAD_LAYER
    section_call = source[source.index("    if not _layer_cosmetic_threads(\n        adapter,\n        section,") :]
    hidden_loop = 'for view, view_label in ((front, "front"), (right, "right")):'
    section_call = section_call[: section_call.index(hidden_loop)]
    assert "layer_name=SECTION_THREAD_LAYER" in section_call
    assert "visible=True" in section_call
    assert "raise RuntimeError" in section_call
    hidden_call = source[source.index(hidden_loop) :]
    hidden_call = hidden_call[: hidden_call.index("        )\n") + 10]
    assert "layer_name=HIDDEN_THREAD_LAYER" in hidden_call
    assert "visible=False" in hidden_call


def test_the_pattern_is_located_from_the_side_and_front_faces() -> None:
    # Machinist review B1: the span located the dowels only to each other.
    # The +X hole's axis stands 5.07 .XX from the +X face, a row above the
    # BASIC span over the top view (clear of the dowel frame's leader under
    # it, and of the span's arrows); the row 7.0 .X from the front face, left
    # of the view.
    assert sm_knife_mount_spec.PIN_HOLE_SIDE_DISTANCE == pytest.approx(
        sm_knife_mount_spec.BLK_HALF_X - sm_knife_mount_spec.PIN_HOLE_X
    )
    assert sm_knife_mount_spec.HOLE_ROW_FACE_DISTANCE == pytest.approx(
        sm_knife_mount_spec.SUPPORT_Z_THICK / 2.0
    )
    top_view_top = drawing.TOP_CENTER[1] + drawing.TOP_HALF_Z
    side_x, side_y = drawing.PIN_SIDE_TEXT_XY
    assert side_y > top_view_top
    assert side_y >= drawing.PIN_SPAN_TEXT_XY[1] + 0.006
    assert drawing._sheet_x(sm_knife_mount_spec.PIN_HOLE_X) < side_x
    assert side_x < drawing._sheet_x(sm_knife_mount_spec.BLK_HALF_X)
    row_x, _ = drawing.ROW_FACE_TEXT_XY
    assert row_x < drawing._sheet_x(-sm_knife_mount_spec.BLK_HALF_X)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for label in ("dowel hole from side face", "hole row from front face"):
        assert f'_set_sheet_precision(side, label="{label}")' in source or (
            f'_set_sheet_precision(row, label="{label}")' in source
        )
        assert source.count(f'label="{label}"') == 3


def test_the_tap_and_bore_axis_is_basic_from_the_dowel_pattern() -> None:
    # Machinist review (2026-10-10): the tap frame and the bore's frames
    # reference B, but their offset from B was only the implied centre.  The
    # tap axis, run on through the bore's centre in section A-A, stands BASIC
    # 7.632 from the -X dowel axis; its boxed value parks left of that axis,
    # over the section's top seat.
    assert sm_knife_mount_spec.PIN_HOLE_X == pytest.approx(
        sm_knife_mount_spec.PIN_HOLE_SPAN / 2.0
    )
    section_top = drawing._section_y(sm_knife_mount_spec.BLK_TOP)
    pin_x = drawing._section_x(-sm_knife_mount_spec.PIN_HOLE_X)
    text_x, text_y = drawing.TAP_STATION_TEXT_XY
    assert pin_x < text_x < drawing._section_x(0.0)
    assert text_y > section_top
    offset_x, offset_y = drawing.TAP_STATION_OFFSET_XY
    assert offset_y == text_y
    assert offset_x < pin_x
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The tap's axis reaches past the bore's bottom, the dowel's past its
    # floor, both inside the block.
    assert "(0.0, BORE_CY - R_BORE - SECTION_AXIS_TAIL_MM, 0.0)" in source
    assert "BLK_TOP - PIN_HOLE_DEPTH - SECTION_AXIS_TAIL_MM" in source
    assert (
        sm_knife_mount_spec.BORE_CY
        - sm_knife_mount_spec.R_BORE
        - drawing.SECTION_AXIS_TAIL_MM
        > sm_knife_mount_spec.BLK_BOT
    )
    assert 'entity_types=("SKETCHSEGMENT", "SKETCHSEGMENT")' in source
    assert source.count('label="dowel hole from tap axis"') == 3


def test_the_bore_states_its_ream_and_band() -> None:
    # Machinist review B3: a bare THRU left drill or ream open; the bore is
    # reamed to +0.03/0 at two places (Ra 1.6 stays).
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "REAM THRU"
    assert sm_knife_mount_spec.BORE_DIA_BAND == (0.03, 0.0)
    assert sm_knife_mount_spec.BORE_DIA_PLACES == 2
    assert sm_knife_mount_spec.DRAWING_PRECISION["BoreProfile"] == {"BoreDia": 2}
    assert sm_knife_mount_spec.BORE_R_MIN == sm_knife_mount_spec.R_BORE
    assert sm_knife_mount_spec.BORE_R_MAX == pytest.approx(6.015)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        "        \"BoreProfile\",\n"
        "        \"BoreDia\",\n"
        "        *deviations(BORE_DIA_BAND),\n"
        "        places=BORE_DIA_PLACES,\n"
    ) in source
    assert source.index("*deviations(BORE_DIA_BAND)") < source.index(
        "apply_drawing_precision(adapter, DRAWING_PRECISION)"
    )
