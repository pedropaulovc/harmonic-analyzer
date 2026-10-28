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
length, braze shank Ø and length) and counterbore (Ø, LIMIT depth, floor
corner R0.10 MAX); the end view's native blind-tap callout.  The notes state
stock, process and intent only.  The counterbore's wall shortfall (owner
minor sm-gooseneck RV-01) is stated on its Ø as ``C'BORE WALL n.nn MIN``
(drawing-guidelines.md rule 20), the shank's braze fit on the shank Ø (rule
4, the matched fit names its mate and clearance) and the tap's location
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
    COUNTERBORE_WALL_CALLOUT_MIN,
    COUNTERBORE_WALL_MIN,
    DRILL_WANDER_MAX,
    PLUG_WALL_TARGET,
    THREAD_AXIS_OFFSET_MAX,
    owner_minor,
)

# The counterbore wall under the rule 17 target stands only on owner minor
# RV-01 (sm_gooseneck_spring_joint.owner_minor).
if COUNTERBORE_WALL_MIN < PLUG_WALL_TARGET:
    owner_minor(_config.parts("sm-gooseneck"), "RV-01", "sm_gooseneck")

# Stock designations as the supplier lists them.  The print states them in
# inches; each one is checked against the millimetre geometry it names.
STOCK_SUPPLIER = "ONLINEMETALS"
TUBE_STOCK_SIZE = "1/2 OD X 0.065 WALL"
TUBE_STOCK_SKU = "7322"
SLEEVE_STOCK_SIZE = "5/8 OD X 0.058 WALL"
SLEEVE_STOCK_SKU = "7324"
for _name, _mm, _inches in (
    ("tube OD", geom.TUBE_DIA, 0.500),
    ("tube wall", geom.WALL_T, 0.065),
    ("sleeve OD", geom.SLEEVE_DIA, 0.625),
    ("sleeve wall", geom.SLEEVE_WALL_T, 0.058),
):
    if not math.isclose(_mm, _inches * geom.MM_PER_IN, abs_tol=1e-9):
        raise AssertionError(f"gooseneck {_name} no longer matches its stated stock")
# R76.2 is the 1/2 in x 3 in CLR die's (owner ruling 2026-10-27); the print
# states the radius, not the tool (rule 7, codjiflo on #1997).
if not math.isclose(geom.BEND_R, 3.000 * geom.MM_PER_IN, abs_tol=1e-9):
    raise AssertionError("gooseneck bend radius is no longer the 3 in CLR die's")
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
# the part, #1942).  The counterbore's tight limits (depth band, axis, floor
# corner) all serve one function, clearing MHA-SM-04's thread run-out
# (sm_gooseneck_spring_joint), so its Ø names the mate (rule 4; machinist
# review of e487a1bb4).
SCREW_NUMBER = str(_config.parts("sm-gooseneck-spring-screw")["number"])
COUNTERBORE_WALL_CALLOUT = f"C'BORE WALL {COUNTERBORE_WALL_CALLOUT_MIN:.2f} MIN"
COUNTERBORE_MATE_CALLOUT = f"CLEARS {SCREW_NUMBER} RUN-OUT"
# The floor corner's own native "R0.10 MAX" names the corner it limits.
COUNTERBORE_FLOOR_CALLOUT = "FLOOR CORNER"
COUNTERBORE_AXIS_CALLOUT = f"ON TAP AXIS WITHIN {COUNTERBORE_AXIS_OFFSET_MAX:.2f}"
PLUG_DIA_CALLOUT = "FLUSH WITH TUBE OD,\nNO STEP"
# The bend radius is the tube's centreline radius; the arrowhead lands on the
# outer arc, so the value says which (machinist review of e487a1bb4).
BEND_RADIUS_CALLOUT = "CLR"
# Three short rows, so the block ends left of the end view (sheet layout,
# draw_sm_gooseneck).  The window is the joint's, braze or retaining compound
# (owner ruling 2026-10-27 on #1997, sm_gooseneck_spring_joint), so the
# callout names no method; note 3 does.
SHANK_FIT_CALLOUT = (
    "FIT TO TUBE BORE,\n"
    f"{BRAZE_CLEARANCE_MIN:.2f}-{BRAZE_CLEARANCE_MAX:.2f} DIAMETRAL\n"
    "CLEARANCE"
)
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "BendPath": {"BendRadius": BEND_RADIUS_CALLOUT},
    "EndPieceProfile": {
        "PlugDia": PLUG_DIA_CALLOUT,
        "PlugShankDia": SHANK_FIT_CALLOUT,
    },
    "CounterboreProfile": {
        "CounterboreDia": (
            f"{COUNTERBORE_MATE_CALLOUT}\n{COUNTERBORE_AXIS_CALLOUT}\n"
            f"{COUNTERBORE_WALL_CALLOUT}"
        ),
        "CounterboreFloorCornerR": COUNTERBORE_FLOOR_CALLOUT,
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
# (sm_gooseneck_spring_joint.TAP_DEPTH_BAND), measured from the counterbore
# floor (the Hole Wizard start face; codjiflo P2 on #1997 asked the datum be
# stated), and its location limits print under it as finished geometry,
# with the mate they serve: the thread axis, and the tap drill's point, which
# the wall budgets take off that axis by DRILL_WANDER_MAX
# (DRILL_POINT_SHANK_WALL_MIN).  "DRILL WANDER" and "TAP AFTER BRAZE" read as
# method (machinist review of e487a1bb4).  Four rows in all (the layout
# audit's tall-block limit: a fifth row gated, farm run 20261028T005208028Z).
TAP_CALLOUT_PRECISION = {"hw-threaddepth": 2, "hw-tapdrldepth": 2}
DRILL_POINT_OFFSET_MAX = round(THREAD_AXIS_OFFSET_MAX + DRILL_WANDER_MAX, 6)
TAP_CALLOUT_BELOW = (
    f"FOR {SCREW_NUMBER}; DEPTHS FROM C'BORE FLOOR\n"
    f"AXIS TO TUBE AXIS +/-{THREAD_AXIS_OFFSET_MAX:.2f}, "
    f"DRILL POINT +/-{DRILL_POINT_OFFSET_MAX:.2f}"
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
    "CounterboreProfile": {
        "CounterboreDia",
        "CounterboreDepth",
        "CounterboreFloorCornerR",
    },
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

# Four lines (drawing-guidelines.md rule 7; codjiflo on #1997): the stock,
# the sleeve's select-fit acceptance on the tube (its bore is stock, so no
# feature carries it) and its braze, the joints, then the order the owner
# ruled (2026-10-27, #1997: join the end piece before bending, cooled or
# fully cured) with the bend's acceptance.  Sizes are on the features and the
# bend radius is native, so no line names a tool; the tap's sequence rides
# its callout (rule 7, flag it where it applies), and section A-A shows the
# end piece solid.  Each line ends left of the title block.
DRAWING_NOTES = "\n".join(
    (
        f"1. TUBE {TUBE_STOCK_SIZE}, {STOCK_SUPPLIER} {TUBE_STOCK_SKU}; "
        f"SLEEVE {SLEEVE_STOCK_SIZE}, {SLEEVE_STOCK_SKU}",
        f"2. AS STOCK. SLEEVE {BRAZE_CLEARANCE_MIN:.2f}-{BRAZE_CLEARANCE_MAX:.2f} "
        "DIAMETRAL ON TUBE, SILVER-BRAZED BOTH ENDS.",
        "3. BRAZE BAg-7 (AWS A5.8), FULL PENETRATION; END PIECE: BRAZE OR LOCTITE 638.",
        "4. JOIN END PIECE, COOL OR FULLY CURE, THEN BEND: OVALITY 5% MAX, NO KINKS.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
