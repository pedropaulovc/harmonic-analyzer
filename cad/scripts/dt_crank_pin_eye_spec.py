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
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_deviations

# Mean loop radius (an O5.3 eye, photo-scaled, low): the Ø3.3 inside diameter
# is the least one-place size whose title-block lower limit still admits the
# keeper chain's bead (dt_vn_keeper_chain_spec asserts the air).
LOOP_R = 2.15
WIRE_DIA = 1.0  # brass wire (low)
TAIL_LEN = 4.0  # straight tail from the loop's tangent point to under the screw head
# Air the drive train leaves between the tail wire and the arm face, the screw
# head and the wire, and the tail end and the screw shank.
ANCHOR_AIR = 0.02

LOOP_INNER_R = LOOP_R - WIRE_DIA / 2.0
# The loop's inside diameter prints at the title block's one place on the
# eye's sheet: an accepted loop lies anywhere in these limits.
LOOP_ID = 2.0 * LOOP_INNER_R
LOOP_ID_PLACES = 1
LOOP_ID_MIN, LOOP_ID_MAX = (
    round(LOOP_ID + deviation, 12)
    for deviation in printed_deviations(LOOP_ID, LOOP_ID_PLACES)
)
V_LOOP = 2.0 * math.pi**2 * LOOP_R * (WIRE_DIA / 2.0) ** 2
V_TAIL = math.pi * (WIRE_DIA / 2.0) ** 2 * TAIL_LEN
