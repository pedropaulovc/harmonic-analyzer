r"""Pure-data dimensional contract shared by the pinion lift cam and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  An eccentric steel collar set-screwed to the
lift rod: the bore is offset ECC from the collar OD axis, so the two are NOT
concentric -- the drawing MUST dimension that offset (the cam-note precedent).
The nominals drive the part's named equation globals AND the drawing's
coordinate math; the marked-dimension map keeps the part marks and drawing keeps
in lockstep (``test_dt_pinion_cam_drawing.py``).

Loose screw source (read 2026-10-19): ASME B18.3-2012, Table 14,
https://www.finesz.com/pic/ASME%20B18.3.pdf . Notes 6, 7 and 11 define
overall length, the .13/.16/.19-in standard lengths for sizes 0..3, and
the +/- .01-in length tolerance below .63 in. The supplied 3/16-in nominal
has a .19-in basic length under note 6, so its limits are .18..20 in.
The #2 row gives .086-in basic diameter, .035-in hex socket and
.039..047-in flat point, corroborated by
https://fullerfasteners.com/tech/ansi-asme-b18-3-specifications-hex-socket-set-screws-flat-point/ .
Note 2 specifies the point's 45 +5/-0-deg angle below the thread root;
note 1 specifies the socket-end chamfer at 30..45 deg, slightly below the
root. The full-thread budget below subtracts the maximum point taper plus
an explicit 1.5-pitch socket-end incomplete-thread allowance. That allowance
is an owner-accepted design assumption, NOT a chamfer-depth limit supplied
by ASME. The through tap must provide full receiver thread over that span.
"""

from __future__ import annotations

import math

import _config
from _drawing_units import drawing_unit
from _fit_deviations import deviations
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import printed_deviations
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _gtol_cylinder import CylinderFace
from dt_pinion_lift_rod_spec import ROD_DIA as LIFT_ROD_DIA
from dt_pinion_lift_rod_spec import ROD_DIA_BAND as LIFT_ROD_DIA_BAND
from dt_pinion_cam_geometry import (
    BORE as BORE,
    CAM_LEN as CAM_LEN,
    CAM_OD as CAM_OD,
    ECC as ECC,
    SET_SCREW_Z as SET_SCREW_Z,
    SET_SCREW_MAJOR_DIA as SET_SCREW_MAJOR_DIA,
    TAP_DRILL_DIA as TAP_DRILL_DIA,
)

# Issue #290: the registry row's drawing_unit is the one declaration of this
# sheet's unit; the bands, the roughness grade and the tolerance display all
# read it.  The bands and places below are inch-native, so a row that stopped
# declaring inches must fail here rather than print them in mm.
_ROW = _config.parts("dt-pinion-cam")
UNIT = drawing_unit("parts/dt-pinion-cam", _ROW)
if UNIT != "in":
    raise AssertionError(
        f"dt-pinion-cam is dimensioned in inches but its row declares {UNIT!r}"
    )

# Owner ruling (#290 pilot, 2026-10-30, via Main): only the bore moves, onto
# the owned .2510 reamer.  Every other nominal keeps its millimetre value
# (OD 14.6, eccentricity 2.0, length 9.0, station 4.1: the drive train's
# park/engage/rig geometry) and prints in inches at its own grade, so the
# printed number is the model rounded to these places.  Every wall below is
# therefore judged at the PRINTED limits (printed_deviations), never at the
# model value.  Every feature here feeds a fit, a wall or the rig stack, so
# none prints at .X.
BORE_PLACES = 4  # .2510 +.0005/.0000: the reamer band needs four
COLLAR_OD_PLACES = 3  # 14.6 prints .575 +/-.002
ECC_PLACES = 3  # 2.0 prints .079 +/-.002
LENGTH_PLACES = 2  # 9.0 prints .35 at .XX
SET_SCREW_Z_PLACES = 2  # 4.1 prints .16 at .XX
TAP_DRILL_PLACES = 3  # .070 (#50): inch drill diameters print three places

# U27 (Main, 2026-09-23): the cam is set-screwed to the lift rod (MHA-DT-17), so
# the bore only has to slip over it: enough clearance to slide on at assembly,
# small enough that the set screw's shift is noise under the feeler-set rig
# location.  #290: the authored functional window is U27's 0.02-0.10 mm put
# inside the .0001-in grid, .0008-.0039 in.  The owned .2510 over reamer cuts
# R +.0000/+.0005 (trial-cut it before relying on the band), so the bore
# prints .2510 +.0005/.0000; on today's MHA-DT-17 ground h band (0/-0.020 mm)
# the derived clearance is 0.0254-0.0581 mm (.0010-.00229 in), inside it.
LIFT_ROD_NUMBER = "MHA-DT-17"
BORE_BAND = (0.0127, 0.0)  # (upper, lower) about BORE: +.0005/.0000 in
SLIP_CLEARANCE_WINDOW_MM = (0.02032, 0.09906)  # .0008-.0039 in
_BORE_LOWER, _BORE_UPPER = printed_deviations(
    BORE, BORE_PLACES, deviations(BORE_BAND), unit=UNIT
)
SLIP_CLEARANCE_MIN = round(
    BORE + _BORE_LOWER - (LIFT_ROD_DIA + LIFT_ROD_DIA_BAND[0]), 6
)
SLIP_CLEARANCE_MAX = round(
    BORE + _BORE_UPPER - (LIFT_ROD_DIA + LIFT_ROD_DIA_BAND[1]), 6
)
if (
    SLIP_CLEARANCE_MIN < SLIP_CLEARANCE_WINDOW_MM[0]
    or SLIP_CLEARANCE_MAX > SLIP_CLEARANCE_WINDOW_MM[1]
):
    raise AssertionError(
        f"cam slip clearance {SLIP_CLEARANCE_MIN}-{SLIP_CLEARANCE_MAX} mm is "
        f"outside {SLIP_CLEARANCE_WINDOW_MM}"
    )
# The cam OD is the working surface the follower rides, and the bore-to-OD
# offset IS the lift: both are on the drive train's critical list.  Nothing
# else on this collar mates with anything, so nothing else carries a band.
# Routine controlling dimensions use the title block's general grade.
# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# both tight bands name the MHA-DT-25 follower pin they serve (machinist
# review ENFORCE r1: the bands named no mate).
FOLLOWER_PIN_NUMBER = "MHA-DT-25"
COLLAR_OD_TOLERANCE_MM = 0.0508  # +/-.002 in (was +/-0.05 mm)
COLLAR_AXIS_TOLERANCE_MM = 0.0508  # +/-.002 in (was +/-0.05 mm)

_OD_LOWER, _OD_UPPER = printed_deviations(
    CAM_OD,
    COLLAR_OD_PLACES,
    (-COLLAR_OD_TOLERANCE_MM, COLLAR_OD_TOLERANCE_MM),
    unit=UNIT,
)
_ECC_LOWER, _ECC_UPPER = printed_deviations(
    ECC,
    ECC_PLACES,
    (-COLLAR_AXIS_TOLERANCE_MM, COLLAR_AXIS_TOLERANCE_MM),
    unit=UNIT,
)
_LENGTH_LOWER, _LENGTH_UPPER = printed_deviations(CAM_LEN, LENGTH_PLACES, unit=UNIT)
_STATION_LOWER, _STATION_UPPER = printed_deviations(
    SET_SCREW_Z, SET_SCREW_Z_PLACES, unit=UNIT
)
# The model is an accepted part: each off-grid nominal must still lie inside
# the limits its rounded print states.
for _name, (_lower, _upper) in {
    "CollarOd": (_OD_LOWER, _OD_UPPER),
    "CollarCy": (_ECC_LOWER, _ECC_UPPER),
    "Depth": (_LENGTH_LOWER, _LENGTH_UPPER),
    "TapCz": (_STATION_LOWER, _STATION_UPPER),
}.items():
    if not _lower < 0.0 < _upper:
        raise AssertionError(f"{_name}'s printed limits exclude its model value")

THIN_SIDE_WALL_MIN_MM = (
    (CAM_OD + _OD_LOWER) / 2.0 - (BORE + _BORE_UPPER) / 2.0 - (ECC + _ECC_UPPER)
)
THICK_SIDE_WALL_MIN_MM = (
    (CAM_OD + _OD_LOWER) / 2.0 - (BORE + _BORE_UPPER) / 2.0 + (ECC + _ECC_LOWER)
)
# Owner-ruled rule-17 shortfall (RV-01 in cad/config/parts/dt-pinion-cam.yaml):
# at the printed limits (OD .573, bore .2515, eccentricity .081) the thin side
# keeps .07975 in (2.02565 mm), .00025 in under the .080 target and .01975 in
# over the .060 floor.  The floor stays hard; RV-01 covers the wall down to
# exactly that worst case, so anything thinner must be ruled again.  The sheet
# states the accepted wall natively (THIN_WALL_MIN_MM below, rule 20).
THIN_SIDE_WALL_EXCEPTION_MIN_MM = 0.07975 * 25.4
if THIN_SIDE_WALL_MIN_MM < WALL_FLOOR_MM:
    raise AssertionError("cam thin-side wall falls below the .060 in floor")
if THIN_SIDE_WALL_MIN_MM < WALL_TARGET_MM:
    if not any(
        entry.get("id") == "RV-01" and entry.get("kind") == "minor"
        for entry in _ROW.get("machinist_exceptions") or ()
    ):
        raise AssertionError(
            "no owner minor RV-01 declares the cam thin-wall shortfall"
        )
    if THIN_SIDE_WALL_MIN_MM < THIN_SIDE_WALL_EXCEPTION_MIN_MM - 1e-9:
        raise AssertionError("cam thin-side wall falls below RV-01's ruled .07975 in")

# Rule 20: the sheet states the accepted shortfall, on its own NATIVE
# dimension, never in note text.  build_dt_pinion_cam draws a hidden
# construction line up the thin side from the bore's top, as long as the
# printed minimum, and its driving dimension prints as the single limit
# ".0797 MIN" (swTolMIN prints the nominal plus MIN, so the model value IS the
# printed limit): the ruled .07975 floored to its four places, so the sheet
# never claims more wall than the printed worst case leaves.  Its band records
# the printed best case (OD .577, bore .2510, eccentricity .077).
THIN_WALL_MIN_PLACES = 4
THIN_WALL_MIN_MM = round(
    math.floor(THIN_SIDE_WALL_MIN_MM / 25.4 * 10**THIN_WALL_MIN_PLACES + 1e-9)
    / 10**THIN_WALL_MIN_PLACES
    * 25.4,
    9,
)
THIN_WALL_MIN_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints ".0797 MIN"
THIN_SIDE_WALL_MAX_MM = (
    (CAM_OD + _OD_UPPER) / 2.0 - (BORE + _BORE_LOWER) / 2.0 - (ECC + _ECC_LOWER)
)
THIN_WALL_MIN_BAND = (round(THIN_SIDE_WALL_MAX_MM - THIN_WALL_MIN_MM, 6), 0.0)
if not WALL_FLOOR_MM <= THIN_WALL_MIN_MM <= THIN_SIDE_WALL_MIN_MM:
    raise AssertionError(
        "the printed wall minimum overstates the worst case or the floor"
    )
THIN_WALL_CALLOUT = "THIN-SIDE WALL"

# Table 14 note 6 expresses the fractional nominal as a two-place basic
# length; note 11's tolerance applies to that .19-in basic, not .1875 in.
# The screw's Class 3A major cannot exceed its basic diameter; the native
# hole's basic major remains _hole_spec's authority.
SET_SCREW_LENGTH_IN = 3.0 / 16.0
SET_SCREW_BASIC_LENGTH_IN = round(SET_SCREW_LENGTH_IN, 2)
SET_SCREW_LENGTH_TOLERANCE_IN = 0.01
SET_SCREW_LENGTH_MIN_MM = (
    SET_SCREW_BASIC_LENGTH_IN - SET_SCREW_LENGTH_TOLERANCE_IN
) * 25.4
SET_SCREW_LENGTH_MAX_MM = (
    SET_SCREW_BASIC_LENGTH_IN + SET_SCREW_LENGTH_TOLERANCE_IN
) * 25.4
SET_SCREW_MAJOR_MAX_MM = 0.086 * 25.4
SET_SCREW_POINT_MIN_MM = 0.039 * 25.4
SET_SCREW_PITCH_MM = 25.4 / 56.0
# The source's exact .086-in basic major is slightly larger than the native
# table's rounded 2.184 mm; never gain engagement by that rounding.
_ENGAGEMENT_MAJOR_MM = max(SET_SCREW_MAJOR_DIA, SET_SCREW_MAJOR_MAX_MM)
SET_SCREW_POINT_TAPER_MAX_MM = (
    (_ENGAGEMENT_MAJOR_MM - SET_SCREW_POINT_MIN_MM) / 2.0
) / math.tan(math.radians(45.0))
# Main's owner-ruling integration (2026-10-19): keep the 3/16 nominal/.19
# basic with this explicit 1.5-pitch socket-end allowance. A 1/4-in screw
# cannot replace it without standing proud of the unchanged heavy-side OD.
# ASME note 1 bounds the chamfer angle, but not its "slightly below root"
# depth; the allowance is not an independently guaranteed supplier maximum.
SET_SCREW_SOCKET_END_ALLOWANCE_MM = 1.5 * SET_SCREW_PITCH_MM
SET_SCREW_FULL_THREAD_MIN_MM = (
    SET_SCREW_LENGTH_MIN_MM
    - SET_SCREW_POINT_TAPER_MAX_MM
    - SET_SCREW_SOCKET_END_ALLOWANCE_MM
)
SET_SCREW_FULL_THREAD_REQUIRED_MM = 1.5 * _ENGAGEMENT_MAJOR_MM
SET_SCREW_FULL_THREAD_MARGIN_MM = (
    SET_SCREW_FULL_THREAD_MIN_MM - SET_SCREW_FULL_THREAD_REQUIRED_MM
)
if SET_SCREW_FULL_THREAD_MARGIN_MM < 0.0:
    raise AssertionError("cam screw's assumed full-thread budget is below 1.5D")

# The tap's thread may break neither end face: the rear wall stacks the
# collar length AND the station, each at its printed .XX limits; the front
# stacks the station alone.  Neither band is tightened to rescue a wall.
SET_SCREW_FRONT_WALL_MIN_MM = SET_SCREW_Z + _STATION_LOWER - _ENGAGEMENT_MAJOR_MM / 2.0
SET_SCREW_REAR_WALL_MIN_MM = (
    CAM_LEN
    + _LENGTH_LOWER
    - (SET_SCREW_Z + _STATION_UPPER)
    - _ENGAGEMENT_MAJOR_MM / 2.0
)
if min(SET_SCREW_FRONT_WALL_MIN_MM, SET_SCREW_REAR_WALL_MIN_MM) < WALL_TARGET_MM:
    raise AssertionError("cam tap leaves less than the .080 in end-face wall target")

# A screw seated against the near bore tangent is the shallowest seated case;
# any travel across the rod/bore clearance only sinks it further. Its outer
# rim must clear the curved OD, not merely the axial centre's tangent plane.
_OD_RADIUS_MIN_MM = (CAM_OD + _OD_LOWER) / 2.0
_SCREW_RIM_SAG_MM = _OD_RADIUS_MIN_MM - math.sqrt(
    _OD_RADIUS_MIN_MM**2 - (SET_SCREW_MAJOR_MAX_MM / 2.0) ** 2
)
SET_SCREW_SUBFLUSH_MIN_MM = (
    THICK_SIDE_WALL_MIN_MM - SET_SCREW_LENGTH_MAX_MM - _SCREW_RIM_SAG_MM
)
if SET_SCREW_SUBFLUSH_MIN_MM <= 0.0:
    raise AssertionError("the longest supplied screw can stand proud of the cam OD")

BORE_CALLOUT = f"REAM THRU\nSLIP FIT ON LIFT ROD {LIFT_ROD_NUMBER}"
# ENFORCE r8 (gating): the tap breaks out on the heavy side of this OD, and a
# blind reader could not tell whether the pin's track crosses it.  It does
# not: the follower contact stays 45 deg or more off the tap mouth over the
# whole stroke (test_cam_set_screw_hole_stays_clear_of_the_follower), so the
# callout says so, without a number (notes carry no dimensions).
COLLAR_OD_CALLOUT = (
    f"{FOLLOWER_PIN_NUMBER} FOLLOWER\nPIN RIDES THIS OD\nON AN ARC CLEAR\nOF THE TAP"
)
ECCENTRICITY_CALLOUT = (
    f"ECCENTRICITY\nBORE AXIS TO OD AXIS\nSETS {FOLLOWER_PIN_NUMBER} PIN LIFT"
)
# drawing-guidelines.md rule 23 (lock threaded joints exposed to operating
# loads), #1176: MHA-DT-00's cam-collars-set step stakes the tap mouth over
# the set screw; the drawing resolves this key through dt_drive_train_steps
# so the number follows the assembly sequence.  The spec holds only the key:
# importing the steps module here would re-key the part on every step edit
# (as MHA-DT-16 / MHA-DT-17 hold LEVER_PIN_SET_STEP_KEY).
SET_SCREW_STAKE_STEP_KEY = "cam-collars-set"
TAP_DRILL_CALLOUT = "TAP DRILL THRU TO BORE\n#2-56 UNC\nSTAKE AT ASSEMBLY PER"

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs,
# slides or locates): the roughness goes on the surface that runs.  The
# follower pin rides the cam OD (63 µin Ra on this inch sheet); the
# set-screwed bore never moves on the rod, so it carries none.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "cam_od",
        MACHINED_UM,
        CylinderFace(CAM_OD),
        production_method="CAM OD",
        display_unit=UNIT,
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarCy"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    "TapDrillProfile": {"TapDrillDia", "TapCz"},
    "ThinWallReference": {"ThinWallMin"},
}

# The MODEL owns every printed decimal place: build_dt_pinion_cam applies this
# map to the .SLDPRT and draw_dt_pinion_cam only reads it back.  Inch places:
# four on the reamed bore (its +.0005 band needs them) and on the RV-01 wall
# minimum (.0797 MIN, a single limit), three on the banded cam OD and
# eccentricity (+/-.002) and on the #2-56 tap drill (an inch drill diameter),
# two on the collar length and tap station, which feed the end-face walls and
# the rig's collar stations, so .X never applies.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CollarProfile": {"CollarOd": COLLAR_OD_PLACES, "CollarCy": ECC_PLACES},
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "Collar": {"Depth": LENGTH_PLACES},
    "TapDrillProfile": {"TapDrillDia": TAP_DRILL_PLACES, "TapCz": SET_SCREW_Z_PLACES},
    "ThinWallReference": {"ThinWallMin": THIN_WALL_MIN_PLACES},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The tapped-hole requirement is attached to its tap-drill dimension. The
# linked note carries only loose hardware; the ASME source and stack above
# account for the supplier's overall-length limits, not an invented SKU.
DRAWING_NOTES = "SUPPLY ASME B18.3 #2-56 UNC X 3/16\nFLAT-POINT SOCKET SET SCREW LOOSE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
