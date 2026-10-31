r"""MHA-FR-05's central web and the rocker pivot brackets' hold-down seats (#743 PR2).

PURE DATA, no SolidWorks/COM imports: ``build_fr_rocker_arm_support`` cuts the
web and its seats from it, and the channel assembly places the screws from
it. Kept out of ``fr_rocker_arm_support_section_spec`` on purpose: the base,
frame and drive train import that module, and a web or seat edit must not
re-key them.

Each MHA-CH-08 bracket is held by one MHA-CH-VN-57 (McMaster 90280A196, #8-32 x
5/8 slotted fillister; owner Q13c, 2026-10-16) through its #8 close-clearance
foot hole into a bottoming-tapped seat in the support's top face, transferred
from the set bracket at assembly (the south bracket is blade-set off the
preload spring's washer, so its seat cannot be cast or pre-drilled). The 5/8
length keeps 1.5D in the cast iron at worst case with the shallowest seat.

The brackets' feet run outboard toward the support's end faces (user-approved
sketch, 2026-10-09; the one MHA-CH-08 ends flush with the south end face and
short of the north one, #1341), so each seat lies over the window's side edge:
the post outboard, the central web and its R6.35 pocket-corner fillet inboard. Under
the top rail (the source casting's 6.35, no longer deepened as #743 had it)
the seat runs down the web column, which the cavity (|x| < 63.5) never
reaches, so the drill point has cast iron under it to the window bottom. What
bounds the seat is the web's thickness: 2 * WEB, 12.70 (1/2 in), uniform along
the support's length and symmetric about its centre plane (owner Q13c,
2026-10-16; the source cast 6.35).

Across the web the seat lands where the bracket's foot puts its hole: each
edge of the top flat prints off its nearer web face, a cast surface, at .XX
(owner Q13d, 2026-10-16; Q13-B had them off the web's centre plane, which
carries no feature until the seats are transferred; the r5 review read .XXX
as over-specified, and .XX keeps the wall). The foot may stand anywhere on
the flat up to flush with either edge, the hole sits off the foot's far side
at its own .XX centring band, and the transfer punch (11/64,
dt_arbor_pedestal_spec's) floats in the close hole at its drilled maximum.
The thread keeps the 2.0 wall to both web faces at that worst lateral offset:
to the face the flush edge is measured from, the web's .XX thickness band is
out of the chain; to the far face it enters.

Each seat is transferred from its bracket's hole, so it lands wherever the
bracket's own bands put that hole: the support's end face and the bracket's
station move the thread toward the end wall. The station is given from the
ear's inboard face, the face fit-up sets, so the foot length's band is not in
this chain (user, 2026-10-10, option ii).

The stack is checked at the printed worst case: MHA-CH-08's foot height at
.XX and its station at +/-0.10, the seat depths and the
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
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm
from ch_pivot_bracket_sides import HOLE_MACHINE_Z, SIDES
from fr_rocker_arm_support_section_spec import NARROW
from fr_rocker_arm_support_spec import (
    SUPPORT_HALF_MACHINE_Z,
    SUPPORT_WORLD_X,
    SUPPORT_WORLD_Z,
)

LINEAR_1PL = printed_band_mm(1)  # title-block .X band
LINEAR_2PL = 0.508  # title-block .XX band
LINEAR_3PL = 0.127  # title-block .XXX band
EDGE_BREAK = edge_break_chamfer_mm()  # title-block edge break, also the novice spare
RULE12_WEB_TARGET = 2.0

# MHA-CH-VN-57: the channel assembly pins these to the stock part it places.
SCREW_THREAD = "#8-32"
SCREW_LENGTH = 15.875  # under-head length, 5/8 in
SCREW_LENGTH_BAND = (0.0, 0.76)  # (+, -): commercial screw length tolerance
SCREW_MAJOR_DIA = THREAD_MAJOR_MM[SCREW_THREAD]
SCREW_PITCH = 25.4 / float(SCREW_THREAD.rsplit("-", 1)[1])
SCREW_TIP_CHAMFER = 0.7 * SCREW_PITCH  # 45 deg x 0.7P point (the vendor model)

SEAT_THREAD_DEPTH = 11.5062  # .453
SEAT_DRILL_DEPTH = 14.7066  # .579
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
WEB = 6.35  # 12.70 (1/2 in) web (owner Q13c)
WEB_PLACES = 2
# Each top-flat edge off its nearer web face (owner Q13d), 2.1165.
TOP_FLAT_EDGE_FROM_WEB = NARROW - WEB
TOP_FLAT_PLACES = 2

# Machine (x, z) of the two seats, south bracket first: each under its
# bracket's one hold-down hole, on the support's centreline (the brackets sit
# on it, and each hole is on the bracket's x = 0).
SEAT_MACHINE_XZ = tuple((SUPPORT_WORLD_X, HOLE_MACHINE_Z[name]) for name in SIDES)
# The support is turned +90 deg about machine Y: local X -> machine -Z and
# local Z -> machine +X, so a seat on its centreline is local (X, Z) =
# (SUPPORT_WORLD_Z - z, 0).
SEAT_LOCAL_X = tuple(SUPPORT_WORLD_Z - z for _x, z in SEAT_MACHINE_XZ)

# Worst-case stack at the printed limits.
FOOT_H_RANGE = (_bracket.FOOT_H - LINEAR_2PL, _bracket.FOOT_H + LINEAR_2PL)
SCREW_REACH_MAX = SCREW_LENGTH + SCREW_LENGTH_BAND[0] - FOOT_H_RANGE[0]
SCREW_REACH_MIN = SCREW_LENGTH - SCREW_LENGTH_BAND[1] - FOOT_H_RANGE[1]
ENGAGEMENT_MIN = SCREW_REACH_MIN - SCREW_TIP_CHAMFER - EDGE_BREAK
# The foot flush with one flat edge, that edge at either end of its .XX band
# off its web face (the near face), the transfer punch's float in the hole
# at its drilled maximum. Toward the near face: the edge at its outermost,
# the hole at its nearest to the flush side (the foot's narrowest, the hole's
# centring band toward the far side). Toward the far face: the edge at its
# innermost, the hole at its farthest, the web at its thinnest.
TRANSFER_PUNCH_DIA = 11.0 / 64.0 * 25.4
TOP_FLAT_EDGE_BAND = {1: LINEAR_1PL, 2: LINEAR_2PL, 3: LINEAR_3PL}[TOP_FLAT_PLACES]
HOLE_FROM_FOOT_SIDE_MIN = (_bracket.FOOT_W - _bracket.EDGE_BAND) - (
    _bracket.FOOT_W / 2.0 + _bracket.HOLE_X_BAND
)  # 6.98
HOLE_FROM_FOOT_SIDE_MAX = (_bracket.FOOT_W + _bracket.EDGE_BAND) - (
    _bracket.FOOT_W / 2.0 - _bracket.HOLE_X_BAND
)  # 9.02
PUNCH_FLOAT = (_bracket.HOLE_DIA + _bracket.DRILL_GROWTH - TRANSFER_PUNCH_DIA) / 2.0
SEAT_FROM_NEAR_FACE_MIN = (
    HOLE_FROM_FOOT_SIDE_MIN
    - (TOP_FLAT_EDGE_FROM_WEB + TOP_FLAT_EDGE_BAND)
    - PUNCH_FLOAT
)  # 4.21
SEAT_FROM_FAR_FACE_MIN = (2.0 * WEB - LINEAR_2PL) - (
    HOLE_FROM_FOOT_SIDE_MAX
    + PUNCH_FLOAT
    - (TOP_FLAT_EDGE_FROM_WEB - TOP_FLAT_EDGE_BAND)
)  # 4.63
# Beside the thread, to either web face, at the seat's worst offset.
WEB_WALL_MIN = (
    min(SEAT_FROM_NEAR_FACE_MIN, SEAT_FROM_FAR_FACE_MIN) - SCREW_MAJOR_DIA / 2.0
)  # 2.12
# From the thread to the support's end face on its side, at the worst
# transferred position: the end face moves by half the support length's .X
# band, the hole by the bracket's station band from the fit-up-set ear face.
# The end faces lie SUPPORT_HALF_MACHINE_Z off the casting's centre along
# local X (its length; the height is a different 177.8).
END_WALL_MIN = tuple(
    (SUPPORT_HALF_MACHINE_Z - abs(x))
    - SCREW_MAJOR_DIA / 2.0
    - _bracket.STATION_BAND
    - LINEAR_1PL / 2.0
    for x in SEAT_LOCAL_X
)  # S 2.36, N 3.97

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
if (
    max(abs(x) for x in SEAT_LOCAL_X) + SEAT_DRILL_DIA / 2.0
    > SUPPORT_HALF_MACHINE_Z - EDGE_BREAK
):
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
    "HOLE_FROM_FOOT_SIDE_MAX",
    "HOLE_FROM_FOOT_SIDE_MIN",
    "LINEAR_1PL",
    "LINEAR_2PL",
    "LINEAR_3PL",
    "PUNCH_FLOAT",
    "SCREW_LENGTH",
    "SCREW_REACH_MAX",
    "SCREW_REACH_MIN",
    "SCREW_THREAD",
    "SEAT_DRILL_BOTTOM_MAX",
    "SEAT_DRILL_DEPTH",
    "SEAT_DRILL_NAME",
    "SEAT_FROM_FAR_FACE_MIN",
    "SEAT_FROM_NEAR_FACE_MIN",
    "SEAT_LOCAL_X",
    "SEAT_MACHINE_XZ",
    "SEAT_SPEC",
    "SEAT_THREAD_DEPTH",
    "TOP_FLAT_EDGE_BAND",
    "TOP_FLAT_EDGE_FROM_WEB",
    "TOP_FLAT_PLACES",
    "TRANSFER_PUNCH_DIA",
    "WEB",
    "WEB_PLACES",
    "WEB_WALL_MIN",
]
