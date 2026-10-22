"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_sm_knife_mount as part
import draw_sm_knife_mount as drawing
import sm_knife_mount_interface as mount_interface
import sm_knife_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm


@pytest.fixture
def native_dimension_factory(monkeypatch):
    """Stateful native interfaces: exercise the real callout/BASIC helpers."""
    from types import SimpleNamespace

    import _drawing_dimensions as dimensions

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        dimensions._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_interfaces: value,
    )
    rebuilds = []
    adapter = SimpleNamespace(
        _attempt=lambda operation, **_options: operation(),
        _get_attr_or_call=lambda value, name: getattr(value, name),
        currentModel=SimpleNamespace(EditRebuild3=lambda: rebuilds.append(True)),
    )

    class NativeDimension:
        def __init__(self, name, value, band):
            self.Name = name
            self.SystemValue = value
            self.band = band
            self.tolerance_type = 4

        def SetToleranceType(self, tolerance_type):
            self.tolerance_type = tolerance_type
            return True

        def GetToleranceType(self):
            return self.tolerance_type

    class NativeDisplay:
        def __init__(self, name, value, band, retain_offset, accept_position):
            self.dimension = NativeDimension(name, value, band)
            self.text = {4: "previous callout"}
            self.offset = True
            self.retain_offset = retain_offset
            self.accept_position = accept_position
            self.position = (0.0, 0.0, 0.0)
            self.line_position = self.position

        @property
        def OffsetText(self):
            return self.offset

        @OffsetText.setter
        def OffsetText(self, offset):
            if not self.retain_offset:
                self.offset = bool(offset)

        def GetDimension(self):
            return self.dimension

        def GetSpecificAnnotation(self):
            return self

        def GetAnnotation(self):
            return self

        def SetText(self, part, text):
            self.text[part] = text

        def GetText(self, part):
            return self.text.get(part, "")

        def SetPosition2(self, x, y, z):
            if not self.accept_position:
                return False
            self.position = (x, y, z)
            if not self.offset:
                self.line_position = self.position
            return True

    def make(name, value, band=(0.0, 0.0), *, retain_offset=False, accept_position=True):
        return NativeDisplay(name, value, band, retain_offset, accept_position)

    return adapter, make, rebuilds


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
    assert start[0] < -mount_interface.BLK_HALF_X
    assert end[0] > mount_interface.BLK_HALF_X
    assert start[0] < -mount_interface.PIN_HOLE_X < 0.0 < mount_interface.PIN_HOLE_X < end[0]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("create_section_view(") == 1
    assert "_look_section_along_minus_z(adapter, section)" in source
    assert "set_hidden_lines_removed(adapter, section)" in source
    # Section before top: the MHA-PD-18 import order.
    assert source.index("keep=SECTION_KEEP") < source.index("keep=TOP_KEEP")
    # The depth text stands right of the cut block, level with the hole.
    x, y = drawing.SECTION_KEEP["PinHoleDepth"]
    scale = drawing.SHEET_SCALE[0] / 1000.0
    assert x > drawing.SECTION_CENTER[0] + mount_interface.BLK_HALF_X * scale
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
    face_x = drawing._sheet_x(mount_interface.BLK_HALF_X)
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
    # R4: no tap tool is named (the full thread's depth says how deep), and
    # the bolt is named once, on the reason row.
    assert "process=" not in source
    assert "BOTTOMING TAP" not in "".join(
        str(value)
        for value in vars(sm_knife_mount_spec).values()
        if isinstance(value, str)
    )
    assert drawing.TAP_DRILL_CALLOUT is sm_knife_mount_spec.TAP_DRILL_CALLOUT
    assert drawing.TAP_DRILL_CALLOUT == "#25 DRILL"
    assert drawing.TAP_CALLOUT_REASON is sm_knife_mount_spec.TAP_CALLOUT_REASON
    assert drawing.TAP_CALLOUT_REASON == "SETS MHA-SM-VN-52 TIP CLEARANCE"
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
    assert wanted[7] == "#25 DRILL <HOLE-DEPTH> <hw-tapdrldepth> X <hw-drlang>"
    assert wanted[5] == "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
    assert wanted[8] == "SETS MHA-SM-VN-52 TIP CLEARANCE"
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
    # The widest row is now the reason, "SETS MHA-SM-VN-52 TIP CLEARANCE":
    # 16.13 em of Century Gothic at the 4.83 mm an em the run's drill row gave
    # (15.97 em printed 77.1 mm, its +0.10 stack included), ~78 mm, inside the
    # half width's 88.  The drill row, "#25 DRILL" in Ø3.797's place and no
    # stack, is ~14.6 em.
    run_width = RUN_CALLOUT_SPAN_X[1] - RUN_CALLOUT_SPAN_X[0]
    assert run_width == pytest.approx(0.0771)
    reason_width = 16.13 * run_width / 15.97
    assert reason_width == pytest.approx(0.0779, abs=1e-4)
    assert 2.0 * drawing.TAP_CALLOUT_HALF_WIDTH >= reason_width + 0.005


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
    # that run's printed ones (sheet metres); the frame's elbow stood 6.35 mm
    # left of its left end, at its middle height, its top then 6 mm under the
    # Ø's shoulder start.  The frame has since dropped to PIN_FRAME_DROP under
    # it (room for its above-frame 2X), its elbow with it.
    from _layout_audit import _segment_crossing
    from _layout_geometry import Segment

    run_dia_tip, run_dia_shoulder = (0.13275, 0.23301), (0.14640, 0.22221)
    run_frame_tip, run_frame_elbow = (0.13268, 0.23294), (0.14164, 0.21548)
    assert math.dist(run_dia_tip, run_frame_tip) < 0.0002
    frame_left, frame_top = drawing.PIN_FRAME_XY
    run_frame_top = drawing.PIN_CALLOUT_SHOULDER_START[1] - 0.006
    run_elbow = (frame_left - 0.00635, run_frame_top - drawing.PIN_FRAME_SIZE[1] / 2.0)
    assert math.dist(run_elbow, run_frame_elbow) < 0.0003
    assert run_frame_top - frame_top == pytest.approx(0.005)
    elbow = (frame_left - 0.00635, frame_top - drawing.PIN_FRAME_SIZE[1] / 2.0)
    centre = (drawing._sheet_x(mount_interface.PIN_HOLE_X), drawing.TOP_CENTER[1])
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
    face_x = drawing._sheet_x(-mount_interface.BLK_HALF_X)
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
    # The block's width is the spec's alone: the build imports it.
    assert mount_interface.BLK_HALF_X == part.BLK_HALF_X == 12.7
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
    assert mount_interface.PIN_HOLE_X == 7.632
    assert mount_interface.PIN_HOLE_XS == (-7.632, 7.632)
    assert mount_interface.PIN_HOLE_SPAN == 15.264
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
    # (MHA-PD-18 precedent); their position frame hangs under the callout.
    assert drawing.CALLOUTS_ABOVE == {"PinHoleDia": "2X"}
    assert sm_knife_mount_spec.PIN_HOLE_CALLOUT.splitlines() == [
        "BLIND FLAT-BOTTOM REAM",
        "PRESS MHA-SM-VN-53 DOWEL TO FLOOR",
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


def test_knife_geometry_controls_retain_their_position_and_orientation_bands() -> None:
    assert sm_knife_mount_spec.GEOMETRIC_TOLERANCES_MM == {
        "knife-bore position": "0.20",
        "knife-bore perpendicularity": "0.05",
        "knife-hanger tap position": "0.15",
        "dowel hole pattern position": "0.13",
    }
    assert sm_knife_mount_spec.KNIFE_BORE_ORIENTATION_TOL == 0.05
    assert mount_interface.PIN_HOLE_COUNT == 2


def test_dowel_frame_quantity_and_datum_have_geometric_clearance() -> None:
    # Retained native calibration: quantity above the frame, datum below it.
    from _layout_audit import TEXT_SEPARATION_HEIGHTS

    assert drawing.PIN_CALLOUT_SHOULDER_PRINTED_Y == pytest.approx(0.22221)
    assert drawing.PIN_FRAME_QUANTITY_TOP == pytest.approx(
        drawing.PIN_FRAME_XY[1] + 0.0011 + 0.0034
    )
    assert drawing.PIN_FRAME_QUANTITY_TOP_CLEARANCE == pytest.approx(0.00371)
    assert drawing.PIN_FRAME_QUANTITY_TOP_CLEARANCE >= TEXT_SEPARATION_HEIGHTS * 0.0035
    assert drawing.PIN_FRAME_QUANTITY_SECTION_CLEARANCE == pytest.approx(0.0165)
    section_end_x = drawing._sheet_x(
        mount_interface.BLK_HALF_X + drawing.SECTION_LINE_OVERRUN_MM
    )
    assert drawing.PIN_FRAME_XY[0] - section_end_x == pytest.approx(0.0026)
    assert drawing.PIN_DATUM_B_XY[0] - drawing.DATUM_TAG_BOX / 2.0 == pytest.approx(
        drawing.PIN_FRAME_XY[0] + 0.0112
    )
    assert drawing.PIN_DATUM_B_XY[1] == pytest.approx(
        drawing.PIN_FRAME_XY[1] - drawing.PIN_FRAME_SIZE[1] - 0.005 - 0.007
    )


@pytest.mark.parametrize(
    ("label", "basic"),
    (
        ("knife-bore centre from top seat", part.BORE_CENTRE_DEPTH),
        ("dowel hole span", mount_interface.PIN_HOLE_SPAN),
        ("dowel hole from tap axis", mount_interface.PIN_HOLE_X),
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


def test_title_material_uses_the_existing_manufacturing_specification(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    material = _config.parts("sm-knife-mount")["material_specification"]
    generic_link = drawing.property_link("Material")
    specification_link = drawing.property_link("Material Specification")
    note = SimpleNamespace(PropertyLinkedText=f"MATERIAL: {generic_link}")
    note.GetText = lambda: note.PropertyLinkedText.replace(specification_link, material)
    finish = SimpleNamespace(PropertyLinkedText=drawing.property_link("Finish"))
    annotations = [
        SimpleNamespace(GetType=lambda: 6, GetSpecificAnnotation=lambda: note),
        SimpleNamespace(GetType=lambda: 6, GetSpecificAnnotation=lambda: finish),
    ]
    rebuilds = []
    model = SimpleNamespace(
        GetFirstView=lambda: SimpleNamespace(GetAnnotations=lambda: annotations),
        ForceRebuild3=lambda top_only: rebuilds.append(top_only),
    )
    binding = drawing._bind_title_material_specification(model, material)
    assert note.PropertyLinkedText == f"MATERIAL: {specification_link}"
    assert finish.PropertyLinkedText == drawing.property_link("Finish")
    drawing._verify_title_material_specification(model, binding)
    assert rebuilds == [False]
    note.GetText = lambda: "MATERIAL: Plain Carbon Steel"
    with pytest.raises(RuntimeError, match="material title link did not resolve"):
        drawing._verify_title_material_specification(model, binding)


@pytest.mark.parametrize("material_cells", (0, 2))
def test_title_material_refuses_missing_or_duplicate_cells(monkeypatch, material_cells) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    notes = [
        SimpleNamespace(PropertyLinkedText=drawing.property_link("Material"))
        for _ in range(material_cells)
    ]
    annotations = [
        SimpleNamespace(GetType=lambda: 6, GetSpecificAnnotation=lambda note=note: note)
        for note in notes
    ]
    model = SimpleNamespace(
        GetFirstView=lambda: SimpleNamespace(GetAnnotations=lambda: annotations)
    )
    with pytest.raises(RuntimeError, match="exactly one Material property link"):
        drawing._bind_title_material_specification(model, "AISI O1 tool steel")


def test_title_material_refuses_a_blank_specification() -> None:
    with pytest.raises(RuntimeError, match="material specification is blank"):
        drawing._bind_title_material_specification(None, " ")


def test_close_bore_clears_the_hex_trunnion_only_at_the_ridge() -> None:
    import math

    from sm_knife_contact import HEX_H, HEX_W

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
    assert drawing.TAP_CALLOUT_BANDS == {
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
        "hw-threaddepth": 2,
        "hw-tapdrldepth": 2,
    }
    from build_sm_summing_assembly import HANGER_REACH_MAX

    assert sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH_MIN > HANGER_REACH_MAX
    bare_deepest_thread = (
        sm_knife_mount_spec.STUD_TAP_THREAD_DEPTH + printed_band_mm(2)
    )
    shallowest_drill = (
        sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH
        - sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH_BAND
    )
    assert shallowest_drill - bare_deepest_thread == pytest.approx(1.03)
    assert shallowest_drill - bare_deepest_thread < sm_knife_mount_spec.STUD_PITCH
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
    assert "hw-tapdrldia" not in body
    assert "if required:" in body
    assert "_prove_tap_point(points[0])" in body


def test_tap_crown_web_charges_a_pilot_wider_than_accepted_at_its_sharpest_point() -> None:
    # The pilot, the #25 drill under the title block's DRILLED HOLES row,
    # accepts Ø3.7973-3.8973 (the row on the drill's true 0.1495 in).  The
    # crown web charges more, Ø3.927 (the wizard's Ø3.797 plus the larger of
    # that row and the general .XXX): a conservative envelope, charged, not
    # accepted.
    # The point, dimensioned 118° on the callout, takes the title block's
    # angular +/-1: its sharpest, 117°, stands tallest.
    from _printed_angular_tolerance import angular_band_deg
    from _printed_drilled_tolerance import drilled_oversize_mm

    spec = sm_knife_mount_spec
    assert spec.STUD_TAP_DRILL == "#25"
    assert spec.STUD_TAP_DRILL_IN == 0.1495
    assert round(spec.STUD_TAP_DRILL_IN * 25.4, 3) == spec.STUD_TAP_DIA == 3.797
    assert spec.TAP_DRILL_CALLOUT == f"{spec.STUD_TAP_DRILL} DRILL"
    assert not hasattr(spec, "STUD_TAP_DIA_PLACES")
    assert drilled_oversize_mm() == pytest.approx(0.10)
    assert spec.STUD_TAP_DIA_BAND == (drilled_oversize_mm(), 0.0)
    assert spec.STUD_TAP_DRILL_DIA == pytest.approx(0.1495 * 25.4, abs=1e-12)
    assert spec.STUD_TAP_DIA_ACCEPTED == pytest.approx((3.7973, 3.8973), abs=1e-9)
    assert spec.STUD_TAP_DIA_ACCEPTED[1] > spec.STUD_TAP_DIA + drilled_oversize_mm()
    assert spec.STUD_TAP_DIA_MAX == pytest.approx(3.927)
    assert spec.STUD_TAP_DIA_MAX - max(spec.STUD_TAP_DIA_ACCEPTED) == pytest.approx(
        0.0297, abs=1e-9
    )
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
            "#25 DRILL <HOLE-DEPTH> <hw-tapdrldepth> X <hw-drlang>\n"
            "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
        ),
        8: "SETS MHA-SM-VN-52 TIP CLEARANCE",
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
    assert sm_knife_mount_spec.TAP_CALLOUT_REASON == (
        f"SETS {sm_knife_mount_spec.BOLT_NUMBER} TIP CLEARANCE"
    )
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


def test_the_pattern_is_located_from_the_side_and_front_faces() -> None:
    # Machinist review B1: the span located the dowels only to each other.
    # The +X hole's axis stands 5.07 .XX from the +X face, a row above the
    # BASIC span over the top view (clear of the dowel frame's leader under
    # it, and of the span's arrows); the row 7.0 .X from the front face, left
    # of the view.
    assert mount_interface.PIN_HOLE_SIDE_DISTANCE == pytest.approx(
        mount_interface.BLK_HALF_X - mount_interface.PIN_HOLE_X
    )
    assert mount_interface.HOLE_ROW_FACE_DISTANCE == pytest.approx(
        mount_interface.SUPPORT_Z_THICK / 2.0
    )
    top_view_top = drawing.TOP_CENTER[1] + drawing.TOP_HALF_Z
    side_x, side_y = drawing.PIN_SIDE_TEXT_XY
    assert side_y > top_view_top
    assert side_y >= drawing.PIN_SPAN_TEXT_XY[1] + 0.006
    assert drawing._sheet_x(mount_interface.PIN_HOLE_X) < side_x
    assert side_x < drawing._sheet_x(mount_interface.BLK_HALF_X)
    row_x, _ = drawing.ROW_FACE_TEXT_XY
    assert row_x < drawing._sheet_x(-mount_interface.BLK_HALF_X)
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
    # 7.632 from the -X dowel axis; its BASIC box stays between those axes,
    # with native inline text rather than the line-struck outside jog.
    assert mount_interface.PIN_HOLE_X == pytest.approx(
        mount_interface.PIN_HOLE_SPAN / 2.0
    )
    section_top = drawing._section_y(sm_knife_mount_spec.BLK_TOP)
    pin_x = drawing._section_x(-mount_interface.PIN_HOLE_X)
    text_x, text_y = drawing.TAP_STATION_TEXT_XY
    assert pin_x < text_x < drawing._section_x(0.0)
    assert text_y > section_top
    # The tap's axis reaches past the bore's bottom, the dowel's past its
    # floor, both inside the block.
    assert (
        sm_knife_mount_spec.BORE_CY
        - sm_knife_mount_spec.R_BORE
        - drawing.SECTION_AXIS_TAIL_MM
        > sm_knife_mount_spec.BLK_BOT
    )


def test_bore_mate_callout_reaches_the_named_feature_without_changing_its_fit(
    native_dimension_factory,
) -> None:
    adapter, make, _rebuilds = native_dimension_factory
    bore = make("BoreDia", 0.012, band=(0.00003, 0.0))
    pin = make("PinHoleDia", 0.003175, band=(0.0, -0.00001))
    same_size_other_feature = make("UnrelatedDiameter", 0.012)
    original_unrelated_text = same_size_other_feature.GetText(4)
    before = [
        (display.dimension.SystemValue, display.dimension.band, display.dimension.tolerance_type)
        for display in (bore, pin, same_size_other_feature)
    ]
    drawing.set_dimension_callouts(
        adapter, [same_size_other_feature, pin, bore], drawing.DIMENSION_CALLOUTS
    )
    assert _config.parts("sm-summing-lever")["number"] in bore.GetText(4)
    assert sm_knife_mount_spec.DOWEL_NUMBER in pin.GetText(4)
    assert same_size_other_feature.GetText(4) == original_unrelated_text
    assert [
        (display.dimension.SystemValue, display.dimension.band, display.dimension.tolerance_type)
        for display in (bore, pin, same_size_other_feature)
    ] == before
    assert sm_knife_mount_spec.BORE_DIA_BAND == (0.03, 0.0)
    assert sm_knife_mount_spec.BORE_DIA_PLACES == 2
    assert sm_knife_mount_spec.DRAWING_PRECISION["BoreProfile"] == {"BoreDia": 2}
    assert sm_knife_mount_spec.BORE_R_MIN == sm_knife_mount_spec.R_BORE
    assert sm_knife_mount_spec.BORE_R_MAX == pytest.approx(6.015)


def test_basic_station_leaves_offset_mode_and_moves_its_line_with_the_text(
    native_dimension_factory,
) -> None:
    import _drawing_dimensions as dimensions

    adapter, make, rebuilds = native_dimension_factory
    station = make("TapStation", mount_interface.PIN_HOLE_X / 1000.0)
    measured = station.dimension.SystemValue
    drawing._set_inline_tap_station(adapter, station)
    assert station.OffsetText is False
    assert station.position == station.line_position == (*drawing.TAP_STATION_TEXT_XY, 0.0)
    assert station.dimension.GetToleranceType() == dimensions.TOL_BASIC
    assert station.dimension.SystemValue == measured
    assert station.GetText(4) == ""
    assert rebuilds == [True]


@pytest.mark.parametrize(
    "failure", ({"retain_offset": True}, {"accept_position": False})
)
def test_basic_station_refuses_ignored_inline_placement(native_dimension_factory, failure) -> None:
    adapter, make, _rebuilds = native_dimension_factory
    station = make("TapStation", mount_interface.PIN_HOLE_X / 1000.0, **failure)
    with pytest.raises(RuntimeError, match="inline placement"):
        drawing._set_inline_tap_station(adapter, station)
