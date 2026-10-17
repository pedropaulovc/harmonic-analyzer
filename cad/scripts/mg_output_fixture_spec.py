r"""MHA-MG-006 output fixture: the drawing contract shared by part and sheet.

PURE DATA, no SolidWorks/COM imports.  The shape is
``mg_output_fixture_geom``'s (the assembly and the wire read that module, not
this one); this module adds what the print states about it: the marked model
dimensions and their places, the walls at the worst case of the title block's
rows (each holds the 2.0 target, so the sheet states none), and the
manufacturing notes.

Sheet datums: the rod bore is the datum along the hex axis.  The bore is
dimensioned from the free end and to the spigot face (the thumb screw's
reach and the tap's wall are one dimension each, not a stack); the lathe's
own lengths run from the faced spigot end: the shoulder (the spigot's
length) and the groove.  The overall length is REF.  The rod bore is centred
on the hex axis: the end view draws its axis through the tap's centre, and
the walls take the drill's run-off as its only offset from that axis.  The
stations are dimensions on the model (``build_mg_output_fixture``), so the
sheet only proves it imported them.
"""

from __future__ import annotations

import math

import mg_output_fixture_geom as _geom
from _mcmaster_91882a221 import PITCH as SCREW_PITCH
from _mcmaster_91882a221 import SHANK_DIA as SCREW_DIA
from _mcmaster_91882a221 import SHANK_LEN as SCREW_SHANK_LEN
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from mg_magnifying_vertical_rod_geom import ROD_STOCK_DIA_LOW
from mg_output_fixture_geom import (
    FREE_END_X,
    GROOVE_RADIUS,
    GROOVE_ROOT_DIA,
    GROOVE_STATION,
    HEX_AF,
    HEX_CORNER_RADIUS,
    HEX_LENGTH,
    OVERALL_LENGTH,
    ROD_BORE_DIA,
    ROD_STATION,
    SHOULDER_FILLET_R,
    SPIGOT_DIA,
    SPIGOT_FACE_X,
    SPIGOT_LENGTH,
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_LENGTH,
    THREAD_MAJOR,
    VROD_DIA,
)

# The thumb-screw receiver: the joint-retention audit and the sheet's hole
# callout both read it here.
TAP_SPEC = _geom.TAP_SPEC

# The bore's station back from the spigot face (the bore axis is the part
# origin); the groove's runs from the same face (mg_output_fixture_geom).
BORE_STATION = SPIGOT_FACE_X

# Drill wander, restated (mg_magnifying_clamp_spec's precedent) so this recipe
# does not import other parts' closures: linear start wander and angular
# run-off.
DRILL_WANDER_MAX = 0.10
DRILL_WANDER_DEG = 0.3


def _wander(depth_mm: float) -> float:
    """A drill's worst lateral run-off at ``depth_mm``: the linear start
    wander plus the angular wander over the depth."""
    return DRILL_WANDER_MAX + depth_mm * math.tan(math.radians(DRILL_WANDER_DEG))


# --- Places each printed dimension carries ---------------------------------------
# Every length and turned Ø prints at the title block's .XX; none carries its
# own band (drawing-guidelines.md rule 3: the places carry the tolerance).
# The bar's flats: the exact 7/16 in, printed as a stock reference (11.113).
HEX_AF_PLACES = 3
ROD_STATION_PLACES = 2
SPIGOT_LENGTH_PLACES = 2
BORE_STATION_PLACES = 2
GROOVE_STATION_PLACES = 2
OVERALL_LENGTH_PLACES = 2
SPIGOT_DIA_PLACES = 2
GROOVE_ROOT_DIA_PLACES = 2
# The groove's radius prints as the single limit "R1.2 MAX" (rule 16: the
# largest acceptable concave radius; swTolMAX prints the model value, so the
# model IS the limit).  Any smaller radius narrows the mouth and thickens both
# lips; at the title block's .X (R up to 2.0) the face-side lip falls under
# the wall target (test_mg_output_fixture_drawing proves it).
GROOVE_RADIUS_PLACES = 1
GROOVE_RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
# The drilled rod bore prints at one place; its band is the title block's
# DRILLED HOLES row (+0.10/0): running clearance on the rod, no fit.
ROD_BORE_DIA_PLACES = 1
# The shoulder's internal corner prints as the single limit "R0.2 MAX" (rule
# 16: the largest tool-nose radius the shoulder takes; the model IS the limit).
SHOULDER_RADIUS_PLACES = 1
SHOULDER_RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
# The tap's drill and thread depths (native Hole Wizard variables): one place,
# the general .X.  The drill depth governs; the thread depth is REF -- the
# callout prints it in parentheses, and the note's FULL THREAD TO ROD BORE
# governs the thread's extent, not a .X band.
TAP_DEPTH_PLACES = 1
# The overall length is the sum of the bore's two stations: REF, so the sheet
# never closes a loop of three toleranced lengths.
REFERENCE_DIMENSIONS = frozenset({"HexAf", "OverallLength"})

# --- Printed limits ----------------------------------------------------------------
# An assumption, not a printed band: the flats as supplied stay within
# +/-0.13 of 7/16 in (the band MG-002's same bar assumes,
# mg_magnifying_clamp_geom.HEX_AF_BAND).  Every wall, the spigot's clean-up
# and the tap's reach below hold at it.
HEX_STOCK_AF_BAND = 0.13
_ROD_STATION_LO, _ = printed_deviations(ROD_STATION, ROD_STATION_PLACES)
_SPIGOT_LENGTH_LO, _SPIGOT_LENGTH_HI = printed_deviations(
    SPIGOT_LENGTH, SPIGOT_LENGTH_PLACES
)
_BORE_STATION_LO, _BORE_STATION_HI = printed_deviations(
    BORE_STATION, BORE_STATION_PLACES
)
_, _GROOVE_HI = printed_deviations(GROOVE_STATION, GROOVE_STATION_PLACES)
_SPIGOT_LO, _ = printed_deviations(SPIGOT_DIA, SPIGOT_DIA_PLACES)
_ROOT_LO, _ROOT_HI = printed_deviations(GROOVE_ROOT_DIA, GROOVE_ROOT_DIA_PLACES)
# MAX: from sharp up to the printed (= model) radius.
GROOVE_RADIUS_MAX = GROOVE_RADIUS
SHOULDER_FILLET_R_MAX = SHOULDER_FILLET_R
ROD_BORE_R_MIN = ROD_BORE_DIA / 2.0
ROD_BORE_R_MAX = (ROD_BORE_DIA + drilled_oversize_mm()) / 2.0
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025
_THREAD_R_MAX = THREAD_MAJOR / 2.0 + _TAP_OVERSIZE_R
# Spigot face to the bore axis: one printed dimension.
FACE_TO_BORE_AXIS_MAX = BORE_STATION + _BORE_STATION_HI
FACE_TO_BORE_AXIS_MIN = BORE_STATION + _BORE_STATION_LO
# The bore is drilled corner to corner: its run-off at the exit corner.
BORE_WANDER = _wander(HEX_CORNER_RADIUS)

# The turned spigot cleans up all round inside the thinnest stock's flats at
# the Ø the shop turns to.  A part that kept a flat would not carry the
# printed Ø at all (a Ø is round), so this is the route's check, not a band's.
if not SPIGOT_DIA < HEX_AF - HEX_STOCK_AF_BAND:
    raise AssertionError("MHA-MG-006 spigot Ø leaves flats on the thinnest stock")


def groove_half_opening(radius: float, root_dia: float, spigot_dia: float) -> float:
    """Half the groove's mouth along the axis: where the full-radius arc on a
    root of ``root_dia`` meets an OD of ``spigot_dia``."""
    centre_above_od = root_dia / 2.0 + radius - spigot_dia / 2.0
    return (radius**2 - max(centre_above_od, 0.0) ** 2) ** 0.5


# Whatever root and OD the title block allows, the mouth's half-opening never
# exceeds the radius (the chord of a circle never exceeds its diameter): the
# widest mouth the print allows is the MAX radius itself.
GROOVE_HALF_OPENING_MAX = GROOVE_RADIUS_MAX
if groove_half_opening(GROOVE_RADIUS, GROOVE_ROOT_DIA, SPIGOT_DIA) > (
    GROOVE_HALF_OPENING_MAX
):
    raise AssertionError("MHA-MG-006 groove mouth exceeds its MAX radius")
# The wire stays in the groove: at the smallest OD over the largest root the
# groove is still deeper than the wire's radius.
GROOVE_DEPTH_MIN = ((SPIGOT_DIA + _SPIGOT_LO) - (GROOVE_ROOT_DIA + _ROOT_HI)) / 2.0
if not GROOVE_DEPTH_MIN > _geom.WIRE_DIA / 2.0:
    raise AssertionError("MHA-MG-006 groove shallower than the wire's radius")
# The groove stays on the spigot at the worst case: its shoulder-side mouth
# clears the shoulder (the spigot's length and the groove's station both run
# from the spigot face: one band each), and the shoulder's corner radius.
GROOVE_SHOULDER_CLEARANCE = (SPIGOT_LENGTH + _SPIGOT_LENGTH_LO) - (
    GROOVE_STATION + _GROOVE_HI + GROOVE_HALF_OPENING_MAX
)
GROOVE_FILLET_CLEARANCE = GROOVE_SHOULDER_CLEARANCE - SHOULDER_FILLET_R_MAX
if not GROOVE_FILLET_CLEARANCE > 0.0:
    raise AssertionError(
        "MHA-MG-006 groove runs into the shoulder's corner at the worst case"
    )
# The shoulder's corner radius stays on the shoulder face, inside the flats'
# annulus round the spigot, even on the thinnest bar.
SHOULDER_ANNULUS = (HEX_AF - SPIGOT_DIA) / 2.0
SHOULDER_ANNULUS_MIN = (HEX_AF - HEX_STOCK_AF_BAND - SPIGOT_DIA) / 2.0
if not SHOULDER_FILLET_R_MAX < SHOULDER_ANNULUS_MIN:
    raise AssertionError("MHA-MG-006 shoulder radius runs off the shoulder face")

# --- Walls at the printed worst case (drawing-guidelines.md rule 17 (walls and webs)) ----------------------------
# (nominal, worst).  Drilled walls take the drill's wander over its depth;
# turned walls do not.  The bore is centred by the hex sketch's symmetry, with
# no printed location: its worst offset from the hex axis is the drill's
# corner-to-corner run-off.
WALL_TARGET = 2.0
BORE_OFFSET_MAX = BORE_WANDER
# The far side of the groove from the spigot face: where the tap's run-off
# under the groove's root is largest.
_GROOVE_FAR_DEPTH = GROOVE_STATION + _GROOVE_HI + GROOVE_RADIUS_MAX
WALLS: dict[str, tuple[float, float]] = {
    "rod bore to a flat": (
        (HEX_AF - ROD_BORE_DIA) / 2.0,
        (HEX_AF - HEX_STOCK_AF_BAND) / 2.0 - ROD_BORE_R_MAX - BORE_OFFSET_MAX,
    ),
    "rod bore to the free end": (
        ROD_STATION - ROD_BORE_DIA / 2.0,
        ROD_STATION + _ROD_STATION_LO - ROD_BORE_R_MAX - BORE_WANDER,
    ),
    "rod bore to the shoulder": (
        BORE_STATION - SPIGOT_LENGTH - ROD_BORE_DIA / 2.0,
        FACE_TO_BORE_AXIS_MIN
        - (SPIGOT_LENGTH + _SPIGOT_LENGTH_HI)
        - ROD_BORE_R_MAX
        - BORE_WANDER,
    ),
    "groove lip to the spigot face": (
        GROOVE_STATION - _geom.GROOVE_HALF_OPENING,
        GROOVE_STATION - _GROOVE_HI - GROOVE_HALF_OPENING_MAX,
    ),
    "groove root over the thread major": (
        (GROOVE_ROOT_DIA - THREAD_MAJOR) / 2.0,
        (GROOVE_ROOT_DIA + _ROOT_LO) / 2.0 - _THREAD_R_MAX - _wander(_GROOVE_FAR_DEPTH),
    ),
}
# Every wall holds the target at the worst case (the owner's 2026-10-16
# ruling, #1559), so the sheet states none (drawing-guidelines.md rule 20).
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET - 1e-9:
        raise AssertionError(
            f"MHA-MG-006 {_name} wall {_worst:.3f} under the {WALL_TARGET} target "
            "at the printed worst case"
        )


# --- The thumb screw (McMaster 91882A221) ------------------------------------------
# Its tip pushes the rod against the bore's far wall: the reach it needs runs
# from the spigot face to the rod's near side there.  Its threaded shank must
# reach it at the deepest bore, largest drilled Ø and thinnest rod stock.
ROD_DIA_MIN = VROD_DIA - ROD_STOCK_DIA_LOW
SCREW_REACH_NEEDED = FACE_TO_BORE_AXIS_MAX + ROD_BORE_R_MAX - ROD_DIA_MIN
SCREW_REACH_MARGIN = SCREW_SHANK_LEN - SCREW_REACH_NEEDED
if not SCREW_REACH_MARGIN > 0.0:
    raise AssertionError("MHA-MG-006 thumb screw bottoms before it clamps the rod")
# Full thread from the face to the shallowest bore wall on the tap's axis,
# less the first pitch at the face: at least 1.5 D of engagement.
ENGAGEMENT_MIN = 1.5 * SCREW_DIA
ENGAGEMENT_WORST = FACE_TO_BORE_AXIS_MIN - ROD_BORE_R_MAX - SCREW_PITCH
if ENGAGEMENT_WORST < ENGAGEMENT_MIN - 1e-9:
    raise AssertionError("MHA-MG-006 thumb-screw thread under 1.5D")

# --- The tap's reach (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)) -----------------------------------------------
# FULL THREAD TO ROD BORE asks for a bottoming tap: the #4-40 hand tap's
# usable length is 9/16 in on a 0.141 in shank (Morse Cutting Tools
# https://morsecuttingtools.com/catalogue/product/552474; ICS Cutting Tools
# "Tap Dimensions" https://www.icscuttingtools.com/pdfs/Tap-Dimensions.pdf),
# the shank over the thread's major, so it stops at the spigot face: LU is
# all the tap can reach.  ICS gives the bottoming chamfer as 1-2 threads (the
# plug's 3-6 threads cannot reach full thread at the worst case: the tests
# prove it).
TAP_USABLE_LENGTH = 9.0 / 16.0 * 25.4
TAP_SHANK_DIA = 0.141 * 25.4
BOTTOMING_TAP_CHAMFER_THREADS = (1, 2)
THREAD_PITCH = 25.4 / 40.0
BOTTOMING_TAP_LEAD = BOTTOMING_TAP_CHAMFER_THREADS[1] * THREAD_PITCH
if not TAP_SHANK_DIA > THREAD_MAJOR:
    raise AssertionError("MHA-MG-006 tap shank enters its own thread")
# The bore's half-chord at the thread's widest reach off the bore axis: the
# major envelope, with the bore off centre by the drill's run-off.
THREAD_HALF_CHORD = math.sqrt(
    ROD_BORE_R_MIN**2 - (_THREAD_R_MAX + BORE_OFFSET_MAX) ** 2
)
# The deepest wall the thread crosses (its flanks run past the axis' 10.1
# before the bore takes the whole envelope), and the far wall's nearest point.
TAP_WALL_DEEPEST = FACE_TO_BORE_AXIS_MAX - THREAD_HALF_CHORD
TAP_REACH_NEEDED = TAP_WALL_DEEPEST + BOTTOMING_TAP_LEAD
FAR_WALL_NEAREST = FACE_TO_BORE_AXIS_MIN + THREAD_HALF_CHORD
if TAP_REACH_NEEDED > TAP_USABLE_LENGTH + 1e-9:
    raise AssertionError(
        "MHA-MG-006 bottoming tap cannot cut full thread through the wall"
    )
# On ONE part the near and far walls move together: the tap stops once its
# lead has passed into the bore, inside the bore's chord less the lead.
TAP_STOP_WINDOW = 2.0 * THREAD_HALF_CHORD - BOTTOMING_TAP_LEAD
if not TAP_STOP_WINDOW > 0.0:
    raise AssertionError("MHA-MG-006 tap meets the far wall before full thread")
# The callout's (REF) thread depth is the nominal wall on the tap's axis: where
# the rod bore ends the thread.
if abs(TAP_LENGTH - (BORE_STATION - ROD_BORE_DIA / 2.0)) > 1e-9:
    raise AssertionError("MHA-MG-006 thread depth is not the wall on the tap's axis")

# The tap drill, at its printed .X depth and drilled-hole Ø: its full Ø clears
# the near wall at the shallowest depth, and its 118 deg point stops short of
# the far wall at the deepest.
_DRILL_DEPTH_LO, _DRILL_DEPTH_HI = printed_deviations(TAP_DRILL_DEPTH, TAP_DEPTH_PLACES)
_DRILL_R_MAX = (TAP_DRILL_DIA + drilled_oversize_mm()) / 2.0
_DRILL_POINT = _DRILL_R_MAX / math.tan(math.radians(59.0))
_DRILL_HALF_CHORD = math.sqrt(ROD_BORE_R_MIN**2 - (_DRILL_R_MAX + BORE_OFFSET_MAX) ** 2)
TAP_DRILL_NEAR_CLEAR = (
    TAP_DRILL_DEPTH + _DRILL_DEPTH_LO - (FACE_TO_BORE_AXIS_MAX - _DRILL_HALF_CHORD)
)
TAP_DRILL_FAR_CLEAR = (FACE_TO_BORE_AXIS_MIN + _DRILL_HALF_CHORD) - (
    TAP_DRILL_DEPTH + _DRILL_DEPTH_HI + _DRILL_POINT
)
if not TAP_DRILL_NEAR_CLEAR > 0.0:
    raise AssertionError("MHA-MG-006 tap drill stops in the near wall")
if not TAP_DRILL_FAR_CLEAR > 0.0:
    raise AssertionError("MHA-MG-006 tap drill point reaches the far wall")

# The turned profile (Top plane) carries the bore's stations from the free end
# and to the spigot face, the shoulder from the spigot face (the spigot's
# length), the overall length (driven, REF) and the spigot's Ø; the shoulder
# fillet its corner radius (a single MAX limit); the groove profile (Top
# plane) the groove's station from the spigot face, its root Ø and its radius;
# the hex sketch (the FreeEnd plane) the flats, a stock reference (the bore is
# centred: no location from a flat); the bore sketch (Top plane) its Ø.  The
# tap is a Hole Wizard feature: its native callout prints it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "TurnedProfile": {
        "RodStation": ROD_STATION_PLACES,
        "SpigotLength": SPIGOT_LENGTH_PLACES,
        "BoreStation": BORE_STATION_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
        "SpigotDia": SPIGOT_DIA_PLACES,
    },
    "ShoulderFillet": {"ShoulderRadius": SHOULDER_RADIUS_PLACES},
    "GrooveProfile": {
        "GrooveStation": GROOVE_STATION_PLACES,
        "GrooveRootDia": GROOVE_ROOT_DIA_PLACES,
        "GrooveRadius": GROOVE_RADIUS_PLACES,
    },
    "HexProfile": {"HexAf": HEX_AF_PLACES},
    "RodBoreProfile": {"RodBoreDia": ROD_BORE_DIA_PLACES},
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Single-limit dimensions (name -> (owning feature, swTolType)).
SINGLE_LIMITS: dict[str, tuple[str, int]] = {
    "GrooveRadius": ("GrooveProfile", GROOVE_RADIUS_TOL_TYPE),
    "ShoulderRadius": ("ShoulderFillet", SHOULDER_RADIUS_TOL_TYPE),
}
if not REFERENCE_DIMENSIONS <= set(DRAWING_PRECISION_BY_NAME) - set(SINGLE_LIMITS):
    raise AssertionError("MHA-MG-006 reference dimension is unprinted or limited")
if abs(OVERALL_LENGTH - (ROD_STATION + BORE_STATION)) > 1e-9:
    raise AssertionError("MHA-MG-006 overall REF is not the bore's two stations")
# The hex is extruded to the shoulder the spigot's length sets: its depth is
# the bore's two stations less the spigot (the part's equation).
if abs(HEX_LENGTH - (ROD_STATION + BORE_STATION - SPIGOT_LENGTH)) > 1e-9:
    raise AssertionError("MHA-MG-006 hex length is not the stations less the spigot")
if abs(FREE_END_X + ROD_STATION) > 1e-9:
    raise AssertionError("MHA-MG-006 rod station does not run free end to bore axis")

# --- Sheet text -------------------------------------------------------------------
# Under the bore's Ø: how it is made (drilled; the DRILLED HOLES row is its
# band), across the corners as the end view's centreline draws it.
ROD_BORE_CALLOUT = "DRILL THRU"
# Ahead of the native thread row: the tap runs from the spigot face into the
# bore (no THRU: the tap stops in the bore, short of the far wall).
TAP_PROCESS = "TAP INTO BORE"
# The controlling drill depth and the reference thread depth, by their native
# Hole Wizard variable names: the sheet brackets the thread depth's variable in
# the callout's own definition, so the printed (10.1) stays the model's.
TAP_DRILL_DEPTH_VARIABLE = "hw-tapdrldepth"
TAP_THREAD_DEPTH_VARIABLE = "hw-threaddepth"
TAP_CALLOUT_PRECISION = {
    TAP_DRILL_DEPTH_VARIABLE: TAP_DEPTH_PLACES,
    TAP_THREAD_DEPTH_VARIABLE: TAP_DEPTH_PLACES,
}
STOCK_NOTE = "7/16 HEX BAR, FLATS AS SUPPLIED."
# The thread's extent: the rod bore ends it; the callout prints the native
# thread depth, its nominal, as (REF).
TAP_EXTENT_NOTE = "FULL THREAD TO ROD BORE."
# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): two rows.
DRAWING_NOTES = "\n".join((STOCK_NOTE, TAP_EXTENT_NOTE))
