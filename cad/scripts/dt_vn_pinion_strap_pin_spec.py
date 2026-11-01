r"""Pure-data contract for the torque-shaft set pins (option E-a).

User ruling (2026-09-24, ch25 page001_img01 strap-foot dot): one slotted
spring pin runs through each MHA-DT-14 strap's foot and the MHA-DT-19 torque
shaft, so strap, shaft and strap swing as one group in the MHA-DT-18 block
bores.  The blocks still locate the straps (ruling (c)) and the pins make the
straps locate the shaft: no collar, no spacer.  The user then chose the
IMPERIAL pin for historical accuracy: ASME B18.8.2, 1/16 x 1/2, in a hole
drilled with the same 1/16 drill as the MHA-DT-30 lever pin.

PURE DATA, no SolidWorks/COM imports and no drive-train imports: the strap
and shaft specs read it, the drive-train assembly never does.
"""

from __future__ import annotations

import math

import _config
from _fit_ream_slide import REAM_SLIDE
from _fit_shaft_h import SHAFT_H
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _supplier_pin_data import SupplierPinReference
from dt_pinion_bracket_geometry import (
    CROSS_HOLE_CZ_PLACES,
    END_RADIUS_PLACES,
    PIN_BORE,
    PIN_DROP,
    PIVOT_BORE,
    R_END,
    THICKNESS,
    THICKNESS_PLACES,
    UNIT,
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
# The one drill for every 1/16 pin on the rig (this pin, the MHA-DT-30 lever pin
# and the arbor-collar pin): the callout a sheet uses when it drills rather
# than match-drills.
DRILL_THRU_CALLOUT = "1/16 DRILL THRU"
# A functional band, not habit (U27): B18.8.2's recommended hole for a 1/16
# pin is .062-.065 in.  The title block's DRILLED HOLES row (+.004/0) would
# let the hole open to .0665, past what the pin can grip, so the hole carries
# its own +.0025/.0000 band on its diameter dimension: .0625-.0650.
HOLE_BAND = (0.0635, 0.0)
HOLE_MAX = HOLE_DIA + HOLE_BAND[0]
if not (0.062 * INCH <= HOLE_DIA and HOLE_MAX <= 0.065 * INCH + 1e-9):
    raise AssertionError("pin hole band leaves B18.8.2's recommended hole")

# The deviations the hole's surroundings PRINT at (_printed_tolerance): each
# dimension's title-block row for the places MHA-DT-14 shows it at, in its
# unit.  Places come from dt_pinion_bracket_geometry, which the sheet's
# DRAWING_PRECISION also reads (restricted review).
_THICKNESS_LOWER = printed_deviations(THICKNESS, THICKNESS_PLACES, unit=UNIT)[0]
_CROSS_HOLE_CZ_UPPER = printed_deviations(
    THICKNESS / 2.0, CROSS_HOLE_CZ_PLACES, unit=UNIT
)[1]
# The hole's height prints no offset: its centre sits on the pivot-axis line
# the flank view draws (an implied zero).  A zero carries no decimal places,
# so no single title-block row owns it (Codex P1 on #1663): it is charged the
# coarsest row a located feature may print at.  On the inch sheet that is
# .XX: the owner's ruling keeps .X for profiles, chamfers and unmated
# overall lengths only (#290).
IMPLIED_ZERO_PLACES = 2
_AXIS_OFFSET_MAX = max(
    abs(d) for d in printed_deviations(0.0, IMPLIED_ZERO_PLACES, unit=UNIT)
)
_R_END_LOWER = printed_deviations(R_END, END_RADIUS_PLACES, unit=UNIT)[0]

# Web from the cross hole to the FAR broad face (Codex #858 P2).  MHA-DT-14
# prints the hole's station from broad face A at .XX (.18, the model's own
# CrossHoleCz, half the thickness), so the far face sees the thinnest bar
# (.XXX minus band) less the station at its printed maximum, the hole's
# upper-limit radius and the 0.05 drilled-hole allowance.  The near-face web
# is larger.
STRAP_FACE_WEB_WORST = (
    (THICKNESS + _THICKNESS_LOWER)
    - (THICKNESS / 2.0 + _CROSS_HOLE_CZ_UPPER)
    - HOLE_MAX / 2.0
    - 0.05
)
# Ligament from the cross hole to the MHA-DT-25 follower seat 7 above it.
FOLLOWER_SEAT_LIGAMENT = abs(PIN_DROP) - HOLE_MAX / 2.0 - PIN_BORE / 2.0
# Shaft wall beside the match-drilled hole.  The hole must cross the shaft
# axis: an offset e from it thins one side by e.  MHA-DT-14 draws the strap
# hole's centre ON the pivot-axis line of its flank view (r1 machinist
# review, ENFORCE #1007: the former 3.18 offset from the pivot-bore wall ran
# to a hidden line, rule 9), so e is that implied zero at the .XX grade:
# 2.339 centred less .010 in leaves 2.085, over the .080 in target.  The
# MHA-DT-19 shaft is the ruled 1/4 in, the pin the smallest B18.8.2 size
# (1/16), and the hole band B18.8.2's recommended window; no print tolerance
# is tighter than the title block, and no position frame, which
# drawing-guidelines.md rule 5 (avoid excessive GD&T) bars on a bracket.  A
# V-block set-up holding 0.25 leaves SHAFT_LIGAMENT_QUARTER.
# The MHA-DT-19 shaft is the pivot bore's own nominal (a lockstep test pins it).
SHAFT_LIGAMENT_FLOOR = WALL_FLOOR_MM
_SHAFT_MIN = PIVOT_BORE + SHAFT_H[1]
SHAFT_LIGAMENT_CENTRED = (_SHAFT_MIN - HOLE_MAX) / 2.0
SHAFT_LIGAMENT_QUARTER = SHAFT_LIGAMENT_CENTRED - 0.25
SHAFT_LIGAMENT_WORST = SHAFT_LIGAMENT_CENTRED - _AXIS_OFFSET_MAX
# The pin must never stand proud of either strap edge: its west end faces the
# MHA-DT-23 cam collar with only 0.38 of air at the printed worst case.  The
# longest pin fits inside the narrowest strap foot (twice the smallest
# end-cap radius), so driven flush-or-below on the west edge it is buried on
# the east edge too; a centred nominal pin sits PIN_CENTRED_SUB_FLUSH under
# both edges.
STRAP_FOOT_MIN_WIDTH = 2.0 * (R_END + _R_END_LOWER)
PIN_BURIED_MARGIN = STRAP_FOOT_MIN_WIDTH - (PIN_LEN + PIN_LEN_BAND)
PIN_CENTRED_SUB_FLUSH = (STRAP_FOOT_MIN_WIDTH - PIN_LEN) / 2.0

# The drive's acceptance (Codex #858, PRRT_kwDOPHDy386mV2GL): each pin end
# 0 to PIN_SUB_FLUSH_MAX below its strap edge.  The 0 keeps the pin out of
# the 0.38 of air to the MHA-DT-23 collar.  The upper limit keeps each strap
# wall gripping PIN_WALL_ENGAGEMENT_FLOOR of pin past the pivot bore: with
# one end PIN_SUB_FLUSH_MAX down, the shortest pin reaches
# (L - S - bore) / 2 into the far wall at the widest foot it can still sit
# inside, so S is the loosest 0.1 step that keeps that over the floor.  One
# pin diameter per wall is the least grip this rig accepts.  The window
# holds every pin in every foot: the most the two ends must share, widest
# foot less shortest pin, is under 2 S.
_R_END_UPPER = printed_deviations(R_END, END_RADIUS_PLACES, unit=UNIT)[1]
STRAP_FOOT_MAX_WIDTH = 2.0 * (R_END + _R_END_UPPER)
PIVOT_BORE_MAX = PIVOT_BORE + REAM_SLIDE[0]  # MHA-DT-14 PIVOT_BORE_BAND
PIN_WALL_ENGAGEMENT_FLOOR = PIN_DIA
_PIN_LEN_MIN = PIN_LEN - PIN_LEN_BAND
PIN_SUB_FLUSH_MAX = (
    math.floor(
        round((_PIN_LEN_MIN - PIVOT_BORE_MAX - 2.0 * PIN_WALL_ENGAGEMENT_FLOOR) * 10.0, 9)
    )
    / 10.0
)
PIN_WALL_ENGAGEMENT_WORST = (_PIN_LEN_MIN - PIN_SUB_FLUSH_MAX - PIVOT_BORE_MAX) / 2.0
PIN_DRIVE_SHARE_MAX = STRAP_FOOT_MAX_WIDTH - _PIN_LEN_MIN

if STRAP_FACE_WEB_WORST < WALL_TARGET_MM:
    raise AssertionError(f"strap face web {STRAP_FACE_WEB_WORST:.3f} is under .080 in")
if FOLLOWER_SEAT_LIGAMENT < WALL_TARGET_MM:
    raise AssertionError(
        f"follower-seat ligament {FOLLOWER_SEAT_LIGAMENT:.3f} is under .080 in"
    )
if SHAFT_LIGAMENT_WORST < SHAFT_LIGAMENT_FLOOR:
    raise AssertionError(
        f"shaft ligament {SHAFT_LIGAMENT_WORST:.3f} is under the"
        f" {SHAFT_LIGAMENT_FLOOR} floor"
    )
if PIN_BURIED_MARGIN < 0.0:
    raise AssertionError("the longest pin stands proud of the narrowest strap foot")
if PIN_WALL_ENGAGEMENT_WORST < PIN_WALL_ENGAGEMENT_FLOOR:
    raise AssertionError("a pin at the sub-flush limit barely grips the far strap wall")
if PIN_DRIVE_SHARE_MAX > 2.0 * PIN_SUB_FLUSH_MAX:
    raise AssertionError("the widest foot cannot hold the shortest pin in the window")

# Inspected McMaster engineering drawing, 2026-10-19. The .063 print is
# three-place presentation of the exact installed 1/16 cylinder; the
# supplier's hole range belongs to a separate MATING HOLE reference.
# The pin's own sheet unit (#290 drawing_unit), which drops the supplier REFs'
# " in" on an inch sheet (_supplier_pin_model._reference_suffix).
SHEET_UNIT = drawing_unit("parts/dt-vn-pinion-strap-pin", _config.parts("dt-vn-pinion-strap-pin"))
SUPPLIER_REFERENCE = SupplierPinReference(
    sku="98296A027",
    units="in",
    diameter_mm=PIN_DIA,
    length_mm=PIN_LEN,
    diameter_nominal=0.063,
    diameter_precision=3,
    length_precision=3,
    wall_mm=WALL_T,
    wall_precision=3,
    application_hole_limits=(0.062, 0.065),
    application_hole_precision=3,
    sheet_unit=SHEET_UNIT,
)
