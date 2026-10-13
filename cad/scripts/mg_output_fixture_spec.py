r"""MHA-MG-006 output fixture: the drawing contract shared by part and sheet.

PURE DATA, no SolidWorks/COM imports.  The shape is
``mg_output_fixture_geom``'s (the assembly and the wire read that module, not
this one); this module adds what the print states about it: the marked model
dimensions and their places, the explicit bands the model carries, the walls
at the worst case of those printed bands, and the manufacturing notes.

Sheet datums: the axial stations are baselined from the free end of the hex
(the rod bore, the shoulder, the groove and the spigot face); the rod bore is
centred on the hex axis, and the stated bore-to-flat wall is the centring's
acceptance.  The stations are dimensions on the model
(``build_mg_output_fixture``), so the sheet only proves it imported them.
"""

from __future__ import annotations

import math

import mg_output_fixture_geom as _geom
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from mg_output_fixture_geom import (
    FREE_END_X,
    GROOVE_RADIUS,
    GROOVE_ROOT_DIA,
    GROOVE_X,
    HEX_AF,
    HEX_LENGTH,
    OVERALL_LENGTH,
    ROD_BORE_DIA,
    ROD_STATION,
    SPIGOT_DIA,
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_LENGTH,
    THREAD_MAJOR,
)

# The thumb-screw receiver: the joint-retention audit and the sheet's hole
# callout both read it here.
TAP_SPEC = _geom.TAP_SPEC

# Axial stations from the free end (local x - FREE_END_X).
GROOVE_STATION = GROOVE_X - FREE_END_X

# --- Explicit bands the model carries (drawing-guidelines.md rule 3 (decimal places carry the tolerance)) --------------------------
# (upper, lower): the reamed slip bore on the Ø5 rod.
ROD_BORE_DIA_BAND = (0.03, 0.0)
# +/- on the bore's station from the free end (its end wall and the tap's
# reach), on the shoulder, the groove and the spigot face (both groove lips;
# the face also sets the tap's reach), and on the spigot and groove sizes
# that set the groove's mouth.  None can open to its general row: each one
# there takes a groove lip under the 2.0 target, the tap's reach past its
# 9/16 in of thread, or the spigot's Ø past the thinnest stock's flats
# (test_mg_output_fixture_drawing proves each relaxation fails).
POSITION_TOLERANCE = 0.05
SIZE_TOLERANCE = 0.05

# --- Places each printed dimension carries ---------------------------------------
# The bar's flats: the exact 3/8 in, printed as a stock reference, (9.525).
HEX_AF_PLACES = 3
ROD_STATION_PLACES = 2
HEX_LENGTH_PLACES = 2
GROOVE_STATION_PLACES = 2
OVERALL_LENGTH_PLACES = 2
SPIGOT_DIA_PLACES = 2
GROOVE_ROOT_DIA_PLACES = 2
GROOVE_RADIUS_PLACES = 2
ROD_BORE_DIA_PLACES = 2
# The tap's drill and thread depths (native Hole Wizard variables): one place,
# the general .X.  The drill depth governs; the thread depth is REF -- the
# callout prints it in parentheses, and the note's THREAD ENDS AT ROD BORE
# governs the thread's extent, not a .X band.
TAP_DEPTH_PLACES = 1
REFERENCE_DIMENSIONS = frozenset({"HexAf"})

# --- Printed limits ----------------------------------------------------------------
_POSITION = (-POSITION_TOLERANCE, POSITION_TOLERANCE)
_SIZE = (-SIZE_TOLERANCE, SIZE_TOLERANCE)
# An assumption, not a printed band: the flats as supplied stay within
# +/-0.13 of 3/8 in (the .XXX row this size printed under before it became a
# stock reference).  Every wall, the spigot's clean-up and the tap's reach
# below hold at it.
HEX_STOCK_AF_BAND = 0.13
_ROD_STATION_LO, _ROD_STATION_HI = printed_deviations(
    ROD_STATION, ROD_STATION_PLACES, _POSITION
)
_, _SHOULDER_HI = printed_deviations(HEX_LENGTH, HEX_LENGTH_PLACES, _POSITION)
_GROOVE_LO, _GROOVE_HI = printed_deviations(
    GROOVE_STATION, GROOVE_STATION_PLACES, _POSITION
)
_FACE_LO, _FACE_HI = printed_deviations(
    OVERALL_LENGTH, OVERALL_LENGTH_PLACES, _POSITION
)
_, _SPIGOT_HI = printed_deviations(SPIGOT_DIA, SPIGOT_DIA_PLACES, _SIZE)
_ROOT_LO, _ = printed_deviations(GROOVE_ROOT_DIA, GROOVE_ROOT_DIA_PLACES, _SIZE)
_, _RADIUS_HI = printed_deviations(GROOVE_RADIUS, GROOVE_RADIUS_PLACES, _SIZE)
_ROD_BORE_R_MIN = (ROD_BORE_DIA + ROD_BORE_DIA_BAND[1]) / 2.0
_ROD_BORE_R_MAX = (ROD_BORE_DIA + ROD_BORE_DIA_BAND[0]) / 2.0
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025
_THREAD_R_MAX = THREAD_MAJOR / 2.0 + _TAP_OVERSIZE_R

# The turned spigot cleans up all round inside the thinnest stock's flats.
if not SPIGOT_DIA + _SPIGOT_HI < HEX_AF - HEX_STOCK_AF_BAND:
    raise AssertionError("MHA-MG-006 spigot at its largest leaves flats on the turned Ø")


def groove_half_opening(radius: float, root_dia: float, spigot_dia: float) -> float:
    """Half the groove's mouth along the axis: where the full-radius arc on a
    centre ``radius`` above the root meets the spigot OD."""
    centre_above_od = root_dia / 2.0 + radius - spigot_dia / 2.0
    return (radius**2 - centre_above_od**2) ** 0.5


# The widest mouth the printed bands allow: the largest radius on the
# smallest root under the largest OD, while the arc's centre stays outside
# that OD (past it, the widest mouth is the radius itself).
if not (GROOVE_ROOT_DIA + _ROOT_LO) / 2.0 + GROOVE_RADIUS + _RADIUS_HI > (
    SPIGOT_DIA + _SPIGOT_HI
) / 2.0:
    raise AssertionError("MHA-MG-006 groove arc centre falls inside the largest OD")
GROOVE_HALF_OPENING_MAX = groove_half_opening(
    GROOVE_RADIUS + _RADIUS_HI, GROOVE_ROOT_DIA + _ROOT_LO, SPIGOT_DIA + _SPIGOT_HI
)

# --- Walls at the printed worst case (drawing-guidelines.md rule 17 (walls and webs)) ----------------------------
# (nominal, worst).  The bore-to-flat wall is the bore centred on the thinnest
# stock at its largest Ø; how far off centre the bore may stand is what the
# sheet's stated MIN accepts (below), not a printed band.
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
BORE_WALL_NAME = "rod bore to a flat"
WALLS: dict[str, tuple[float, float]] = {
    BORE_WALL_NAME: (
        (HEX_AF - ROD_BORE_DIA) / 2.0,
        (HEX_AF - HEX_STOCK_AF_BAND) / 2.0 - _ROD_BORE_R_MAX,
    ),
    "rod bore to the free end": (
        ROD_STATION - ROD_BORE_DIA / 2.0,
        ROD_STATION + _ROD_STATION_LO - _ROD_BORE_R_MAX,
    ),
    "groove lip to the shoulder": (
        GROOVE_STATION - _geom.GROOVE_HALF_OPENING - HEX_LENGTH,
        GROOVE_STATION
        + _GROOVE_LO
        - GROOVE_HALF_OPENING_MAX
        - (HEX_LENGTH + _SHOULDER_HI),
    ),
    "groove lip to the spigot face": (
        OVERALL_LENGTH - GROOVE_STATION - _geom.GROOVE_HALF_OPENING,
        OVERALL_LENGTH
        + _FACE_LO
        - (GROOVE_STATION + _GROOVE_HI)
        - GROOVE_HALF_OPENING_MAX,
    ),
    "groove root over the thread major": (
        (GROOVE_ROOT_DIA - THREAD_MAJOR) / 2.0,
        (GROOVE_ROOT_DIA + _ROOT_LO) / 2.0 - _THREAD_R_MAX,
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET - 1e-9:
        raise AssertionError(
            f"MHA-MG-006 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under {WALL_TARGET}"
        )


def floor_2(value: float) -> float:
    """A MIN on the sheet never rounds up past the arithmetic."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


# The sheet's bore-to-flat MIN: the authorized 1.97, under the 2.0 target, so
# the one named shortfall.  It may sit below the centred worst wall (the
# difference is the centring it accepts) but never above it, nor under the floor.
BORE_WALL_STATED_MIN = 1.97
BORE_WALL_WORST_PRINTED = floor_2(WALLS[BORE_WALL_NAME][1])
if not WALL_FLOOR <= BORE_WALL_STATED_MIN <= BORE_WALL_WORST_PRINTED:
    raise AssertionError(
        f"MHA-MG-006 stated bore-to-flat wall {BORE_WALL_STATED_MIN} left "
        f"{WALL_FLOOR}..{BORE_WALL_WORST_PRINTED}"
    )
# The farthest the bore axis may stand off the hex axis on a part the stated
# MIN accepts: the widest stock, the smallest bore.
BORE_OFFSET_MAX = (
    (HEX_AF + HEX_STOCK_AF_BAND) / 2.0 - _ROD_BORE_R_MIN - BORE_WALL_STATED_MIN
)

# --- The tap's reach (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)) -----------------------------------------------
# The sheet calls for a plug tap with a 3-5 thread chamfer: the #4-40 plug in
# Morse Cutting Tools' catalogue
# (https://morsecuttingtools.com/catalogue/product/552474, item 30000) is
# that tap, usable length LU 9/16 in on a 0.141 in shank.  The shank is over
# the thread's major, so it stops at the spigot face: LU is all the tap can
# reach.  ICS Cutting Tools "Tap Dimensions"
# (https://www.icscuttingtools.com/pdfs/Tap-Dimensions.pdf) corroborates the
# standard #4 hand tap's 0.141 in shank, and gives the plug chamfer as 3-6
# threads: a 6-thread plug falls short at the worst case below, hence the
# sheet's 3-5.
PLUG_TAP_USABLE_LENGTH = 9.0 / 16.0 * 25.4
PLUG_TAP_SHANK_DIA = 0.141 * 25.4
PLUG_TAP_CHAMFER_THREADS = (3, 5)
THREAD_PITCH = 25.4 / 40.0
# A plug tap's lead to its first full thread: its longest chamfer (five
# threads, as machining-dfm.md's "Blind-thread DFM rule" takes four chamfered
# threads and a pitch of margin).
PLUG_TAP_LEAD = PLUG_TAP_CHAMFER_THREADS[1] * THREAD_PITCH
_FACE_TO_BORE_AXIS_MAX = OVERALL_LENGTH + _FACE_HI - (ROD_STATION + _ROD_STATION_LO)
_FACE_TO_BORE_AXIS_MIN = OVERALL_LENGTH + _FACE_LO - (ROD_STATION + _ROD_STATION_HI)
# The bore's half-chord at the thread's widest reach off the bore axis: the
# major envelope, with the bore off centre by all the stated MIN accepts.
_THREAD_HALF_CHORD = math.sqrt(
    _ROD_BORE_R_MIN**2 - (_THREAD_R_MAX + BORE_OFFSET_MAX) ** 2
)
# The deepest wall the thread crosses (its flanks run past the axis' 10.1
# before the bore takes the whole envelope), and the far wall's nearest point.
TAP_WALL_DEEPEST = _FACE_TO_BORE_AXIS_MAX - _THREAD_HALF_CHORD
TAP_REACH_NEEDED = TAP_WALL_DEEPEST + PLUG_TAP_LEAD
FAR_WALL_NEAREST = _FACE_TO_BORE_AXIS_MIN + _THREAD_HALF_CHORD
if not PLUG_TAP_SHANK_DIA > THREAD_MAJOR:
    raise AssertionError("MHA-MG-006 tap shank enters its own thread")
if TAP_REACH_NEEDED > PLUG_TAP_USABLE_LENGTH + 1e-9:
    raise AssertionError("MHA-MG-006 plug tap cannot cut full thread through the wall")
if not FAR_WALL_NEAREST > PLUG_TAP_USABLE_LENGTH:
    raise AssertionError("MHA-MG-006 plug tap reaches the rod bore's far wall")
# The callout's (REF) thread depth is the nominal wall on the tap's axis: where
# the rod bore ends the thread.
if abs(TAP_LENGTH - (OVERALL_LENGTH - ROD_STATION - ROD_BORE_DIA / 2.0)) > 1e-9:
    raise AssertionError("MHA-MG-006 thread depth is not the wall on the tap's axis")

# The tap drill, at its printed .X depth and drilled-hole Ø: its full Ø clears
# the near wall at the shallowest depth, and its 118 deg point stops short of
# the far wall at the deepest.
_DRILL_DEPTH_LO, _DRILL_DEPTH_HI = printed_deviations(TAP_DRILL_DEPTH, TAP_DEPTH_PLACES)
_DRILL_R_MAX = (TAP_DRILL_DIA + drilled_oversize_mm()) / 2.0
_DRILL_POINT = _DRILL_R_MAX / math.tan(math.radians(59.0))
_DRILL_HALF_CHORD = math.sqrt(
    _ROD_BORE_R_MIN**2 - (_DRILL_R_MAX + BORE_OFFSET_MAX) ** 2
)
if not TAP_DRILL_DEPTH + _DRILL_DEPTH_LO > _FACE_TO_BORE_AXIS_MAX - _DRILL_HALF_CHORD:
    raise AssertionError("MHA-MG-006 tap drill stops in the near wall")
if not (
    TAP_DRILL_DEPTH + _DRILL_DEPTH_HI + _DRILL_POINT
    < _FACE_TO_BORE_AXIS_MIN + _DRILL_HALF_CHORD
):
    raise AssertionError("MHA-MG-006 tap drill point reaches the far wall")

# --- Marked model dimensions and the places the model authors on them ------------
# The turned profile (Top plane) carries the axial stations from the free end
# and the spigot's Ø; the groove profile (Top plane) the groove's station from
# the free end, its root Ø and its radius; the hex sketch (the FreeEnd plane)
# the flats, a stock reference (the bore is centred: no location from a
# flat); the bore sketch (Top plane) its Ø.  The tap is a Hole Wizard
# feature: its native callout prints it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "TurnedProfile": {
        "RodStation": ROD_STATION_PLACES,
        "HexLength": HEX_LENGTH_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
        "SpigotDia": SPIGOT_DIA_PLACES,
    },
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
# Model dimensions with an explicit symmetric band (name -> owning feature).
SYMMETRIC_BANDS: dict[str, tuple[str, float]] = {
    "RodStation": ("TurnedProfile", POSITION_TOLERANCE),
    "HexLength": ("TurnedProfile", POSITION_TOLERANCE),
    "GrooveStation": ("GrooveProfile", POSITION_TOLERANCE),
    "OverallLength": ("TurnedProfile", POSITION_TOLERANCE),
    "SpigotDia": ("TurnedProfile", SIZE_TOLERANCE),
    "GrooveRootDia": ("GrooveProfile", SIZE_TOLERANCE),
    "GrooveRadius": ("GrooveProfile", SIZE_TOLERANCE),
}
if not set(SYMMETRIC_BANDS) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("MHA-MG-006 banded a dimension the sheet does not print")
if not REFERENCE_DIMENSIONS <= set(DRAWING_PRECISION_BY_NAME) - set(SYMMETRIC_BANDS):
    raise AssertionError("MHA-MG-006 reference dimension is unprinted or banded")

# --- Sheet text -------------------------------------------------------------------
# The bore is a fit on the rod: the callout under its Ø says how it is made.
ROD_BORE_CALLOUT = "REAM THRU"
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
STOCK_NOTE = "3/8 HEX BAR, FLATS AS SUPPLIED."
# Pending exception ruling: MHA-MG-006 bore-to-flat wall (#1433).
# The source bore runs through the corners, along Y; its parallel-flat wall
# acceptance is unchanged.  Keep the approved wording on one short row.
BORE_WALL_NOTE = (
    f"ROD BORE THROUGH CORNERS, CENTRED; BORE TO FLAT WALL {BORE_WALL_STATED_MIN:.2f} MIN"
)
BORE_TOOL_NOTE = "HOLD ON FLATS; CENTRE-DRILL ON CORNER BEFORE DRILL/REAM."
# The tap the reach above rests on, and the thread's extent: the rod bore ends
# it; the callout prints the native thread depth, its nominal, as (REF).
TAP_TOOL_NOTE = (
    f"{TAP_SPEC.size.lstrip('#')}: PLUG TAP, "
    f"{PLUG_TAP_CHAMFER_THREADS[0]}-{PLUG_TAP_CHAMFER_THREADS[1]} THREAD CHAMFER."
)
TAP_EXTENT_NOTE = "THREAD ENDS AT ROD BORE."
# The specifically approved corner-start method and the two existing tap
# facts fit drawing-guidelines.md rule 7 (notes: few, flagged, never a method)'s four rows; the tap's two sentences share the last row.
DRAWING_NOTES = "\n".join(
    (STOCK_NOTE, BORE_WALL_NOTE, BORE_TOOL_NOTE, f"{TAP_TOOL_NOTE} {TAP_EXTENT_NOTE}")
)
