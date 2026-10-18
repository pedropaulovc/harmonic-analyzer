r"""Pure-data contract for the oblique trammel's pivot pin
(MHA-CH-006-TL-23; shop tooling, two off).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). Each
pivot block (MHA-CH-006-TL-22) carries two 6200-2RS bearings back to back
about a 4 mm shoulder; this pin is pressed through both inner races for life
and its upper section stands in one of the carrier's (MHA-CH-006-TL-21)
Ø10 H7 pin holes, so the carrier swings about the bearing axis
(``ch_rocker_arm_tl_oblique_trammel_spec``, imported as ``trammel``).

Material: 1144 stress-proof steel, 1/2 in round, turned in one chucking.
Stock: Ø12.70 bar; finished envelope Ø12.70 x 37 (the collar is the bar).

Frame: the pin axis is model +Z; the origin is on the axis at the pin's
bottom end. The bearing section runs z 0..22, the collar z 22..26 and the
carrier section z 26..37. In the pivot block's frame the collar's underside
seats on the upper inner race, so block z = model z + ``BEARING_RECESS``.

Sections, bottom to top (⚙ marks calculator values):

1. Bearing section Ø10 k5 (10.001/10.007), 22 long: ⚙ ``BEARINGS_PER_PIN``
   x ``BEARING_WIDTH`` (9) plus ⚙ ``BEARING_SHOULDER`` (4), so it fills both
   inner races. In the 6200-2RS bore (10 0/-0.008, inventory
   ``fixtures.trammel-6200-2rs``): 0.001-0.015 diametral interference.
   Sensitivity: the press leaves no play at the race, so the pin axis is the
   inner races' axis; the bearings' own C3 radial play is the calculator's
   ``RADIUS_FROM_BEARING_PLAY``. k5, not p6 (Codex, #1578; Main ruling 4,
   2026-10-17): with the TL-22 N6 seat a p6 press could turn the 8 µm
   minimum C3 clearance into a 24 µm preload (NTN: 70 % of the shaft's
   interference less 7 µm smoothing, 60 % of the seat's); k5 leaves 7 µm
   play at mid-limits and at worst a 12 µm preload.
2. Collar Ø12.70 x 4, the bar as supplied (⚙ ``PIN_COLLAR_HEIGHT``: the
   1 mm ⚙ ``BEARING_RECESS`` plus the 3 mm ⚙ ``PIN_COLLAR_PROUD``). It
   seats on the upper inner race only (6200 da min 12, below the outer race
   and the seal) and stands 3 above the block; the carrier rests on it. It
   prints at two places, so even the title block's low limit (12.19) seats
   on the race's abutment.
3. Carrier section Ø10 h6 (9.991/10.000), 11 long (⚙ ``CARRIER_THICK`` less
   1, so the pin never stands proud of the carrier top), in the carrier's
   Ø10 H7 pin hole (10.000/10.015): 0.000-0.024 diametral clearance.
   Sensitivity: the clearance is carrier edge error 1:1.

0.5 x 45 degree lead chamfers finish both ends. Both shoulder corners carry
R0.2 MAX: under the 6200's 0.6 bore chamfer and the carrier hole's
title-block edge break, so each mate seats on the collar's flat face.

Rule 16 (knockout): the block's bore is open from below, so a drift on the
pin's top end, with the block supported on its top face, presses the pin
out downward through both inner races and out of the block bottom.
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _fit_deviations import deviations
from _printed_tolerance import printed_band_mm

STOCK_DIA = 12.7  # 1/2 in 1144 round
LENGTH_PLACES = 1

# --- Collar ---------------------------------------------------------------------
# The bar's own OD: cold-drawn 1144 is +0/-0.002 in, so no cut is needed to
# hold the abutment, and the print's two places keep its low limit on it too.
COLLAR_DIA = STOCK_DIA
COLLAR_PLACES = 2
STOCK_DIA_MIN = STOCK_DIA - 0.002 * 25.4
BEARING_DA_MIN = 12.0  # 6200 abutment diameter, minimum (SKF)
if not BEARING_DA_MIN <= COLLAR_DIA - printed_band_mm(COLLAR_PLACES):
    raise AssertionError("the printed collar's low limit misses the inner race")
if not BEARING_DA_MIN <= STOCK_DIA_MIN:
    raise AssertionError("the smallest bar misses the inner race")

# --- Matched fits (ISO 286, 6-10 mm row: IT5 0.006, IT6 0.009, IT7 0.015) -----
FIT_DIA = trammel.BEARING_BORE  # ⚙ 10
FIT_PLACES = 3
RACE_BORE_BAND = (0.0, -0.008)  # (upper, lower): 6200-2RS bore (inventory)
PIN_HOLE_BAND = (0.015, 0.0)  # Ø10 H7, the carrier's reamed pin holes
BEARING_BAND = (0.007, 0.001)  # k5 (docstring: p6 would preload the 6200s)
CARRIER_BAND = (0.0, -0.009)  # h6

_bearing_low, _bearing_high = deviations(BEARING_BAND)
_race_low, _race_high = deviations(RACE_BORE_BAND)
BEARING_INTERFERENCE_MIN = round(_bearing_low - _race_high, 6)
BEARING_INTERFERENCE_MAX = round(_bearing_high - _race_low, 6)
if (BEARING_INTERFERENCE_MIN, BEARING_INTERFERENCE_MAX) != (0.001, 0.015):
    raise AssertionError("the pivot pin bearing section is not the 0.001-0.015 fit")

_carrier_low, _carrier_high = deviations(CARRIER_BAND)
_hole_low, _hole_high = deviations(PIN_HOLE_BAND)
CARRIER_CLEARANCE_MIN = round(_hole_low - _carrier_high, 6)
CARRIER_CLEARANCE_MAX = round(_hole_high - _carrier_low, 6)
if (CARRIER_CLEARANCE_MIN, CARRIER_CLEARANCE_MAX) != (0.0, 0.024):
    raise AssertionError("the pivot pin carrier section is not the 0.000-0.024 fit")
# The model carries the bearing section at the k5 low limit (an exported
# nominal lies inside its band) and prints it as Ø10.001 +0.006/0: the
# same 10.001/10.007 limits.
BEARING_DIA = round(FIT_DIA + BEARING_BAND[1], 6)
BEARING_PRINT_BAND = (round(BEARING_BAND[0] - BEARING_BAND[1], 6), 0.0)

# --- Section lengths -------------------------------------------------------------
BEARING_LENGTH = (
    trammel.BEARINGS_PER_PIN * trammel.BEARING_WIDTH + trammel.BEARING_SHOULDER
)  # ⚙ 22.0
COLLAR_HEIGHT = trammel.PIN_COLLAR_HEIGHT  # ⚙ 4.0
CARRIER_TOP_SHORTFALL = 1.0
CARRIER_LENGTH = trammel.CARRIER_THICK - CARRIER_TOP_SHORTFALL  # ⚙ 11.0
COLLAR_STATION = BEARING_LENGTH  # bottom end to the collar's seat face
CARRIER_STATION = COLLAR_STATION + COLLAR_HEIGHT  # bottom end to the collar top
OVERALL_LENGTH = CARRIER_STATION + CARRIER_LENGTH
# The hidden named axis on the turned axis that the jig assembly mates the
# carrier's holes on: a name pick is view-independent, a face point is not.
AXIS_NAME = "PinAxis"
# The print reads from the top end, faced in the turning chucking (rule 11):
# top to the collar top, top to the collar seat, and the overall length.
TOP_TO_COLLAR_SEAT = OVERALL_LENGTH - COLLAR_STATION
LEAD_CHAMFER = 0.5
LEAD_CHAMFER_PLACES = 1
SHOULDER_FILLET_RADIUS = 0.2
FILLET_PLACES = 1
RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
BEARING_BORE_CHAMFER_MIN = 0.6  # 6200 r1,2 min

if COLLAR_HEIGHT != trammel.BEARING_RECESS + trammel.PIN_COLLAR_PROUD:
    raise AssertionError("the collar does not stand PIN_COLLAR_PROUD above the block")
if not 0.0 < CARRIER_LENGTH < trammel.CARRIER_THICK:
    raise AssertionError("the pivot pin stands proud of the carrier top")
if not LEAD_CHAMFER < min(BEARING_LENGTH, CARRIER_LENGTH):
    raise AssertionError("a lead chamfer eats a fit section")
if not SHOULDER_FILLET_RADIUS < BEARING_BORE_CHAMFER_MIN:
    raise AssertionError("the collar fillet fouls the inner race's bore chamfer")

# --- Print -----------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {
        "BearingDia",
        "CollarDia",
        "CarrierDia",
        "CarrierLength",
        "CollarSeatStation",
        "PinLength",
        "BottomChamfer",
        "TopChamfer",
    },
    "SeatFillet": {"SeatFilletR"},
    "CarrierFillet": {"CarrierFilletR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "BearingDia": FIT_PLACES,
        "CollarDia": COLLAR_PLACES,
        "CarrierDia": FIT_PLACES,
        "CarrierLength": LENGTH_PLACES,
        "CollarSeatStation": LENGTH_PLACES,
        "PinLength": LENGTH_PLACES,
        "BottomChamfer": LEAD_CHAMFER_PLACES,
        "TopChamfer": LEAD_CHAMFER_PLACES,
    },
    "SeatFillet": {"SeatFilletR": FILLET_PLACES},
    "CarrierFillet": {"CarrierFilletR": FILLET_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-pin dimension needs authored places")

# drawing-guidelines rule 4: each tight band is a matched-fit callout naming
# its mate. Callouts ride the below lane, one short line each (SolidWorks
# does not wrap callout text).
BEARING_CALLOUT = (
    f"{BEARING_INTERFERENCE_MIN:.3f}-{BEARING_INTERFERENCE_MAX:.3f} DIAMETRAL\n"
    "INTERFERENCE ON\n6200-2RS INNER RACE"
)
CARRIER_CALLOUT = (
    f"{CARRIER_CLEARANCE_MIN:.3f}-{CARRIER_CLEARANCE_MAX:.3f} DIAMETRAL\n"
    "CLEARANCE ON\nMHA-CH-006-TL-21 PIN HOLES"
)
BEARING_NOTE = " ".join(BEARING_CALLOUT.splitlines())
CARRIER_NOTE = " ".join(CARRIER_CALLOUT.splitlines())
LEAD_CHAMFER_CALLOUT = "X 45° LEAD CHAMFER"
DIMENSION_CALLOUTS = {
    "BearingDia": BEARING_CALLOUT,
    "CarrierDia": CARRIER_CALLOUT,
    "BottomChamfer": LEAD_CHAMFER_CALLOUT,
    "TopChamfer": LEAD_CHAMFER_CALLOUT,
}

# Notes never carry dimensions or methods; the fits ride their callouts.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
