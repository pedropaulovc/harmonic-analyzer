r"""Pure-data print contract for MHA-SM-01, the gooseneck weldment.

PURE DATA, no SolidWorks/COM imports.  ``sm_gooseneck_geom`` owns every size
and ``sm_gooseneck_spring_joint`` the end piece's tap, counterbore and wall
budget; this module adds what the print states: the marked model dimensions,
their places and callouts, the end-piece tap's callout rows, and the notes.
``build_sm_gooseneck`` marks and authors them on the part;
``draw_sm_gooseneck`` places exactly ``DRAWING_DIMENSIONS``.

Design (owner rulings 2026-10-27, #1951).  The whole gooseneck is 1/2 in x
0.065 in 4130-N seamless tube (OnlineMetals 7322), its OD and wall printed as
stock, bent R76.2 on the 1/2 in x 3 in CLR die.  The arm ends flush, with no
step, in a solid Ø12.70 end piece silver-brazed on a shank inside the tube
and tapped 1/4-28 UNF-2B blind after the braze for MHA-SM-04; an arm-end
counterbore clears that screw's die run-out.  A 5/8 in x 0.058 in 4130-N
seamless sleeve (OnlineMetals 7324), select-fitted from stock and brazed both
ends, covers the leg from its foot: the post the top frame's Ø17 hub bore
takes.

Every size is a native model dimension: the elevation's leg length, bend
radius, arm straight and sleeve length; section A-A's end piece (head Ø and
length, braze shank Ø and length) and counterbore (Ø, LIMIT depth); the end
view's native blind-tap callout.  The notes state stock, process and intent
only.  The counterbore's wall shortfall (owner minor sm-gooseneck RV-01) is
stated on its Ø as ``C'BORE WALL n.nn MIN`` (drawing-guidelines.md rule 20),
its floor-corner limit on its depth, the shank's braze fit on the shank Ø
(rule 4, the matched fit names its mate and clearance) and the tap's location
limits under its callout.
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as geom
from sm_gooseneck_spring_joint import (
    BRAZE_CLEARANCE_MAX,
    BRAZE_CLEARANCE_MIN,
    COUNTERBORE_AXIS_OFFSET_MAX,
    COUNTERBORE_FLOOR_CORNER_R_MAX,
    COUNTERBORE_WALL_CALLOUT_MIN,
    DRILL_WANDER_MAX,
    THREAD_AXIS_OFFSET_MAX,
)

SCREW_NUMBER = str(_config.parts("sm-gooseneck-spring-screw")["number"])

# Stock designations as the supplier lists them.  The print states them in
# inches; each one is checked against the millimetre geometry it names.
TUBE_STOCK = "1/2 OD X 0.065 WALL 4130-N SEAMLESS"
TUBE_STOCK_SKU = "ONLINEMETALS 7322"
SLEEVE_STOCK = "5/8 OD X 0.058 WALL 4130-N SEAMLESS"
SLEEVE_STOCK_SKU = "ONLINEMETALS 7324"
BEND_DIE = "1/2 X 3 CLR DIE"
for _name, _mm, _inches in (
    ("tube OD", geom.TUBE_DIA, 0.500),
    ("tube wall", geom.WALL_T, 0.065),
    ("sleeve OD", geom.SLEEVE_DIA, 0.625),
    ("sleeve wall", geom.SLEEVE_WALL_T, 0.058),
    ("bend centreline radius", geom.BEND_R, 3.000),
):
    if not math.isclose(_mm, _inches * geom.MM_PER_IN, abs_tol=1e-9):
        raise AssertionError(f"gooseneck {_name} no longer matches its stated stock")
# The sleeve's select-fit window is the end piece's cited braze window
# (sm_gooseneck_spring_joint.BRAZE_CLEARANCE_MIN/MAX), since the sleeve's
# stock bore is not machined (owner ruling 2026-10-27, "select-fit from
# stock, stock wall printed, no hone"); nominal stock over nominal tube sits
# inside it.
if not (
    BRAZE_CLEARANCE_MIN <= geom.SLEEVE_BORE_DIA - geom.TUBE_DIA <= BRAZE_CLEARANCE_MAX
):
    raise AssertionError("gooseneck sleeve stock does not select-fit the tube")

# Callouts the PART authors on its dimensions, below the value (the drawing
# imports and reads them back; a drawing-side SetText can write through to
# the part, #1942).
COUNTERBORE_WALL_CALLOUT = f"C'BORE WALL {COUNTERBORE_WALL_CALLOUT_MIN:.2f} MIN"
COUNTERBORE_FLOOR_CALLOUT = f"FLOOR CORNER R{COUNTERBORE_FLOOR_CORNER_R_MAX:.2f} MAX"
COUNTERBORE_AXIS_CALLOUT = f"ON TAP AXIS WITHIN {COUNTERBORE_AXIS_OFFSET_MAX:.2f}"
PLUG_DIA_CALLOUT = "FLUSH WITH TUBE OD,\nNO STEP"
SHANK_FIT_CALLOUT = (
    "BRAZE FIT TO TUBE BORE,\n"
    f"{BRAZE_CLEARANCE_MIN:.2f}-{BRAZE_CLEARANCE_MAX:.2f} DIAMETRAL CLEARANCE"
)
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "EndPieceProfile": {
        "PlugDia": PLUG_DIA_CALLOUT,
        "PlugShankDia": SHANK_FIT_CALLOUT,
    },
    "CounterboreProfile": {
        "CounterboreDia": f"{COUNTERBORE_AXIS_CALLOUT}\n{COUNTERBORE_WALL_CALLOUT}",
        "CounterboreDepth": COUNTERBORE_FLOOR_CALLOUT,
    },
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}

# The end piece's native blind-tap callout (end view): the title block's
# THREADS row owns the 2B class (drawing-guidelines.md rule 2), the tap's
# two depths print at the places their band is read at
# (sm_gooseneck_spring_joint.TAP_DEPTH_BAND), and its location limits print
# under it.
TAP_CALLOUT_PRECISION = {"hw-threaddepth": 2, "hw-tapdrldepth": 2}
TAP_CALLOUT_BELOW = (
    f"THREAD AXIS TO TUBE AXIS +/-{THREAD_AXIS_OFFSET_MAX:.2f}\n"
    f"DRILL WANDER {DRILL_WANDER_MAX:.2f} MAX"
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  StationReference is a hidden construction sketch on the
# Front plane carrying the elevation's leg length (foot to the bend tangent)
# and arm straight (bend tangent to the end face) on the tube's axes;
# BendPath the bend's centreline radius; SleeveProfile the sleeve length from
# the leg's foot (its top station).  EndPieceProfile and CounterboreProfile
# lie on the arm-axis plane, so section A-A (cut along the arm axis) carries
# them. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StationReference": {"LegLength", "ArmStraight"},
    "BendPath": {"BendRadius"},
    "SleeveProfile": {"SleeveLength"},
    "EndPieceProfile": {"PlugDia", "PlugHeadLength", "PlugShankDia", "PlugShankLength"},
    "CounterboreProfile": {"CounterboreDia", "CounterboreDepth"},
}
# The bent form's overall sizes are near enough at one place (the title
# block's .X band, drawing-guidelines.md rule 3); the arm straight sets the
# spring eye's station and every end-piece size is turned, so they print at
# two.
ONE_PLACE_DIMENSIONS = frozenset({"LegLength", "BendRadius", "SleeveLength"})
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 1 if name in ONE_PLACE_DIMENSIONS else 2 for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DIMENSION_CALLOUTS_BY_NAME) - set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a gooseneck callout names an unmarked dimension")

# Lines kept short so the left-anchored block clears the views; it grows
# DOWNWARD.  Stock, process and intent only: every size is on a feature.
DRAWING_NOTES = "\n".join(
    (
        f"1. TUBE: {TUBE_STOCK},",
        f"   {TUBE_STOCK_SKU}; STOCK OD AND WALL, NOT",
        f"   MACHINED. BEND ON {BEND_DIE}; OVALITY 5%",
        "   MAX; NO FLATS, KINKS OR CRACKS.",
        "2. END PIECE: SOLID. SILVER-BRAZE ON ITS SHANK,",
        "   BAg-7 PER AWS A5.8, FULL FAYING-SURFACE",
        "   PENETRATION; NO OPEN GAP AT THE TUBE END.",
        "   TAP AFTER BRAZE.",
        f"3. SLEEVE: {SLEEVE_STOCK},",
        f"   {SLEEVE_STOCK_SKU}; STOCK WALL (NO HONE).",
        "   SELECT-FIT FROM STOCK TO THE TUBE AT THE",
        "   END-PIECE SHANK'S BRAZE CLEARANCE.",
        "   SILVER-BRAZE BOTH ENDS.",
        f"4. {SCREW_NUMBER} SPRING SCREW: MADE SEPARATELY;",
        "   NOT INCLUDED IN THIS WELDMENT.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
