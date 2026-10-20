r"""Pure-data contract for the oblique trammel's HUB locator pin
(MHA-CH-06-TL-25; shop tooling, one off).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). Once
the running jig has reamed the carrier's (MHA-CH-06-TL-21) HUB hole to
Ø10.20 H7 in place, this headed pin is pressed up into it from under the
carrier. Its head is the press stop; its upper section passes the riser's
(MHA-CH-06-TL-24) Ø12 clearance and locates the strap (MHA-CH-13) by the
strap's hole, so the strap's hub sits on the circle the jig cuts
(``ch_rocker_arm_tl_oblique_trammel_spec``).

Material: 1144 stress-proof steel, 3/4 in round, turned in one chucking.
Stock: Ø19.05 bar; finished envelope Ø16 x 24 (modelled), supplied
``SUPPLY_LENGTH_MIN`` 26.8 MIN long and faced to fit at assembly.

Frame: the pin axis is model +Z; the origin is on the axis at the bottom face
of the head; the head runs z 0..4, the press seat z 4..16 and the strap
locator z 16..24. In the carrier frame the head's top face seats on the
carrier's underside, so carrier z = model z - HEAD_LENGTH - CARRIER_THICK.

Sections, bottom to top:

1. Head Ø16 x 4, the press stop under the carrier.
2. Press seat Ø10.20 p6 (10.218/10.229), 12 long (⚙ ``CARRIER_THICK``),
   in the HUB hole Ø10.20 H7: 0.000-0.029 diametral interference.
   Sensitivity: an interference fit leaves no play, so the hub position is
   the reamed hole's position.
3. Strap locator Ø10.20 g6 (10.183/10.194), 8 long (⚙ ``RISER_THICK`` 6 plus
   the strap's 2.5 ``ARM_THICKNESS``, less 0.5 so its top sits under the
   strap top), in the strap's Ø10.20 H7 hole (user ruling: names
   ``MHA-CH-13 STRAP HOLE``): 0.006-0.035 diametral clearance.
   Sensitivity: the clearance is hub-position error 1:1.

A 0.5 x 45 degree lead chamfer finishes the top, cut again after the facing
below. The model carries each fit section at its low limit (the pivot pin's
convention), so the p6 seat (10.218) and the g6 locator (10.183) are two
faces with a real 0.035 step at z 16, and each prints +0.011/0 to the same
limits as its fit.

Lengths print as the lathe reads them (rule 11): the head thickness 4.0 and
the press seat 12.0 as a baseline from the head's seating face (its top face,
which bears on the TL-21 carrier). The 8.0 locator is the remainder.

Rule 19: head, faced carrier and faced riser (each at the .X title-block
band) put the locator's top anywhere in 2.0 ± 2.4 above the riser against a
2.5 strap, so the pin is supplied long and its top is faced in place after
the riser is screwed down, to
``LOCATOR_SET_MIN``-``LOCATOR_SET_MAX`` (1.80-2.20) above the riser top: the
g6 cylinder engages the strap hole at least ``STRAP_ENGAGEMENT_MIN`` past the
chamfer and the top stays under the strap's. The 24.0 overall prints as a
reference under that fit-up callout.

The internal corner between the press seat and the head carries an R0.2 MAX
fillet (rule 16). A fillet of radius r clears a hole edge only if the edge
is broken by at least r (chamfer leg or radius). The title block sets no
minimum break, so a hole edge left nearly sharp would let the fillet hold
the head off its seat: the HUB hole is reamed in place at assembly, and
that step breaks its underside edge ``HUB_HOLE_UNDERSIDE_BREAK_MIN`` (0.3)
MIN x 45 degrees, the carrier pin holes' own break for the pivot pins'
collar fillet.

Rule 16 (knockout): the head stands below the carrier with nothing above the
pin but the riser's clearance, so a drift on the pin's top end presses it out
downward, head first, through the open underside of the carrier.
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _fit_deviations import deviations
from _printed_tolerance import printed_band_mm

STOCK_DIA = 19.05  # 3/4 in 1144 round

# --- Head: the press stop -----------------------------------------------------
HEAD_DIA = 16.0
HEAD_LENGTH = 4.0
HEAD_PLACES = 1
LENGTH_PLACES = 1
if not HEAD_DIA < STOCK_DIA:
    raise AssertionError("the hub pin head does not clean up on its stock")

# --- Matched fits (ISO 286, 10-18 mm row: IT6 0.011, IT7 0.018) ---------------
FIT_DIA = 10.20
FIT_PLACES = 3
HUB_HOLE_BAND = (0.018, 0.0)  # (upper, lower): Ø10.20 H7, reamed in place
STRAP_HOLE_BAND = (0.018, 0.0)  # Ø10.20 H7 in MHA-CH-13
SEAT_BAND = (0.029, 0.018)  # p6
LOCATOR_BAND = (-0.006, -0.017)  # g6

_seat_low, _seat_high = deviations(SEAT_BAND)
_hub_low, _hub_high = deviations(HUB_HOLE_BAND)
SEAT_INTERFERENCE_MIN = round(_seat_low - _hub_high, 6)
SEAT_INTERFERENCE_MAX = round(_seat_high - _hub_low, 6)
if (SEAT_INTERFERENCE_MIN, SEAT_INTERFERENCE_MAX) != (0.0, 0.029):
    raise AssertionError("the hub pin press seat is not the 0.000-0.029 p6/H7 fit")

_loc_low, _loc_high = deviations(LOCATOR_BAND)
_strap_low, _strap_high = deviations(STRAP_HOLE_BAND)
LOCATOR_CLEARANCE_MIN = round(_strap_low - _loc_high, 6)
LOCATOR_CLEARANCE_MAX = round(_strap_high - _loc_low, 6)
if (LOCATOR_CLEARANCE_MIN, LOCATOR_CLEARANCE_MAX) != (0.006, 0.035):
    raise AssertionError("the hub pin locator is not the 0.006-0.035 g6/H7 fit")

# Each section is modelled at its fit's low limit and printed +IT6/0: the
# same limits, distinct diameters (an equal nominal merges the two faces).
SEAT_DIA = round(FIT_DIA + SEAT_BAND[1], 6)  # 10.218
SEAT_PRINT_BAND = (round(SEAT_BAND[0] - SEAT_BAND[1], 6), 0.0)  # +0.011/0
LOCATOR_DIA = round(FIT_DIA + LOCATOR_BAND[1], 6)  # 10.183
LOCATOR_PRINT_BAND = (round(LOCATOR_BAND[0] - LOCATOR_BAND[1], 6), 0.0)
if (
    round(SEAT_DIA + SEAT_PRINT_BAND[1], 6),
    round(SEAT_DIA + SEAT_PRINT_BAND[0], 6),
) != (round(FIT_DIA + _seat_low, 6), round(FIT_DIA + _seat_high, 6)):
    raise AssertionError("the printed press seat limits are not the p6 limits")
if (
    round(LOCATOR_DIA + LOCATOR_PRINT_BAND[1], 6),
    round(LOCATOR_DIA + LOCATOR_PRINT_BAND[0], 6),
) != (round(FIT_DIA + _loc_low, 6), round(FIT_DIA + _loc_high, 6)):
    raise AssertionError("the printed strap locator limits are not the g6 limits")
if not SEAT_DIA > round(LOCATOR_DIA + LOCATOR_PRINT_BAND[0], 6):
    raise AssertionError("the seat-to-locator step can vanish inside the bands")

# --- Section lengths -----------------------------------------------------------
SEAT_LENGTH = trammel.CARRIER_THICK  # ⚙ fills the carrier's HUB hole
LOCATOR_TOP_BELOW_STRAP = 0.5
LOCATOR_LENGTH = (
    trammel.RISER_THICK + rocker.ARM_THICKNESS - LOCATOR_TOP_BELOW_STRAP
)  # ⚙ 8.0
SEAT_STATION = HEAD_LENGTH + SEAT_LENGTH  # head bottom to the seat's top
OVERALL_LENGTH = SEAT_STATION + LOCATOR_LENGTH
# The lead chamfer prints as a single MAX limit (swTolMAX, as the shoulder
# radius below): at one place's ±0.8 a 1.3 leg would leave the faced locator
# 0.5 in the strap (Codex #1582), so the strap stack below holds at its MAX.
LEAD_CHAMFER = 0.5
LEAD_CHAMFER_PLACES = 1
# Shoulder radius (rule 16) at the press seat's root against the head, printed
# as a single MAX limit (swTolMAX prints the model value, so the model carries
# the printed maximum; the pivot pin's SeatFillet convention).
SHOULDER_FILLET_RADIUS = 0.2
FILLET_PLACES = 1
RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
# The jig assembly's HUB step breaks the carrier's HUB hole underside edge
# at least this much (chamfer leg), so the head fillet seats.
HUB_HOLE_UNDERSIDE_BREAK_MIN = 0.3
if not SHOULDER_FILLET_RADIUS <= HUB_HOLE_UNDERSIDE_BREAK_MIN:
    raise AssertionError("the head fillet is larger than the HUB hole's break")

# The locator passes the riser's Ø12 clearance; the head bears on the carrier
# outside the reamed hole.
RISER_HUB_CLEARANCE_DIA = 12.0
if not SEAT_DIA + SEAT_PRINT_BAND[0] < RISER_HUB_CLEARANCE_DIA:
    raise AssertionError("the hub pin does not pass the riser's Ø12 clearance")
if not HEAD_DIA > FIT_DIA + HUB_HOLE_BAND[0]:
    raise AssertionError("the hub pin head does not stop on the carrier")
if not LEAD_CHAMFER < LOCATOR_LENGTH:
    raise AssertionError("the lead chamfer eats the strap locator")

# --- The top, faced to fit at assembly (rule 19) ---------------------------------
# Head, faced carrier and faced riser stack under the locator's top. Each
# native dimension prints at one place (±0.8), so the top above the riser
# could fall anywhere in 2.0 ± 2.4 (±3.2 with a turned overall's own band)
# against a 2.5 strap. The inch starting stock does not enter this stack.
# Supply the pin long and face it in place once the riser is screwed down:
# the strap engages the cylinder above the riser, and the top stays below
# the strap's top face.
LOCATOR_SET_ABOVE_RISER = LOCATOR_LENGTH - trammel.RISER_THICK  # ⚙ 2.0
LOCATOR_SET_BAND = 0.2
LOCATOR_SET_MIN = LOCATOR_SET_ABOVE_RISER - LOCATOR_SET_BAND  # 1.8
LOCATOR_SET_MAX = LOCATOR_SET_ABOVE_RISER + LOCATOR_SET_BAND  # 2.2
STRAP_ENGAGEMENT_MIN = 1.0  # g6 cylinder in the strap hole, past the chamfer
if not LOCATOR_SET_MAX < rocker.ARM_THICKNESS + rocker.ARM_THICKNESS_BAND[1]:
    raise AssertionError("the faced HUB pin top can stand above the strap")
if not LOCATOR_SET_MIN - LEAD_CHAMFER >= STRAP_ENGAGEMENT_MIN:
    raise AssertionError("the faced HUB pin engages the strap hole too little")
FACING_ALLOWANCE = 0.2
_HEAD_BAND = printed_band_mm(LENGTH_PLACES)
SUPPLY_LENGTH_MIN = round(
    (HEAD_LENGTH + _HEAD_BAND)
    + (trammel.CARRIER_THICK + trammel.CARRIER_THICK_BAND)
    + (trammel.RISER_THICK + trammel.RISER_THICK_BAND)
    + LOCATOR_SET_MAX
    + FACING_ALLOWANCE,
    6,
)  # 26.8: the finished .X bands remain ±0.8 after the stock cutover.

# --- Print ---------------------------------------------------------------------
# One turned profile carries every size; the head fillet carries its radius.
# The locator's 8.0 is the remainder of the overall, so it does not print.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {
        "HeadDia",
        "HeadLength",
        "SeatDia",
        "SeatLength",
        "LocatorDia",
        "PinLength",
        "LeadChamfer",
    },
    "HeadFillet": {"HeadFilletR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "HeadDia": HEAD_PLACES,
        "HeadLength": LENGTH_PLACES,
        "SeatDia": FIT_PLACES,
        "SeatLength": LENGTH_PLACES,
        "LocatorDia": FIT_PLACES,
        "PinLength": LENGTH_PLACES,
        "LeadChamfer": LEAD_CHAMFER_PLACES,
    },
    "HeadFillet": {"HeadFilletR": FILLET_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked hub-pin dimension needs authored places")

# drawing-guidelines rule 4: each tight band is a matched-fit callout naming
# its mate. Callouts ride the below lane, one short line each (SolidWorks
# does not wrap callout text).
SEAT_CALLOUT = (
    f"{SEAT_INTERFERENCE_MIN:.3f}-{SEAT_INTERFERENCE_MAX:.3f} DIAMETRAL\n"
    "INTERFERENCE ON\nMHA-CH-06-TL-21 HUB HOLE"
)
LOCATOR_CALLOUT = (
    f"{LOCATOR_CLEARANCE_MIN:.3f}-{LOCATOR_CLEARANCE_MAX:.3f} DIAMETRAL\n"
    "CLEARANCE ON\nMHA-CH-13 STRAP HOLE"
)
SEAT_NOTE = " ".join(SEAT_CALLOUT.splitlines())
LOCATOR_NOTE = " ".join(LOCATOR_CALLOUT.splitlines())
LEAD_CHAMFER_CALLOUT = "X 45° LEAD CHAMFER"
DIMENSION_CALLOUTS = {
    "SeatDia": SEAT_CALLOUT,
    "LocatorDia": LOCATOR_CALLOUT,
    "LeadChamfer": LEAD_CHAMFER_CALLOUT,
}
# Rule 19: the overall prints as a reference with its fit-up stacked under
# its value, between its extension lines (close-c3-r3 review: one line above
# it read as a floating note, not the overall's). It names the faced end and
# the recut lead chamfer (close-c4-r2 review). Below, not above: SOLIDWORKS
# drops a multi-line callout above a value from the print
# (draw_ch_amplitude_bar r1; jig-r12 here).
PIN_LENGTH_CALLOUT = (
    f"SUPPLY {SUPPLY_LENGTH_MIN:.1f} MIN;\n"
    "FACE LOCATOR END AT ASSEMBLY\n"
    f"{LOCATOR_SET_MIN:.2f}-{LOCATOR_SET_MAX:.2f} ABOVE MHA-CH-06-TL-24;\n"
    "RECUT LEAD CHAMFER"
)
PIN_LENGTH_NOTE = " ".join(PIN_LENGTH_CALLOUT.splitlines())
PIN_LENGTH_REFERENCE = "PinLength"
REFERENCE_CALLOUTS = {PIN_LENGTH_REFERENCE: PIN_LENGTH_CALLOUT}

# Notes never carry dimensions or methods; the fits ride their callouts.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
