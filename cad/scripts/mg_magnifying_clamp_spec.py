r"""MHA-MG-02 magnifying clamp: the drawing contract shared by part and sheet.

PURE DATA, no SolidWorks/COM imports.  The shape is
``mg_magnifying_clamp_geom``'s (the assembly, the error budget and the web
export read that module, not this one); this module adds what the print states
about it: the marked model dimensions and their places, the walls at the worst
case of the printed bands and the stock, the plug taps' reach and the sheet
text.

Sheet datums: the heights run from the bottom face (the MHA-MG-04 shoulder
seat).  The lever bore and both #4-40 taps sit on the hex axis, centred
between the flats by symmetry (the MHA-MG-06 rod bore's precedent), with no
location from a flat: the thumb-screw tap from the top face into the lever
bore, the rod tap blind from the bottom face (``mg_rod_clamp_joint``).
"""

from __future__ import annotations

import math

from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from mg_magnifying_clamp_geom import (  # noqa: F401 (re-export)
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    EDGE_BREAK,
    HEIGHT_PLACES,
    HEX_AC,
    HEX_AF,
    HEX_AF_BAND,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_TAP_DRILL_DIA,
    ROD_TAP_DRILL_POINT,
    ROD_TAP_FLOOR_WALL_WORST,
    THUMB_ENGAGEMENT_WORST,
    THUMB_TAP_DRILL_DEPTH,
    THUMB_TAP_LENGTH,
    THUMB_TAP_SPEC,
    TOP_TO_BORE,
    WALL_TARGET,
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

# Drill wander, restated (the sh_column_clamp_fit precedent) so this recipe
# does not import those parts' closures: linear start wander
# (sm_gooseneck_spring_joint.DRILL_WANDER_MAX) and angular run-off
# (fr_top_frame_spec.KEEPER_TAP_DRILL_WANDER_DEG).
DRILL_WANDER_MAX = 0.10
DRILL_WANDER_DEG = 0.3

# --- Places each printed dimension carries ----------------------------------
# The flats: the exact 7/16 in, printed as a stock reference (11.113).
HEX_AF_PLACES = 3
# The drilled lever bore prints at one place; its band is the title block's
# DRILLED HOLES row (+0.10/0), its fit the callout's named mate.
LEVER_BORE_DIA_PLACES = 1
REFERENCE_DIMENSIONS = frozenset({"HexAf"})

# --- Printed limits ----------------------------------------------------------
_HEIGHT_BAND = printed_band_mm(HEIGHT_PLACES)  # 0.51 on the height and the bore's
_DEPTH_BAND = printed_band_mm(HOLE_DEPTH_PLACES)  # 0.51 on both taps' depths
_LEVER_BORE_R_MIN = LEVER_BORE_DIA / 2.0
_LEVER_BORE_R_MAX = (LEVER_BORE_DIA + drilled_oversize_mm()) / 2.0
_DRILL_R_MAX = (ROD_TAP_DRILL_DIA + drilled_oversize_mm()) / 2.0
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025
_THREAD_R_MAX = THREAD_MAJOR / 2.0 + _TAP_OVERSIZE_R
_THIN_HALF_AF = (HEX_AF - HEX_AF_BAND) / 2.0


def _wander(depth_mm: float) -> float:
    """A drill's worst lateral run-off at ``depth_mm``: the linear start
    wander plus the angular wander over the depth."""
    return DRILL_WANDER_MAX + depth_mm * math.tan(math.radians(DRILL_WANDER_DEG))


# --- Walls at the printed worst case (drawing-guidelines.md rule 17 (walls and webs)) --
# The lever bore is centred between the flats by symmetry, so its axis stands
# off the hex axis only by the drill's run-off over its half-length to the
# middle of the block.
BORE_WANDER = _wander(HEX_AC / 2.0)
BORE_OFFSET_MAX = BORE_WANDER
# (nominal, worst).  The bore to a flat: its largest drilled Ø on the thinnest
# stock, off centre by its wander.  The taps run on the hex axis: their thread
# major (tap oversize included) to a flat on the thinnest stock, less the
# drill's linear and angular wander over the deepest printed thread.  Each
# holds the target, so the sheet states none (rule 20).
WALLS: dict[str, tuple[float, float]] = {
    "lever bore to a flat": (
        (HEX_AF - LEVER_BORE_DIA) / 2.0,
        _THIN_HALF_AF - _LEVER_BORE_R_MAX - BORE_WANDER,
    ),
    "rod-tap drill point to the lever bore": (
        LEVER_BORE_Y
        - LEVER_BORE_DIA / 2.0
        - ROD_TAP_DRILL_DEPTH
        - ROD_TAP_DRILL_DIA / 2.0 / math.tan(math.radians(59.0)),
        ROD_TAP_FLOOR_WALL_WORST,
    ),
    "rod-tap thread to a flat": (
        (HEX_AF - THREAD_MAJOR) / 2.0,
        _THIN_HALF_AF - _THREAD_R_MAX - _wander(ROD_TAP_THREAD_DEPTH_MAX),
    ),
    "thumb-screw tap thread to a flat": (
        (HEX_AF - THREAD_MAJOR) / 2.0,
        _THIN_HALF_AF - _THREAD_R_MAX - _wander(TOP_TO_BORE + 2.0 * _HEIGHT_BAND),
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET - 1e-9:
        raise AssertionError(
            f"MHA-MG-02 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under {WALL_TARGET}"
        )


# --- The thumb-screw tap's reach (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)) --
# The reach a stock #4-40 plug tap gives (Morse item 30000: usable length
# 9/16 in on a shank over the major, a 3-5 thread chamfer); the sheet names
# no tool, the arithmetic only proves a common one makes the part.
PLUG_TAP_USABLE_LENGTH = 9.0 / 16.0 * 25.4
PLUG_TAP_CHAMFER_THREADS = (3, 5)
if abs(PLUG_TAP_CHAMFER_THREADS[1] * THREAD_PITCH - PLUG_TAP_LEAD) > 1e-9:
    raise AssertionError("MHA-MG-02 plug-tap lead disagrees with the rod joint's")
# Top face to the bore axis: both heights at their .XX limits.
_TOP_TO_AXIS_MAX = TOP_TO_BORE + 2.0 * _HEIGHT_BAND
_TOP_TO_AXIS_MIN = TOP_TO_BORE - 2.0 * _HEIGHT_BAND
# The bore's half-chord at the thread's widest reach off the bore axis: the
# major envelope, with the bore off centre by its wander.
_THREAD_HALF_CHORD = math.sqrt(
    _LEVER_BORE_R_MIN**2 - (_THREAD_R_MAX + BORE_OFFSET_MAX) ** 2
)
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

# The tap drill, at its printed .XX depth: its full Ø clears the near wall at
# the shallowest depth, and its 118 deg point stops short of the far wall at
# the deepest.
_DRILL_HALF_CHORD = math.sqrt(
    _LEVER_BORE_R_MIN**2 - (_DRILL_R_MAX + BORE_OFFSET_MAX) ** 2
)
THUMB_DRILL_NEAR_CLEAR = (
    THUMB_TAP_DRILL_DEPTH - _DEPTH_BAND - (_TOP_TO_AXIS_MAX - _DRILL_HALF_CHORD)
)
THUMB_DRILL_FAR_CLEAR = (_TOP_TO_AXIS_MIN + _DRILL_HALF_CHORD) - (
    THUMB_TAP_DRILL_DEPTH + _DEPTH_BAND + ROD_TAP_DRILL_POINT
)
if not THUMB_DRILL_NEAR_CLEAR > 0.0:
    raise AssertionError("MHA-MG-02 thumb tap drill stops in the near wall")
if not THUMB_DRILL_FAR_CLEAR > 0.0:
    raise AssertionError("MHA-MG-02 thumb tap drill point reaches the far wall")
# The rod tap's drill and thread both fit the plug tap's reach from the face.
if not ROD_TAP_THREAD_DEPTH_MAX + PLUG_TAP_LEAD <= PLUG_TAP_USABLE_LENGTH + 1e-9:
    raise AssertionError("MHA-MG-02 rod tap is deeper than the plug tap reaches")
if not ROD_TAP_DRILL_DEPTH_MAX < LEVER_BORE_Y - _HEIGHT_BAND - _LEVER_BORE_R_MAX:
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
# The hex sketch (Top plane) carries the flats, a stock reference; the block
# extrude its height from the bottom seat; the lever-bore sketch (Right plane)
# its height from the bottom seat and its Ø (the bore sits on the hex axis by
# a relation, centred between the flats).  Both taps are Hole Wizard features:
# their native callouts print them.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HexProfile": {"HexAf": HEX_AF_PLACES},
    "Block": {"Height": HEIGHT_PLACES},
    "LeverBoreProfile": {
        "LeverBoreYDim": HEIGHT_PLACES,
        "LeverBoreDiaDim": LEVER_BORE_DIA_PLACES,
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
if not REFERENCE_DIMENSIONS <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("MHA-MG-02 reference dimension is unprinted")

# --- Sheet text ----------------------------------------------------------------
# The lever bore's Ø: drilled and the mate it slides on (rule 4), one row each
# under the Ø.  Its wall to a flat holds the target, so the sheet states none.
LEVER_BORE_CALLOUT = "\n".join(("DRILL THRU CORNERS", "SLIP ON Ø6 LEVER MHA-MG-03"))
# Ahead of each native thread row.
THUMB_TAP_PROCESS = "TAP INTO BORE"
ROD_TAP_PROCESS = "TAP"
# Native Hole Wizard depth variables; both taps print their depths at .XX,
# the thumb tap's thread depth bracketed REF (the bore ends the thread).
TAP_DRILL_DEPTH_VARIABLE = "hw-tapdrldepth"
TAP_THREAD_DEPTH_VARIABLE = "hw-threaddepth"
TAP_CALLOUT_PRECISION = {
    TAP_DRILL_DEPTH_VARIABLE: HOLE_DEPTH_PLACES,
    TAP_THREAD_DEPTH_VARIABLE: HOLE_DEPTH_PLACES,
}
STOCK_NOTE = "7/16 HEX BAR, FLATS AS SUPPLIED."
# The MHA-MG-04 shoulder's face, flagged on Section A-A's bottom line.
SEAT_NOTE = "MHA-MG-04 SHOULDER SEAT:\nNO CHAMFER OR SPOTFACE AT TAP"
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the stock.
DRAWING_NOTES = STOCK_NOTE
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
