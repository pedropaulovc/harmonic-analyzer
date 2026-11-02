r"""Pure-data print contract for MHA-SM-01, the gooseneck weldment.

PURE DATA, no SolidWorks/COM imports.  ``sm_gooseneck_geom`` owns every size
and ``sm_gooseneck_spring_joint`` the end piece's tap, counterbore and wall
budget; this module adds what the print states: the marked model dimensions,
their places and callouts, the end-piece tap's callout rows, and the notes.
``build_sm_gooseneck`` marks and authors them on the part;
``draw_sm_gooseneck`` places exactly ``DRAWING_DIMENSIONS``.

Design (owner rulings 2026-10-27, #1951).  The whole gooseneck is 1/2 in x
0.065 in 4130-N seamless tube (OnlineMetals 7322), its OD and wall printed as
stock, bent R3.0 on the 1/2 in x 3 in CLR die.  The arm ends flush, with no
step, in a solid Ø.500 end piece silver-brazed on a shank inside the tube
and tapped 1/4-28 UNF-2B blind after the braze for MHA-SM-04; an arm-end
counterbore clears that screw's die run-out.  A 5/8 in x 0.058 in 4130-N
seamless sleeve (OnlineMetals 7324), select-fitted from stock and brazed both
ends, covers the leg from its foot: the post the top frame's Ø17 hub bore
takes.

Every size is a native model dimension: the elevation's leg length, bend
radius, arm straight and sleeve length; section A-A's end piece (head Ø and
length, braze shank Ø and length) and counterbore (LIMIT Ø and depth, floor
corner R.004 MAX); the end view's native blind-tap callout.  The notes state
stock, process and intent only.  The counterbore's wall shortfall (owner
minor sm-gooseneck RV-01) is stated as ``C'BORE WALL .nnn MIN`` under the
head Ø, the wall's outer bound (drawing-guidelines.md rule 20), the shank's
braze fit on the shank Ø (rule 4, the matched fit names its mate and
clearance) and the tap's location limits under its callout.

Decimal-inch sheet (#290): every size prints at the places its band needs
(DRAWING_PRECISION, below); the end piece's calibrated spring-support sizes
keep their millimetre model values (sm_gooseneck_geom) and print on the inch
grid.
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as geom
from _package_units import drawing_unit
from sm_gooseneck_spring_joint import (
    BRAZE_CLEARANCE_MAX,
    BRAZE_CLEARANCE_MIN,
    COUNTERBORE_AXIS_OFFSET_MAX,
    COUNTERBORE_WALL_CALLOUT_MIN,
    COUNTERBORE_WALL_MIN,
    PLUG_WALL_TARGET,
    THREAD_AXIS_OFFSET_MAX,
    owner_minor,
)

# #290: the registry row's drawing_unit (in) is this sheet's unit; the joint
# charges the geometry module's SHEET_UNIT, so the two must agree.
UNIT = drawing_unit("parts/sm-gooseneck", _config.parts("sm-gooseneck"))
if UNIT != geom.SHEET_UNIT:
    raise AssertionError("MHA-SM-01's registry unit is not its geometry's SHEET_UNIT")


def _inch(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: inches at ``places``, no leading
    zero."""
    return f"{value_mm / geom.MM_PER_IN:.{places}f}".removeprefix("0")


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
# R3.0 (76.2 mm) is the 1/2 in x 3 in CLR die's (owner ruling 2026-10-27); the
# print states the radius, not the tool (rule 7, codjiflo on #1997).
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
# the part, #1942).  The counterbore's MIN limits (Ø, depth) and its axis
# clear MHA-SM-04's thread run-out (sm_gooseneck_spring_joint).  Each .004
# band names its mate and each MAX its job on its own callout (rule 4; owner
# ruling via Main on machinist review r7 of farm run 20261101T022045634Z:
# keep both bands, state each max's job; r8, farm run 20261101T035809796Z:
# the Ø's own callout named neither).  The Ø's max holds the wall stated
# under the head Ø ("AT C'BORE MAX"), the depth's max the tap drill's deepest
# point (the tap block).  The Ø's block stands between its own extension
# lines, 21.0 mm apart at 3:1: its stacked LIMIT pair and two rows, which r8
# inked y 190.4-209.6 mm between lines at 189.5 and 210.5.  A single value
# with three rows, ~20.4 mm, was struck by the lower line (machinist review
# of cca02b34c); set below them, its text ran off the sheet's left edge
# (farm run 20261028T072132691Z).  So the Ø's two rows carry its mate and
# max, the axis limit moves to the floor corner's block (room for a third
# row between the Ø's upper dimension line and the depth's shoulder), and
# the wall rides under the head Ø, its outer bound.
SCREW_NUMBER = str(_config.parts("sm-gooseneck-spring-screw")["number"])
COUNTERBORE_WALL_CALLOUT = (
    f"C'BORE WALL {_inch(COUNTERBORE_WALL_CALLOUT_MIN * geom.MM_PER_IN, 3)} MIN"
)
# ~53.6 and ~56.4 mm in Century Gothic; centred on the Ø's line at x 45 mm,
# x ~16.5-73.5 mm: inside the left border (12.7) and short of the c'bore
# mouth (75.0).  "WALL" is the C'BORE WALL row under the head Ø.
COUNTERBORE_DIA_CALLOUT = f"MIN CLEARS {SCREW_NUMBER}\nRUN-OUT; MAX SETS WALL"
# A radial offset between two named axes (machinist review r7: "WITHIN"
# said neither radial nor diametral).
COUNTERBORE_AXIS_CALLOUT = (
    f"C'BORE AXIS TO TAP AXIS\n{_inch(COUNTERBORE_AXIS_OFFSET_MAX, 3)} MAX RADIAL"
)
# The floor corner's native "R.004 MAX" names the corner it limits; its row
# says why, the Ø and depth beside it naming whose run-out.
COUNTERBORE_FLOOR_CALLOUT = f"CLEARS RUN-OUT;\n{COUNTERBORE_AXIS_CALLOUT}"
# No row longer than r8's 23-character axis row (55.5 mm): each block stands
# between the sheet's left border and the end face (farm run
# 20261028T062539287Z: "CLEARS MHA-SM-04 RUN-OUT" crossed the border).
COUNTERBORE_ROW_MAX_CHARS = 23
_COUNTERBORE_ROWS = f"{COUNTERBORE_DIA_CALLOUT}\n{COUNTERBORE_FLOOR_CALLOUT}"
if max(map(len, _COUNTERBORE_ROWS.splitlines())) > COUNTERBORE_ROW_MAX_CHARS:
    raise AssertionError("a counterbore callout row is wider than its axis row")
PLUG_DIA_CALLOUT = (
    f"FLUSH WITH TUBE OD,\nNO STEP\n{COUNTERBORE_WALL_CALLOUT}\nAT C'BORE MAX"
)
# The bend radius is the tube's centreline radius; the arrowhead lands on the
# outer arc, so the value says which (machinist review of e487a1bb4).
BEND_RADIUS_CALLOUT = "CLR"
# Three short rows, so the block ends left of the end view (sheet layout,
# draw_sm_gooseneck).  The window is the joint's, braze or retaining compound
# (owner ruling 2026-10-27 on #1997, sm_gooseneck_spring_joint), so the
# callout names no method; note 3 does.  The window prints in inches,
# rounded inward at four places.
_BRAZE_WINDOW = "-".join(
    f"{inches:.4f}".removeprefix("0")
    for inches in (
        math.ceil(round(BRAZE_CLEARANCE_MIN / geom.MM_PER_IN * 1e4, 6)) / 1e4,
        math.floor(round(BRAZE_CLEARANCE_MAX / geom.MM_PER_IN * 1e4, 6)) / 1e4,
    )
)
SHANK_FIT_CALLOUT = f"FIT TO TUBE BORE,\n{_BRAZE_WINDOW} DIAMETRAL\nCLEARANCE"
# The sleeve's select-fit window rides its own Ø on the elevation (rule 7: a
# matched fit goes on the feature, not in a note; codjiflo P2 on #1997), with
# the stock it is cut from (owner ruling 2026-10-27: select-fit from stock,
# no hone).
SLEEVE_FIT_CALLOUT = f"STOCK; FIT ON TUBE,\n{_BRAZE_WINDOW} DIAMETRAL\nCLEARANCE"
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "BendPath": {"BendRadius": BEND_RADIUS_CALLOUT},
    "SleeveProfile": {"SleeveDia": SLEEVE_FIT_CALLOUT},
    "EndPieceProfile": {
        "PlugDia": PLUG_DIA_CALLOUT,
        "PlugShankDia": SHANK_FIT_CALLOUT,
    },
    "CounterboreProfile": {
        "CounterboreDia": COUNTERBORE_DIA_CALLOUT,
        "CounterboreFloorCornerR": COUNTERBORE_FLOOR_CALLOUT,
    },
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}
# Above the value, one row (SolidWorks prints no line break in the above
# compartment, pn_pen_v_block_spec): the counterbore depth's .004 LIMIT band
# names its MIN's mate at its own callout (rule 4; machinist review of
# 3a807442b; r7: only the MIN does the clearing).  Below its stacked pair it
# would cross the end face's extension lines.  ~74.6 mm wide, centred on the
# value: x ~25.7-100.3 mm, inside the left border (12.7) and short of the tap
# callout's native rows (x 137.7).
COUNTERBORE_DEPTH_CALLOUT = f"MIN CLEARS {SCREW_NUMBER} RUN-OUT"
DIMENSION_CALLOUTS_ABOVE: dict[str, dict[str, str]] = {
    "CounterboreProfile": {"CounterboreDepth": COUNTERBORE_DEPTH_CALLOUT},
}
DIMENSION_CALLOUTS_ABOVE_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS_ABOVE.values()
    for name, text in callouts.items()
}

# The end piece's native blind-tap callout (end view): the title block's
# THREADS row owns the 2B class (drawing-guidelines.md rule 2), the tap's
# two depths print at the places their band is read at
# (sm_gooseneck_spring_joint.TAP_DEPTH_BAND), measured from the counterbore
# floor (the Hole Wizard start face; codjiflo P2 on #1997), and the thread
# axis's location limit prints under it with the mate it serves.  The
# counterbore depth's MAX sets the drill's deepest point
# (sm_gooseneck_spring_joint.TAP_DRILL_DEPTH_MAX, depths from the floor), and
# with it the drill point's wall to the shank: the first row states that job
# in place of the floor datum, which it implies (Main's ruling on r7: drop
# "DEPTHS FROM C'BORE FLOOR" before anything else).  ~105.3 mm, 2 mm wider
# than r7's 103.9 mm row, still clear of the arm straight's text right of it.
# The drill's wander is a budget term, not a print row
# (sm_gooseneck_spring_joint.DRILL_WANDER_MAX).  Four rows in all (the layout
# audit's tall-block limit: a fifth row gated, farm run 20261028T005208028Z).
# Inch sheet: the depths at .XX (their band), the drill Ø at .XXX (#3, .213).
TAP_CALLOUT_PRECISION = {"hw-tapdrldia": 3, "hw-threaddepth": 2, "hw-tapdrldepth": 2}
# The thread axis's limit is a radial offset from the tube's OD axis, worded
# as the counterbore's (r7 review: "+/-" named no zone and no surface).
TAP_CALLOUT_BELOW = (
    f"FOR {SCREW_NUMBER}; DEEPEST DRILL AT C'BORE MAX\n"
    f"THREAD AXIS TO TUBE OD AXIS {_inch(THREAD_AXIS_OFFSET_MAX, 3)} MAX RADIAL"
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  StationReference is a hidden construction sketch on the
# Front plane carrying the elevation's leg length (foot to the bend tangent)
# and arm straight (bend tangent to the end face) on the tube's axes;
# BendPath the bend's centreline radius; SleeveProfile the sleeve length from
# the leg's foot (its top station) and its stock Ø, which carries the
# select-fit window; TubeOdReference a hidden construction sketch on the
# Front plane carrying the tube's stock Ø across the bare leg above the
# sleeve; OverallReference a hidden construction sketch on the Front plane
# whose lines lie on drawn edges, carrying the bent form's overall height
# (foot face to the arm's top) and reach (end face to the leg's outer side).
# EndPieceProfile and CounterboreProfile
# lie on the arm-axis plane, so section A-A (cut along the arm axis) carries
# them. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StationReference": {"LegLength", "ArmStraight"},
    "TubeOdReference": {"TubeOdRef"},
    "OverallReference": {"OverallHeight", "OverallReach"},
    "BendPath": {"BendRadius"},
    "SleeveProfile": {"SleeveLength", "SleeveDia"},
    "EndPieceProfile": {"PlugDia", "PlugHeadLength", "PlugShankDia", "PlugShankLength"},
    "CounterboreProfile": {
        "CounterboreDia",
        "CounterboreDepth",
        "CounterboreFloorCornerR",
    },
}
# The tube and sleeve are as supplied: their stock Ø print as reference,
# untoleranced, and the supplier's catalogue tolerance governs (drawing-
# guidelines.md units; machinist review of main 31cea0b73, owner ruling
# 2026-10-31).  Their walls are hidden on the elevation and cut by no
# section, so they stay as the stock designations in note 1 (rule 9).
# sm_gooseneck_geom proves the sleeve's select fit on the supplier's bands.
# The overall height and reach are references too: the tangent stations
# (16.4, 1.07) lay out the bend and govern; the overall sizes check the
# finished bend from real faces (machinist review r5 of farm run
# 20261101T004958072Z).
REFERENCE_DIMENSIONS: dict[str, frozenset[str]] = {
    "TubeOdReference": frozenset({"TubeOdRef"}),
    "SleeveProfile": frozenset({"SleeveDia"}),
    "OverallReference": frozenset({"OverallHeight", "OverallReach"}),
}
# Where TubeOdReference's line runs on the bare leg: TUBE_OD_REF_SPAN long,
# centred mid-way between the sleeve's top and the bend's entry tangent.
TUBE_OD_REF_Y = round((geom.SLEEVE_TOP + geom.LEG_TOP) / 2.0, 1)
TUBE_OD_REF_SPAN = 20.0
# Inch places (#290).  The leg and sleeve are sawn tube lengths and the bend
# radius the die's: the title block's .X band (drawing-guidelines.md rule 3).
# The two overall references print at two places (the snapped leg puts the
# height at 19.650, a one-place tie).  The stock Ø (REF) print at their
# three-place sizes; the braze shank and the counterbore's LIMIT Ø, depth and
# floor-corner MAX at three, the places their bands need
# (sm_gooseneck_spring_joint); the arm straight (the spring eye's station)
# and the end piece's head Ø and lengths at the title block's .XX.
ONE_PLACE_DIMENSIONS = frozenset({"LegLength", "BendRadius", "SleeveLength"})
THREE_PLACE_DIMENSIONS = frozenset(
    {
        "TubeOdRef",
        "SleeveDia",
        "PlugShankDia",
        "CounterboreDia",
        "CounterboreDepth",
        "CounterboreFloorCornerR",
    }
)


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
if (set(DIMENSION_CALLOUTS_BY_NAME) | set(DIMENSION_CALLOUTS_ABOVE_BY_NAME)) - set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("a gooseneck callout names an unmarked dimension")

# Four lines (drawing-guidelines.md rule 7; codjiflo on #1997): the stock,
# both members as supplied, the supplier's tolerance governing them, and the
# sleeve's braze with its extent (its
# select-fit window rides the sleeve's Ø), the end piece's joint, then the
# order the owner ruled (2026-10-27, #1997: join the end piece before
# bending, cooled or fully cured; recorded as RV-02 in sm-gooseneck.yaml)
# with the bend's acceptance.  The sleeve's braze is a fillet at each end of
# its lap and the end piece's a full-penetration joint (machinist review of
# 3a807442b: "full penetration" read as covering the sleeve's 8.6 lap too).
# Sizes are on the features and the bend radius is native, so no line names
# a tool, and section A-A shows the end piece solid.  Each line ends left of
# the title block.
DRAWING_NOTES = "\n".join(
    (
        f"1. TUBE {TUBE_STOCK_SIZE}, {STOCK_SUPPLIER} {TUBE_STOCK_SKU}; "
        f"SLEEVE {SLEEVE_STOCK_SIZE}, {SLEEVE_STOCK_SKU}",
        "2. BOTH AS SUPPLIED, SUPPLIER TOL.; SLEEVE: CONTINUOUS BRAZE FILLET EACH END.",
        "3. BRAZE BAg-7 (AWS A5.8); END PIECE: FULL-PENETRATION BRAZE OR LOCTITE 638.",
        "4. JOIN END PIECE, COOL OR FULLY CURE, THEN BEND: OVALITY 5% MAX, NO KINKS.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
