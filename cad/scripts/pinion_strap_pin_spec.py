r"""Pure-data contract for the torque-shaft set pins (option E-a).

User ruling (2026-09-24, ch25 page001_img01 strap-foot dot): one slotted
spring pin runs through each MHA-056 strap's foot and the MHA-062 torque
shaft, so strap, shaft and strap swing as one group in the MHA-061 block
bores.  The blocks still locate the straps (ruling (c)) and the pins make the
straps locate the shaft: no collar, no spacer.  The user then chose the
IMPERIAL pin for historical accuracy: ASME B18.8.2, 1/16 x 1/2, in a hole
drilled with the same 1/16 drill as the MHA-135 lever pin.

PURE DATA, no SolidWorks/COM imports and no drive-train imports: the strap
and shaft specs read it, the drive-train assembly never does.
"""

from __future__ import annotations

from _fit_limits import SHAFT_H
from _printed_tolerance import printed_deviations
from pinion_bracket_geometry import (
    CROSS_HOLE_CZ_PLACES,
    CROSS_HOLE_FROM_BORE_WALL_PLACES,
    END_RADIUS_PLACES,
    PIN_BORE,
    PIN_DROP,
    PIVOT_BORE,
    R_END,
    THICKNESS,
    THICKNESS_PLACES,
)

INCH = 25.4
PIN_STANDARD = "ASME B18.8.2"
PIN_DIA = INCH / 16.0  # 1/16 in
PIN_LEN = INCH / 2.0  # 1/2 in
# McMaster 98296A027 (_fastener_catalog), read live on September 25, 2026:
# 1050-1095 spring steel, 0.012 in wall.  The catalog gives no slot or
# chamfer size, so the stock recipe models neither.
WALL_T = 0.012 * INCH
# B18.8.2 cuts the length to +/-0.010 in.
PIN_LEN_BAND = 0.010 * INCH

HOLE_DIA = PIN_DIA
# The one drill for every 1/16 pin on the rig (this pin, the MHA-135 lever pin
# and the arbor-collar pin): the callout a sheet uses when it drills rather
# than match-drills.
DRILL_THRU_CALLOUT = "1/16 DRILL THRU"
# A functional band, not habit (U27): B18.8.2's recommended hole for a 1/16
# pin is 0.062-0.065 in (1.575-1.651).  The title block's DRILLED HOLES row
# (+0.10/0) would let the hole open to 1.69, past what the pin can grip, so
# the hole carries its own +0.06/0 band on its diameter dimension.
HOLE_BAND = (0.06, 0.0)
HOLE_MAX = HOLE_DIA + HOLE_BAND[0]
if not (0.062 * INCH <= HOLE_DIA and HOLE_MAX <= 0.065 * INCH):
    raise AssertionError("pin hole band leaves B18.8.2's recommended hole")

# The deviations the hole's surroundings PRINT at (_printed_tolerance): each
# dimension's title-block row for the places MHA-056 shows it at, plus the
# rounding of a nominal that does not print exactly (the 3.175 bore-wall
# offset prints at two places).  Places come from pinion_bracket_geometry,
# which the sheet's DRAWING_PRECISION also reads (restricted review).
_THICKNESS_LOWER = printed_deviations(THICKNESS, THICKNESS_PLACES)[0]
_CROSS_HOLE_CZ_UPPER = printed_deviations(THICKNESS / 2.0, CROSS_HOLE_CZ_PLACES)[1]
_BORE_WALL_OFFSET_MAX = max(
    abs(d)
    for d in printed_deviations(PIVOT_BORE / 2.0, CROSS_HOLE_FROM_BORE_WALL_PLACES)
)
_R_END_LOWER = printed_deviations(R_END, END_RADIUS_PLACES)[0]

# Web from the cross hole to the FAR broad face (Codex #858 P2).  MHA-056
# prints the hole's station from broad face A at .XX (the model's own
# CrossHoleCz, half the thickness), so the far face sees the thinnest bar (.X
# minus band) less the station at its .XX maximum, the hole's upper-limit
# radius and the 0.05 drilled-hole allowance.  The near-face web is larger.
STRAP_FACE_WEB_WORST = (
    (THICKNESS + _THICKNESS_LOWER)
    - (THICKNESS / 2.0 + _CROSS_HOLE_CZ_UPPER)
    - HOLE_MAX / 2.0
    - 0.05
)
# Ligament from the cross hole to the MHA-116 follower seat 7 above it.
FOLLOWER_SEAT_LIGAMENT = abs(PIN_DROP) - HOLE_MAX / 2.0 - PIN_BORE / 2.0
# Shaft wall beside the match-drilled hole.  The hole must cross the shaft
# axis: an offset e from it thins one side by e.  MHA-056 prints the strap
# hole's height as its distance from the pivot-bore wall (the model's own
# "PivotBore" / 2 reference, Codex #858 P2 user ruling (a)) at .XX, so the
# offset is read against the full general .XX grade -- the worst case below,
# which still clears the 1.5 floor, so no tighter band (and no position
# frame, which rule 3 bars on a bracket) is needed.  A V-block set-up holding
# 0.25 leaves SHAFT_LIGAMENT_QUARTER.
# The MHA-062 shaft is the pivot bore's own nominal (a lockstep test pins it).
_SHAFT_MIN = PIVOT_BORE + SHAFT_H[1]
SHAFT_LIGAMENT_CENTRED = (_SHAFT_MIN - HOLE_MAX) / 2.0
SHAFT_LIGAMENT_QUARTER = SHAFT_LIGAMENT_CENTRED - 0.25
SHAFT_LIGAMENT_WORST = SHAFT_LIGAMENT_CENTRED - _BORE_WALL_OFFSET_MAX
# The pin must never stand proud of either strap edge: its west end faces the
# MHA-104 cam collar with only 0.38 of air at the printed worst case.  The
# longest pin fits inside the narrowest strap foot (twice the smallest .X
# end-cap radius), so driven flush-or-below on the west edge it is buried on
# the east edge too; a centred nominal pin sits PIN_CENTRED_SUB_FLUSH under
# both edges.
STRAP_FOOT_MIN_WIDTH = 2.0 * (R_END + _R_END_LOWER)
PIN_BURIED_MARGIN = STRAP_FOOT_MIN_WIDTH - (PIN_LEN + PIN_LEN_BAND)
PIN_CENTRED_SUB_FLUSH = (STRAP_FOOT_MIN_WIDTH - PIN_LEN) / 2.0

if STRAP_FACE_WEB_WORST < 2.0:
    raise AssertionError(f"strap face web {STRAP_FACE_WEB_WORST:.2f} is under 2.0")
if FOLLOWER_SEAT_LIGAMENT < 2.0:
    raise AssertionError(
        f"follower-seat ligament {FOLLOWER_SEAT_LIGAMENT:.2f} is under 2.0"
    )
if SHAFT_LIGAMENT_WORST < 1.5:
    raise AssertionError(f"shaft ligament {SHAFT_LIGAMENT_WORST:.2f} is under 1.5")
if PIN_BURIED_MARGIN < 0.0:
    raise AssertionError("the longest pin stands proud of the narrowest strap foot")
