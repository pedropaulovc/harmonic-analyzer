r"""Crank keeper-chain anchor eye (MHA-DT-28) nominals, pure data.

No SolidWorks/COM calls and no ``build_*`` module in the import closure: the
eye build, the keeper chain and the drive-train assembly read these here, so
the eye's build recipe never rides a consumer's cache key (#880).

The formed brass eye (ch11 p.14 page001_img02) has a straight tail clamped
under the arm's anchor screw and a closed loop turned 90 deg up off the arm
face, like the photographed hook. The loop's hole axis runs across the arm
width, so the keeper chain can thread it. A loop lying flat on the face would
have the arm plate in its hole.

Part frame: the tail root, where the tail runs tangent into the loop, is the
origin. The tail runs along +Y, lying on the arm face. The loop is in the YZ
plane, centred LOOP_R along -Z (away from the face), so its hole axis is X.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``); the wire is
.040 in brass wire, and the loop and tail print at .XX because the chain's
bead and the anchor screw read them.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations

UNIT = drawing_unit("parts/dt-crank-pin-eye", _config.parts("dt-crank-pin-eye"))

WIRE_DIA = 1.016  # .040 brass wire (low)
# Mean loop radius (photo-scaled, low): the Ø.13 inside diameter's .XX lower
# limit still admits the keeper chain's bead (dt_vn_keeper_chain_spec asserts
# the air).
LOOP_R = (3.302 + WIRE_DIA) / 2.0  # .13 ID
# Straight tail from the loop's tangent point to under the screw head.
TAIL_LEN = 4.064  # .16
# Air the drive train leaves between the tail wire and the arm face, the screw
# head and the wire, and the tail end and the screw shank.
ANCHOR_AIR = 0.02

LOOP_INNER_R = LOOP_R - WIRE_DIA / 2.0
# The loop's inside diameter prints at the title block's two places on the
# eye's sheet: an accepted loop lies anywhere in these limits.
LOOP_ID = 2.0 * LOOP_INNER_R
LOOP_ID_PLACES = 2
LOOP_ID_MIN, LOOP_ID_MAX = (
    round(LOOP_ID + deviation, 12)
    for deviation in printed_deviations(LOOP_ID, LOOP_ID_PLACES, unit=UNIT)
)
V_LOOP = 2.0 * math.pi**2 * LOOP_R * (WIRE_DIA / 2.0) ** 2
V_TAIL = math.pi * (WIRE_DIA / 2.0) ** 2 * TAIL_LEN
