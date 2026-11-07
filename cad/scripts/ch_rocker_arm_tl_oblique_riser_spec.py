r"""R4 6061 riser clearance contract (MHA-CH-06-TL-24).

The .24 in seat supports the faced strap. The HUB has a literal 12 mm
drill relief for the in-place product-hole operation, not a sleeve socket.
CL/CR have loose #8 clearances for two common screws. No LEFT hole or
precision dowel remains. Four #4 flat-head screws retain the riser.

Two plain stock 1/8 x 3/4 in dowels in loose drilled holes register the end
waste. They seat on the carrier, not in press fits; their full stock height
is included in the tool-retraction envelope. Common 3/4 in stop screws
would penetrate the carrier and cannot obtain 1.5D in this thin riser.
The blank is widened toward -Y within the same 1/4 x 1-3/4 in stock, keeping
its former far edge. Hole stations for strap clamps remain carrier-spotted
REF; the stop-hole stations are ordinary manufactured .XX dimensions.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_strap_spec as strap
from _mcmaster_98381a473 import DIA_BAND_IN, DOWEL_SIZE, ENDS
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-riser",
    _config.parts("ch-rocker-arm-tl-oblique-riser"),
)
if UNIT != trammel.RISER_UNIT:
    raise AssertionError("the riser row and the calculator disagree on its unit")

_XX = printed_band_mm(2, unit=UNIT)
DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)
INCLUDED_ANGLE_TOL_DEG = angular_band_deg(unit=UNIT)
# Reference stations (located from TL-21 at assembly) print at 2 places.
STATION_PLACES = 2

# --- Blank (faced and milled from 1/4 in stock) -------------------------------
BLANK_LENGTH = 350.52  # 13.80
BLANK_WIDTH = 42.926  # 1.69; same 1-3/4 in stock, room below stop holes
BLANK_PLACES = 2
THICKNESS = trammel.RISER_THICK  # .24 ⚙
THICKNESS_PLACES = trammel.RISER_THICK_PLACES
THICKNESS_BAND = trammel.RISER_THICK_BAND
BLANK_ORIGIN = (-BLANK_LENGTH / 2.0, 13.208)  # .52; far edge unchanged
BAND_Y = (
    math.sqrt(trammel.RISER_INNER_RADIUS**2 - (BLANK_LENGTH / 2.0)**2) - trammel.H1,
    trammel.RISER_OUTER_RADIUS - trammel.H1,
)
if not (BLANK_ORIGIN[1] + 5.0 <= BAND_Y[0]
        and BAND_Y[1] <= BLANK_ORIGIN[1] + BLANK_WIDTH - 5.0):
    raise AssertionError("the riser's nominal band runs within 5 mm of a blank edge")



def to_riser(point: tuple[float, float]) -> tuple[float, float]:
    """Carrier-frame point -> riser model frame, without presentation rounding."""
    return (
        point[0] - BLANK_ORIGIN[0],
        point[1] - BLANK_ORIGIN[1],
    )


# --- Holes ------------------------------------------------------------------
SCREW_HOLES = tuple(to_riser(p) for p in trammel.RISER_SCREWS)  # ⚙
HUB_HOLE = to_riser(trammel.HUB)  # ⚙
CL_HOLE = to_riser(trammel.CL)  # ⚙
CR_HOLE = to_riser(trammel.CR)  # ⚙

# Supplier-qualified 98381A473, unmodified stock. No custom pin-diameter or
# length bands: +.0001/+.0003 diameter and +/- .010 length are supplier REF.
STOP_PIN_DIA = DOWEL_SIZE[0]
STOP_PIN_DIA_LIMITS = tuple(STOP_PIN_DIA + d * trammel.INCH for d in DIA_BAND_IN)
STOP_PIN_LENGTH = DOWEL_SIZE[1]
STOP_PIN_LENGTH_BAND = 0.010 * trammel.INCH
STOP_PIN_NUMBER = _config.parts("sm-vn-knife-mount-dowel")["number"]
STOP_PIN_CARRIER_POINTS = ((-167.894, 18.034), (167.894, 18.034))
STOP_PIN_HOLES = tuple(to_riser(p) for p in STOP_PIN_CARRIER_POINTS)
STOP_HOLE_DIA = 3.2512  # .128 +.004/0 design nominal; #30 drill
STOP_HOLE_PLACES = 3
STOP_HOLE_MAX = STOP_HOLE_DIA + DRILLED_BAND[0]
STOP_PIN_FLOAT_MAX = (STOP_HOLE_MAX - STOP_PIN_DIA_LIMITS[0]) / 2.0
STRAP_RAW_Y_MIN = trammel.STRAP_SPAN_Y[0] - trammel.BLANK_EDGE_WASTE
STRAP_STOCK_WIDTH = trammel.BLANK_WIDTH  # procured OnlineMetals 4807, 1-1/2 in
STOP_FACE_NOMINAL = STOP_PIN_CARRIER_POINTS[0][1] + STOP_PIN_DIA / 2.0
# Charge loose-pin tilt through the actual supported cylindrical length,
# not just radial hole play. The source pin's chamfer goes down on carrier;
# the drilled mouth gets the ordinary .010 break.
STOP_PIN_SUPPORT_MIN = (
    THICKNESS - THICKNESS_BAND - 0.010 * trammel.INCH
    - ENDS.chamfer_len(STOP_PIN_DIA_LIMITS[1])
)
STOP_PIN_SLOPE_MAX = 2.0 * STOP_PIN_FLOAT_MAX / STOP_PIN_SUPPORT_MIN
STOP_PIN_CONTACT_FLOAT_MAX = STOP_PIN_FLOAT_MAX * (
    1.0 + 2.0 * (strap.ARM_THICKNESS + max(strap.ARM_THICKNESS_BAND))
    / STOP_PIN_SUPPORT_MIN
)
STOP_PIN_TILT_RADIUS = STOP_PIN_DIA_LIMITS[1] / 2.0 * (
    math.sqrt(1.0 + STOP_PIN_SLOPE_MAX**2) - 1.0
)
# Seat the blank toward -Y against BOTH stops before clamping: the loaded
# pins cannot take positive-Y clearance. These are directional setup bounds;
# setup locates the installed riser, not an extra independent blank-edge
# manufacturing stack. Mark the preform from its raw edge/end midpoint.
STOP_RAW_Y_LIMITS = (
    STOP_PIN_CARRIER_POINTS[0][1] - _XX + STOP_PIN_DIA_LIMITS[0] / 2.0
    - STOP_PIN_CONTACT_FLOAT_MAX,
    STOP_PIN_CARRIER_POINTS[0][1] + _XX + STOP_PIN_DIA_LIMITS[1] / 2.0
    + STOP_PIN_TILT_RADIUS,
)
STOP_REGISTRATION_ERROR = max(abs(y - STRAP_RAW_Y_MIN) for y in STOP_RAW_Y_LIMITS)
STOP_PIN_TOP_LIMITS = (
    STOP_PIN_LENGTH - STOP_PIN_LENGTH_BAND,
    STOP_PIN_LENGTH + STOP_PIN_LENGTH_BAND,
)
if STOP_HOLE_DIA <= STOP_PIN_DIA_LIMITS[1]:
    raise AssertionError("plain stop pins must slip in ordinary drilled holes")
if STOP_REGISTRATION_ERROR > 0.5:
    raise AssertionError("plain stop pins exceed the allowed across-strap corridor")

# "#4-40" -> the wizard's "#4" clearance size.
SCREW_SIZE = trammel.RISER_SCREW.split("-")[0]
SCREW_SPEC = HoleSpec(kind="clearance", size=SCREW_SIZE, fit="normal")
SCREW_DIA = CLEARANCE_MM[(SCREW_SIZE, "normal")]  # .1285, the wizard table's #30
SCREW_DRILL = "#30"
SCREW_DRILL_DIA = 0.1285 * trammel.INCH
if SCREW_DIA != round(SCREW_DRILL_DIA, 3):  # the clearance table is rounded to .001 mm
    raise AssertionError("the riser clearance no longer matches its named drill")
# Rule 3: a three-place DESIGN nominal on the existing native reference
# circle, not a rounded measurement of the Wizard cut. Floor for +.004/0:
# .128-.132 contains the actual #30; nearest .129-.133 would exclude it.
SCREW_DIA_PLACES = 3
SCREW_DIA_PRINTED = (
    math.floor(SCREW_DIA / trammel.INCH * 1000.0 + 1e-9) / 1000.0 * trammel.INCH
)
if not SCREW_DIA_PRINTED - 1e-6 <= SCREW_DIA <= SCREW_DIA_PRINTED + DRILLED_BAND[0]:
    raise AssertionError("the wizard's #4 clearance falls outside its printed band")
if not SCREW_DIA_PRINTED <= SCREW_DRILL_DIA <= SCREW_DIA_PRINTED + DRILLED_BAND[0]:
    raise AssertionError("the actual #30 drill falls outside the design limits")
STOP_DRILL = "#30"
STOP_SPEC = HoleSpec(kind="clearance", size=SCREW_SIZE, fit="normal")
STOP_DIA = SCREW_DIA
if not STOP_HOLE_DIA <= SCREW_DRILL_DIA <= STOP_HOLE_MAX:
    raise AssertionError("the actual stop-hole drill leaves its printed design limits")
SCREW_BODY_DIA = 0.112 * trammel.INCH  # #4 major diameter
SCREW_HEAD_DIA_MAX = trammel.RISER_SCREW_HEAD_DIA  # .225
CSK_ANGLE = 82.0  # the flat head's own included angle
CSK_FLANK_ANGLE = 90.0 - CSK_ANGLE / 2.0  # face to flank, the sketch's
CSK_DIA = trammel.RISER_CSK_DIA  # .25 ⚙
CSK_PLACES = trammel.RISER_CSK_PLACES  # 2 ⚙
HUB_DIA = 12.0  # exact metric drill size; loose relief, not a fit
HUB_DRILL = "12 MM"
HUB_PLACES = 3
# The owner's literal 12 mm relief is the model's cut. Like the #30 holes,
# the inch sheet prints a three-place DESIGN nominal on a blanked reference
# circle, floored (as SCREW_DIA_PRINTED) so DRILLED HOLES +.004/0 (.472-.476)
# always contains the actual drill (.47244); the relief's clearance is the
# drill's, not the printed floor's.
HUB_DIA_PRINTED = (
    math.floor(HUB_DIA / trammel.INCH * 10.0**HUB_PLACES + 1e-9)
    / 10.0**HUB_PLACES
    * trammel.INCH
)
CLAMP_DIA = 4.9784  # .196, #9 drill: clears #8 body AND underhead fillet
CLAMP_PLACES = 3

if SCREW_DIA_PRINTED <= SCREW_BODY_DIA:
    raise AssertionError("the smallest accepted riser screw hole does not clear the #4 body")
# The smallest printed countersink still sinks the largest head (no head
# proud of the riser top under the strap blank); the largest stays short of
# the bottom face.
if (CSK_DIA - _XX) / 2.0 < SCREW_HEAD_DIA_MAX / 2.0:
    raise AssertionError("#4 head stands proud of the riser top")
CSK_DEPTH_MAX = (CSK_DIA + _XX) / 2.0 / math.tan(math.radians(CSK_ANGLE / 2.0))
if CSK_DEPTH_MAX >= THICKNESS - THICKNESS_BAND:
    raise AssertionError("riser countersink breaks through the blank")
if HUB_DIA <= strap.HOLE_DIA:
    raise AssertionError("the relief must pass the product-hole reamer")
if not HUB_DIA_PRINTED <= HUB_DIA <= HUB_DIA_PRINTED + DRILLED_BAND[0]:
    raise AssertionError("the 12 mm relief drill falls outside its printed design limits")
if HUB_DIA_PRINTED <= strap.HOLE_DIA:
    raise AssertionError("the smallest printed relief does not pass the product-hole reamer")

HOLES: dict[str, tuple[tuple[float, float], float]] = {
    **{f"screw {i}": (xy, SCREW_DIA) for i, xy in enumerate(SCREW_HOLES, start=1)},
    "HUB": (HUB_HOLE, HUB_DIA),
    "CL": (CL_HOLE, CLAMP_DIA),
    "CR": (CR_HOLE, CLAMP_DIA),
    **{f"stop {i}": (xy, STOP_HOLE_DIA) for i, xy in enumerate(STOP_PIN_HOLES, start=1)},
}

# Rule 17 at worst case: every hole (or its countersink) to the blank edges,
# the blank set on the carrier within its stations' 2-place band, on the
# shortest, narrowest blank.
_BLANK_BAND = printed_band_mm(BLANK_PLACES, unit=UNIT)
_POSITION = printed_band_mm(STATION_PLACES, unit=UNIT)
_LENGTH_MIN = BLANK_LENGTH - _BLANK_BAND
_WIDTH_MIN = BLANK_WIDTH - _BLANK_BAND
WALLS_MM: dict[str, float] = {}
for _name, ((_x, _y), _dia) in HOLES.items():
    _r = (
        (CSK_DIA + _XX) / 2.0
        if _name.startswith("screw")
        else (_dia + DRILLED_BAND[0]) / 2.0
    )
    WALLS_MM[f"{_name} to edges"] = min(
        _x - _POSITION - _r,
        _LENGTH_MIN - (_x + _POSITION) - _r,
        _y - _POSITION - _r,
        _WIDTH_MIN - (_y + _POSITION) - _r,
    )
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(f"riser {_wall} wall {_mm:.3f} under rule 17's .080")

# CL and CR sit on the hub radius inside the self-cut band, the drill at its
# band's top. Spotted through the carrier's holes, each carries the carrier
# station's error about the cut's centre C (trammel.ARC_CENTRE): its X and Y
# title-block bands, X also half the D1 band (C stands D1/2 from A1, as
# carrier.RISER_WALLS_FROM_A1), each times its direction cosine to C.
_CLAMP_R_MAX = (CLAMP_DIA + DRILLED_BAND[0]) / 2.0
_CLAMP_RADIUS = math.dist(trammel.CL, trammel.ARC_CENTRE)
if abs(math.dist(trammel.CR, trammel.ARC_CENTRE) - _CLAMP_RADIUS) > 1e-9:
    raise AssertionError("CL and CR are not on one radius")


def _radial_station_error(
    point: tuple[float, float], x_name: str, y_name: str
) -> float:
    """The carrier station's worst radial error about C at ``point``."""
    places = carrier.DRAWING_PRECISION_BY_NAME
    x_band = (
        printed_band_mm(places[x_name], unit=carrier.UNIT) + carrier.POSITION_BAND / 2.0
    )
    y_band = printed_band_mm(places[y_name], unit=carrier.UNIT)
    dx, dy = (abs(p - c) for p, c in zip(point, trammel.ARC_CENTRE, strict=True))
    return (dx * x_band + dy * y_band) / _CLAMP_RADIUS


CLAMP_STATION_ERROR = max(
    _radial_station_error(trammel.CL, "ClX", "ClY"),
    _radial_station_error(trammel.CR, "CrX", "CrY"),
)
CLAMP_BAND_WALLS = (
    _CLAMP_RADIUS - _CLAMP_R_MAX - CLAMP_STATION_ERROR - trammel.RISER_INNER_RADIUS,
    trammel.RISER_OUTER_RADIUS - _CLAMP_RADIUS - _CLAMP_R_MAX - CLAMP_STATION_ERROR,
)
if min(CLAMP_BAND_WALLS) < WALL_TARGET_MM:
    raise AssertionError("the #8 end-clearance holes lack the .080 band wall")
if CLAMP_DIA <= THREAD_MAJOR_MM[carrier.CLAMP_THREAD]:
    raise AssertionError("the end-clamp clearance does not pass its #8 mate")

if not (
    SCREW_HOLES[0][1] == SCREW_HOLES[1][1]
    and SCREW_HOLES[2][1] == SCREW_HOLES[3][1]
    and CL_HOLE[1] == CR_HOLE[1]
):
    raise AssertionError("riser hole pairs are not on common rows")

# Model globals: name -> value (mm). The build sets each and drives from it.
GLOBALS: dict[str, float] = {
    "BlankLength": BLANK_LENGTH,
    "BlankWidth": BLANK_WIDTH,
    # Never a bare "Thickness": SolidWorks refused that global (farm run
    # jig-r1, Add2/Add3 -1); the jig's parts prefix theirs (BarThick, LeverThick).
    "BlankThick": THICKNESS,
    "Screw1X": SCREW_HOLES[0][0],
    "Screw2X": SCREW_HOLES[1][0],
    "Screw3X": SCREW_HOLES[2][0],
    "Screw4X": SCREW_HOLES[3][0],
    "ScrewInnerY": SCREW_HOLES[0][1],
    "ScrewOuterY": SCREW_HOLES[2][1],
    "HubX": HUB_HOLE[0],
    "HubY": HUB_HOLE[1],
    "ClX": CL_HOLE[0],
    "CrX": CR_HOLE[0],
    "ClampY": CL_HOLE[1],
    # The cut is the actual 12 mm drill; HubDia is its printed design nominal
    # on the blanked HubHoleReference circle.
    "HubCutDia": HUB_DIA,
    "HubDia": HUB_DIA_PRINTED,
    "ClampDia": CLAMP_DIA,
    "CskDia": CSK_DIA,
    # Native design nominal; the Wizard still cuts the actual #30 SCREW_DIA.
    "ScrewDia": SCREW_DIA_PRINTED,
    "Stop1X": STOP_PIN_HOLES[0][0],
    "Stop2X": STOP_PIN_HOLES[1][0],
    "StopY": STOP_PIN_HOLES[0][1],
    "StopDia": STOP_HOLE_DIA,
}

# Plain clearance circles on one sketch: (centre, dia, (x, y, size) names,
# (x, y, size) drives). CR's row and size repeat CL's and stay off the print.
CIRCLES: tuple[
    tuple[tuple[float, float], float, tuple[str, str, str], tuple[str, str, str]], ...
] = (
    (HUB_HOLE, HUB_DIA, ("HubX", "HubY", "HubCutDia"),
     ('"HubX"', '"HubY"', '"HubCutDia"')),
    (CL_HOLE, CLAMP_DIA, ("ClX", "ClampY", "ClampDia"),
     ('"ClX"', '"ClampY"', '"ClampDia"')),
    (CR_HOLE, CLAMP_DIA, ("CrX", "CrY", "ClampDia2"),
     ('"CrX"', '"ClampY"', '"ClampDia"')),
)  # fmt: skip

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankLength", "BlankWidth"},
    "Blank": {"BlankThick"},
    "ScrewHoles": {
        "Screw1X",
        "Screw2X",
        "Screw3X",
        "Screw4X",
        "ScrewInnerY",
        "ScrewOuterY",
    },
    "HoleProfile": {
        "HubX", "HubY", "ClX", "CrX", "ClampY", "ClampDia",
    },
    "ScrewHoleReference": {"ScrewDia"},
    "HubHoleReference": {"HubDia"},
    "StopHoles": {"Stop1X", "Stop2X", "StopY"},
    "StopHoleReference": {"StopDia"},
}
_STATIONS = DRAWING_DIMENSIONS["ScrewHoles"] | {
    "HubX", "HubY", "ClX", "CrX", "ClampY",
}
_SIZE_PLACES = {
    "BlankLength": BLANK_PLACES,
    "BlankWidth": BLANK_PLACES,
    "BlankThick": THICKNESS_PLACES,
    "ScrewDia": SCREW_DIA_PLACES,
    "HubDia": HUB_PLACES,
    "ClampDia": CLAMP_PLACES,
    "Stop1X": 2,
    "Stop2X": 2,
    "StopY": 2,
    "StopDia": STOP_HOLE_PLACES,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {
        name: STATION_PLACES if name in _STATIONS else _SIZE_PLACES[name]
        for name in names
    }
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
for _name, _places in DRAWING_PRECISION_BY_NAME.items():
    # Reference stations display at 2 places without moving the model axes.
    if _name in _STATIONS:
        continue
    if not carrier.prints_exactly(GLOBALS[_name], _places):
        raise AssertionError(
            f"riser {_name} {GLOBALS[_name]} does not print as modelled"
        )
if not carrier.prints_exactly(CSK_DIA, CSK_PLACES):
    raise AssertionError("the riser countersink does not print as modelled")

# Every hole is located from the TL-21 carrier at assembly, so its stations
# print as REFERENCE values, parenthesised and untoleranced, and each hole
# callout carries the mate in its last rows (review r7: one row per callout,
# not a general note); only the sizes carry bands. The rows name neither the
# assembly nor a step: the riser builds in the PR before the jig assembly, and
# the assembly's step numbers move as it gains steps.
REFERENCE_DIMENSIONS = frozenset(_STATIONS)
CARRIER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
LOCATE_CALLOUT = f"LOCATE FROM {CARRIER_NUMBER}\nAT ASSEMBLY"
CSK_CALLOUT = (
    f"CSK<MOD-DIAM>{carrier.inch_text(CSK_DIA, CSK_PLACES)} X {CSK_ANGLE:.0f}\u00b0"
)
CALLOUTS_ABOVE = {"ScrewDia": "4X", "ClampDia": "2X", "StopDia": "2X"}
# A row height shared by a hole pair prints its count in the reference's
# prefix on one line, "2X (.53)": stacked above the value it overflowed the
# short spans (jig-r6).
ROW_COUNTS = {"ScrewInnerY": "2X", "ScrewOuterY": "2X", "ClampY": "2X", "StopY": "2X"}
if not set(ROW_COUNTS) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a counted row height has no authored dimension")
# The hole callouts, one per hole size: the screw hole's carries its
# countersink, and each its location from the carrier.
HOLE_CALLOUTS = ("ScrewDia", "HubDia", "ClampDia", "StopDia")
CALLOUTS_BELOW = {
    "ScrewDia": f"{SCREW_DRILL} DRILL THRU\n{CSK_CALLOUT}\n{LOCATE_CALLOUT}",
    "HubDia": f"{HUB_DRILL} DRILL THRU\nHUB REAMER RELIEF\n{LOCATE_CALLOUT}",
    "ClampDia": f"#9 DRILL THRU\nCL AND CR CLAMPS\n{LOCATE_CALLOUT}",
    "StopDia": f"#30 DRILL THRU\nLOOSE 1/8 STOP PINS\n{STOP_PIN_NUMBER}",
}

SURFACE_FINISHES = ()
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
