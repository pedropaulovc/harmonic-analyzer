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
    # overall size, the reamed bore's .XX band, datum B's slip Ø and datum
    # C's slot width at their band's three, the slot end's .XX station from
    # B and the shared floor depth's .X); the block depth, the tap axis's
    # BASIC station from B, the bore's BASIC height and B's face locations
    # are sheet-added, their places the spec's.
    assert set(sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME) == marked == {
        "BlockWidth",
        "BlockHeight",
        "BoreDia",
        "PinHoleDia",
        "SlotWidth",
        "SlotEndFromB",
        "PinHoleDepth",
    }
    assert sm_knife_mount_spec.DRAWING_DIMENSIONS["PinHoleProfile"] == {
        "PinHoleDia",
        "SlotWidth",
        "SlotEndFromB",
    }
    assert sm_knife_mount_spec.DRAWING_DIMENSIONS["PinHole"] == {"PinHoleDepth"}
    assert sm_knife_mount_spec.DRAWING_PRECISION["PinHoleProfile"] == {
        "PinHoleDia": sm_knife_mount_spec.PIN_HOLE_DIA_PLACES,
        "SlotWidth": sm_knife_mount_spec.SLOT_WIDTH_PLACES,
        "SlotEndFromB": sm_knife_mount_spec.SLOT_END_PLACES,
    }
    assert sm_knife_mount_spec.SLOT_END_PLACES == 2
    # The slot end's .XX claims the title block's 2-place band, the one its
    # margins charge.
    assert sm_knife_mount_spec.SLOT_END_TOL == sm_knife_mount_spec._XX
    for feature, names in sm_knife_mount_spec.DRAWING_PRECISION.items():
        assert set(names) <= sm_knife_mount_spec.DRAWING_DIMENSIONS[feature]


def test_dowel_hole_depth_is_dimensioned_on_the_section_not_a_hidden_edge() -> None:
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): the
    # blind slip hole's and slot's shared floor is a hidden edge in the front
    # view, so its depth rides section A-A, cut on z = 0 through the tap axis
    # (the origin), datum B's axis and the slot's centre plane, and only there.
    assert set(drawing.SECTION_KEEP) == {"PinHoleDepth"}
    assert "PinHoleDepth" not in drawing.FRONT_KEEP
    assert "PinHoleDepth" not in drawing.TOP_KEEP
    (start, end) = drawing.SECTION_LINE_MODEL_MM
    assert start[2] == end[2] == 0.0
    assert start[0] < -sm_knife_mount_spec.BLK_HALF_X
    assert end[0] > sm_knife_mount_spec.BLK_HALF_X
    assert sm_knife_mount_spec.SLOT_X == -sm_knife_mount_spec.PIN_HOLE_X
    assert start[0] < sm_knife_mount_spec.SLOT_X < 0.0 < sm_knife_mount_spec.PIN_HOLE_X < end[0]
    # One cut, one floor: the depth states, under the value, that the floor
    # is flat and holds for both seats (the hole and the slot).  Nothing
    # seats on it, so its corner is the title block's (machinist review, farm
    # run 20261027T233328148Z: a local CORNER R0.1 MAX named no function).
    from _layout_audit import TEXT_ROW_LIMIT
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M
    from _printed_tolerance import inside_corner_radius_mm

    callout = sm_knife_mount_spec.PIN_DEPTH_CALLOUT
    depth_rows = callout.splitlines()
    assert "FLAT BOTTOM" in depth_rows[0]
    assert "2X" in depth_rows[0].split()
    assert "CORNER" not in callout
    corner = sm_knife_mount_spec.DOWEL_HOLE_FLOOR_CORNER_R_MAX
    assert corner == inside_corner_radius_mm(unit=sm_knife_mount_spec.UNIT)
    assert 0.0 <= sm_knife_mount_spec.DOWEL_HOLE_CORNER_RECESS < 0.001
    assert 1 + len(depth_rows) <= TEXT_ROW_LIMIT
    assert drawing.DEPTH_TEXT_ROWS == 1 + len(depth_rows)
    assert drawing.DIMENSION_CALLOUTS["PinHoleDepth"] is callout
    assert sm_knife_mount_spec.PIN_HOLE_DEPTH == pytest.approx(9.398)  # .37
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("create_section_view(") == 1
    assert "_look_section_along_minus_z(adapter, section)" in source
    assert "set_hidden_lines_removed(adapter, section)" in source
    # Section before top: the MHA-PD-18 import order.
    assert source.index("keep=SECTION_KEEP") < source.index("keep=TOP_KEEP")
    # Farm run 20261027T175429300Z: left in line, the value printed across
    # the top seat's witness line and the dimension line's outer tail
    # (y 152.9..156.4 mm), so the text parks on a jog right of the witness
    # lines' ends, draw_fr_top_frame's form.  The same run printed that
    # form's three rows on F-F: the value's baseline 2.78 mm over the offset
    # y, rows 5.56 mm apart and 3.5 mm tall, centred on the offset x, the
    # widest ("CORNER R0.1 MAX") 41.94 mm, 2.80 mm a glyph; the underline
    # under the last row from its left end, where the leader lands.
    assert "offset_dimension_text(adapter, annotations, " in source
    assert '{"PinHoleDepth": PIN_DEPTH_OFFSET_XY})' in source
    assert source.index('{"PinHoleDepth": PIN_DEPTH_OFFSET_XY}') > source.index(
        "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)"
    )
    assert (
        drawing.DEPTH_VALUE_RISE,
        drawing.DEPTH_ROW_PITCH,
        drawing.DEPTH_TEXT_HEIGHT,
    ) == (0.00278, 0.00556, 0.0035)
    line_x, line_y = drawing.SECTION_KEEP["PinHoleDepth"]
    assert line_x == drawing.PIN_DEPTH_LINE_X
    x, y = drawing.PIN_DEPTH_OFFSET_XY
    top_y = drawing._section_y(sm_knife_mount_spec.BLK_TOP)
    floor_y = drawing._section_y(
        sm_knife_mount_spec.BLK_TOP - sm_knife_mount_spec.PIN_HOLE_DEPTH
    )
    assert line_y == pytest.approx((top_y + floor_y) / 2.0)
    rows_top = y + drawing.DEPTH_VALUE_RISE + drawing.DEPTH_TEXT_HEIGHT
    underline_y = y + drawing.DEPTH_VALUE_RISE - len(depth_rows) * drawing.DEPTH_ROW_PITCH
    half_width = drawing.DEPTH_ROW_HALF_WIDTH
    assert 2.0 * half_width >= max(len(row) for row in depth_rows) * 0.00280
    rows_left, rows_right = x - half_width, x + half_width
    # Wholly right of the witness lines' ends (1 mm past the dimension
    # line) and between their heights, so nothing it owns or crosses runs
    # through it; the leader falls from the dimension line's midpoint.
    witness_end_x = line_x + 0.001
    assert rows_left >= witness_end_x + ARROW_TEXT_CLEARANCE_M
    assert rows_top <= top_y - ARROW_TEXT_CLEARANCE_M
    assert underline_y >= floor_y + ARROW_TEXT_CLEARANCE_M
    assert top_y - rows_top == pytest.approx(underline_y - floor_y, abs=1e-9)
    # The dimension line right of the 7.632 BASIC's leader shoulder (its end
    # x 334.5 mm, farm run 20261027T133857303Z), whose box stands over the
    # top seat's witness; the section's +X face (x 325.4 mm) further left.
    face_x = drawing.SECTION_CENTER[0] + sm_knife_mount_spec.BLK_HALF_X * (
        drawing.SHEET_SCALE[0] / 1000.0
    )
    assert face_x < 0.3345 < line_x - 0.010
    # Inside the border, under the isometric's caption (y 170.5 mm).
    assert rows_right <= 0.4318 - SHEET_INNER_BORDER_LEFT - 0.010
    assert rows_top <= 0.1705 - 0.010


def test_dowel_callout_is_parked_clear_of_the_top_view() -> None:
    # drawing-guidelines.md rule 14 (keep text off the part) (dda9a33a8 render): the three callout lines ran through both
    # holes and the leader shoulder crossed the view.  Datum B's Ø and its
    # three rows now hang wholly right of the block's +X face and under the
    # top view, and the shoulder's near end stands below the hole centre so
    # the leader climbs to the hole rim.
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M

    x, y = drawing.TOP_KEEP["PinHoleDia"]
    face_x = drawing._sheet_x(sm_knife_mount_spec.BLK_HALF_X)
    shoulder_x, shoulder_y = drawing.PIN_CALLOUT_SHOULDER_START
    assert shoulder_x > face_x
    shoulder_start_x = (
        x - drawing.PIN_CALLOUT_HALF_WIDTH - drawing.PIN_CALLOUT_SHOULDER_OVERHANG
    )
    assert shoulder_start_x == pytest.approx(shoulder_x)
    assert y - drawing.PIN_CALLOUT_SHOULDER_DROP == pytest.approx(shoulder_y)
    assert shoulder_y < drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    # Right edge clear of the right view's column and on the sheet.
    right_edge = x + drawing.PIN_CALLOUT_HALF_WIDTH
    assert right_edge < drawing.ISO_CENTER[0] - 0.050
    # Above the right view's box (front row, 2:1 block height).
    assert shoulder_y > drawing.RIGHT_CENTER[1] + drawing.RIGHT_HALF_Y + 0.040
    # The block's left end stands right of B's 7.0 row dimension line, which
    # runs down the top view's +X side.
    assert shoulder_x - drawing.ROW_FACE_TEXT_XY[0] >= ARROW_TEXT_CLEARANCE_M
    # The half width tracks the widest row at the ~2.52 mm a capital the
    # sheet prints, and the Ø row and its callout rows stay inside the layout
    # audit's row limit.
    from _layout_audit import TEXT_ROW_LIMIT

    rows = drawing.DIMENSION_CALLOUTS["PinHoleDia"].splitlines()
    assert 1 + len(rows) <= TEXT_ROW_LIMIT
    widest = max(len(row) for row in rows)
    assert 2.0 * drawing.PIN_CALLOUT_HALF_WIDTH == pytest.approx(
        widest * 0.00252, abs=0.0005
    )


def test_the_tap_is_stated_once_on_its_hole_callout() -> None:
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the tap rides one native Hole Wizard callout (thread, full
    # thread depth, drill and drill depth stay associative); SolidWorks' raw
    # "#10-24 Tapped Hole" note would restate it, so it is deleted and
    # finalize proves none is left at export.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 1
    # R4: no tap tool is named (the full thread's depth says how deep), and
    # the bolt is named once, on the reason row.
    assert "process=" not in source
    assert "BOTTOMING TAP" not in "".join(
        str(value)
        for value in vars(sm_knife_mount_spec).values()
        if isinstance(value, str)
    )
    assert drawing.TAP_DRILL_CALLOUT is sm_knife_mount_spec.TAP_DRILL_CALLOUT
    assert sm_knife_mount_spec.STUD_TAP_DRILL in drawing.TAP_DRILL_CALLOUT.split()
    assert "DRILL" in drawing.TAP_DRILL_CALLOUT.split()
    assert drawing.TAP_CALLOUT_REASON is sm_knife_mount_spec.TAP_CALLOUT_REASON
    assert sm_knife_mount_spec.BOLT_NUMBER in drawing.TAP_CALLOUT_REASON.split()
    assert "CLEARANCE" in drawing.TAP_CALLOUT_REASON.split()
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
# ('+0.10') row 213.8..217.4, and the 7.0's (RD4's) outside tail, then left of
# the top view at x 77.6, ran (77.6, 221.0)->(77.6, 214.7) through that row.
RUN_CALLOUT_XY = (0.0586, 0.2090)
RUN_CALLOUT_SPAN_X = (0.0200, 0.0971)
RUN_CALLOUT_TOP = 0.2174
# The three-row block moved 6.0 mm down from the run's anchor; T+H3
# (2026-10-24) took it 20 mm lower again, under datum C's tag.
TAP_CALLOUT_RUN_DROP = 0.006 + 0.020


def test_tap_callout_moves_clear_of_the_row_dimension_tail() -> None:
    # drawing-guidelines.md rule 14 (keep text off the part): the three rows
    # stand inside the five-row run's envelope, moved down with the anchor,
    # whichever way SolidWorks restacks them.  The 7.0 (B's row from the
    # front face) now runs down the top view's +X side, so its outside tail
    # stands right of the block's whole span, and the block's top stays
    # under that tail's end by more than the gating arrow-to-text clearance.
    from _layout_audit import ARROW_TAIL_M
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M

    x, y = drawing.TAP_CALLOUT_XY
    # The 7.0's tail, from the drawing's own placement: its line at its
    # text's x, its outside tail one ARROW_TAIL_M under the view's lower edge.
    top_view_bottom = drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    tail_x = drawing.ROW_FACE_TEXT_XY[0]
    tail_end = top_view_bottom - ARROW_TAIL_M
    assert tail_x > drawing._sheet_x(sm_knife_mount_spec.BLK_HALF_X)
    # Wherever SolidWorks restacks the rows, they stay inside the run's
    # span, which ends well left of the tail.
    assert tail_x > RUN_CALLOUT_SPAN_X[1] + ARROW_TEXT_CLEARANCE_M
    assert tail_x > x + drawing.TAP_CALLOUT_HALF_WIDTH + ARROW_TEXT_CLEARANCE_M
    top = y + drawing.TAP_CALLOUT_TOP_REACH
    assert top <= tail_end - ARROW_TEXT_CLEARANCE_M - 0.001
    assert drawing.TAP_FRAME_XY[1] == pytest.approx(y - drawing.TAP_FRAME_DROP)


def test_tap_callout_prints_three_rows_with_its_bands_and_drill_point() -> None:
    # Tall-block (the 4-row limit): the c673e62ee seat's definitions, the
    # pilot's stacked upper deviation a row of its own, printed five rows with
    # the mate below the thread.  Now the pilot is named by its drill (no Ø,
    # no band, no stacked row), the thread prints no class (the title block's
    # thread row), and the reason naming the mate is the one row under the
    # thread, no process row above it: three.  The symmetric bands, the drill
    # point and the thread's native depth stay.
    from _layout_audit import TEXT_ROW_LIMIT

    drill_row = "<MOD-DIAM> <hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>"
    thread_row = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"
    seat = {5: thread_row, 6: "", 7: drill_row, 8: ""}
    # A bilateral band stacks its deviations a row of their own.
    stacked_band_rows = sum(
        1
        for _, band in drawing.TAP_CALLOUT_BANDS.values()
        if drawing.tap_callout_tolerance(band)[0] != drawing._TOL_SYMMETRIC
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
        8: "FOR MHA-SM-VN-52 HEX BOLT",
    }
    assert printed_rows(run, 1) == TEXT_ROW_LIMIT + 1
    assert stacked_band_rows == 0
    wanted = drawing.tap_callout_definitions(seat)
    assert printed_rows(wanted, stacked_band_rows) == 3 <= TEXT_ROW_LIMIT
    assert wanted[7] == (
        f"{drawing.TAP_DRILL_CALLOUT} <HOLE-DEPTH> <hw-tapdrldepth> X <hw-drlang>"
    )
    assert wanted[5] == "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
    assert wanted[8] == drawing.TAP_CALLOUT_REASON
    joined = "".join(wanted.values())
    assert "threadclass" not in joined
    assert "<MOD-DIAM>" not in joined and "<hw-tapdrldia>" not in joined
    assert joined.count(sm_knife_mount_spec.BOLT_NUMBER) == 1
    assert "TAP" not in joined
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
    # stand in the band under the top view, under datum C's tag and left of
    # the front view's datum-A tag, their frame under them and over the
    # lowered front view.
    from _layout_audit import TEXT_SEPARATION_HEIGHTS

    x, y = drawing.TAP_CALLOUT_XY
    top_view_bottom = drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    top = y + drawing.TAP_CALLOUT_TOP_REACH
    assert top < top_view_bottom
    assert drawing.SLOT_DATUM_C_XY[1] - top >= TEXT_SEPARATION_HEIGHTS * 0.0035
    assert x + drawing.TAP_CALLOUT_HALF_WIDTH < drawing.FRONT_CENTER[0] - 0.0035 - 0.005
    # The frame (7 mm tall) stays over the 29.6 height line's upper witness
    # line (y at the block top), not beside it, a text height and more clear.
    frame_bottom = drawing.TAP_FRAME_XY[1] - 0.007
    front_top = drawing._front_y(sm_knife_mount_spec.BLK_TOP)
    assert frame_bottom - front_top >= TEXT_SEPARATION_HEIGHTS * 0.0035
    # T+H3 lowered the front and right views 15 mm, the band they open
    # taking the callout's 20 mm drop.
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1] == 0.125
    # Rule 13: the block stays inside the inner border.
    assert x - drawing.TAP_CALLOUT_HALF_WIDTH > SHEET_INNER_BORDER_LEFT + 0.001
    # The widest row is the reason naming the bolt.  Farm run
    # 20261027T133857303Z printed its 31 characters 80.7 mm wide (x
    # 18.2..98.9 mm), 2.60 mm a character, inside the half width's 88: the
    # reason, at that rate, keeps 5 mm and more of it spare whatever its
    # wording.  The drill row, named by its drill and no stack, is narrower.
    run_reason_span_x = (0.0182, 0.0989)
    run_mm_per_char = (run_reason_span_x[1] - run_reason_span_x[0]) / 31
    assert run_mm_per_char == pytest.approx(0.0026, abs=1e-5)
    reason_width = len(drawing.TAP_CALLOUT_REASON) * run_mm_per_char
    assert 2.0 * drawing.TAP_CALLOUT_HALF_WIDTH >= reason_width + 0.005
    assert len(drawing.TAP_CALLOUT_REASON) >= len(drawing.TAP_DRILL_CALLOUT)


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

    run_tap_drill_dia = 2.705
    run_rim = lower_rim(drawing.TAP_CALLOUT_RIM_SIDE, run_tap_drill_dia)
    assert math.dist(run_rim, run_callout_tip) < 0.001
    assert drawing.TAP_FRAME_RIM_SIDE == -drawing.TAP_CALLOUT_RIM_SIDE
    # Farm run 20261027T133857303Z printed the frame's leader root 47.9207
    # mm right of and 3.5 mm under TAP_FRAME_XY (its 6.35 shoulder off the
    # frame's right end); the frame keeps that shape wherever TAP_FRAME_XY
    # puts it, and the tips land on the #10-24 drill's lower rims.
    frame_root = (drawing.TAP_FRAME_XY[0] + 0.0479207, drawing.TAP_FRAME_XY[1] - 0.0035)
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
    # The frame's leader passes left of the datum-A tag's 7 mm box over the
    # front view's top seat.
    tag_left = drawing.DATUM_A_X - 0.0035
    tag_top = drawing._front_y(sm_knife_mount_spec.BLK_TOP) + 0.018 + 0.0075
    assert frame_root[1] < tag_top < frame_tip[1]

    def x_at(y: float) -> float:
        return frame_root[0] + (frame_tip[0] - frame_root[0]) * (
            (y - frame_root[1]) / (frame_tip[1] - frame_root[1])
        )

    assert x_at(tag_top) < tag_left - 0.001
    # Datum B's former bare tag box (x 116.5..123.5, y 207.7..214.7 mm in farm
    # run 20261027T133857303Z) passed 0.08 mm off this leader and was crossed
    # in farm run 20261027T143609236Z.  B now rides its ⊥ frame, whose leader
    # shoulder and frame stand well right of this leader, and the two
    # leaders do not cross.
    b_elbow, b_tip = datum_b_frame_leader()
    assert x_at(b_elbow[1]) <= b_elbow[0] - 0.010
    assert x_at(drawing.PIN_FRAME_XY[1]) <= drawing.PIN_FRAME_XY[0] - 0.010
    assert _segment_crossing(frame, Segment(*b_elbow, *b_tip)) is None
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "tap_rim = _tap_lower_rim(adapter, top, TAP_CALLOUT_RIM_SIDE)" in source
    assert "edge_xy=_tap_lower_rim(adapter, top, TAP_FRAME_RIM_SIDE)" in source


# Farm run 20261027T133857303Z's printed ink near datum B (sheet metres): the
# Ø3.240's arrow tip on B's rim and its shoulder's near end (its underline
# runs right from there), the knife-bore frame's top-left corner and its
# leader's elbow segment, and the lower end of the 14.40's witness line
# from B's centre (x on B's axis, the centre mark's vertical arm with it).
RUN_PIN_DIA_TIP = (0.13190, 0.23220)
RUN_PIN_DIA_SHOULDER = (0.15174, 0.19836)
RUN_BORE_FRAME_TOP_LEFT = (0.15000, 0.17362)
RUN_BORE_FRAME_ELBOW = ((0.14365, 0.17012), (0.15000, 0.17012))
RUN_B_AXIS_LINE_END = (0.13026, 0.22576)


def _point_segment_distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    return math.dist(point, (a[0] + t * dx, a[1] + t * dy))


def datum_b_frame_leader() -> tuple[tuple[float, float], tuple[float, float]]:
    """Datum B's ⊥ frame leader: its 6.35 mm shoulder end off the frame's
    left end at the row's mid-height, and its landing on B's rim."""
    centre = (drawing._sheet_x(sm_knife_mount_spec.PIN_HOLE_X), drawing.TOP_CENTER[1])
    rim = sm_knife_mount_spec.PIN_HOLE_DIA / 2.0 * drawing.SHEET_SCALE[0] / 1000.0
    angle = math.radians(drawing.PIN_FRAME_RIM_DEG)
    tip = (centre[0] + rim * math.cos(angle), centre[1] + rim * math.sin(angle))
    left, top = drawing.PIN_FRAME_XY
    return (left - 0.00635, top - drawing.PIN_FRAME_SIZE[1] / 2.0), tip


def test_datum_b_frame_lands_apart_from_the_slip_hole_diameter_leader() -> None:
    # Blind machinist review R3 (farm run 20261014T010316127Z): the Ø's
    # arrowhead and datum B's frame's landed on the +X hole's lower-right rim
    # 0.10 mm apart, so the two leaders read as one.  Owner ruling 2026-10-27
    # (#2016): B's hole carries ⊥Ø0.015 to A, and B's symbol rides that
    # frame.  The frame stands in the band between the views; its leader
    # leaves the frame's left end (the landing lies wholly left of it) and
    # lands on B's lower-left rim, left of B's vertical centre line, while
    # the Ø's leader lands on the lower-right rim.
    from _layout_audit import _segment_crossing
    from _layout_geometry import Segment

    centre = (drawing._sheet_x(sm_knife_mount_spec.PIN_HOLE_X), drawing.TOP_CENTER[1])
    assert drawing.PIN_FRAME_RIM_DEG == -140.0
    elbow, tip = datum_b_frame_leader()
    left, top = drawing.PIN_FRAME_XY
    width, height = drawing.PIN_FRAME_SIZE
    assert height == 0.007
    # The landing stands left of the frame, so SolidWorks leaves its left end.
    assert tip[0] < left
    # Its own point: ~4 mm round the rim from the Ø's arrow, below the
    # cutting line, and ~2.5 mm left of B's vertical centre line.
    assert math.dist(tip, RUN_PIN_DIA_TIP) >= 0.004
    assert tip[1] < centre[1]
    assert centre[0] - tip[0] >= 0.0024
    # The leader crosses neither the Ø's leader nor the tap frame's, and
    # passes 3 mm and more clear of the lower end of B's vertical line.
    leader = Segment(*elbow, *tip)
    assert _segment_crossing(leader, Segment(*RUN_PIN_DIA_TIP, *RUN_PIN_DIA_SHOULDER)) is None
    assert _point_segment_distance(RUN_B_AXIS_LINE_END, elbow, tip) >= 0.003
    # The frame: in the band under the top view, a text height and more
    # under the Ø's shoulder line (which runs right from x 151.74 mm, over
    # the frame's right end), left of the bore frame's column.
    assert left + width > RUN_PIN_DIA_SHOULDER[0]
    assert RUN_PIN_DIA_SHOULDER[1] - top >= 0.0033
    assert top < drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z - 0.020
    # B's symbol hangs a stem under the frame's middle, its box (bottom
    # middle at PIN_DATUM_B_XY) 3 mm and more clear of the bore frame's
    # top-left corner and over its leader's elbow.  Its stem differs from
    # C's: a tag on a frame reads its position relative to the frame, so on
    # equal stems the two read alike and the layout audit took them for a
    # duplicate (farm run 20261027T162806664Z).
    box = drawing.DATUM_TAG_BOX
    x, y = drawing.PIN_DATUM_B_XY
    assert x == pytest.approx(left + width / 2.0)
    assert (top - height) - (y + box) == pytest.approx(drawing.PIN_DATUM_B_STEM)
    assert abs(drawing.PIN_DATUM_B_STEM - drawing.DATUM_TAG_STEM) >= 0.0005
    assert drawing.PIN_DATUM_B_STEM >= 0.003
    assert math.dist((x + box / 2.0, y), RUN_BORE_FRAME_TOP_LEFT) >= 0.003
    assert x + box / 2.0 < RUN_BORE_FRAME_TOP_LEFT[0]
    assert y - RUN_BORE_FRAME_ELBOW[0][1] >= 0.006
    # Clear of the datum-A tag's 7 mm box over the front view's top seat.
    tag_right = drawing.DATUM_A_X + 0.0035
    tag_top = drawing._front_y(sm_knife_mount_spec.BLK_TOP) + 0.018 + 0.007
    assert left - tag_right >= 0.002
    assert (top - height) - tag_top >= 0.008
    assert x - box / 2.0 - tag_right >= 0.015
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("    b_frame_angle = math.radians(PIN_FRAME_RIM_DEG)\n") :]
    body = body[: body.index("    # Datum C = ")]
    assert (
        "    pin_frame = add_feature_control_frame(\n"
        "        adapter,\n"
        "        top,\n"
        "        edge_xy=b_frame_rim,\n"
        "        leader_attach_xy=b_frame_rim,\n"
        "        frame_xy=PIN_FRAME_XY,\n"
    ) in body
    assert (
        "    add_frame_datum_feature(\n"
        "        adapter,\n"
        "        top,\n"
        "        pin_frame,\n"
        '        datum="B",\n'
        "        symbol_xy=PIN_DATUM_B_XY,\n"
    ) in body


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
    # Its top row stays under the block top's 29.6 extension line (farm run
    # 20261024T114146582Z: the +0.03 rode it, text-on-line).
    top_line = drawing._front_y(sm_knife_mount_spec.BLK_TOP)
    assert y + drawing.BORE_DIA_TEXT_TOP_REACH < top_line - 0.0035
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
    assert sm_knife_mount_spec.BLK_TOP == pytest.approx(14.866)
    # The build owns no tap constants: they are the spec's (consumers import
    # them there).
    assert not hasattr(part, "STUD_TAP_DEPTH")
    assert part.STUD_TAP_SPEC is sm_knife_mount_spec.STUD_TAP_SPEC
    assert part.STUD_TAP_DIA == sm_knife_mount_spec.STUD_TAP_DIA
    # The slip seats (T+H3): datum B's round hole +X of the tap at 7.62,
    # datum C's slot along the line -X of it, its half-round inner end's
    # centre SlotEndFromB from B, running out through the -X face; their
    # printed places and the volume the build's gate expects.
    assert sm_knife_mount_spec.PIN_HOLE_X == pytest.approx(7.62)  # .300
    assert sm_knife_mount_spec.SLOT_END_FROM_B == pytest.approx(14.478)  # .57
    for gone in ("PIN_HOLE_XS", "PIN_HOLE_SPAN", "PIN_HOLE_PAIR_CALLOUT", "PIN_HOLE_COUNT"):
        assert not hasattr(sm_knife_mount_spec, gone)
    dia, width = sm_knife_mount_spec.PIN_HOLE_DIA, sm_knife_mount_spec.SLOT_WIDTH
    depth = sm_knife_mount_spec.PIN_HOLE_DEPTH
    assert dia == width == pytest.approx(3.2512)  # .1280
    assert part.V_PIN == pytest.approx(math.pi * (dia / 2.0) ** 2 * depth, abs=1e-9)
    inner_x = sm_knife_mount_spec.PIN_HOLE_X - sm_knife_mount_spec.SLOT_END_FROM_B
    assert part.SLOT_INNER_X == pytest.approx(inner_x)
    # The stadium's outer end is modelled wholly past the -X face, in air.
    assert part.SLOT_OUTER_X + width / 2.0 < -sm_knife_mount_spec.BLK_HALF_X
    slot_area = (inner_x + sm_knife_mount_spec.BLK_HALF_X) * width + math.pi * width**2 / 8.0
    assert part.V_SLOT == pytest.approx(slot_area * depth, abs=1e-9)
    assert part.V_PINS == part.V_PIN + part.V_SLOT
    # B's Ø and C's width each carry the symmetric slip band, one row
    # (.1280 +/-.0007).
    assert sm_knife_mount_spec.PIN_HOLE_DIA_BAND == pytest.approx((0.01778, -0.01778))
    assert sm_knife_mount_spec.SLOT_WIDTH_BAND == pytest.approx((0.01778, -0.01778))


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
    # No quantity rides above B's Ø (the 2X pattern is gone); the slip hole's
    # and the slot's callouts name their mate and the clearance it sets
    # (rule 4), and the depth states one floor for both.
    assert not hasattr(drawing, "CALLOUTS_ABOVE")
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": drawing.BORE_CALLOUT,
        "PinHoleDia": sm_knife_mount_spec.PIN_HOLE_CALLOUT,
        "SlotWidth": sm_knife_mount_spec.SLOT_WIDTH_CALLOUT,
        "PinHoleDepth": sm_knife_mount_spec.PIN_DEPTH_CALLOUT,
    }
    dowel_number = _config.parts("sm-vn-knife-mount-dowel")["number"]
    assert sm_knife_mount_spec.DOWEL_NUMBER == dowel_number
    # The printed clearance band, in inch, rounds the dowel's slip band
    # outward to four places.
    import sm_vn_knife_mount_dowel_spec as dowel

    low = math.floor(dowel.SLIP_CLEARANCE_MIN / 25.4 * 1e4 + 1e-6) / 1e4
    high = math.ceil(dowel.SLIP_CLEARANCE_MAX / 25.4 * 1e4 - 1e-6) / 1e4
    assert sm_knife_mount_spec.PIN_SLIP_PRINTED == pytest.approx((low, high))
    assert low * 25.4 - 1e-9 <= dowel.SLIP_CLEARANCE_MIN < (low + 0.0001) * 25.4
    assert (high - 0.0001) * 25.4 < dowel.SLIP_CLEARANCE_MAX <= high * 25.4 + 1e-9
    # B's hole names its process (a flat-bottomed ream), the clearance band
    # it sets and its mate; the slot names its open end and its mate.  Each
    # fact once, and each callout few enough rows for the layout audit's
    # limit with its value row.
    from _layout_audit import TEXT_ROW_LIMIT

    hole = sm_knife_mount_spec.PIN_HOLE_CALLOUT
    assert "REAM" in hole.split()
    assert "FLAT-BOTTOM" in hole or "FLAT BOTTOM" in hole
    assert hole.count(f"{low:.4f}-{high:.4f}".replace("0.", ".")) == 1
    assert "CLEARANCE" in hole
    assert hole.count(dowel_number) == 1
    slot = sm_knife_mount_spec.SLOT_WIDTH_CALLOUT
    assert "OPEN-END SLOT" in slot
    assert slot.count(dowel_number) == 1
    for callout in (hole, slot):
        assert 1 + len(callout.splitlines()) <= TEXT_ROW_LIMIT
    assert not any(
        "PRESS" in text or "INTERFERENCE" in text
        for text in drawing.DIMENSION_CALLOUTS.values()
    )


# Farm run 20261027T133857303Z printed the slot width's lower arrow tail
# (78.0, 231.76)->(78.0, 225.41) mm, and the tap callout's top row's ink to
# y 190.3 mm.
RUN_SLOT_WIDTH_TAIL = ((0.0780, 0.23176), (0.0780, 0.22541))
RUN_TAP_CALLOUT_INK_TOP = 0.1903


def test_datum_c_hangs_under_the_slot_frames_clear_of_the_tap_callout() -> None:
    # Datum C, the slot, is its width's ⌖0.05 to A|B (the crossbar's former
    # slot frame, moved with the slot) and, stacked under it, its ⊥0.015 to
    # A (owner ruling 2026-10-27, #2016): the C symbol's box (its bottom
    # middle at SLOT_DATUM_C_XY) hangs under the two-row stack, within its
    # width, a stem under it, and over the tap's callout block below.
    from _layout_audit import TEXT_SEPARATION_HEIGHTS, _segment_crossing
    from _layout_geometry import Segment

    frame_left, frame_top = drawing.SLOT_FRAME_XY
    frame_w, frame_h = drawing.SLOT_FRAME_SIZE
    assert frame_h == pytest.approx(2 * 0.007)
    box = drawing.DATUM_TAG_BOX
    x, y = drawing.SLOT_DATUM_C_XY
    assert x == pytest.approx(frame_left + frame_w / 2.0)
    assert (frame_top - frame_h) - (y + box) == pytest.approx(drawing.DATUM_TAG_STEM)
    assert drawing.DATUM_TAG_STEM >= 0.004
    # Over the tap callout's envelope by a text height, over its printed
    # top row by 4.7 mm.
    tap_top = drawing.TAP_CALLOUT_XY[1] + drawing.TAP_CALLOUT_TOP_REACH
    assert tap_top > RUN_TAP_CALLOUT_INK_TOP
    assert y - tap_top >= TEXT_SEPARATION_HEIGHTS * 0.0035
    assert y - RUN_TAP_CALLOUT_INK_TOP == pytest.approx(0.0047)
    # The stack stands left of the block inside the inner border (rule 13),
    # under the top view's centre line, its leader landing on the slot's
    # front wall between the slot's inner end and the -X face.
    assert frame_left > SHEET_INNER_BORDER_LEFT + 0.010
    assert frame_left + frame_w < RUN_SLOT_WIDTH_TAIL[0][0] - 0.010
    assert frame_top < drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    inner_end_x = sm_knife_mount_spec.PIN_HOLE_X - sm_knife_mount_spec.SLOT_END_FROM_B
    assert -sm_knife_mount_spec.BLK_HALF_X < drawing.SLOT_FRAME_WALL_X < inner_end_x
    # Its leader leaves a 6.35 mm shoulder off the upper row's right end at
    # that row's mid-height and lands on the slot's lower wall: it passes
    # 2.4 mm and more under the end of the slot width's lower arrow tail,
    # whether the stack prints 2 mm narrower or wider than its ~34.7 mm.
    tip = (
        drawing._sheet_x(drawing.SLOT_FRAME_WALL_X),
        drawing.TOP_CENTER[1]
        - sm_knife_mount_spec.SLOT_WIDTH / 2.0 * drawing.SHEET_SCALE[0] / 1000.0,
    )
    tail = Segment(*RUN_SLOT_WIDTH_TAIL[0], *RUN_SLOT_WIDTH_TAIL[1])
    for width_error in (-0.002, 0.0, 0.002):
        root = (frame_left + frame_w + width_error + 0.00635, frame_top - 0.0035)
        assert _segment_crossing(Segment(*root, *tip), tail) is None
        assert _point_segment_distance(RUN_SLOT_WIDTH_TAIL[1], root, tip) >= 0.0024
    # Over the part from the -X face to its landing for under the layout
    # audit's 10 mm leader-over-part detour.
    root = (frame_left + frame_w + 0.00635, frame_top - 0.0035)
    face_x = drawing._sheet_x(-sm_knife_mount_spec.BLK_HALF_X)
    face_y = root[1] + (tip[1] - root[1]) * (face_x - root[0]) / (tip[0] - root[0])
    assert math.dist((face_x, face_y), tip) < 0.0095
    # The width's three rows (~24 capitals at ~2.52 mm, the mate row) print
    # left of the vertical dimension line, which stands at the text x
    # (farm run 20261027T030041319Z: centred there, they ran 25.8 mm past
    # the border); the line stands left of the A-A cutting line's -X end and
    # the rows inside the border.
    rows = drawing.DIMENSION_CALLOUTS["SlotWidth"].splitlines()
    width = max(len(row) for row in rows) * 0.00252
    text_x, text_y = drawing.TOP_KEEP["SlotWidth"]
    assert (text_x, text_y) == drawing.SLOT_WIDTH_TEXT_XY
    assert text_x - width > SHEET_INNER_BORDER_LEFT + 0.003
    section_start_x = drawing._sheet_x(
        -(sm_knife_mount_spec.BLK_HALF_X + drawing.SECTION_LINE_OVERRUN_MM)
    )
    assert text_x < section_start_x - 0.005
    assert text_y > drawing.TOP_CENTER[1]


def test_native_gdt_and_bore_geometry() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Datum A the top seat, a tag on its edge.  Datum B the round slip hole
    # (owner ruling 2026-10-24, T+H3: one hole, no 2X pattern) and datum C
    # the slot, each its symbol on its feature's frame (owner ruling
    # 2026-10-27, #2016: B's ⊥ frame, C's ⌖/⊥ stack; a frame's datum
    # identifier read "B" back but printed nothing, 20261009T171439353Z).
    assert source.count("add_datum_feature(") == 1
    assert "add_dimension_datum_feature" not in source
    assert "datum_identifier" not in source
    assert source.count("add_frame_datum_feature(") == 2
    assert 'datum="A"' in source
    assert source.count('datum="B"') == 1
    assert source.count('datum="C"') == 1
    # A is printed first, and B's frame (to A) before C's stack (to A|B).
    assert source.index('datum="A"') < source.index('datum="B"') < source.index(
        'datum="C"'
    )
    slot = source[source.index("    slot_frame = add_feature_control_frame(") :]
    slot = slot[: slot.index("    # The bore:")]
    assert (
        "        edge_xy=slot_wall,\n"
        "        leader_attach_xy=slot_wall,\n"
        "        frame_xy=SLOT_FRAME_XY,\n"
        '        characteristic="position",\n'
        '        tolerance=GEOMETRIC_TOLERANCES_IN["dowel slot position"],\n'
        '        datums=("A", "B"),\n'
        "        lower_frame=(\n"
        '            "perpendicularity",\n'
        '            GEOMETRIC_TOLERANCES_IN["dowel slot perpendicularity"],\n'
        '            ("A",),\n'
        "        ),\n"
    ) in slot
    assert (
        "    add_frame_datum_feature(\n"
        "        adapter,\n"
        "        top,\n"
        "        slot_frame,\n"
        '        datum="C",\n'
        "        symbol_xy=SLOT_DATUM_C_XY,\n"
    ) in slot
    assert "position_tolerance_m" not in slot
    # The sheet fails unless every frame's datum is printed, over every view
    # a frame or tag stands in.
    assert (
        "assert_frame_datums_defined(\n        (front, right, top, section),"
    ) in source
    assert source.index("assert_frame_datums_defined(") > source.rindex(
        "add_frame_datum_feature("
    )
    # The slot's width to A|B, with ⊥ to A stacked under it (widths: planar
    # zones, no Ø); B's hole ⊥Ø to A (a cylindrical zone); the bore's and the
    # tap's Ø zones to A|B|C.  The bore's is composite (owner ruling
    # 2026-10-27, #2016): Ø0.20 over a Ø0.05 refinement to the same A|B|C,
    # whose datums only orient, holding the axis to A and clocking it to the
    # B-C line, the far-end offset the rock budget charges.
    import ast

    frames = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_feature_control_frame"
    ]

    def literal(value: ast.expr) -> object:
        # A GEOMETRIC_TOLERANCES_IN[...] lookup reads as its key.
        if isinstance(value, ast.Subscript):
            return ast.literal_eval(value.slice)
        if isinstance(value, ast.Tuple):
            return tuple(literal(item) for item in value.elts)
        return ast.literal_eval(value)

    by_label = {}
    lower_frames = {}
    for frame in frames:
        keywords = {keyword.arg: keyword.value for keyword in frame.keywords}
        assert set(keywords) <= {
            "edge_xy",
            "leader_attach_xy",
            "frame_xy",
            "characteristic",
            "tolerance",
            "datums",
            "diameter",
            "lower_frame",
            "composite",
            "label",
        }
        label = literal(keywords["label"])
        by_label[label] = (
            literal(keywords["characteristic"]),
            literal(keywords["tolerance"]),
            literal(keywords["datums"]),
            literal(keywords["diameter"]) if "diameter" in keywords else False,
        )
        if "lower_frame" in keywords:
            lower_frames[label] = (
                literal(keywords["lower_frame"]),
                literal(keywords["composite"]) if "composite" in keywords else False,
            )
    assert by_label == {
        "dowel hole perpendicularity": (
            "perpendicularity",
            "dowel hole perpendicularity",
            ("A",),
            True,
        ),
        "dowel slot position": ("position", "dowel slot position", ("A", "B"), False),
        "knife-bore position": (
            "position",
            "knife-bore position",
            ("A", "B", "C"),
            True,
        ),
        "knife-hanger tap position": (
            "position",
            "knife-hanger tap position",
            ("A", "B", "C"),
            True,
        ),
    }
    # A lower frame takes its upper frame's Ø flag (add_feature_control_frame):
    # the slot's stacked ⊥, none; the bore's composite segment, Ø.  The
    # composite segment shares its upper's characteristic (one symbol cell).
    assert lower_frames == {
        "dowel slot position": (
            ("perpendicularity", "dowel slot perpendicularity", ("A",)),
            False,
        ),
        "knife-bore position": (
            ("position", "knife-bore orientation", ("A", "B", "C")),
            True,
        ),
    }
    assert source.count('datums=("A", "B", "C")') == 2
    assert source.count('datums=("A", "B")') == 1
    assert source.count('datums=("A",)') == 1
    assert source.count("lower_frame=") == 2
    assert source.count("composite=True") == 1
    assert "composite_lower" not in source
    assert "quantity=" not in source
    assert "_GTOL_TEXT_CALLOUT_ABOVE" not in source
    for gone in ("PIN_FRAME_QUANTITY", "PIN_SPAN_TEXT_XY", "PIN_DATUM_B_RIM_DEG"):
        assert not hasattr(drawing, gone)
    # The composite readback (_drawing_gdt.add_feature_control_frame): the
    # segments are joined by SetCompositeFrame2(True, 1), which must read
    # back True, and each segment's XML is read back, the lower's shared
    # symbol cell standing for the upper's.
    import _drawing_gdt

    gdt = Path(_drawing_gdt.__file__).read_text(encoding="utf-8")
    assert "gtol.SetCompositeFrame2(True, 1)" in gdt
    assert "if gtol.GetCompositeFrame2(1) is not True:" in gdt
    assert "composite upper segment did not persist" in gdt
    assert "shared_symbol=shared" in gdt
    assert gdt.index("gtol.SetCompositeFrame2(True, 1)") < gdt.index(
        "lower_applied = str(lower.GetSymbolXml()"
    )
    bore_frame = source[source.index("    # The bore: composite position to A|B|C") :]
    bore_frame = bore_frame[: bore_frame.index("    bore_basic = ")]
    assert 'tolerance=GEOMETRIC_TOLERANCES_IN["knife-bore position"],' in bore_frame
    assert "composite=True," in bore_frame
    assert sm_knife_mount_spec.GEOMETRIC_TOLERANCES_IN == {
        "knife-bore position": ".008",
        "knife-bore orientation": ".002",
        "knife-hanger tap position": ".005",
        "dowel slot position": ".002",
        "dowel hole perpendicularity": ".0006",
        "dowel slot perpendicularity": ".0006",
    }
    # Owner ruling 2026-10-27 (#2016): the name a sibling's assembly check
    # imports.
    assert sm_knife_mount_spec.DOWEL_HOLE_PERPENDICULARITY_TOL == pytest.approx(0.01524)
    assert sm_knife_mount_spec.DOWEL_SLOT_PERPENDICULARITY_TOL == pytest.approx(0.01524)
    assert sm_knife_mount_spec.KNIFE_BORE_POSITION_TOL == pytest.approx(0.2032)
    assert sm_knife_mount_spec.KNIFE_BORE_ORIENTATION_TOL == pytest.approx(0.0508)
    assert (
        sm_knife_mount_spec.KNIFE_BORE_ORIENTATION_TOL
        < sm_knife_mount_spec.KNIFE_BORE_POSITION_TOL
    )
    assert sm_knife_mount_spec.STUD_TAP_POSITION_TOL == pytest.approx(0.127)
    assert sm_knife_mount_spec.SLOT_POSITION_TOL == pytest.approx(0.0508)
    # The composite refinement is an extra GD&T row: the package declares it
    # (drawing-simplicity-policy.md, GD&T allowlist), citing the ruling.
    declared = _config.parts("sm-knife-mount")["machinist_exceptions"]
    composite_accepts = [
        entry
        for entry in declared
        if entry["kind"] == "accept" and "composite" in entry["where"]
    ]
    assert len(composite_accepts) == 1
    assert "2026-10-27" in composite_accepts[0]["reason"]
    assert "#2016" in composite_accepts[0]["reason"]
    # Sheet-added: the block depth, the tap axis's station from B's axis and
    # the bore centre's height under A (both BASIC), and B's two face
    # locations; B's Ø, the slot's width and end station and the shared
    # depth are marked model dimensions (DRAWING_DIMENSIONS).
    assert source.count("add_edge_dimension(") == 5
    assert source.count("set_basic_dimension(") == 2
    assert "dowel hole span" not in source
    assert (
        'set_basic_dimension(adapter, station, label="dowel hole from tap axis")'
        in source
    )
    assert (
        'set_basic_dimension(adapter, bore_basic, label="knife-bore centre from top seat")'
        in source
    )


@pytest.mark.parametrize(
    ("label", "basic"),
    (
        ("knife-bore centre from top seat", part.BORE_CENTRE_DEPTH),
        ("dowel hole from tap axis", sm_knife_mount_spec.PIN_HOLE_X),
    ),
)
def test_each_basic_prints_the_modelled_value_unrounded(label: str, basic: float) -> None:
    # A BASIC is exact: the sheet measures it off the model (1e-5 gate) and
    # its places must print that value, not a rounding of it.  48ad988c6
    # checked the bore height against the spec's 14.87 mirror (20.62) at
    # .XX; the model measured 20.616, and the leaf failed.  The inch sheet
    # prints it at .XXX, so it must be an exact thousandth of an inch.
    places = sm_knife_mount_spec.DRAWING_REFERENCE_PRECISION[label]
    assert abs(round(basic / 25.4, places) * 25.4 - basic) < 1e-9
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from build_sm_knife_mount import BORE_CENTRE_DEPTH" in source
    assert not hasattr(sm_knife_mount_spec, "BORE_CENTRE_DEPTH")


def test_bore_basic_is_the_built_geometry() -> None:
    assert part.BORE_CENTRE_DEPTH == part.BLK_TOP - part.BORE_CY
    assert part.BORE_CENTRE_DEPTH == pytest.approx(20.5994, abs=1e-9)
    assert f"{part.BORE_CENTRE_DEPTH / 25.4:.3f}" == "0.811"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("sm-knife-mount")
    # ch18 p.42 (2026-09-02): unpainted heat-treated steel, not brass.  The
    # SolidWorks library material stays the generic steel (density); the
    # title block's MATERIAL cell names the hardenable grade the finish
    # needs (ENFORCE review, 2026-10-24, rule 2).
    assert part.MATERIAL == "Plain Carbon Steel"
    assert config["material"] == "AISI O1 tool steel"
    assert config["material_specification"] == "AISI O1 tool steel"
    # drawing-guidelines.md rule 2 (the title block is the general specification): the heat treatment and the bare surface are the Finish field's,
    # stated once there (the sheet has no notes block), with the state the
    # slip bands are inspected in (T+H3: cut soft, hardening's growth inside
    # the band).
    finish = config["finish"]
    assert "58-60 HRC" in finish
    assert "unpainted" in finish
    assert "after hardening" in finish
    assert "Brass" not in config["material_specification"]
    assert int(config["quantity"]) == 2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_color(adapter, HARDENED_STEEL)" in source
    assert part.HARDENED_STEEL == (0.30, 0.30, 0.31)


def test_close_bore_clears_the_hex_trunnion_only_at_the_ridge() -> None:
    import math

    from sm_summing_lever_spec import HEX_H, HEX_W

    assert part.R_BORE == pytest.approx(5.9944)  # Ø.4720
    assert abs(part.BLK_BOT - (-14.852)) < 1e-9
    assert abs(part.BORE_CY - (-5.7334)) < 1e-9
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
    # (R3: no third place; bare, the .XX row's +/-0.51 would give a 10.16
    # deepest thread the 11.19 shallowest drill clears by under a pitch) and
    # its shallowest 9.52 still holds 1.5 D and the bolt's 9.07 longest
    # fit-up reach; the drill runs 1.5 pitch past it nominally and
    # carries the explicit +/-0.05 the 2.0 crown web leaves, 11.24, on the
    # native callout (the summing-lever bracket-tap precedent), still one
    # 1.058 pitch past the deepest thread at worst.  Rule 3: the #25 pilot
    # prints its drill's name, no Ø and no band, so the DRILLED HOLES row
    # governs it (R3: its native +0.10/0 restated that row; R4: its three
    # places claimed a precision no drill holds).
    bands = drawing.TAP_CALLOUT_BANDS
    assert set(bands) == {"hw-threaddepth", "hw-tapdrldepth"}
    assert bands["hw-threaddepth"][0] == pytest.approx(9.525)  # .375
    assert bands["hw-threaddepth"][1] == pytest.approx((0.127, -0.127))
    assert bands["hw-tapdrldepth"][0] == pytest.approx(11.1252)  # .438
    assert bands["hw-tapdrldepth"][1] == pytest.approx((0.0508, -0.0508))
    # swTolType_e: both bands symmetric (4), each (lower, upper) as
    # SolidWorks takes it; a one-sided band would write bilateral (2).
    assert drawing.tap_callout_tolerance((0.127, -0.127)) == (4, -0.127, 0.127)
    assert drawing.tap_callout_tolerance((0.0508, -0.0508)) == (4, -0.0508, 0.0508)
    assert drawing.tap_callout_tolerance((0.10, 0.0)) == (2, 0.0, 0.10)
    from build_sm_summing_assembly import HANGER_REACH_MAX

    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_MIN > HANGER_REACH_MAX
    assert sm_knife_mount_spec.STUD_THREAD == "#10-24"
    assert sm_knife_mount_spec.STUD_TAP_DIA == pytest.approx(3.797)
    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_BAND == pytest.approx(0.127)
    pitch = sm_knife_mount_spec.STUD_PITCH
    assert pitch == pytest.approx(25.4 / 24.0)
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT == pytest.approx(1.6002)
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT >= 1.5 * pitch
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT_MIN == pytest.approx(1.4224)
    assert sm_knife_mount_spec.STUD_TAP_RUNOUT_MIN >= pitch
    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.398)
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
    assert "hw-tapdrldia" not in body
    assert "if required:" in body
    assert "_prove_tap_point(points[0])" in body


def test_tap_crown_web_charges_a_pilot_wider_than_accepted_at_its_sharpest_point() -> None:
    # The pilot, the #25 drill under the title block's DRILLED HOLES row,
    # accepts Ø3.7973-3.8989 (the row on the drill's true 0.1495 in).  The
    # crown web charges more, Ø3.924 (the wizard's Ø3.797 plus the larger of
    # that row and the general .XXX): a conservative envelope, charged, not
    # accepted.
    # The point, dimensioned 118° on the callout, takes the title block's
    # angular +/-1: its sharpest, 117°, stands tallest.
    from _printed_tolerance import angular_band_deg, drilled_oversize_mm

    spec = sm_knife_mount_spec
    assert spec.STUD_TAP_DRILL == "#25"
    assert spec.STUD_TAP_DRILL_IN == 0.1495
    assert round(spec.STUD_TAP_DRILL_IN * 25.4, 3) == spec.STUD_TAP_DIA == 3.797
    assert spec.STUD_TAP_DRILL in spec.TAP_DRILL_CALLOUT.split()
    assert "DRILL" in spec.TAP_DRILL_CALLOUT.split()
    assert f"{spec.STUD_TAP_DIA:g}" not in spec.TAP_DRILL_CALLOUT
    assert not hasattr(spec, "STUD_TAP_DIA_PLACES")
    oversize = drilled_oversize_mm(unit=spec.UNIT)
    assert oversize == pytest.approx(0.1016)
    assert spec.STUD_TAP_DIA_BAND == (oversize, 0.0)
    assert spec.STUD_TAP_DRILL_DIA == pytest.approx(0.1495 * 25.4, abs=1e-12)
    assert spec.STUD_TAP_DIA_ACCEPTED == pytest.approx((3.7973, 3.8989), abs=1e-9)
    assert spec.STUD_TAP_DIA_ACCEPTED[1] > spec.STUD_TAP_DIA + oversize
    assert spec.STUD_TAP_DIA_MAX == pytest.approx(3.924)
    assert spec.STUD_TAP_DIA_MAX - max(spec.STUD_TAP_DIA_ACCEPTED) == pytest.approx(
        0.0251, abs=1e-9
    )
    assert spec.STUD_TAP_DIA_OVERSIZE == pytest.approx(0.127)
    assert angular_band_deg(unit=spec.UNIT) == pytest.approx(1.0)
    assert spec.STUD_TAP_POINT_ANGLE_DEG == 118.0
    assert spec.STUD_TAP_POINT_ANGLE_PLACES == 0
    assert spec.STUD_TAP_POINT_ANGLE_TOL_DEG == angular_band_deg(unit=spec.UNIT)
    assert spec.STUD_TAP_POINT_ANGLE_MIN_DEG == pytest.approx(117.0)
    assert spec.STUD_TAP_POINT_H == pytest.approx(
        3.924 / 2.0 / math.tan(math.radians(117.0 / 2.0))
    )
    assert spec.STUD_TAP_DRILL_DEPTH_MAX == pytest.approx(11.176)
    # The bore's Ø.008 location zone charges 0.1016 of crown (owner ruling
    # 2026-10-27, #2016).
    assert spec.STUD_TAP_WEB_WORST == pytest.approx(2.1098448537, abs=1e-9)
    assert part._TAP_WEB_WORST == pytest.approx(2.1098448537, abs=1e-9)
    assert part._TAP_WEB_WORST >= spec.STUD_TAP_WEB_MIN == pytest.approx(2.032)
    # The nominal pilot at an exact 118 deg overstated the web.
    assert spec.tap_web_worst(
        part.BLK_TOP,
        spec.STUD_TAP_DRILL_DEPTH,
        spec.STUD_TAP_DIA,
        drill_dia_oversize=0.0,
        point_angle_deg=118.0,
    ) > part._TAP_WEB_WORST


def test_tap_point_rides_the_native_definitions_and_the_reason_names_the_mate() -> None:
    # The installed calloutformat.txt's blind tap.
    drill_row = "<MOD-DIAM> <hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>"
    thread_row = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"
    before = {
        5: f"{drill_row}\n{thread_row}",
        6: "",
        7: "",
        8: "",
    }
    wanted = drawing.tap_callout_definitions(before)
    # The drill is named in its native size run's place; the class rides the
    # title block's thread row: the variable and its separator go, the
    # description and the full thread stay; the reason row is the below
    # definition.
    assert wanted == {
        **before,
        5: (
            f"{drawing.TAP_DRILL_CALLOUT} <HOLE-DEPTH> <hw-tapdrldepth> X <hw-drlang>\n"
            "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
        ),
        8: drawing.TAP_CALLOUT_REASON,
    }
    assert drawing.tap_callout_definitions(
        {**before, 5: before[5].replace(" <hw-threadclass>", "-<hw-threadclass>")}
    ) == wanted
    assert drawing.tap_callout_definitions(
        {**before, 5: before[5].replace("<MOD-DIAM> ", "<MOD-DIAM>")}
    ) == wanted
    # Rule 4: the full thread's band names its function and its mate, the
    # registry's bolt, once, on the row under the thread.
    assert sm_knife_mount_spec.BOLT_NUMBER == _config.parts("sm-vn-knife-hanger-stud")[
        "number"
    ]
    reason = sm_knife_mount_spec.TAP_CALLOUT_REASON
    assert reason.count(sm_knife_mount_spec.BOLT_NUMBER) == 1
    assert "TIP CLEARANCE" in reason
    assert len(reason.splitlines()) == 1
    assert not hasattr(sm_knife_mount_spec, "TAP_CALLOUT_PROCESS")
    assert not hasattr(drawing, "TAP_CALLOUT_PROCESS")
    assert drawing._CALLOUT_BELOW_DEFINITION == 8
    assert drawing._CALLOUT_DEFINITION_PARTS[8] == 4
    assert drawing.TAP_POINT_ANGLE_VARIABLE == "hw-drlang"
    assert drawing.TAP_DRILL_DIA_VARIABLE == "hw-tapdrldia"
    assert drawing._CALLOUT_ANGLE_VARIABLE == 2
    assert drawing._DRILL_ANGLE_VARIABLE == 16
    for bad in (
        {**before, 5: thread_row},
        {**before, 6: drill_row},
        {**before, 5: before[5].replace("<MOD-DIAM> <hw-tapdrldia>", "<hw-tapdrldia>")},
        {**before, 6: "<MOD-DIAM> <hw-tapdrldia>"},
        {**before, 6: drawing.TAP_DRILL_CALLOUT},
        {**before, 6: drawing.TAP_CALLOUT_REASON},
        {**before, 8: "FOR MHA-SM-VN-52 HEX BOLT"},
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
    # The #25 stands for the feature's own drill: its native Ø is read back
    # before the size run is replaced.
    assert body.index("_prove_tap_drill(callout)") < body.index("callout.SetText(")
    body = source[source.index("def _prove_tap_drill(") :]
    body = body[: body.index("\ndef ")]
    assert "callout.GetHoleCalloutVariables()" in body
    assert '_early_bound(raw, "ICalloutLengthVariable").Length' in body
    assert "TAP_DRILL_DIA_VARIABLE" in body
    assert "abs(diameters[0] - STUD_TAP_DIA) > _TAP_DRILL_DIA_READBACK_TOL" in body
    assert drawing._TAP_DRILL_DIA_READBACK_TOL == 0.0005
    assert abs(0.1495 * 25.4 - 3.797) < drawing._TAP_DRILL_DIA_READBACK_TOL
    assert abs(3.80 - 3.797) > drawing._TAP_DRILL_DIA_READBACK_TOL
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


def test_datum_b_is_located_from_the_side_and_front_faces() -> None:
    # Machinist review B1: the span located the dowels only to each other.
    # Datum B's axis stands 5.07 .XX from the +X face, a row above the slot
    # end's station over the top view; the row 7.0 .X from the front face,
    # right of the view, past the A-A cutting line's +X end.  Both measure
    # B's hole.
    assert sm_knife_mount_spec.PIN_HOLE_SIDE_DISTANCE == pytest.approx(
        sm_knife_mount_spec.BLK_HALF_X - sm_knife_mount_spec.PIN_HOLE_X
    )
    assert sm_knife_mount_spec.HOLE_ROW_FACE_DISTANCE == pytest.approx(
        sm_knife_mount_spec.SUPPORT_Z_THICK / 2.0
    )
    top_view_top = drawing.TOP_CENTER[1] + drawing.TOP_HALF_Z
    side_x, side_y = drawing.PIN_SIDE_TEXT_XY
    end_x, end_y = drawing.SLOT_END_TEXT_XY
    assert drawing.TOP_KEEP["SlotEndFromB"] == drawing.SLOT_END_TEXT_XY
    assert end_y > top_view_top
    assert side_y - end_y == pytest.approx(0.006)
    assert drawing._sheet_x(sm_knife_mount_spec.PIN_HOLE_X) < side_x
    assert side_x < drawing._sheet_x(sm_knife_mount_spec.BLK_HALF_X)
    # The slot end's value stands between its two centres, B's and the
    # slot's inner end's.
    inner_end_x = sm_knife_mount_spec.PIN_HOLE_X - sm_knife_mount_spec.SLOT_END_FROM_B
    assert drawing._sheet_x(inner_end_x) < end_x < drawing._sheet_x(
        sm_knife_mount_spec.PIN_HOLE_X
    )
    row_x, row_y = drawing.ROW_FACE_TEXT_XY
    section_end_x = drawing._sheet_x(
        sm_knife_mount_spec.BLK_HALF_X + drawing.SECTION_LINE_OVERRUN_MM
    )
    assert row_x > section_end_x
    assert drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z < row_y < drawing.TOP_CENTER[1]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '_set_sheet_precision(side, label="dowel hole from side face")' in source
    assert '_set_sheet_precision(row, label="hole row from front face")' in source
    for label in ("dowel hole from side face", "hole row from front face"):
        assert source.count(f'label="{label}"') == 3
    # Both pick B's rim, on the +X side of its axis.
    assert "(PIN_HOLE_X + pin_rim_mm) / 1000.0," in source
    assert source.count("        p1=b_pick,\n") == 2


def test_the_tap_and_bore_axis_is_basic_from_datum_b() -> None:
    # Machinist review (2026-10-10): the tap frame and the bore's frames
    # reference B, but their offset from B was only the implied centre.  The
    # tap axis, run on through the bore's centre in section A-A, stands BASIC
    # 7.632 from datum B's axis (+X); its boxed value parks right of that
    # axis, over the section's top seat.
    import sm_vn_knife_mount_dowel_spec as dowel

    assert sm_knife_mount_spec.PIN_HOLE_X == dowel.HANGER_OFFSET
    assert sm_knife_mount_spec.DRAWING_REFERENCE_PRECISION[
        "dowel hole from tap axis"
    ] == dowel.HANGER_OFFSET_PLACES
    section_top = drawing._section_y(sm_knife_mount_spec.BLK_TOP)
    pin_x = drawing._section_x(sm_knife_mount_spec.PIN_HOLE_X)
    text_x, text_y = drawing.TAP_STATION_TEXT_XY
    assert drawing._section_x(0.0) < text_x < pin_x
    assert text_y > section_top
    offset_x, offset_y = drawing.TAP_STATION_OFFSET_XY
    assert offset_y == text_y
    assert offset_x > pin_x
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "    if not pin_axis_x > tap_axis_x:\n" in source
    # The tap's axis reaches past the bore's bottom, B's past its floor,
    # both inside the block.
    assert "(0.0, BORE_CY - R_BORE - SECTION_AXIS_TAIL_MM, 0.0)" in source
    assert "(PIN_HOLE_X, BLK_TOP - PIN_HOLE_DEPTH - SECTION_AXIS_TAIL_MM, 0.0)" in source
    assert (
        sm_knife_mount_spec.BORE_CY
        - sm_knife_mount_spec.R_BORE
        - drawing.SECTION_AXIS_TAIL_MM
        > sm_knife_mount_spec.BLK_BOT
    )
    assert 'entity_types=("SKETCHSEGMENT", "SKETCHSEGMENT")' in source
    assert source.count('label="dowel hole from tap axis"') == 3


def test_the_slip_seats_hold_their_margins_and_webs() -> None:
    # T+H3: the -X pin, at the crossbar's span limits plus B's slip, bears
    # wholly on the slot's straight walls (clocking) and wholly inside the
    # block short of the open mouth; the half-round end stands a web inboard
    # of the mouth; and every web the hole, the slot, the tap and the bore
    # leave holds the 2.0 floor (drawing-guidelines.md rule 17).  Each is
    # recomputed here from the dowel's and the title block's terms.
    import sm_vn_knife_mount_dowel_spec as dowel

    spec = sm_knife_mount_spec
    slip_half = dowel.SLIP_CLEARANCE_MAX / 2.0
    pin_from_b = (
        dowel.SPAN - dowel.SPAN_TOL - slip_half,
        dowel.SPAN + dowel.SPAN_TOL + slip_half,
    )
    assert spec.SLOT_PIN_FROM_B == pytest.approx(pin_from_b, abs=1e-9)
    end_longest = spec.SLOT_END_FROM_B + spec.SLOT_END_TOL
    assert spec.SLOT_PIN_LOCATION_MARGIN == pytest.approx(
        pin_from_b[0] - end_longest, abs=1e-9
    )
    assert spec.SLOT_PIN_LOCATION_MARGIN > 0.0
    face_from_b_min = (2.0 * spec.BLK_HALF_X - spec.BLOCK_SIZE_TOL) - (
        spec.PIN_HOLE_SIDE_DISTANCE + spec.PIN_HOLE_SIDE_TOL
    )
    assert spec.SLOT_MOUTH_PIN_MARGIN == pytest.approx(
        face_from_b_min - pin_from_b[1] - dowel.DIA_MAX / 2.0, abs=1e-9
    )
    assert spec.SLOT_MOUTH_PIN_MARGIN > 0.0
    slot_half_w_max = (spec.SLOT_WIDTH + max(spec.SLOT_WIDTH_BAND)) / 2.0
    assert spec.SLOT_END_TO_MOUTH == pytest.approx(
        face_from_b_min - end_longest - slot_half_w_max, abs=1e-9
    )
    assert spec.SLOT_END_TO_MOUTH >= spec.STUD_TAP_WEB_MIN == pytest.approx(2.032)
    for web in (
        spec.PIN_HOLE_SIDE_WEB,
        spec.PIN_HOLE_Z_WEB,
        spec.SLOT_CHEEK_WEB,
        spec.PIN_HOLE_TAP_WEB,
        spec.SLOT_TAP_WEB,
        spec.PIN_HOLE_BORE_WEB,
        spec.SLOT_BORE_WEB,
        spec.STUD_TAP_Z_WALL,
        spec.BORE_SIDE_WEB,
        spec.BORE_BOTTOM_WALL,
        spec.STUD_TAP_WEB_WORST,
        part._TAP_WEB_WORST,
    ):
        assert web >= 2.0
    # The slot end's shortest limit keeps its half-round end clear of the
    # tap's thread by that web, recomputed.
    tip_from_b_min = spec.SLOT_END_FROM_B - spec.SLOT_END_TOL - slot_half_w_max
    assert spec.SLOT_TAP_WEB == pytest.approx(
        tip_from_b_min
        - (spec.PIN_HOLE_X + spec.STUD_TAP_POSITION_TOL / 2.0)
        - spec.STUD_THREAD_MAJOR / 2.0,
        abs=1e-9,
    )
    # The slip band holds the dowel at 0.02..0.10 diametral clearance.
    assert 0.02 <= dowel.SLIP_CLEARANCE_MIN < dowel.SLIP_CLEARANCE_MAX <= 0.10
    assert spec.PIN_HOLE_DIA == spec.SLOT_WIDTH == dowel.SLIP_HOLE_DIA
    assert spec.PIN_HOLE_DIA_BAND == spec.SLOT_WIDTH_BAND == dowel.SLIP_HOLE_DIA_BAND


def test_the_bore_states_its_bored_band_and_mate() -> None:
    # Machinist review B3: a bare THRU left drill or ream open; the bore is
    # bored to Ø.4720 +.0012/0 (S3: a boring head, not a ream; Ra 63 µin
    # stays).  ENFORCE review (2026-10-24, rule 4): the band names its mate,
    # the lever's trunnion.  The process word and the mate's number, the
    # lever's from the registry; three rows, the ones BORE_DIA_TEXT_TOP_REACH
    # was measured on under the stacked band (farm run 20261024T114146582Z).
    rows = drawing.DIMENSION_CALLOUTS["BoreDia"].splitlines()
    assert "BORE" in rows[0].split()
    assert "REAM" not in drawing.DIMENSION_CALLOUTS["BoreDia"]
    # The mate's number is drawing text: the spec, in MHA-FR-02's and the
    # frame assembly's import closure, must not read the lever's registry row.
    lever_number = _config.parts("sm-summing-lever")["number"]
    assert drawing.LEVER_NUMBER == lever_number
    assert not hasattr(sm_knife_mount_spec, "LEVER_NUMBER")
    assert not hasattr(sm_knife_mount_spec, "BORE_CALLOUT")
    assert "sm-summing-lever" not in Path(sm_knife_mount_spec.__file__).read_text(
        encoding="utf-8"
    )
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].count(lever_number) == 1
    assert len(rows) <= 3
    widest = max(len(row) for row in rows)
    assert drawing.BORE_DIA_TEXT_HALF_WIDTH >= widest * 0.00252 / 2.0
    assert sm_knife_mount_spec.BORE_DIA_BAND == pytest.approx((0.03048, 0.0))
    assert sm_knife_mount_spec.BORE_R_MIN == sm_knife_mount_spec.R_BORE
    assert sm_knife_mount_spec.BORE_R_MAX == pytest.approx(6.00964)
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
