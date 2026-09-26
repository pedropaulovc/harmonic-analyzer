r"""MHA-089's top rail and the rocker pivot brackets' hold-down seats (#743 PR2).

PURE DATA, no SolidWorks/COM imports: ``build_rocker_arm_support`` cuts the
rail and its seats from it, and the channel assembly places the screws from
it. Kept out of ``rocker_arm_support_spec`` on purpose: the base, frame and
drive train import that module, and a rail or seat edit must not re-key them.

Each MHA-123 bracket is held by two MHA-143 (McMaster 90280A197, #8-32 x 3/4
slotted fillister) through its #8 close-clearance foot holes into
bottoming-tapped seats in the support's top rail, transferred from the set
bracket at assembly (the south bracket is feeler-set, so its seats cannot be
cast or pre-drilled).

The rail was 6.35 deep, the window's top edge at local y 82.55: too shallow
for 1.5D of #8-32 thread with the drill point still in cast iron. It is now
RAIL_DEPTH deep along its whole length, grown DOWN into the window: the top
face stays at local y +HALF_Y (machine y 228.6), so the brackets, shaft and
rocker pivot do not move, and the foot, base interface and hold-down drills
are untouched. The window is then 165.1 wide by WINDOW_HEIGHT tall -- no
longer square.

The stack is checked at the printed worst case: MHA-123's foot at .XX, the
seat and rail depths at .X, the screw at its +0/-0.76 commercial length band,
and the 0.25 edge break at the seat mouth. Every check raises on import.
"""

from __future__ import annotations

import math

import pivot_bracket_spec as _bracket
from _hole_spec import (
    DRILL_POINT_H,
    NUMBER_DRILL_MM,
    TAP_DRILL_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
)
from rocker_arm_support_spec import (
    FOOT_THICKNESS,
    HALF_Y,
    NARROW,
    SUPPORT_WORLD_X,
    SUPPORT_WORLD_Z,
)
from rocker_bank_layout import PIVOT_BRACKET_Z, STACK_MID_Z

LINEAR_1PL = 0.8  # title-block .X band
LINEAR_2PL = 0.508  # title-block .XX band
EDGE_BREAK = 0.25  # title-block edge break, also the novice spare
RULE12_WEB_TARGET = 2.0

# MHA-143: the channel assembly pins these to the stock part it places.
SCREW_THREAD = "#8-32"
SCREW_LENGTH = 19.05  # under-head length, 3/4 in
SCREW_LENGTH_BAND = (0.0, 0.76)  # (+, -): commercial screw length tolerance
SCREW_MAJOR_DIA = THREAD_MAJOR_MM[SCREW_THREAD]
SCREW_PITCH = 25.4 / float(SCREW_THREAD.rsplit("-", 1)[1])
SCREW_TIP_CHAMFER = 0.7 * SCREW_PITCH  # 45 deg x 0.7P point (the vendor model)

SEAT_THREAD_DEPTH = 14.7  # .X
SEAT_DRILL_DEPTH = 18.0  # .X
SEAT_SPEC = HoleSpec(
    "tapped_bottoming",
    SCREW_THREAD,
    end="blind",
    depth_mm=SEAT_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": SEAT_THREAD_DEPTH},
)
SEAT_DRILL_DIA = TAP_DRILL_MM[SCREW_THREAD]
SEAT_DRILL_NAME = next(
    name for name, dia in NUMBER_DRILL_MM.items() if dia == SEAT_DRILL_DIA
)  # #29, for the print's process line
SEAT_DRILL_POINT = SEAT_DRILL_DIA / 2.0 * DRILL_POINT_H
SEAT_DRILL_BOTTOM_MAX = SEAT_DRILL_DEPTH + LINEAR_1PL + SEAT_DRILL_POINT

# The rail: its top face is the casting's top (local y +HALF_Y); its underside
# is the window's top edge. The window's bottom edge stays FOOT_THICKNESS over
# the foot face, so the window is symmetric about local x only. The seat drill
# is already as short as the bottoming tap's lead allows, so the rail is the
# shallowest .X depth that keeps the 2.0 web target of cast iron under the
# drill point at the printed worst case (Codex #936 PRRT_kwDOPHDy386mS91G: at
# 21.0 the floor was 0.36).
RAIL_DEPTH = round(
    math.ceil((SEAT_DRILL_BOTTOM_MAX + LINEAR_1PL + RULE12_WEB_TARGET) * 10.0 - 1e-9)
    / 10.0,
    1,
)  # 22.7, .X on the print
WINDOW_TOP_Y = HALF_Y - RAIL_DEPTH  # local 66.2 (machine y 205.9)
WINDOW_BOTTOM_Y = FOOT_THICKNESS - HALF_Y  # local -82.55, unchanged
WINDOW_HEIGHT = WINDOW_TOP_Y - WINDOW_BOTTOM_Y  # 148.75
SEAT_FLOOR_MIN = RAIL_DEPTH - LINEAR_1PL - SEAT_DRILL_BOTTOM_MAX


def _bracket_seat_z(mount_z: float) -> tuple[float, ...]:
    """Machine z of one bracket's two hold-down holes.

    The channel assembly places the south bracket (inboard = +z) IDENTITY and
    turns the north one Ry180 about its origin, so its foot runs toward -z.
    """
    sign = 1.0 if mount_z < STACK_MID_Z else -1.0
    return tuple(mount_z + sign * hole_z for hole_z in _bracket.HOLE_Z)


# Machine (x, z) of the four seats, south bracket first. The brackets sit on
# the support's centreline, and each hole is on the bracket's x = 0.
SEAT_MACHINE_XZ = tuple(
    (SUPPORT_WORLD_X, z)
    for mount_z in PIVOT_BRACKET_Z
    for z in _bracket_seat_z(mount_z)
)
# The support is turned +90 deg about machine Y: local X -> machine -Z and
# local Z -> machine +X, so a seat on its centreline is local (X, Z) =
# (SUPPORT_WORLD_Z - z, 0).
SEAT_LOCAL_X = tuple(SUPPORT_WORLD_Z - z for _x, z in SEAT_MACHINE_XZ)

# Worst-case stack at the printed limits.
FOOT_H_RANGE = (_bracket.FOOT_H - LINEAR_2PL, _bracket.FOOT_H + LINEAR_2PL)
SCREW_REACH_MAX = SCREW_LENGTH + SCREW_LENGTH_BAND[0] - FOOT_H_RANGE[0]
SCREW_REACH_MIN = SCREW_LENGTH - SCREW_LENGTH_BAND[1] - FOOT_H_RANGE[1]
ENGAGEMENT_MIN = SCREW_REACH_MIN - SCREW_TIP_CHAMFER - EDGE_BREAK
RAIL_WALL = NARROW - SCREW_MAJOR_DIA / 2.0  # beside the thread, at the top face

if ENGAGEMENT_MIN < 1.5 * SCREW_MAJOR_DIA:
    raise AssertionError(
        f"bracket screw keeps {ENGAGEMENT_MIN:.2f} of thread at worst case,"
        f" under 1.5D ({1.5 * SCREW_MAJOR_DIA:.2f})"
    )
if SCREW_REACH_MAX + EDGE_BREAK > SEAT_THREAD_DEPTH - LINEAR_1PL:
    raise AssertionError("bracket screw tip reaches the seat's incomplete threads")
if SEAT_DRILL_DEPTH - LINEAR_1PL < SEAT_THREAD_DEPTH + LINEAR_1PL + 2.0 * SCREW_PITCH:
    raise AssertionError(
        "bracket seat drill loses the bottoming-tap lead at worst case"
    )
if SEAT_FLOOR_MIN < RULE12_WEB_TARGET:
    raise AssertionError(
        f"bracket seat drill point reaches {SEAT_DRILL_BOTTOM_MAX:.2f} deep, leaving"
        f" {SEAT_FLOOR_MIN:.2f} of the {RAIL_DEPTH:.1f} (.X) rail over the window,"
        f" under the {RULE12_WEB_TARGET} web"
    )
if RAIL_WALL < RULE12_WEB_TARGET:
    raise AssertionError("bracket seat thread leaves under 2.0 of rail wall")
if max(abs(x) for x in SEAT_LOCAL_X) + SEAT_DRILL_DIA / 2.0 > HALF_Y - EDGE_BREAK:
    raise AssertionError("a bracket seat runs off the end of the support rail")

__all__ = [
    "EDGE_BREAK",
    "ENGAGEMENT_MIN",
    "LINEAR_1PL",
    "LINEAR_2PL",
    "RAIL_DEPTH",
    "RAIL_WALL",
    "SCREW_LENGTH",
    "SCREW_REACH_MAX",
    "SCREW_REACH_MIN",
    "SCREW_THREAD",
    "SEAT_DRILL_BOTTOM_MAX",
    "SEAT_DRILL_DEPTH",
    "SEAT_DRILL_NAME",
    "SEAT_FLOOR_MIN",
    "SEAT_LOCAL_X",
    "SEAT_MACHINE_XZ",
    "SEAT_SPEC",
    "SEAT_THREAD_DEPTH",
    "WINDOW_BOTTOM_Y",
    "WINDOW_HEIGHT",
    "WINDOW_TOP_Y",
]
