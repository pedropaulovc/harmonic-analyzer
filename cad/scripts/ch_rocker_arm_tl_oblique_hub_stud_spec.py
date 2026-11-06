r"""MHA-CH-06-TL-33: oblique-trammel hub clamp stud, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop fixture tooling
(cad/docs/subsystem-identities.md): the turned steel stud that replaces the
bonded TL-VN-80 gauge pin (retired 2026-11-06).  Its shank slips up through
the TL-21 carrier's unchanged .4000 REAM_H7 HUB bore, its flange bears on the
carrier's underside and takes the hub screw's pull, and its nose stands
``TIP_SET`` proud of the TL-24 riser to locate the MHA-CH-13 strap's HUB hole
exactly as the gauge pin did (nose Ø and proud height unchanged).  A #10-24
blind tap in the nose takes the TL-VN-85 low-head screw that clamps the strap
through the TL-35 brass washer; the TL-34 steel sleeve rides the shank inside
the riser's HUB clearance and supports the strap under the washer.

The shank is a free slip in the carrier bore (.3990-.3995 in the
.4000-.4005 reamed hole, .0005-.0015 diametral); the nose keeps the gauge
pin's .4000 -.0001/0 because it locates the strap (owner, 2026-11-06).
The flange is the owner's literal 18 x 3 mm (parent ruling 2026-11-06: the
model keeps the exact millimetres; the inch sheet prints them .709 x .118).

Proud height is a fit-up adjustment (drawing-guidelines rule 19): the
carrier (.47) and riser (.24) each carry the .XX band, so no part band can
hold the gauge pin's .080 +/-.008 proud.  The model is the INSTALLED stud
(nose top ``TIP_SET`` above the nominal riser); the sheet prints the
flange-top-to-nose length as a reference set at assembly and the supply
length a stud is turned to before it is faced to fit, as a single MIN limit
(the cut-to-fit idiom of TL-VN-64).  ``SUPPLY_LENGTH_MIN`` covers the
thickest carrier and riser at the band's top.

Part frame: stud axis +Z through the origin (``Axis1``, Top Plane x Right
Plane); the flange underside on the Front Plane (z = 0), the flange top
(the carrier seat) at z = FLANGE_THICK, the nose top at z = LENGTH.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _fit_ream_h7 import REAM_H7
from _hole_spec import DRILL_POINT_H, THREAD_MAJOR_MM, TAP_DRILL_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from ch_rocker_arm_spec import inch_text

STEM = "ch-rocker-arm-tl-oblique-hub-stud"
UNIT = drawing_unit(f"parts/{STEM}", _config.parts(STEM))
NUMBER = _config.parts(STEM)["number"]
QUANTITY = 1
INCH = trammel.INCH

# --- Flange: the owner's literal 18 x 3 mm ----------------------------------
FLANGE_DIA = 18.0  # prints .709
FLANGE_THICK = 3.0  # prints .118
FLANGE_PLACES = 3

# --- Shank: free slip in the carrier's HUB bore -----------------------------
# The bore is the carrier's .4000 REAM_H7 (+.0005/0); the shank .3995/.3990.
CARRIER_BORE_DIA = 10.16  # .4000, the TL-21 HUB bore's reamer
SHANK_DIA = 10.1473  # .3995
SHANK_DIA_BAND = (0.0, -0.0127)  # upper, lower: .3990-.3995
SHANK_DIA_PLACES = 4
SHANK_CLEARANCE = (
    CARRIER_BORE_DIA + REAM_H7[1] - (SHANK_DIA + SHANK_DIA_BAND[0]),
    CARRIER_BORE_DIA + REAM_H7[0] - (SHANK_DIA + SHANK_DIA_BAND[1]),
)
# The shank runs from the flange seat through the carrier and the riser.
SHANK_LENGTH = trammel.CARRIER_THICK + trammel.RISER_THICK  # .71
SHANK_LENGTH_PLACES = 2

# --- Nose: the gauge pin's locating diameter and proud height ---------------
DIA = 10.16  # .4000
DIA_BAND = (0.0, -0.00254)  # upper, lower: .3999-.4000
DIA_PLACES = 4
TIP_SET = 2.032  # .080 above the actual riser, set at assembly
TIP_SET_BAND = 0.2032  # +/-.008
NOSE_LENGTH = TIP_SET
LENGTH = FLANGE_THICK + SHANK_LENGTH + NOSE_LENGTH
# Flange seat to nose top: the length the fitter faces to (reference).
FIT_LENGTH = SHANK_LENGTH + NOSE_LENGTH  # .79
FIT_LENGTH_PLACES = 2

# Supply length above the flange seat: the thickest carrier and riser at their
# .XX bands plus the proud at its band's top, rounded UP to the .01 grid.
_CARRIER_MAX = trammel.CARRIER_THICK + trammel.CARRIER_THICK_BAND
_RISER_MAX = trammel.RISER_THICK + trammel.RISER_THICK_BAND
_FIT_MAX = _CARRIER_MAX + _RISER_MAX + TIP_SET + TIP_SET_BAND
SUPPLY_LENGTH_PLACES = 2
SUPPLY_LENGTH_MIN = (
    math.ceil(round(_FIT_MAX / INCH * 10**SUPPLY_LENGTH_PLACES, 9))
    / 10**SUPPLY_LENGTH_PLACES
    * INCH
)  # .82
SUPPLY_LENGTH_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints ".82 MIN"
# (upper, lower) deviations: the nominal IS the limit; any excess is faced off.
SUPPLY_LENGTH_BAND = (printed_band_mm(SUPPLY_LENGTH_PLACES, unit=UNIT), 0.0)
if SUPPLY_LENGTH_MIN <= FIT_LENGTH:
    raise AssertionError("the hub stud supply leaves nothing to face to fit")

# --- Shank root ---------------------------------------------------------------
# The flange top seats on the carrier's underside, so the internal corner at
# the shank root is printed as a single MAX limit (sharp is good, anything up
# to the limit is good): .008 clears the carrier's broken bore mouth (the
# pn_pen_rod shoulder precedent).
ROOT_FILLET_R = 0.2032  # .008
ROOT_FILLET_BAND = (0.0, -ROOT_FILLET_R)
ROOT_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.008 MAX"
ROOT_FILLET_PLACES = 3
if SHANK_DIA / 2.0 + ROOT_FILLET_R >= FLANGE_DIA / 2.0:
    raise AssertionError("the root radius must end inside the flange seat")

# --- #10-24 blind tap in the nose: the TL-VN-85 hub screw ------------------
TAP_THREAD = "#10-24"
TAP_MAJOR = THREAD_MAJOR_MM[TAP_THREAD]
TAP_DRILL_DIA = TAP_DRILL_MM[TAP_THREAD]  # #25 drill
TAP_PITCH = INCH / 24.0
TAP_DEPTH_PLACES = 2
# Full thread from the finished nose face, past the screw's deepest reach.
TAP_FULL_DEPTH = 11.684  # .46
# Drill depth: the full thread plus room for a plug tap's lead.
TAP_DRILL_DEPTH = 16.51  # .65
TAP_SPEC = HoleSpec(
    "tapped",
    TAP_THREAD,
    end="blind",
    depth_mm=TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": TAP_FULL_DEPTH},
)
_TAP_DEPTH_BAND = printed_band_mm(TAP_DEPTH_PLACES, unit=UNIT)
TAP_FULL_DEPTH_MIN = TAP_FULL_DEPTH - _TAP_DEPTH_BAND
TAP_LEAD_ROOM_PITCHES = (TAP_DRILL_DEPTH - TAP_FULL_DEPTH - 2.0 * _TAP_DEPTH_BAND) / TAP_PITCH
TAP_POINT_BOTTOM_Z = LENGTH - TAP_DRILL_DEPTH - TAP_DRILL_DIA / 2.0 * DRILL_POINT_H

# Rule 17: the thread major to the smallest shank, at the worst case.
TAP_WALL = (SHANK_DIA + SHANK_DIA_BAND[1] - TAP_MAJOR) / 2.0
FLANGE_WALL_ABOVE_POINT = TAP_POINT_BOTTOM_Z - FLANGE_THICK

if SHANK_CLEARANCE[0] <= 0.0:
    raise AssertionError("the hub stud shank does not slip in the carrier bore")
if DIA + DIA_BAND[0] > CARRIER_BORE_DIA + REAM_H7[1]:
    raise AssertionError("the hub stud nose does not pass the carrier bore")
if TAP_WALL < WALL_TARGET_MM:
    raise AssertionError("the nose tap breaks rule 17's .080 wall target")
if TAP_LEAD_ROOM_PITCHES < 3.0:
    raise AssertionError("the nose tap drill leaves under three pitches of tap lead")
if FLANGE_WALL_ABOVE_POINT <= 0.0:
    raise AssertionError("the nose tap drill point reaches the flange")
if NOSE_LENGTH >= trammel.STRAP_THICK:
    raise AssertionError("the hub stud nose stands above the strap")

# Marked model dimensions and the places the part authors on them.  The end
# view's diameters move onto the side view (rule 11).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlangeProfile": {"FlangeDia"},
    "Flange": {"FlangeThick"},
    "ShankProfile": {"ShankDia"},
    "Shank": {"ShankLength"},
    "NoseProfile": {"NoseDia"},
    "RootFillet": {"RootRadius"},
    "FitReference": {"FitLength", "SupplyLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FlangeProfile": {"FlangeDia": FLANGE_PLACES},
    "Flange": {"FlangeThick": FLANGE_PLACES},
    "ShankProfile": {"ShankDia": SHANK_DIA_PLACES},
    "Shank": {"ShankLength": SHANK_LENGTH_PLACES},
    "NoseProfile": {"NoseDia": DIA_PLACES},
    "RootFillet": {"RootRadius": ROOT_FILLET_PLACES},
    "FitReference": {
        "FitLength": FIT_LENGTH_PLACES,
        "SupplyLength": SUPPLY_LENGTH_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for names in DRAWING_PRECISION.values() for name, places in names.items()
}
# (feature, dimension) -> (upper, lower) native band (rule 4: both fits).
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("ShankProfile", "ShankDia"): SHANK_DIA_BAND,
    ("NoseProfile", "NoseDia"): DIA_BAND,
}

CARRIER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
RISER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
STRAP_NUMBER = _config.parts("ch-rocker-strap")["number"]
# Every tight band names its mate (rule 4); the root names the seat it must
# not hold off; the fit and supply lengths say how the proud is set (rule 19).
DIMENSION_CALLOUTS: dict[str, str] = {
    "ShankDia": f"SLIP FIT IN\n{CARRIER_NUMBER} HUB BORE",
    "NoseDia": f"LOCATES {STRAP_NUMBER}\nHUB HOLE",
    "RootRadius": f"SEATS ON\n{CARRIER_NUMBER}",
    "FitLength": (
        f"FIT AT ASSEMBLY: NOSE {inch_text(TIP_SET, 3)}"
        f" +/-{inch_text(TIP_SET_BAND, 3)}\nABOVE {RISER_NUMBER}"
    ),
    "SupplyLength": "SUPPLY",
}
