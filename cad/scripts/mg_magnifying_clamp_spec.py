r"""MHA-MG-02 magnifying clamp: the drawing contract shared by part and sheet.

PURE DATA, no SolidWorks/COM imports.  The shape is
``mg_magnifying_clamp_geom``'s (the assembly, the error budget and the web
export read that module, not this one); this module owns the printed contract:
the nominal walls, ordinary native dimensional bands, plug-tap reach and
sheet text. The ordinary HEX size and default drawn angles govern all
three opposed-flat pairs over the full length.

The heights run from the bottom shoulder-seat face. An actual diagonal-flat
distance and a location from the SAME actual Z flat locate each tap entry.
The bore uses that common Z-flat baseline and its own bottom-seat height.
There is no separate finished 2 MIN wall or 15 MAX envelope requirement.
Rule 17's 2 mm target and 1.5 mm floor are engineering checks; ordinary HEX
acceptance is not a certificate for unconstrained as-supplied stock.
"""

from __future__ import annotations

import math

from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from mg_magnifying_clamp_geom import (  # noqa: F401 (re-export)
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BORE_FULL_ANGULAR,
    BORE_TO_FLAT_WALL_WORST,
    DRILL_WANDER_DEG,
    EDGE_BREAK,
    HEIGHT_PLACES,
    HEX_AC,
    HEX_AF,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    LOCATION_BAND,
    LOCATION_FROM_FLAT,
    LOCATION_PLACES,
    ROD_TAP_DRILL_DIA,
    ROD_TAP_DRILL_POINT,
    ROD_TAP_FLOOR_WALL_WORST,
    THUMB_ENGAGEMENT_WORST,
    STOCK_ENVELOPE_MAX,
    THUMB_TAP_DRILL_DEPTH,
    THUMB_TAP_LENGTH,
    THUMB_TAP_SPEC,
    TOP_TO_BORE,
    WALL_TARGET,
    WALL_FLOOR,
    TAP_TO_BORE_ENTRY_Z_MAX,
)
from mg_rod_clamp_joint import (  # noqa: F401 (re-export)
    ENGAGEMENT_MIN,
    ENGAGEMENT_WORST,
    HOLE_DEPTH_PLACES,
    PLUG_TAP_LEAD,
    ROD_TAP_DRILL_DEPTH,
    ROD_TAP_DRILL_DEPTH_MAX,
    ROD_TAP_SPEC,
    ROD_TAP_THREAD_DEPTH,
    ROD_TAP_THREAD_DEPTH_MAX,
    THREAD_MAJOR,
    THREAD_PITCH,
)


# --- Places each printed dimension carries ----------------------------------
# The native, non-reference AF uses the ordinary title-block .XX band.
HEX_AF_PLACES = 2
# The drilled lever bore uses .XX and the DRILLED HOLES +0.10/0 row.
LEVER_BORE_DIA_PLACES = 2

# --- Printed limits ----------------------------------------------------------
_HEIGHT_BAND = printed_band_mm(HEIGHT_PLACES)  # 0.51 on the height and the bore's
_DEPTH_BAND = printed_band_mm(HOLE_DEPTH_PLACES)  # 0.51 on both taps' depths
_LEVER_BORE_R_MIN = LEVER_BORE_DIA / 2.0
_LEVER_BORE_R_MAX = (LEVER_BORE_DIA + drilled_oversize_mm()) / 2.0
_DRILL_R_MAX = (ROD_TAP_DRILL_DIA + drilled_oversize_mm()) / 2.0
# Normal-shop cutting allowance for plug-reach arithmetic, not an ASME
# maximum internal-root limit or a custom thread inspection requirement.
_TAP_OVERSIZE_R = 0.025
_THREAD_R_MAX = THREAD_MAJOR / 2.0 + _TAP_OVERSIZE_R


# Realistic drill run-off is additional to the ordinary entry locations.
# Standard thread roots retain the same shop-cut allowance below; it is not
# an ASME maximum-major guarantee or a new finished-wall inspection note.
_DRILL_SLOPE = math.tan(math.radians(DRILL_WANDER_DEG))


# --- Derived dimensional walls, judged against the policy FLOOR --------------
DERIVED_WALL_BOUNDS: dict[str, tuple[float, float]] = {
    "lever bore to the nonintersecting flats": (
        HEX_AF / 2.0 - LEVER_BORE_DIA / 2.0,
        BORE_TO_FLAT_WALL_WORST,
    ),
    "rod-tap drill point to the lever bore": (
        LEVER_BORE_Y
        - LEVER_BORE_DIA / 2.0
        - ROD_TAP_DRILL_DEPTH
        - ROD_TAP_DRILL_DIA / 2.0 / math.tan(math.radians(59.0)),
        ROD_TAP_FLOOR_WALL_WORST,
    ),
}
for _name, (_nominal, _worst) in DERIVED_WALL_BOUNDS.items():
    if _worst < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-MG-02 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under the {WALL_FLOOR} policy floor"
        )


# --- The thumb-screw tap's reach (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)) --
# The reach a stock #4-40 plug tap gives (Morse item 30000: usable length
# 9/16 in on a shank over the major, a 3-5 thread chamfer); the sheet names
# no tool, the arithmetic only proves a common one makes the part.
PLUG_TAP_USABLE_LENGTH = 9.0 / 16.0 * 25.4
PLUG_TAP_CHAMFER_THREADS = (3, 5)
if abs(PLUG_TAP_CHAMFER_THREADS[1] * THREAD_PITCH - PLUG_TAP_LEAD) > 1e-9:
    raise AssertionError("MHA-MG-02 plug-tap lead disagrees with the rod joint's")
# Bound run-off to the entire plug, including its lead in the bore's air.
_TAP_BORE_ANGULAR = BORE_FULL_ANGULAR
_TAP_RELATIVE_Z_MAX = TAP_TO_BORE_ENTRY_Z_MAX + PLUG_TAP_USABLE_LENGTH * _DRILL_SLOPE + _TAP_BORE_ANGULAR
_TOP_TO_AXIS_MAX = TOP_TO_BORE + 2.0 * _HEIGHT_BAND + _TAP_BORE_ANGULAR
_TOP_TO_AXIS_MIN = TOP_TO_BORE - 2.0 * _HEIGHT_BAND - _TAP_BORE_ANGULAR
_THREAD_HALF_CHORD = math.sqrt(_LEVER_BORE_R_MIN**2 - (_THREAD_R_MAX + _TAP_RELATIVE_Z_MAX)**2)
# The deepest wall the thread crosses, and the far wall's nearest point.
TAP_WALL_DEEPEST = _TOP_TO_AXIS_MAX - _THREAD_HALF_CHORD
TAP_REACH_NEEDED = TAP_WALL_DEEPEST + PLUG_TAP_LEAD
FAR_WALL_NEAREST = _TOP_TO_AXIS_MIN + _THREAD_HALF_CHORD
# The bore's far wall lies inside the tap's 9/16 in, so the tap is run until
# its lead has passed into the bore and stopped there.
# On ONE part the near and far walls move together, so the stop window is the
# bore's chord less the lead (positive: full thread through the wall before
# the tip meets the far wall), and every reach the stack allows is within the
# tap's usable length.
TAP_STOP_WINDOW = 2.0 * _THREAD_HALF_CHORD - PLUG_TAP_LEAD
if TAP_STOP_WINDOW <= 0.0:
    raise AssertionError("MHA-MG-02 plug tap meets the far wall before full thread")
if TAP_REACH_NEEDED > PLUG_TAP_USABLE_LENGTH + 1e-9:
    raise AssertionError("MHA-MG-02 plug tap cannot cut full thread through the wall")
# The callout's (REF) thread depth is the nominal wall on the tap's axis.
if abs(THUMB_TAP_LENGTH - (TOP_TO_BORE - LEVER_BORE_DIA / 2.0)) > 1e-9:
    raise AssertionError("MHA-MG-02 thread depth is not the wall on the tap's axis")
# The thumb screw's full thread at the printed worst case (geom computes it).
if THUMB_ENGAGEMENT_WORST < ENGAGEMENT_MIN - 1e-9:
    raise AssertionError("MHA-MG-02 thumb-screw thread under 1.5D")

# Model the real finite 118-degree point, not a full cylinder extended to
# the tip. Such a surrogate goes negative for 1/2 stock despite a clear cone.
_DRILL_POINT_DEPTH_MAX = THUMB_TAP_DRILL_DEPTH + _DEPTH_BAND + ROD_TAP_DRILL_POINT
_DRILL_BORE_ANGULAR = BORE_FULL_ANGULAR
_DRILL_RELATIVE_Z_MAX = TAP_TO_BORE_ENTRY_Z_MAX + _DRILL_POINT_DEPTH_MAX * _DRILL_SLOPE + _DRILL_BORE_ANGULAR
_DRILL_HALF_CHORD = math.sqrt(_LEVER_BORE_R_MIN**2 - (_DRILL_R_MAX + _DRILL_RELATIVE_Z_MAX)**2)
THUMB_DRILL_NEAR_CLEAR = _DRILL_HALF_CHORD - 3.0 * _HEIGHT_BAND - _DRILL_BORE_ANGULAR
THUMB_DRILL_FAR_CYLINDER_CLEAR = THUMB_DRILL_NEAR_CLEAR
THUMB_DRILL_FAR_POINT_CLEAR = math.sqrt(_LEVER_BORE_R_MIN**2 - _DRILL_RELATIVE_Z_MAX**2) - 3.0 * _HEIGHT_BAND - _DRILL_BORE_ANGULAR - ROD_TAP_DRILL_POINT
# Along the finite cone s, sqrt(rb²-(offset+r(s))²)-3L-w-s is concave:
# r(s) is affine, so checking BOTH endpoints bounds the whole cone.
THUMB_DRILL_FAR_CLEAR = min(THUMB_DRILL_FAR_CYLINDER_CLEAR, THUMB_DRILL_FAR_POINT_CLEAR)
if not THUMB_DRILL_NEAR_CLEAR > 0.0:
    raise AssertionError("MHA-MG-02 thumb tap drill stops in the near wall")
if not THUMB_DRILL_FAR_CLEAR > 0.0:
    raise AssertionError("MHA-MG-02 thumb tap drill point reaches the far wall")
# The rod tap's drill and thread both fit the plug tap's reach from the face.
if not ROD_TAP_THREAD_DEPTH_MAX + PLUG_TAP_LEAD <= PLUG_TAP_USABLE_LENGTH + 1e-9:
    raise AssertionError("MHA-MG-02 rod tap is deeper than the plug tap reaches")
if not ROD_TAP_DRILL_DEPTH_MAX < LEVER_BORE_Y - _HEIGHT_BAND - _LEVER_BORE_R_MAX - BORE_FULL_ANGULAR:
    raise AssertionError("MHA-MG-02 rod tap drill reaches the lever bore")

# --- Squareness ----------------------------------------------------------------
# The MHA-MG-04 rod seats on the bottom face, so it hangs at the lever bore's
# angle to that seat: the title block's +/-1 deg on the drawn 90 deg.  1 deg
# along the lever swings the wire hook (60.00 under the bore axis, 10.02 toward
# the knife) 1.05 along the lever and 0.17 vertically, moving the wire moment
# arm (error_budget.wire_moment_arm) 1.25 of 56.11 at the collar pose (2.2 %),
# 1.07 of 166.87 at the 165 station (0.6 %) and 0.93 of 208.42 at the rod tip
# (0.4 %).  The ratio is common-mode (tolerance-policy.md: the calibration run
# removes it; error_budget.yaml carries no clamp row) and the operator sets the
# station by the k=0 normalisation, so fit-up absorbs it (rule 19).  Rotation
# about the lever is set by hand at the thumb screw.  Nothing is framed.

# --- Marked model dimensions and the places the model authors on them --------
# Five ordinary native location measurements remain authoritative even when
# the three common-flat values print as one explicitly grouped dimension.
# The native HEX size applies to the complete ordinary hex profile; the
# drawing adds no bespoke receiving-envelope or finished-wall inspection.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HexProfile": {"HexAf": HEX_AF_PLACES},
    "Block": {"Height": HEIGHT_PLACES},
    "LeverBoreProfile": {
        "LeverBoreYDim": HEIGHT_PLACES,
        "LeverBoreDiaDim": LEVER_BORE_DIA_PLACES,
    },
    "ThumbTapLocationProfile": {"ThumbTapFromDiagonalFlat": LOCATION_PLACES},
    "RodTapLocationProfile": {"RodTapFromDiagonalFlat": LOCATION_PLACES},
    "LeverBoreLocationProfile": {
        "LeverBoreFromZFlat": LOCATION_PLACES,
        "ThumbTapFromZFlat": LOCATION_PLACES,
        "RodTapFromZFlat": LOCATION_PLACES,
    },
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
Z_FLAT_DIMENSIONS = ("LeverBoreFromZFlat", "ThumbTapFromZFlat", "RodTapFromZFlat")
# All members are authored, marked, imported and checked before display grouping.
DIMENSION_GROUPS = {"LeverBoreFromZFlat": Z_FLAT_DIMENSIONS}
GROUPED_HIDDEN_DIMENSIONS = frozenset(Z_FLAT_DIMENSIONS[1:])
VISIBLE_DIMENSIONS = frozenset(DRAWING_PRECISION_BY_NAME) - GROUPED_HIDDEN_DIMENSIONS

# --- Sheet text ----------------------------------------------------------------
# Process and mate belong to the actual bore diameter.
LEVER_BORE_CALLOUT = "DRILL THRU CORNERS\nSLIP ON 1/4 IN LEVER MHA-MG-03"
# Ahead of each native thread row.
THUMB_TAP_PROCESS = "TAP INTO BORE; MHA-SH-VN-55"
ROD_TAP_PROCESS = "TAP"
# Native Hole Wizard depth variables; both taps print their depths at .XX,
# the thumb tap's thread depth bracketed REF (the bore ends the thread).
TAP_DRILL_DEPTH_VARIABLE = "hw-tapdrldepth"
TAP_THREAD_DEPTH_VARIABLE = "hw-threaddepth"
TAP_CALLOUT_PRECISION = {
    TAP_DRILL_DEPTH_VARIABLE: HOLE_DEPTH_PLACES,
    TAP_THREAD_DEPTH_VARIABLE: HOLE_DEPTH_PLACES,
}
# Native model-owned prefix: one HEX size, all three opposed-flat pairs.
HEX_AF_PREFIX = "HEX "
# The MHA-MG-04 shoulder's face, flagged on Section A-A's bottom line.
SEAT_NOTE = "MHA-MG-04 SHOULDER SEAT: NO CHAMFER OR SPOTFACE AT TAP"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

# --- Section hatch ----------------------------------------------------------------
# Section A-A hatches the brass in ANSI31's continuous 45 deg lines, not the
# Brass material's dashed ANSI33 (Bronze Brass).  IFaceHatch's Pattern and
# Definition are get-only, so the PART's Material Properties crosshatch
# carries it (set after the material: assigning a material applies its own
# crosshatch) and the section view's material hatch picks it up.  The name is
# the Sldwks.ptn entry's.
SECTION_HATCH_PATTERN = "ANSI31 (Iron BrickStone)"
# IModelDocExtension preferences, swDetailingNoOptionSpecified (0):
# swUserPreferenceIntegerValue_e.swMaterialPropertyAreaHatchFillStyle = 268
# takes swAreaHatchFillStyle_e.swAreaHatchFillStyle_Pattern = 2;
# swUserPreferenceStringValue_e.swMaterialPropertyCrosshatchPattern = 13.
PREF_MATERIAL_HATCH_STYLE = 268
PREF_MATERIAL_HATCH_PATTERN = 13
PREF_NO_OPTION = 0
AREA_HATCH_STYLE_PATTERN = 2
