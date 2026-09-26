"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import fulcrum_keeper_spec as keeper
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
import build_top_frame as part
import draw_top_frame as drawing
from frame_attachment_spec import (
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
from tube_frame_cap_spec import MAX_OUTER_DIAMETER
import top_frame_spec as spec
import tube_frame_spec


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
        part.BORE_DIA - tube_frame_spec.OUTER_DIA,
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
