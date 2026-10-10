"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import ch_fulcrum_keeper_spec as keeper
from vn_fillister_screw_spec import FILLISTER_SIZES
import build_fr_top_frame as part
import draw_fr_top_frame as drawing
from fr_frame_attachment_spec import (
    CAP_MOUTH_Y,
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    CASTING_FULL_THREAD_DEPTH,
    CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER
import fr_top_frame_spec as spec
import fr_tube_frame_spec


def test_nominal_corner_bores_and_cap_recesses_clear_the_installed_stack() -> None:
    assert part.BORE_DIA == COLUMN_SOCKET_DIAMETER == 25.5
    assert part.CAP_RECESS_DIAMETER == CAP_RECESS_DIAMETER
    assert part.CAP_RECESS_DEPTH == CAP_RECESS_DEPTH
    assert CAP_RECESS_DIAMETER > MAX_OUTER_DIAMETER
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE,
        CAP_RECESS_DIAMETER - MAX_OUTER_DIAMETER,
        abs_tol=1e-12,
    )
    assert math.isclose(part.CAP_RECESS_DIAMETRAL_CLEARANCE, 0.436232, abs_tol=1e-6)
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE + part.CAP_RECESS_DIAMETER_BAND[0],
        0.636232,
        abs_tol=1e-6,
    )
    # CAD reference clearance is unchanged; actual sockets are matched to
    # their assigned tubes rather than accepted against a fixed bore band.
    assert math.isclose(
        part.BORE_DIA - fr_tube_frame_spec.OUTER_DIA,
        0.10,
        abs_tol=1e-12,
    )
    assert part.CAP_RECESS_FLOOR_Y - part.SIDE_TAP_DRILL_DIA / 2.0 > 0.0
    assert part.CAP_RECESS_DIAMETER_BAND == (0.20, 0.0)
    assert part.CAP_RECESS_DEPTH_BAND == (0.30, 0.0)
    recess_floor_world = TOP_SCREW_Y + part.CAP_RECESS_FLOOR_Y
    assert math.isclose(CAP_MOUTH_Y - recess_floor_world, 1.50875, abs_tol=1e-9)
    assert math.isclose(
        recess_floor_world - (TOP_SCREW_Y + TUBE_CROSS_HOLE_DIAMETER / 2.0),
        3.95,
        abs_tol=1e-9,
    )


def test_four_cross_taps_are_bottoming_10_32_with_tooling_lead() -> None:
    assert len(part.SIDE_SCREW_XS) * len(part.SIDE_SCREW_FACES) == 4
    assert part.SIDE_TAP_SPEC.kind == "tapped_bottoming"
    assert part.SIDE_TAP_SPEC.size == "#10-32"
    assert part.SIDE_TAP_SPEC.thread_class == "2B"
    assert part.SIDE_TAP_SPEC.depth_mm == CASTING_TAP_DRILL_DEPTH
    assert part.SIDE_TAP_SPEC.overrides_mm["ThreadDepth"] == CASTING_FULL_THREAD_DEPTH
    pitch = 25.4 / 32.0
    assert CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH >= 2.0 * pitch
    assert part.SPOTFACE_FLOOR == TOP_SCREW_SEAT_Z
    full_seat_limit = abs(part.FRONT_COLUMN_Z) + math.sqrt(
        (part.BOSS_DIA / 2.0) ** 2 - (part.SPOTFACE_DIA / 2.0) ** 2
    )
    assert part.SPOTFACE_FLOOR < full_seat_limit


def test_cross_tap_major_thread_and_drill_point_clear_the_far_wall() -> None:
    # The major-thread envelope, not the tap-drill cylinder, is the finished
    # thread breakout check.  The drill point has its own positive-wall guard.
    major_dia = 4.826
    major_far_wall_z = abs(part.FRONT_COLUMN_Z) - math.sqrt(
        (part.BOSS_DIA / 2.0) ** 2 - (major_dia / 2.0) ** 2
    )
    thread_end_z = part.SPOTFACE_FLOOR - CASTING_FULL_THREAD_DEPTH
    drill_point_z = (
        part.SPOTFACE_FLOOR
        - CASTING_TAP_DRILL_DEPTH
        - part.SIDE_TAP_DRILL_DIA / 2.0 * part.DRILL_POINT_H
    )
    drill_far_wall_z = abs(part.FRONT_COLUMN_Z) - part.BOSS_DIA / 2.0
    assert part.SIDE_TAP_THREAD_MAJOR_DIA == major_dia
    assert part.SIDE_TAP_MAJOR_FAR_WALL_Z == major_far_wall_z
    assert part.SIDE_TAP_THREAD_END_Z == thread_end_z
    assert part.SIDE_TAP_DRILL_POINT_Z == drill_point_z
    assert part.SIDE_TAP_DRILL_FAR_WALL_Z == drill_far_wall_z
    assert part.SIDE_TAP_THREAD_WALL_MARGIN > 0.0
    assert part.SIDE_TAP_DRILL_WALL_MARGIN > 0.0


def test_keeper_tap_holds_stock_screw_above_a_plug_tap_lead() -> None:
    major, length, _, _, pitch = FILLISTER_SIZES["90280A194"]
    insertion = length - (keeper.FOOT_H - keeper.CBORE_DEPTH_MM)
    spec = part.KEEPER_TAP_SPEC
    full_thread = spec.overrides_mm.get("ThreadDepth", spec.depth_mm)
    depth_tolerance = float(_config.title_block("linear_2pl")["value_in"]) * 25.4

    assert insertion >= major
    assert full_thread - insertion >= 0.25
    assert spec.depth_mm - full_thread - 2.0 * depth_tolerance >= 5.0 * pitch
    drill_point = part.TAP_DRILL_MM[spec.size] / 2.0 * part.DRILL_POINT_H
    assert spec.depth_mm + depth_tolerance + drill_point < part.RING_HEIGHT
    assert abs(part.KEEPER_TAP_X - part.COLUMN_X) + major / 2.0 < part.WEB_T / 2.0
def test_every_imported_drawing_dimension_has_part_authored_places() -> None:
    # Rule 2: the part owns the decimal places, so a kept model dimension
    # nobody authored places for prints SolidWorks' template default and the
    # sheet has nowhere left to say otherwise.
    kept = set().union(
        drawing.GEOMETRY_TOP_KEEP,
        drawing.GEOMETRY_FRONT_KEEP,
        drawing.DETAIL_TOP_KEEP,
        drawing.DETAIL_FRONT_KEEP,
        drawing.DETAIL_SECTION_KEEP,
        drawing.HUB_TOP_KEEP,
        drawing.HUB_LEFT_KEEP,
        drawing.HANGER_SECTION_KEEP,
    )
    assert kept, "the top-frame sheets import no model dimensions"
    assert not kept - set(spec.DRAWING_PRECISION_BY_NAME)


# --- #946 leader-over-part: RD4 and the cap seat Ra 3.2 -------------------
#
# The sheets are projected here from the model constants, as the build reads
# them through each view's ModelToViewTransform: the half-size plan (+X right,
# +Z down the sheet) and section A-A (+Z right, +Y up).  #946's measure: the
# run over the part from the leader's first model-edge crossing to its tip,
# minus the tip's shortest approach (its distance to the nearest side of the
# view's outline).  Main's brief is ~4 mm (swing's RD2 fix, 4dda16fd5, 3.8).
LEADER_DETOUR_TARGET = 0.004
# The frame's title block (layoutcal2-a dump: x >= 216 mm, y <= 66 mm).
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)
_S = drawing.DETAIL_VIEW_SCALE / 1000.0


def _plan(x: float, z: float) -> tuple[float, float]:
    cx, cy = drawing.DETAIL_TOP_CENTER
    return (cx + x * _S, cy - z * _S)


def _section(z: float, y: float) -> tuple[float, float]:
    cx, cy = drawing.DETAIL_SECTION_CENTER
    return (cx + z * _S, cy + y * _S)


def _keeper_geometry():
    hole = _plan(part.KEEPER_TAP_X, part.KEEPER_TAP_Z_REAR)
    hole_r = part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2.0 * _S
    boss = _plan(part.COLUMN_X, part.REAR_COLUMN_Z)
    boss_r = part.BOSS_DIA / 2.0 * _S
    return hole, hole_r, boss, boss_r


def _segment_circle_entry(start, end, centre, radius):
    """Where the segment start -> end first enters the circle, else None."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    fx, fy = x0 - centre[0], y0 - centre[1]
    a, b, c = dx * dx + dy * dy, 2 * (fx * dx + fy * dy), fx * fx + fy * fy - radius**2
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b - math.sqrt(disc)) / (2 * a)
    return (x0 + t * dx, y0 + t * dy) if 0.0 <= t <= 1.0 else None


def _plan_detour(start, tip):
    """#946's detour of a plan leader reaching the right rail's keeper taps:
    it enters the part through a corner boss or the rail's outer face."""
    face_x = _plan(part.OUTER_X, 0.0)[0]
    entries = [
        _segment_circle_entry(start, tip, _plan(part.COLUMN_X, z), part.BOSS_DIA / 2.0 * _S)
        for z in (part.FRONT_COLUMN_Z, part.REAR_COLUMN_Z)
    ]
    if start[0] > face_x > tip[0]:
        t = (start[0] - face_x) / (start[0] - tip[0])
        entries.append((face_x, start[1] + t * (tip[1] - start[1])))
    entry = min((e for e in entries if e), key=lambda e: math.dist(start, e))
    left, top = _plan(-drawing.PLAN_HALF_X, -drawing.PLAN_HALF_Z)
    right, bottom = _plan(drawing.PLAN_HALF_X, drawing.PLAN_HALF_Z)
    approach = min(tip[0] - left, right - tip[0], tip[1] - bottom, top - tip[1])
    over = math.dist(entry, tip)
    return over, approach, over - approach


def _shoulder_end(callout, tip):
    left, down, right, _up = drawing.KEEPER_CALLOUT_EXTENT
    x = callout[0] - left if tip[0] < callout[0] else callout[0] + right
    return (x, callout[1] - down)


def test_keeper_callout_leader_takes_the_short_way_to_its_tap() -> None:
    """#946 / b49e1: RD4 stood above the front keeper tap's boss and its
    leader crossed the boss and bore rings: 29.6 mm over the part, 18.3 mm
    past the tap's approach.  It now reads off the rear tap from the rail's
    outer side, under REAR KEEPER Z's extension line, clear of the boss."""
    hole, hole_r, boss, boss_r = _keeper_geometry()
    callout, tip = drawing.keeper_callout_placement(hole, hole_r, boss, boss_r)
    assert math.dist(tip, hole) == pytest.approx(hole_r)
    start = _shoulder_end(callout, tip)
    over, approach, detour = _plan_detour(start, tip)
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    # The leader passes the rear boss an ink clearance off, and lands under
    # the tap's centre, so it never crosses the extension line through it.
    (x0, y0), (x1, y1) = start, tip
    run = ((boss[0] - x0) * (x1 - x0) + (boss[1] - y0) * (y1 - y0)) / math.dist(start, tip) ** 2
    t = max(0.0, min(1.0, run))
    nearest = (x0 + t * (x1 - x0), y0 + t * (y1 - y0))
    assert math.dist(nearest, boss) >= boss_r + drawing.INK_CLEARANCE
    assert tip[1] < hole[1]
    # The callout stands clear under that extension line, inside the frame
    # and off the title block.
    left, down, right, up = drawing.KEEPER_CALLOUT_EXTENT
    box = (callout[0] - left, callout[1] - down, callout[0] + right, callout[1] + up)
    assert hole[1] - box[3] >= drawing.INK_CLEARANCE + drawing.ARROW_HALF_WIDTH
    frame = drawing.SHEET_FRAME
    assert frame[0] <= box[0] and box[2] <= frame[2] - drawing.INK_CLEARANCE
    assert box[1] > TITLE_BLOCK[3]
    assert box[0] > boss[0] + boss_r


def test_b49e1_keeper_callout_is_what_ran_over_the_boss() -> None:
    """The same measure on b49e1's RD4 (callout (0.366, 0.247), tip on the
    front tap's far rim) gates, as the audit found."""
    front_rim = _plan(
        part.KEEPER_TAP_X,
        part.KEEPER_TAP_Z_FRONT + part.TAP_DRILL_MM[part.KEEPER_TAP_SPEC.size] / 2.0,
    )
    _over, _approach, detour = _plan_detour(_shoulder_end((0.366, 0.247), front_rim), front_rim)
    assert detour > 0.010


def _cap_seat_geometry():
    tip = _section(
        part.FRONT_COLUMN_Z - (part.BORE_DIA + part.CAP_RECESS_DIAMETER) / 4.0,
        part.CAP_RECESS_FLOOR_Y,
    )
    face_z = part.FRONT_COLUMN_Z - part.BOSS_DIA / 2.0
    top = part.HALF_H + part.BOSS_ABOVE
    entry = _section(face_z, (part.SPOTFACE_DIA / 2.0 + top) / 2.0)
    return tip, entry, _section(face_z, top), _section(face_z, part.SPOTFACE_DIA / 2.0)


def _section_detour(start, tip):
    """#946's detour of a leader into A-A's front boss, whose outer face is
    the section's left edge: it enters through that face or the underside."""
    face_x, top_y = _section(
        part.FRONT_COLUMN_Z - part.BOSS_DIA / 2.0, part.HALF_H + part.BOSS_ABOVE
    )
    bottom_y = _section(0.0, -part.HALF_H - part.BOSS_BELOW)[1]
    (x0, y0), (x1, y1) = start, tip
    entry = None
    for step in range(20001):
        t = step / 20000.0
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if x >= face_x and bottom_y <= y <= top_y:
            entry = (x, y)
            break
    approach = min(tip[0] - face_x, top_y - tip[1])
    over = math.dist(entry, tip)
    return over, approach, over - approach


def test_cap_seat_finish_leader_takes_the_short_way_to_its_ledge() -> None:
    """#946 / b49e1: the cap seat Ra 3.2 stood below-left of A-A and its
    leader climbed 24.7 mm through the hatching to the far ledge, 16.6 mm
    past the approach.  It now lands on the near ledge through the boss's
    outer face, between the cross tap's spotface and the boss top."""
    tip, entry, top, spotface_top = _cap_seat_geometry()
    symbol = drawing.cap_seat_finish_placement(tip, entry)
    bend = (symbol[0] + drawing.FINISH_LEADER_TAIL, symbol[1])
    # The bend, the entry and the tip are one straight leader.
    cross = (entry[0] - tip[0]) * (bend[1] - tip[1]) - (entry[1] - tip[1]) * (bend[0] - tip[0])
    assert cross == pytest.approx(0.0, abs=1e-12)
    over, approach, detour = _section_detour(bend, tip)
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    assert spotface_top[1] < entry[1] < top[1]
    # The symbol's ink stays off the part.
    assert bend[0] + drawing.CAP_SEAT_FINISH_INK_PAST_BEND <= entry[0] - drawing.INK_CLEARANCE


def test_b49e1_cap_seat_finish_is_what_ran_through_the_hatching() -> None:
    """b49e1's symbol at (0.175, 0.114) with its leader to the far ledge,
    (240.625, 138.675) mm on that render, gates by the same measure."""
    far_ledge = _section(
        part.FRONT_COLUMN_Z + (part.BORE_DIA + part.CAP_RECESS_DIAMETER) / 4.0,
        part.CAP_RECESS_FLOOR_Y,
    )
    shift = (far_ledge[0] - 0.240625, far_ledge[1] - 0.138675)
    bend = (0.175 + drawing.FINISH_LEADER_TAIL + shift[0], 0.114 + shift[1])
    _over, _approach, detour = _section_detour(bend, far_ledge)
    assert detour > 0.010


def test_build_places_both_leaders_from_their_projected_features() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    for placed in (
        "keeper_callout_placement(",
        "callout_xy=keeper_callout_xy,",
        "rear_keeper = (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR)",
        "symbol_xy=cap_seat_finish_placement(cap_seat_tip, cap_seat_entry),",
        "leader_attach_xy=cap_seat_tip,",
    ):
        assert placed in body, placed


# #955 section letters.  layoutcheck's replay of b49e1 found three cutting-
# plane letters printed on ink (B 3.65 mm on the rail edge and the 183.9,
# E 0.99 on the corner boss, D 6.17 on the hub rail's inner face) and two more
# under 1 mm off it.  The two 1:3 plans are projected as above (+X right, +Z
# down the sheet); each letter's box stands about its arrow's tail.
_PLAN_S = drawing.GEOMETRY_VIEW_SCALE / 1000.0
_SECTION_PLAN = {
    "B": drawing.GEOMETRY_TOP_CENTER,
    "E": drawing.GEOMETRY_TOP_CENTER,
    "D": drawing.HUB_TOP_CENTER,
}
_LETTER_ENDS = ("B-outer", "B-inner", "E-inner", "E-outer", "D-outer", "D-inner")
# b49e1's cutting-line ends, as the build then typed them, start first.
_B49E1_CUT_ENDS = {
    "B": (
        (part.COLUMN_X / 2.0, drawing.PLAN_HALF_Z + 6.0),
        (part.COLUMN_X / 2.0, part.INNER_Z - 6.0),
    ),
    "E": (
        (part.BAR_X1 + 6.0, drawing.SIDE_SECTION_Z),
        (-drawing.PLAN_HALF_X - 6.0, drawing.SIDE_SECTION_Z),
    ),
    "D": (
        (-drawing.PLAN_HALF_X - 6.0, part.GOOSENECK_Z),
        (-part.INNER_X + 5.0, part.GOOSENECK_Z),
    ),
}
# The letters' ink on the b49e1 render (mm).
_B49E1_LETTERS = {
    "B-outer": (193.21, 119.26, 196.86, 125.44),
    "B-inner": (193.21, 138.30, 196.86, 144.47),
    "E-inner": (144.18, 202.99, 147.66, 209.17),
    "E-outer": (67.14, 202.99, 70.63, 209.17),
    "D-outer": (66.28, 214.80, 71.40, 220.97),
    "D-inner": (84.34, 214.80, 89.46, 220.97),
}
# Dimension ink beside the letters, which #955 leaves where b49e1 printed it
# (mm): the "183.9" and its line, the 18.0 gusset run's text and witness
# lines, and the witness lines running off the rear-left corner boss.
_WINDOW_WIDTH_TEXT = (184.84, 116.16, 195.52, 119.72)
_WINDOW_WIDTH_LINE = ((143.67, 115.22), (204.97, 115.22))
_GUSSET_RUN_TEXT = (124.72, 215.88, 165.32, 219.44)
_GUSSET_RUN_WITNESSES = (((143.67, 194.5), (143.67, 215.94)), ((149.67, 200.5), (149.67, 215.94)))
_CORNER_WITNESSES = (
    ((70.63, 206.83), (70.63, 251.94)),  # (446.2)
    ((72.63, 212.17), (45.0, 212.17)),  # 262.0
    ((84.03, 199.5), (58.0, 199.5)),  # 186.0
)
# SolidWorks' cutting-plane arrowhead is 1/8 in across (cone_tip_block's
# SECTION_ARROW_HEAD, measured on its renders) on a 12 mm shaft.
_SECTION_ARROW_LENGTH = 0.012
_SECTION_ARROW_HALF_WIDTH = 0.003175 / 2.0


def _mm(box):
    return tuple(value / 1000.0 for value in box)


def _mm_segment(segment):
    return tuple(tuple(value / 1000.0 for value in point) for point in segment)


def _plan_point(key, x, z):
    cx, cy = _SECTION_PLAN[key]
    return (cx + x * _PLAN_S, cy - z * _PLAN_S)


def _letter_tails(ends):
    """Each letter's arrow tail, keyed '<section>-<outer|inner>'; E's cut
    starts at its inner end, B's and D's at their outer ends."""
    order = {"B": ("outer", "inner"), "E": ("inner", "outer"), "D": ("outer", "inner")}
    return {
        f"{key}-{name}": _plan_point(key, *point)
        for key, pair in ends.items()
        for name, point in zip(order[key], pair)
    }


def _letter_boxes(ends):
    boxes = {}
    for name, (x, y) in _letter_tails(ends).items():
        dx0, dy0, dx1, dy1 = drawing.SECTION_LETTER_EXTENTS[name[0]]
        boxes[name] = (x + dx0, y + dy0, x + dx1, y + dy1)
    return boxes


def _box_point_gap(box, point):
    x, y = point
    return math.hypot(max(box[0] - x, 0.0, x - box[2]), max(box[1] - y, 0.0, y - box[3]))


def _segment_point_gap(start, end, point):
    (x0, y0), (x1, y1) = start, end
    run = ((point[0] - x0) * (x1 - x0) + (point[1] - y0) * (y1 - y0)) / math.dist(start, end) ** 2
    t = max(0.0, min(1.0, run))
    return math.dist(point, (x0 + t * (x1 - x0), y0 + t * (y1 - y0)))


def _box_segment_gap(box, segment):
    start, end = segment
    # A segment through the box is clipped to it (Liang-Barsky).
    (x0, y0), (x1, y1) = start, end
    low, high = 0.0, 1.0
    for p, q in (
        (x0 - x1, x0 - box[0]), (x1 - x0, box[2] - x0),
        (y0 - y1, y0 - box[1]), (y1 - y0, box[3] - y0),
    ):
        if p == 0.0:
            if q < 0.0:
                low, high = 1.0, 0.0
            continue
        t = q / p
        if p < 0.0:
            low = max(low, t)
            continue
        high = min(high, t)
    if low <= high:
        return 0.0
    corners = ((box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3]))
    return min(
        _box_point_gap(box, start),
        _box_point_gap(box, end),
        *(_segment_point_gap(start, end, corner) for corner in corners),
    )


def _box_box_gap(a, b):
    return math.hypot(max(b[0] - a[2], 0.0, a[0] - b[2]), max(b[1] - a[3], 0.0, a[1] - b[3]))


def _plan_line(key, a, b):
    return (_plan_point(key, *a), _plan_point(key, *b))


def _segment_ink(what, segment, clearance):
    return (what, lambda box: _box_segment_gap(box, segment), clearance)


def _letter_ink(name):
    """(what, gap function, clearance) for the ink round one letter: the
    plan's own edges, projected from the model, and the dimension ink b49e1
    printed beside it."""
    ink = drawing.INK_CLEARANCE
    if name == "B-outer":
        edge = _plan_line("B", (-part.COLUMN_X, part.OUTER_Z), (part.COLUMN_X, part.OUTER_Z))
        return (
            _segment_ink("rail outer edge", edge, drawing.TEXT_CLEARANCE),
            _segment_ink("183.9 line", _mm_segment(_WINDOW_WIDTH_LINE), drawing.TEXT_CLEARANCE),
            # Beside the value on its line: a letter's width of air, so the
            # letter does not read as the value's prefix ("B183.9").
            ("183.9", lambda box: _box_box_gap(box, _mm(_WINDOW_WIDTH_TEXT)),
             drawing.SECTION_LETTER_TEXT_GAP),
        )
    if name == "B-inner":
        face = _plan_line("B", (part.BAR_X1, part.INNER_Z), (part.INNER_X, part.INNER_Z))
        return (_segment_ink("rail inner face", face, ink),)
    if name == "E-inner":
        near = -(part.INNER_Z + part.EDGE_CHAMFER)
        far = -(part.OUTER_Z - part.EDGE_CHAMFER)
        return (
            _segment_ink("rail inner edge", _plan_line("E", (part.BAR_X1, near), (part.INNER_X, near)), ink),
            _segment_ink("rail outer edge", _plan_line("E", (part.BAR_X1, far), (part.INNER_X, far)), ink),
            *(
                _segment_ink(f"18.0 witness {i}", _mm_segment(w), ink)
                for i, w in enumerate(_GUSSET_RUN_WITNESSES)
            ),
            ("18.0", lambda box: _box_box_gap(box, _mm(_GUSSET_RUN_TEXT)), ink),
        )
    if name == "E-outer":
        boss = _plan_point("E", -part.COLUMN_X, part.FRONT_COLUMN_Z)
        boss_r = part.BOSS_DIA / 2.0 * _PLAN_S
        return (
            ("corner boss", lambda box: max(0.0, _box_point_gap(box, boss) - boss_r), ink),
            *(
                _segment_ink(f"corner witness {i}", _mm_segment(w), ink)
                for i, w in enumerate(_CORNER_WITNESSES)
            ),
        )
    face_x = {"D-outer": -part.OUTER_X, "D-inner": -part.INNER_X}[name]
    face = _plan_line("D", (face_x, -part.INNER_Z), (face_x, part.INNER_Z))
    return (_segment_ink("hub rail face", face, ink),)


def _letter_shortfalls(ends, name):
    """The ink a letter stands too close to, with its gap in mm."""
    box = _letter_boxes(ends)[name]
    return {
        what: round(gap(box) * 1000.0, 2)
        for what, gap, clearance in _letter_ink(name)
        if gap(box) < clearance
    }


def test_section_letter_model_reproduces_b49e1() -> None:
    """At b49e1's ends the letter model covers the letters b49e1 printed,
    within its 0.1 mm outward rounding, and reproduces the overprints."""
    boxes = _letter_boxes(_B49E1_CUT_ENDS)
    for name, printed in _B49E1_LETTERS.items():
        model, printed = boxes[name], _mm(printed)
        assert model[0] <= printed[0] and model[1] <= printed[1], name
        assert model[2] >= printed[2] and model[3] >= printed[3], name
        assert max(abs(m - p) for m, p in zip(model, printed)) < 0.00015, name
    shortfalls = {name: _letter_shortfalls(_B49E1_CUT_ENDS, name) for name in _LETTER_ENDS}
    assert shortfalls["B-outer"]["rail outer edge"] == 0.0
    assert shortfalls["B-outer"]["183.9"] == 0.0
    assert shortfalls["E-outer"]["corner boss"] == 0.0
    assert shortfalls["E-outer"]["corner witness 0"] == 0.0
    assert shortfalls["D-inner"]["hub rail face"] == 0.0


@pytest.mark.parametrize("name", _LETTER_ENDS)
def test_section_letter_stands_clear_of_its_ink(name: str) -> None:
    """#955: each cutting-plane letter clears the ink round it by
    INK_CLEARANCE; B's outer letter, centred in its 9.6 mm band, clears the
    rail edge and the 183.9's line by TEXT_CLEARANCE."""
    assert _letter_shortfalls(drawing.section_cut_ends(), name) == {}


@pytest.mark.parametrize("name", ("B-outer", "B-inner", "E-inner", "E-outer", "D-inner"))
def test_b49e1_section_letter_is_what_sat_on_ink(name: str) -> None:
    """The same check on b49e1's ends fails for every letter #955 moves off
    ink.  D's outer letter was already 2.2 mm clear; its end only re-derives."""
    assert _letter_shortfalls(_B49E1_CUT_ENDS, name)


def test_b_outer_arrow_keeps_off_the_window_width() -> None:
    """B's outer arrow runs in the same band: its head clears the 183.9's
    line and ends an ink clearance short of the value."""
    tail = _letter_tails(drawing.section_cut_ends())["B-outer"]
    line_y = _WINDOW_WIDTH_LINE[0][1] / 1000.0
    assert tail[1] - _SECTION_ARROW_HALF_WIDTH - line_y >= 0.001
    assert tail[0] + _SECTION_ARROW_LENGTH <= _WINDOW_WIDTH_TEXT[0] / 1000.0 - drawing.INK_CLEARANCE


def test_section_cuts_cross_the_same_stock() -> None:
    """The moved ends keep what each removed section shows: B cuts the
    rail's plain T between the junction land and the corner boss, E runs
    from outside the left rail past the central web, D from outside the hub
    rail past its inner face, each at its own station."""
    ends = drawing.section_cut_ends()
    (bx, b_outer), (bx_inner, b_inner) = ends["B"]
    assert bx == bx_inner and part.LAND_X1 < bx < part.COLUMN_X - part.BOSS_DIA / 2.0
    assert b_inner < part.INNER_Z and b_outer > drawing.PLAN_HALF_Z
    (e_inner, ez), (e_outer, ez_outer) = ends["E"]
    assert ez == ez_outer == drawing.SIDE_SECTION_Z
    assert e_inner > part.BAR_X1 and e_outer < -drawing.PLAN_HALF_X
    (d_outer, dz), (d_inner, dz_inner) = ends["D"]
    assert dz == dz_inner == part.GOOSENECK_Z
    assert d_outer < -part.OUTER_X and -part.INNER_X < d_inner < part.BAR_X0


# Each removed section's profile ink on b49e1 (mm, x only): B-B's T, E-E's
# left side rail (its web to the right), D-D's hub rail.
_B49E1_PROFILES = {
    "B-B": (350.10, 362.76),
    "E-E": (292.38, 344.91),
    "D-D": (314.89, 349.07),
}


def test_section_profiles_pin_where_b49e1_printed_them() -> None:
    """leaders955-f542: the longer cuts slid D-D's profile 4.27 mm, E-E's
    2.84 and B-B's 0.67 under their typed text, so each is pinned by the
    rail centreline it cuts, at b49e1's print."""
    b0, b1 = _B49E1_PROFILES["B-B"]
    assert drawing.RAIL_SECTION_PROFILE_X * 1000.0 == pytest.approx((b0 + b1) / 2.0, abs=0.01)
    e0, _e1 = _B49E1_PROFILES["E-E"]
    side_rail_centre = e0 + (part.OUTER_X - part.COLUMN_X) / 4.0
    assert drawing.SIDE_SECTION_PROFILE_X * 1000.0 == pytest.approx(side_rail_centre, abs=0.01)
    d0, d1 = _B49E1_PROFILES["D-D"]
    assert d1 - d0 == pytest.approx(part.RAIL_W_SIDE, abs=0.05)
    assert drawing.HUB_SECTION_PROFILE_X * 1000.0 == pytest.approx((d0 + d1) / 2.0, abs=0.01)


class _FakeView:
    def __init__(self, position, persists=True):
        self.Position = position
        self.persists = persists

    def SetViewPosition(self, xy, _move_children):
        if self.persists:
            self.Position = tuple(xy)
        return True


def _pin(monkeypatch, view, offset):
    """Pin with the model point printing at the view's position + offset."""
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda _adapter, v, _xyz, *, label: (v.Position[0] + offset[0], v.Position[1] + offset[1]),
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda _adapter, *, label: None)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    drawing._pin_section_profile(None, view, (0.0, 0.0, 0.0), 0.3320, label="D-D")


def test_pin_section_profile_moves_the_view_by_the_miss(monkeypatch) -> None:
    view = _FakeView((0.3300, 0.2100))
    _pin(monkeypatch, view, (-0.0043, 0.0))
    assert view.Position == pytest.approx((0.3363, 0.2100))


def test_pin_section_profile_fails_loud_when_the_move_does_not_hold(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="D-D section profile prints at"):
        _pin(monkeypatch, _FakeView((0.3300, 0.2100), persists=False), (-0.0043, 0.0))


def test_build_pins_every_removed_section_and_writes_centrelines_direct() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for pinned in ("RAIL_SECTION_PROFILE_X, label=\"B-B\"", "SIDE_SECTION_PROFILE_X, label=\"E-E\"",
                   "HUB_SECTION_PROFILE_X, label=\"D-D\"",
                   "HANGER_SECTION_PROFILE_X, label=\"F-F\""):
        assert pinned in source, pinned
    body = source[source.index("def _add_view_centerlines(") :]
    body = body[: body.index("\ndef ")]
    assert "manager.AddToDB = True" in body
    assert "_assert_centreline_placed(adapter, segment, points)" in body


def test_build_cuts_each_section_at_its_derived_ends() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for placed in (
        'for x, z in cut_ends["B"]',
        'for x, z in cut_ends["E"]',
        'for x, z in section_cut_ends()["D"]',
    ):
        assert placed in source, placed


# --- Knife hanger: #6 SHCS counterbore + MHA-VN-051 dowel slip hole --------


def test_knife_hanger_is_a_6_shcs_counterbore_on_the_knife_line() -> None:
    import spring_mount_geom

    hole = spec.HANGER_HOLE_SPEC
    assert (hole.kind, hole.size, hole.end) == ("counterbore_socket", "#6", "through_all")
    assert hole.overrides_mm == {
        "HoleDiameter": spec.HANGER_CLEARANCE_DIA,
        "CounterBoreDiameter": spec.HANGER_CBORE_DIA,
        "CounterBoreDepth": spec.HANGER_CBORE_DEPTH,
    }
    assert spec.HANGER_CLEARANCE_DIA == pytest.approx(4.318)
    assert (spec.HANGER_CBORE_DIA, spec.HANGER_CBORE_DEPTH) == (7.0, 6.5)
    # The 1/2 hanger-stud clearance is gone, not aliased.
    assert not hasattr(part, "STUD_HOLE_SPEC") and not hasattr(part, "STUD_HOLE_DIA")
    # Both stations sit on the knife line, centred on the crossbar.
    assert part.HANGER_X == spring_mount_geom.KNIFE[0] == (part.BAR_X0 + part.BAR_X1) / 2.0
    assert drawing.HANGER_X == part.HANGER_X
    # The counterbore stays inside the junction material at the rear station.
    assert part.STUD_Z_REAR + spec.HANGER_CBORE_DIA / 2.0 < part.INNER_Z + part.GUSSET
    # Print-worst head checks (rule 12).
    assert spec.HANGER_CBORE_HEAD_CLEARANCE == pytest.approx(0.7496)
    assert spec.HANGER_HEAD_RECESS == pytest.approx(2.4848)
    assert spec.HANGER_HEAD_BEARING == pytest.approx(0.6612)


def test_counterbore_floor_is_the_screw_grip_at_one_place() -> None:
    assert spec.HANGER_GRIP == 30.0 == part.RING_HEIGHT - spec.HANGER_CBORE_DEPTH
    assert spec.HANGER_GRIP_PLACES == 1
    assert spec.HANGER_GRIP_TOL == float(
        str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1")
    )
    assert (
        spec.DRAWING_REFERENCE_PRECISION["hanger counterbore floor from underside"]
        == spec.HANGER_GRIP_PLACES
    )


def test_dowel_slip_hole_contract() -> None:
    assert part.PIN_HOLE_X == pytest.approx(-8.65)
    assert part.PIN_HOLE_X - part.HANGER_X == spec.HANGER_PIN_X == 6.35
    assert spec.HANGER_PIN_X_PLACES == 3
    assert spec.DRAWING_REFERENCE_PRECISION["dowel hole from hanger axis"] == 3
    assert (spec.HANGER_PIN_HOLE_DIA, spec.HANGER_PIN_HOLE_DIA_BAND) == (3.24, (0.03, -0.03))
    assert spec.HANGER_PIN_HOLE_DEPTH == 12.0
    assert spec.HANGER_PIN_SLIP_CLEARANCE_MIN == pytest.approx(0.02738)
    assert spec.HANGER_PIN_SLIP_CLEARANCE_MAX == pytest.approx(0.09246)
    assert 0.02 <= spec.HANGER_PIN_SLIP_CLEARANCE_MIN < spec.HANGER_PIN_SLIP_CLEARANCE_MAX <= 0.10
    # Rule 12 walls and floor, print-worst (the station at its .XXX limit).
    assert part.PIN_HOLE_BAR_WALL == pytest.approx(2.885)
    assert part.PIN_HOLE_SCREW_WALL == pytest.approx(2.376)
    assert part.PIN_HOLE_FLOOR_MARGIN == pytest.approx(18.0)
    assert spec.HANGER_PIN_HOLE_DEPTH < spec.HANGER_GRIP
    # The model owns the size, band and depth; the drawing imports them.
    assert spec.DRAWING_DIMENSIONS["HangerPinProfile"] == {"HangerPinHoleDia"}
    assert spec.DRAWING_DIMENSIONS["HangerPinHoles"] == {"HangerPinHoleDepth"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["HangerPinHoleDepth"] == 1
    assert set(drawing.HANGER_SECTION_KEEP) == {"HangerPinHoleDia", "HangerPinHoleDepth"}


def test_dowel_slot_contract() -> None:
    # The slot stands -X of each screw axis, the round hole +X: the knife
    # mount's two dowels at +/-6.350.
    assert part.SLOT_X == pytest.approx(-21.35)
    assert part.SLOT_X - part.HANGER_X == pytest.approx(spec.HANGER_SLOT_X)
    assert spec.HANGER_SLOT_X == -6.35
    assert spec.HANGER_PIN_XS == (spec.HANGER_SLOT_X, spec.HANGER_ROUND_X)
    # Slip width = the round hole's ream; length .XX; floor = the hole's.
    assert (spec.HANGER_SLOT_WIDTH, spec.HANGER_SLOT_WIDTH_BAND) == (3.24, (0.03, -0.03))
    assert (spec.HANGER_SLOT_LENGTH, spec.HANGER_SLOT_LENGTH_TOL) == (4.30, 0.51)
    assert spec.HANGER_SLOT_DEPTH == spec.HANGER_PIN_HOLE_DEPTH
    assert part.SLOT_FLAT == pytest.approx(1.06)
    # The slot stands BASIC 12.700 from its round hole; from the screw axis
    # it carries the round hole's .XXX band plus its zone radius.
    assert spec.HANGER_SLOT_FROM_ROUND == pytest.approx(12.7)
    assert spec.HANGER_SLOT_STATION_TOL == pytest.approx(0.155)
    # Rule 12 walls and floor, print-worst: the screw-side wall under the
    # 2.0 target, over the 1.5 floor.
    assert part.SLOT_BAR_WALL == pytest.approx(2.09)
    assert part.SLOT_SCREW_WALL == pytest.approx(1.581)
    assert part.SLOT_SCREW_WALL >= 1.5
    assert part.SLOT_FLOOR_MARGIN == pytest.approx(18.0)
    # The model owns the width and its band (front slot, on the underside
    # locator); F-F derives the station and the length.
    assert spec.DRAWING_DIMENSIONS["HangerSlotProfile"] == {"HangerSlotWidth"}
    assert spec.DRAWING_PRECISION_BY_NAME["HangerSlotWidth"] == 3
    assert "dowel slot from hanger axis" not in spec.DRAWING_REFERENCE_PRECISION
    assert spec.DRAWING_REFERENCE_PRECISION["dowel slot from dowel hole"] == 3
    assert spec.DRAWING_REFERENCE_PRECISION["dowel slot length"] == 2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'for slot_width_name in ("HangerSlotWidth", "HangerSlot1Width"):' in source
    assert 'prefix = "HangerSlot" if station == "Front" else "HangerSlot1"' in source


def test_dowel_slot_sketch_contours_never_cross() -> None:
    # 48ad988c6 cut each slot's ends as two Ø3.24 circles 1.36 apart in one
    # sketch; they cross, and the farm leaf's cut failed (FeatureCut3 "Type
    # mismatch").  Each slot is now one closed stadium, the two apart.
    w, flat = spec.HANGER_SLOT_WIDTH, part.SLOT_FLAT
    end_circles = tuple(
        ((part.SLOT_X + side * flat / 2, z), (part.SLOT_X + side * flat / 2, z), w / 2)
        for z in (part.STUD_Z_FRONT, part.STUD_Z_REAR)
        for side in (-1.0, 1.0)
    )
    assert not part.swept_contours_disjoint(end_circles)
    assert len(part.HANGER_SLOT_CONTOURS) == 2
    assert part.swept_contours_disjoint(part.HANGER_SLOT_CONTOURS)
    assert part.swept_contours_disjoint(part.HANGER_PIN_CONTOURS)
    # The checker separates by the swept radii, so touching is a failure.
    assert not part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2), (3, 2), 1.0)))
    assert part.swept_contours_disjoint((((0, 0), (1, 0), 1.0), ((1, 2.001), (3, 2.001), 1.0)))
    assert part.HANGER_SLOT_AREA == pytest.approx(flat * w + math.pi * (w / 2) ** 2)
    source = Path(part.__file__).read_text(encoding="utf-8")
    step = source[source.index("    # 12c. Dowel slots") : source.index("    # 13. Cross-screw")]
    assert "define_circle" not in step
    assert step.count("create_cut_extrude(") == 1
    assert step.count("await adapter.add_arc(") == 2
    assert step.count("await adapter.add_line(") == 2


@pytest.mark.parametrize("along_u", [True, False])
def test_dowel_slot_stadium_closes_counter_clockwise(along_u: bool) -> None:
    centre, half_flat, half_w = (5.0, -7.0), part.SLOT_FLAT / 2, spec.HANGER_SLOT_WIDTH / 2
    p1, p2, p3, p4, c_b, c_a = part.slot_stadium_points(
        centre, along_u=along_u, half_flat=half_flat, half_w=half_w
    )
    # Straight sides of the flat run, each end a half round about its centre.
    assert math.dist(p1, p2) == pytest.approx(2 * half_flat)
    assert math.dist(p3, p4) == pytest.approx(2 * half_flat)
    assert math.dist(c_a, c_b) == pytest.approx(2 * half_flat)
    for c, a, b in ((c_b, p2, p3), (c_a, p4, p1)):
        assert math.dist(c, a) == pytest.approx(half_w)
        assert math.dist(c, b) == pytest.approx(half_w)
        # add_arc sweeps counter-clockwise from a to b: the half round
        # bulges away from the slot's centre.
        sweep_mid = (c[0] + (b[1] - a[1]) / 2, c[1] - (b[0] - a[0]) / 2)
        assert math.dist(sweep_mid, centre) == pytest.approx(half_flat + half_w)
    # The sides run along the slot (u when along_u), counter-clockwise.
    axis = 0 if along_u else 1
    assert p1[1 - axis] == pytest.approx(p2[1 - axis])
    area2 = sum(
        x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip((p1, p2, p3, p4), (p2, p3, p4, p1))
    )
    assert area2 > 0


def test_slots_are_positioned_to_the_round_holes_with_translation() -> None:
    # Policy rule 3 (knife-edge system): datum B the front round hole, C the
    # rear; each slot 0.05 to its own station's hole, the other translated.
    assert spec.GEOMETRIC_TOLERANCES_MM == {"knife-hanger slot position": "0.05"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert underside.count("add_datum_feature(") == 1
    assert '(("B", STUD_Z_FRONT), ("C", STUD_Z_REAR))' in underside
    assert underside.count("add_feature_control_frame(") == 1
    assert '("front", STUD_Z_FRONT, ("B", "C"))' in underside
    assert '("rear", STUD_Z_REAR, ("C", "B"))' in underside
    assert "translated=datums[1:]" in underside
    assert 'GEOMETRIC_TOLERANCES_MM["knife-hanger slot position"]' in underside
    assert '"HangerSlotWidth": HANGER_SLOT_WIDTH_TEXT_XY' in underside
    for name, (x, y) in {
        **drawing.HANGER_DATUM_SYMBOL_XY,
        **drawing.HANGER_SLOT_FRAME_XY,
        "slot width": drawing.HANGER_SLOT_WIDTH_TEXT_XY,
        "slot width offset": drawing.HANGER_SLOT_WIDTH_OFFSET_XY,
    }.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.125 < y < 0.270, name


def test_no_datum_tag_is_attached_to_a_circle_by_edge_object() -> None:
    # Farm run 20261009T164113078Z: datum B, attached to the scanned round
    # dowel-hole circle as an edge object, ignored SetPosition2 and stayed at
    # its default drop 37.6 mm from its request (as crank_pinion datum A and
    # the vm2 probe's rod/rack bores did: layout-tuning lesson h).  A circle
    # is attached by a sheet-point pick, proved by expected_entity.
    import ast

    offenders = []
    for path in sorted(Path(drawing.__file__).parent.glob("draw_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not (
                isinstance(call, ast.Call)
                and getattr(call.func, "id", getattr(call.func, "attr", "")) == "add_datum_feature"
            ):
                continue
            for keyword in call.keywords:
                if keyword.arg in {"edge_entity", "entity"} and "circle_at(" in ast.unparse(
                    keyword.value
                ):
                    offenders.append(f"{path.name}:{call.lineno}")
    assert offenders == []


def test_hanger_datums_are_picked_on_their_rims_toward_their_tags() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    loop = underside[: underside.index("add_feature_control_frame(")]
    assert "with _zoomed_on(adapter, datum_pick, HANGER_DATUM_PICK_ZOOM_HALF):" in loop
    assert "edge_xy=datum_pick, expected_entity=round_hole," in loop
    assert "edge_entity" not in loop
    # The zoom window holds the whole rim and the pick is ON it, facing the tag.
    radius = drawing.HANGER_PIN_HOLE_DIA / 2.0 * drawing._HUB_BOTTOM_M_PER_MM
    assert radius < drawing.HANGER_DATUM_PICK_ZOOM_HALF / 2.0
    for datum, (x, y) in drawing.HANGER_DATUM_SYMBOL_XY.items():
        centre = (0.107, 0.172 if datum == "B" else 0.230)
        pick = drawing.hanger_datum_pick(centre, (x, y))
        assert math.dist(pick, centre) == pytest.approx(radius), datum
        to_pick = (pick[0] - centre[0], pick[1] - centre[1])
        to_tag = (x - centre[0], y - centre[1])
        assert to_pick[0] * to_tag[1] - to_pick[1] * to_tag[0] == pytest.approx(0.0, abs=1e-12)
        assert to_pick[0] * to_tag[0] + to_pick[1] * to_tag[1] > 0.0, datum


def test_hanger_datum_leaders_run_clear_of_the_slot_frames() -> None:
    # Farm run 20261009T171439353Z: datum B's leader, rim (107.5, 172.4) to
    # its tag at (122.0, 185.0) mm, ran 7.88 mm through the front slot
    # frame's text [78.9, 179.1]..[128.6, 184.2] mm (leader-through-text).
    from _layout_geometry import Box, Segment, segment_box_overlap_length

    x0, y0, x1, y1 = drawing.HANGER_SLOT_FRAME_TEXT_BOX
    frames = {
        station: Box(fx + x0, fy + y0, fx + x1, fy + y1)
        for station, (fx, fy) in drawing.HANGER_SLOT_FRAME_XY.items()
    }
    front = frames["front"]
    assert (front.xmin, front.ymin, front.xmax, front.ymax) == pytest.approx(
        (0.0789, 0.1797, 0.1105, 0.1842)
    )
    centre = drawing.HUB_BOTTOM_CENTER
    m_per_mm = drawing._HUB_BOTTOM_M_PER_MM
    for datum, station_z in (("B", part.STUD_Z_FRONT), ("C", part.STUD_Z_REAR)):
        hole = (
            centre[0] + part.PIN_HOLE_X * m_per_mm,
            centre[1] + station_z * m_per_mm,
        )
        tag = drawing.HANGER_DATUM_SYMBOL_XY[datum]
        leader = Segment(*drawing.hanger_datum_pick(hole, tag), *tag)
        for station, box in frames.items():
            assert segment_box_overlap_length(leader, box) == 0.0, (datum, station)
            # The 7 mm letter box above the tag point keeps 3 mm off the frame.
            letter = Box(tag[0] - 0.0035, tag[1], tag[0] + 0.0035, tag[1] + 0.007)
            assert (
                letter.xmin - box.xmax >= 0.003
                or box.xmin - letter.xmax >= 0.003
                or letter.ymin - box.ymax >= 0.003
                or box.ymin - letter.ymax >= 0.003
            ), (datum, station)
    # The tag stays in the window right of the crossbar, above the front
    # rail's inner face.
    bx, by = drawing.HANGER_DATUM_SYMBOL_XY["B"]
    assert bx > centre[0] + part.BAR_X1 * m_per_mm
    assert by > centre[1] - part.INNER_Z * m_per_mm


def test_rear_slot_frame_stands_clear_of_section_f_f() -> None:
    # Farm run 20261009T174542021Z: the rear frame at (78, 218) mm printed
    # its text [78.9, 212.1]..[128.6, 217.2] under both F labels and F-F's
    # left arrow (text-clearance 3.87 mm short of 1.78 mm air; text-on-line
    # 3.05 mm), which REPORT mode on fr-top-frame does not enforce.
    from _layout_geometry import Box, Segment, segment_box_distance

    centre, m_per_mm = drawing.HUB_BOTTOM_CENTER, drawing._HUB_BOTTOM_M_PER_MM
    cut_y = centre[1] + drawing.HANGER_SECTION_Z * m_per_mm
    arrows = [centre[0] + x * m_per_mm for x in drawing.HANGER_SECTION_CUT_X]
    # Each F-F arrow runs 12 mm sheet-down from the cutting line; its letter
    # prints [-1.2, +1.8] x [-20.25, -14.15] mm about the line's end (run
    # 20261009T174542021Z: arrows x 91.33 / 118.67 from y 230.05, letters
    # [90.1, 209.8]..[93.1, 215.9] and [117.4, 209.8]..[120.4, 215.9]).
    assert arrows == pytest.approx([0.09133, 0.11867], abs=5e-5)
    assert cut_y == pytest.approx(0.23005, abs=5e-5)
    section_ink: dict[str, Box | Segment] = {
        "cutting line": Segment(arrows[0], cut_y, arrows[1], cut_y),
    }
    for side, x in zip(("left", "right"), arrows):
        section_ink[f"{side} arrow"] = Segment(x, cut_y, x, cut_y - 0.012)
        section_ink[f"{side} F"] = Box(
            x - 0.0012, cut_y - 0.02025, x + 0.0018, cut_y - 0.01415
        )
    fx, fy = drawing.HANGER_SLOT_FRAME_XY["rear"]
    ox0, oy0, ox1, oy1 = drawing.HANGER_SLOT_FRAME_OUTLINE
    outline = Box(fx + ox0, fy + oy0, fx + ox1, fy + oy1)
    # The leader: the shoulder off the outline's left end at mid height, then
    # to the outer end of the rear slot (its arc's bottom, under the line).
    knee = (outline.xmin - drawing.HANGER_SLOT_FRAME_SHOULDER, (outline.ymin + outline.ymax) / 2)
    slot_end = (
        centre[0] + (part.SLOT_X - part.SLOT_FLAT / 2) * m_per_mm,
        centre[1] + (part.STUD_Z_REAR - drawing.HANGER_SLOT_WIDTH / 2) * m_per_mm,
    )
    leader = [
        Segment(outline.xmin, knee[1], *knee),
        Segment(*knee, *slot_end),
    ]
    for name, ink in section_ink.items():
        if isinstance(ink, Box):
            gap = max(
                ink.ymin - outline.ymax, outline.ymin - ink.ymax,
                ink.xmin - outline.xmax, outline.xmin - ink.xmax,
            )
            # The audit asked for 1.78 mm of air between the two texts.
            assert gap >= 0.00178, name
            for run in leader:
                assert segment_box_distance(run, ink) >= 0.00178, name
        else:
            assert segment_box_distance(ink, outline) >= 0.00178, name
            for run in leader:
                assert _segments_apart(run, ink), name
    # The frame stays in the window right of the crossbar, its leader's knee
    # right of the crossbar's edge, and its print inside the rail.
    bar_right = centre[0] + part.BAR_X1 * m_per_mm
    assert knee[0] > bar_right
    assert outline.xmax < centre[0] + part.INNER_X * m_per_mm
    assert outline.ymin > max(drawing.HANGER_SLOT_FRAME_XY["front"][1], drawing.HANGER_DATUM_SYMBOL_XY["B"][1] + 0.007)


def _segments_apart(a, b) -> bool:
    """True when two segments neither cross nor touch."""

    def side(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    a0, a1, b0, b1 = (a.x0, a.y0), (a.x1, a.y1), (b.x0, b.y0), (b.x1, b.y1)
    return side(a0, a1, b0) * side(a0, a1, b1) > 0 or side(b0, b1, a0) * side(b0, b1, a1) > 0


def test_slip_hole_callout_states_process_and_purpose_briefly() -> None:
    text = spec.HANGER_PIN_HOLE_CALLOUT
    assert text.startswith("2X ") and "REAM" in text and "MHA-VN-051" in text
    assert "BLIND" in text and "FLAT-BOTTOM" in text
    # Rule 6: short notes.
    assert len(text.splitlines()) <= 2
    assert max(len(line) for line in text.splitlines()) <= 26
    assert drawing.HANGER_SECTION_CALLOUTS["HangerPinHoleDia"] == text


def test_hanger_section_cuts_the_crossbar_from_window_to_window() -> None:
    """F-F cuts the rear station across the crossbar and its gussets only:
    both ends stand in open window, past the gussets' reach at that z and
    short of the side rails, and the cut stays below the window rim break."""
    x0, x1 = drawing.HANGER_SECTION_CUT_X
    reach = drawing.HANGER_SECTION_GUSSET_REACH
    assert drawing.HANGER_SECTION_Z == part.STUD_Z_REAR
    assert reach == pytest.approx(part.GUSSET - (part.INNER_Z - part.STUD_Z_REAR))
    assert -part.INNER_X < x0 < part.BAR_X0 - reach
    assert part.BAR_X1 + reach < x1 < part.INNER_X
    assert part.STUD_Z_REAR < part.INNER_Z - part.EDGE_CHAMFER


def test_hanger_section_text_stays_on_the_sheet_off_the_title_block() -> None:
    points = {
        "floor": drawing.HANGER_FLOOR_TEXT_XY,
        "floor offset": drawing.HANGER_FLOOR_OFFSET_XY,
        "station": drawing.PIN_STATION_TEXT_XY,
        "station offset": drawing.PIN_STATION_OFFSET_XY,
        "slot station": drawing.SLOT_STATION_TEXT_XY,
        "slot station offset": drawing.SLOT_STATION_OFFSET_XY,
        "slot length": drawing.SLOT_LENGTH_TEXT_XY,
        "slot length offset": drawing.SLOT_LENGTH_OFFSET_XY,
        "caption": drawing.HANGER_SECTION_CAPTION_XY,
        "slip-hole callout": drawing.HANGER_PIN_DIA_OFFSET_XY,
        **drawing.HANGER_SECTION_KEEP,
    }
    for name, (x, y) in points.items():
        assert 0.013 < x < TITLE_BLOCK[0] and 0.013 < y < 0.150, name
    # The station reads above the profile, the slip-hole size below it.
    top = drawing._hanger_section_xy(part.HANGER_X, part.HALF_H)[1]
    bottom = drawing._hanger_section_xy(part.HANGER_X, -part.HALF_H)[1]
    assert drawing.PIN_STATION_TEXT_XY[1] > top
    assert drawing.HANGER_SECTION_KEEP["HangerPinHoleDia"][1] < bottom
    # The slot's BASIC row stands above the hole's station row, so the two
    # dimension lines never meet on the round hole's extension line.
    assert drawing.SLOT_STATION_TEXT_XY[1] > drawing.PIN_STATION_TEXT_XY[1] + 0.004


def test_slot_station_is_basic_from_its_round_hole() -> None:
    # Machinist review (sheet 6): the slot position frames lacked a basic
    # location.  The slot now stands BASIC 12.700 from the round hole beside
    # it (datum B front, C rear), a bare box: its above-text did not print
    # (20261010T001553082Z layout audit, text-unmatched).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    section = source[source.index("def _hanger_section(") : source.index("def _hub_underside_detail(")]
    assert "2X DOWEL SLOT\\nFROM SCREW AXIS" not in section
    assert "p0=(SLOT_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X, -HALF_H-2.0, z)" in section
    assert "entities=(axes[2], axes[1])" in section
    assert "expected_mm=HANGER_SLOT_FROM_ROUND" in section
    assert 'set_basic_dimension(adapter, slot_station, label="dowel slot from dowel hole")' in section
    assert "FROM DOWEL HOLE" not in section
    assert 'location="above"' not in section
    assert spec.HANGER_SLOT_FROM_ROUND == pytest.approx(spec.HANGER_ROUND_X - spec.HANGER_SLOT_X)


def test_slip_hole_callout_is_parked_clear_of_the_section() -> None:
    # Rule 8 (dda9a33a8 render): the four-line callout stood across the hole's
    # own extension lines and the underside edge.  It now rides a leader to a
    # block wholly below the section, right of the size's extension lines and
    # left of the title block.
    half_w, half_h = 0.0325, 0.0095  # 65 x 19 mm block on that render
    x, y = drawing.HANGER_PIN_DIA_OFFSET_XY
    bottom = drawing._hanger_section_xy(part.HANGER_X, -part.HALF_H)[1]
    hole_right = drawing._hanger_section_xy(
        part.PIN_HOLE_X + spec.HANGER_PIN_HOLE_DIA / 2.0, 0.0
    )[0]
    assert y + half_h < bottom - 0.010
    assert x - half_w > hole_right + 0.010
    assert x + half_w < TITLE_BLOCK[0] - 0.005
    assert y - half_h > 0.0127 + 0.005
    # Clear of the caption, which stands left of the section.
    assert x - half_w > drawing.HANGER_SECTION_CAPTION_XY[0] + 0.025
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '{"HangerPinHoleDia": HANGER_PIN_DIA_OFFSET_XY}' in source, (
        "the slip-hole size must be offset onto its leader"
    )


def test_build_places_the_hanger_section_on_the_underside_sheet() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    underside = source[source.index('ddoc.ActivateSheet("UNDERSIDE")') :]
    assert "_hanger_section(adapter, hub_bottom_parent)" in underside
    assert "imported_annotations += hanger_dimensions" in underside
