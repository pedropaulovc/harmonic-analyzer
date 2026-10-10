r"""MHA-FR-005's central web and the rocker pivot brackets' hold-down seats (#743 PR2).

PURE DATA, no SolidWorks/COM imports: ``build_fr_rocker_arm_support`` cuts the
web and its seats from it, and the channel assembly places the screws from
it. Kept out of ``fr_rocker_arm_support_section_spec`` on purpose: the base,
frame and drive train import that module, and a web or seat edit must not
re-key them.

Each MHA-CH-008 bracket is held by one MHA-VN-032 (McMaster 90280A197, #8-32 x
3/4 slotted fillister) through its #8 close-clearance foot hole into a
bottoming-tapped seat in the support's top face, transferred from the set
bracket at assembly (the south bracket is blade-set off the preload spring's
washer, so its seat cannot be cast or pre-drilled).

The brackets' feet run outboard to the support's end faces (user-approved
sketch, 2026-10-09), so each seat lies over the window's side edge: the post
outboard, the central web and its R6.35 pocket-corner fillet inboard. Under
the top rail (the source casting's 6.35, no longer deepened as #743 had it)
the seat runs down the web column, which the cavity (|x| < 63.5) never
reaches, so the drill point has cast iron under it to the window bottom. What
bounds the seat is the web's thickness: 2 * WEB, 9.525 (3/8 in), thickened
from the source's 6.35 so the thread keeps the 2.0 wall to both web faces.

Each seat is transferred from its bracket's hole, so it lands wherever the
bracket's own bands put that hole: the support's end face, the bracket's
station and its foot length all move the thread toward the end wall.

The stack is checked at the printed worst case: MHA-CH-008's foot height at
.XX and its foot length and station at +/-0.10, the seat depths and the
support's 177.8 length at .X, the web at .XX, the screw at its +0/-0.76
commercial length band, and the 0.25 edge break at the seat mouth. Every check
raises on import.
"""

from __future__ import annotations

import ch_pivot_bracket_spec as _bracket
from _hole_spec import (
    DRILL_POINT_H,
    NUMBER_DRILL_MM,
    TAP_DRILL_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
)
from ch_pivot_bracket_sides import CONFIGURATIONS, HOLE_MACHINE_Z
from fr_rocker_arm_support_section_spec import HALF_Y
from fr_rocker_arm_support_spec import SUPPORT_WORLD_X, SUPPORT_WORLD_Z

LINEAR_1PL = 0.8  # title-block .X band
LINEAR_2PL = 0.508  # title-block .XX band
EDGE_BREAK = 0.25  # title-block edge break, also the novice spare
RULE12_WEB_TARGET = 2.0

# MHA-VN-032: the channel assembly pins these to the stock part it places.
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

# The central web: each window cut STARTS WEB off the mid-plane, leaving a
# 2 * WEB web (build_fr_rocker_arm_support). The print carries its thickness at
# .XX, so each face may stand half that band closer to the seat's axis.
WEB = 4.7625  # 9.525 (3/8 in) web
WEB_PLACES = 2

# Machine (x, z) of the two seats, south bracket first: each under its
# bracket's one hold-down hole, on the support's centreline (the brackets sit
# on it, and each hole is on the bracket's x = 0).
SEAT_MACHINE_XZ = tuple(
    (SUPPORT_WORLD_X, HOLE_MACHINE_Z[name]) for name in CONFIGURATIONS
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
# Beside the thread, to either web face, at the web's printed worst case.
WEB_WALL_MIN = WEB - LINEAR_2PL / 2.0 - SCREW_MAJOR_DIA / 2.0
# From the thread to the support's end face on its side, at the worst
# transferred position: the end face moves by half the support length's .X
# band, the hole by the bracket's station and foot-length bands.
END_WALL_MIN = tuple(
    (HALF_Y - abs(x))
    - SCREW_MAJOR_DIA / 2.0
    - _bracket.STATION_BAND
    - _bracket.FOOT_LEN_BAND
    - LINEAR_1PL / 2.0
    for x in SEAT_LOCAL_X
)  # S 2.14, N 2.99

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
if WEB_WALL_MIN < RULE12_WEB_TARGET:
    raise AssertionError(
        f"bracket seat thread leaves {WEB_WALL_MIN:.2f} to the web faces at worst"
        f" case, under the {RULE12_WEB_TARGET} web"
    )
if max(abs(x) for x in SEAT_LOCAL_X) + SEAT_DRILL_DIA / 2.0 > HALF_Y - EDGE_BREAK:
    raise AssertionError("a bracket seat runs off the end of the support")
if min(END_WALL_MIN) < RULE12_WEB_TARGET:
    raise AssertionError(
        f"bracket seat thread leaves {min(END_WALL_MIN):.2f} to the support's end"
        f" face at worst case, under the {RULE12_WEB_TARGET} wall"
    )

__all__ = [
    "EDGE_BREAK",
    "END_WALL_MIN",
    "ENGAGEMENT_MIN",
    "LINEAR_1PL",
    "LINEAR_2PL",
    "SCREW_LENGTH",
    "SCREW_REACH_MAX",
    "SCREW_REACH_MIN",
    "SCREW_THREAD",
    "SEAT_DRILL_BOTTOM_MAX",
    "SEAT_DRILL_DEPTH",
    "SEAT_DRILL_NAME",
    "SEAT_LOCAL_X",
    "SEAT_MACHINE_XZ",
    "SEAT_SPEC",
    "SEAT_THREAD_DEPTH",
    "WEB",
    "WEB_PLACES",
    "WEB_WALL_MIN",
]
