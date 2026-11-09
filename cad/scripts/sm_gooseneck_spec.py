r"""Pure-data print contract for MHA-SM-01, the gooseneck tube.

PURE DATA, no SolidWorks/COM imports.  ``sm_gooseneck_geom`` owns every size;
this module adds what the print states: the marked model dimensions, their
places and callouts, and the notes.  ``build_sm_gooseneck`` marks and authors
them on the part; ``draw_sm_gooseneck`` places exactly ``DRAWING_DIMENSIONS``.

Design (owner rulings 2026-10-27, #1951; 2026-11-08 (Pedro), #2315).
MHA-SM-01 is 1/2 in x 0.065 in 4130-N seamless tube (OnlineMetals 7322), its
OD and wall printed as stock, bent R3.0 on the 1/2 in x 3 in CLR die, then
its arm end sawn and faced to length.  It is polished bare, oiled or waxed
(the registry row's finish, in the title block).  The end plug bonded into
the arm end is its own part and sheet (MHA-SM-05), and the leg carries no
sleeve: the bare leg is the post MHA-FR-02's hub takes.

Every size is a native model dimension on the elevation: the leg length (foot
to the bend's entry tangent), the bend's centreline radius, the overall reach
from the faced arm end to the leg's outer side, and as references the tube's
stock Ø, the arm straight (the bend's exit tangent to the faced end) and the
overall height.  The one note is the bend's acceptance.

Decimal-inch sheet (#290): every size prints at the places its band needs
(DRAWING_PRECISION, below); the arm end's station follows the calibrated
spring-support geometry (sm_gooseneck_geom) and prints on the inch grid.
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as geom
from _package_units import drawing_unit

# #290: the registry row's drawing_unit (in) is this sheet's unit, and the
# geometry module's SHEET_UNIT, so the two must agree.
UNIT = drawing_unit("parts/sm-gooseneck", _config.parts("sm-gooseneck"))
if UNIT != geom.SHEET_UNIT:
    raise AssertionError("MHA-SM-01's registry unit is not its geometry's SHEET_UNIT")


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: inches at ``places``, no leading
    zero."""
    return f"{value_mm / geom.MM_PER_IN:.{places}f}".removeprefix("0")


# The stock the print names (OnlineMetals 7322 tube; the registry's material
# specification): its OD and wall in inches, each checked against the
# millimetre geometry it names.
for _name, _mm, _inches in (
    ("tube OD", geom.TUBE_DIA, 0.500),
    ("tube wall", geom.WALL_T, 0.065),
):
    if not math.isclose(_mm, _inches * geom.MM_PER_IN, abs_tol=1e-9):
        raise AssertionError(f"gooseneck {_name} no longer matches its stated stock")
# R3.0 (76.2 mm) is the 1/2 in x 3 in CLR die's (owner ruling 2026-10-27); the
# print states the radius, not the tool (rule 7, codjiflo on #1997).
if not math.isclose(geom.BEND_R, 3.000 * geom.MM_PER_IN, abs_tol=1e-9):
    raise AssertionError("gooseneck bend radius is no longer the 3 in CLR die's")

# Callouts the PART authors on its dimensions, below the value (the drawing
# imports and reads them back; a drawing-side SetText can write through to
# the part, #1942).  A callout carries at most two lines of words (rule 7).
# The bend radius is the tube's centreline radius; the arrowhead lands on the
# outer arc, so the value says which in plain words (machinist review of
# e487a1bb4; "CLR" read as clearance, novice-rubric screen).  One short row
# keeps the block clear of the bend's inner edge (farm run
# 20261107T102825912Z).
BEND_RADIUS_CALLOUT = "TUBE CENTERLINE"
# The tube is cut from stock as supplied: its reference Ø names its stock
# wall (hidden on the elevation, cut by no section, rule 9).
TUBE_OD_CALLOUT = f"{_inch(geom.WALL_T, 3)} WALL STOCK"
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "BendPath": {"BendRadius": BEND_RADIUS_CALLOUT},
    "TubeOdReference": {"TubeOdRef": TUBE_OD_CALLOUT},
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  StationReference is a hidden construction sketch on the
# Front plane carrying the elevation's leg length (foot to the bend's entry
# tangent) and arm straight (the bend's exit tangent to the faced arm end) on
# the tube's axes; BendPath the bend's centreline radius; TubeOdReference a
# hidden construction sketch on the Front plane carrying the tube's stock Ø
# across the leg; OverallReference a hidden construction sketch on the Front
# plane whose lines lie on drawn edges, carrying the bent form's overall
# height (foot face to the arm's top) and reach (faced arm end to the leg's
# outer side). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StationReference": {"LegLength", "ArmStraight"},
    "TubeOdReference": {"TubeOdRef"},
    "OverallReference": {"OverallHeight", "OverallReach"},
    "BendPath": {"BendRadius"},
}
# The tube is as supplied: its stock Ø prints as reference, untoleranced, and
# the supplier's catalogue tolerance governs (drawing-guidelines.md units;
# machinist review of main 31cea0b73, owner ruling 2026-10-31).  Its wall is
# hidden on the elevation and cut by no section, so the reference Ø's callout
# states the stock wall (rule 9).
# The leg length lays out the bend on the straight stock and governs; the
# overall height checks the finished bend from real faces (machinist review
# r5 of farm run 20261101T004958072Z).  The arm end is sawn and faced AFTER
# the bend (owner rulings 2026-11-08 (Pedro), #2315), so its governing size
# is the overall reach, from the faced end to the leg's outer side, both real
# faces; the arm straight to the bend's exit tangent, a point no one can
# touch on the finished bend, is its reference (rule 10).
REFERENCE_DIMENSIONS: dict[str, frozenset[str]] = {
    "TubeOdReference": frozenset({"TubeOdRef"}),
    "StationReference": frozenset({"ArmStraight"}),
    "OverallReference": frozenset({"OverallHeight"}),
}
# Where TubeOdReference's line runs on the leg: TUBE_OD_REF_SPAN long, centred
# a quarter of the leg below the bend's entry tangent, level with the leg
# length's text and well above the overall height's at the view's mid-height.
TUBE_OD_REF_Y = round(geom.LEG_TOP - geom.LEG_LENGTH / 4.0, 1)
TUBE_OD_REF_SPAN = 20.0
# Inch places (#290).  The leg is a sawn tube length and the bend radius the
# die's: the title block's .X band (drawing-guidelines.md rule 3).  The
# overall reach sets the faced arm end, the spring eye's station less the end
# plug's head: .XX.  The overall height prints at two places (the snapped leg
# puts it at 19.650, a one-place tie), as does the arm straight.  The stock Ø
# (REF) prints at its three-place size.
ONE_PLACE_DIMENSIONS = frozenset({"LegLength", "BendRadius"})
THREE_PLACE_DIMENSIONS = frozenset({"TubeOdRef"})


def places(name: str) -> int:
    if name in ONE_PLACE_DIMENSIONS:
        return 1
    return 3 if name in THREE_PLACE_DIMENSIONS else 2


DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: places(name) for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DIMENSION_CALLOUTS_BY_NAME) - set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a gooseneck callout names an unmarked dimension")

# One line (drawing-guidelines.md rule 7): the bent form's acceptance.  The
# sizes are on the features and the bend radius is native, so it names no
# tool; the bend order (owner rulings 2026-11-08 (Pedro), #2315: bend with a
# tail, then saw and face the arm end) is method, stated by the geometry: the
# arm end's governing size runs from the finished bend's real faces.
DRAWING_NOTES = "1. BEND: OVALITY 5% MAX, NO KINKS"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
