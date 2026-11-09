r"""Pure-data print contract for MHA-SM-01, the gooseneck weldment.

PURE DATA, no SolidWorks/COM imports.  ``sm_gooseneck_geom`` owns every size
and ``sm_gooseneck_spring_joint`` the end piece's tap and wall budget; this
module adds what the print states: the marked model dimensions, their places
and callouts, the end-piece tap's callout rows, and the notes.
``build_sm_gooseneck`` marks and authors them on the part;
``draw_sm_gooseneck`` places exactly ``DRAWING_DIMENSIONS``.

Design (owner rulings 2026-10-27, #1951).  The whole gooseneck is 1/2 in x
0.065 in 4130-N seamless tube (OnlineMetals 7322), its OD and wall printed as
stock, bent R3.0 on the 1/2 in x 3 in CLR die.  The arm ends flush, with no
step, in a solid Ø.500 end piece silver-brazed on a shank inside the tube.  A
5/8 in x 0.058 in 4130-N seamless sleeve (OnlineMetals 7324), select-fitted
from stock and brazed both ends, covers the leg from its foot: the post the
top frame's Ø17 hub bore takes.  Owner ruling 2026-11-08 (Pedro), #2144 item
11.4: the end piece takes a plain #10-24 UNC blind tap for the purchased
MHA-SM-VN-56 shoulder screw, with no counterbore, position frames or datums;
its axis carries the title block's implied-zero coaxial offset.

Every size is a native model dimension: the elevation's leg length, bend
radius, arm straight and sleeve length; section A-A's end piece (head Ø and
length, braze shank Ø and length); the end view's native blind-tap callout,
which names the screw and states its full-thread engagement (rule 20, owner
minor sm-gooseneck RV-04).  The notes state stock, process and intent only.
The shank's braze fit sits on the shank Ø (rule 4, the matched fit names its
mate and clearance).

Decimal-inch sheet (#290): every size prints at the places its band needs
(DRAWING_PRECISION, below); the end piece's calibrated spring-support sizes
keep their millimetre model values (sm_gooseneck_geom) and print on the inch
grid.
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as geom
import sm_vn_gooseneck_shoulder_screw_spec as screw
from _package_units import drawing_unit
from sm_gooseneck_spring_joint import (
    BRAZE_CLEARANCE_MAX,
    BRAZE_CLEARANCE_MIN,
    ENGAGEMENT_CALLOUT_D,
    ENGAGEMENT_CALLOUT_MIN,
    ENGAGEMENT_MIN,
    ENGAGEMENT_MIN_D,
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


# The shoulder screw's engagement under rule 18's 1.5D stands only on owner
# minor RV-04 (sm_gooseneck_spring_joint.owner_minor).
if ENGAGEMENT_MIN < ENGAGEMENT_MIN_D * screw.MAJOR_DIA:
    owner_minor(_config.parts("sm-gooseneck"), "RV-04", "sm_gooseneck")

# The stock the print names (OnlineMetals 7322 tube, 7324 sleeve; the
# registry's material specification): its OD and wall in inches, each
# checked against the millimetre geometry it names.
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
# The sleeve's joint is BAg-7 alone (note 2), so its select-fit window is the
# filler maker's flux-brazed window, .002-.005 in per side, .004-.010
# diametral (Lucas-Milhaupt, as cited in sm_gooseneck_spring_joint); the end
# piece's narrower window also admits LOCTITE 638.  The sleeve's stock bore
# is not machined (owner ruling 2026-10-27, "select-fit from stock, stock
# wall printed, no hone"); nominal stock over nominal tube sits inside it.
SLEEVE_CLEARANCE_MIN = BRAZE_CLEARANCE_MIN  # .004 in
SLEEVE_CLEARANCE_MAX = 0.254  # .010 in
if not (
    SLEEVE_CLEARANCE_MIN <= geom.SLEEVE_BORE_DIA - geom.TUBE_DIA <= SLEEVE_CLEARANCE_MAX
):
    raise AssertionError("gooseneck sleeve stock does not select-fit the tube")

# Callouts the PART authors on its dimensions, below the value (the drawing
# imports and reads them back; a drawing-side SetText can write through to
# the part, #1942).  Novice rubric (fan-out of #2223): a callout carries at
# most two lines of words, a feature with several tight dimensions names its
# mate once on one numbered flag note linked to each of them (rule 4), and a
# fit is named with its clearance as REF.  The braze shank and the sleeve
# each link their own fit note.
SCREW_NUMBER = str(_config.parts("sm-vn-gooseneck-shoulder-screw")["number"])
SHANK_FIT_NOTE = 1
SLEEVE_FIT_NOTE = 2
# The head Ø ends flush with the tube's OD.
PLUG_DIA_CALLOUT = "FLUSH WITH TUBE OD"
# The bend radius is the tube's centreline radius; the arrowhead lands on the
# outer arc, so the value says which in plain words (machinist review of
# e487a1bb4; "CLR" read as clearance, novice-rubric screen).  One short row
# keeps the block clear of the bend's inner edge (farm run
# 20261107T102825912Z).
BEND_RADIUS_CALLOUT = "TUBE CENTERLINE"
# Each window is printed in inches rounded inward at three places, plain
# inch steps (machinist review of fanout/integration 8fb7fb46f7: the shank
# joint's .0040-.0098 read as converted millimetres).  The shank's is the
# joint's, braze or retaining compound (owner ruling 2026-10-27 on #1997,
# sm_gooseneck_spring_joint), .004-.009; the sleeve's is BAg-7's, .004-.010.
# Each is the acceptance of a matched fit (fan-out policy 1; machinist review
# 20261107T102825912Z: as REF beside a .XXX shank it set no limit): the
# shank is turned to the measured tube ID (its Ø a reference,
# REFERENCE_DIMENSIONS; round 2: "TO SUIT" is a rule-26 private phrase), and
# the sleeve's stock is selected on the tube (owner ruling 2026-10-27:
# select-fit from stock, no hone).
def _clearance_window(low_mm: float, high_mm: float) -> str:
    return "-".join(
        f"{inches:.3f}".removeprefix("0")
        for inches in (
            math.ceil(round(low_mm / geom.MM_PER_IN * 1e3, 6)) / 1e3,
            math.floor(round(high_mm / geom.MM_PER_IN * 1e3, 6)) / 1e3,
        )
    )


SHANK_CLEARANCE_WINDOW = _clearance_window(BRAZE_CLEARANCE_MIN, BRAZE_CLEARANCE_MAX)
SLEEVE_CLEARANCE_WINDOW = _clearance_window(SLEEVE_CLEARANCE_MIN, SLEEVE_CLEARANCE_MAX)
SHANK_FIT_CALLOUT = f"SEE NOTE {SHANK_FIT_NOTE}"
# The tube and the sleeve are cut from stock as supplied: each reference Ø
# names its stock wall (hidden on the elevation, cut by no section, rule 9),
# and the sleeve links its fit on the tube (owner ruling 2026-10-27:
# select-fit from stock, no hone).
TUBE_OD_CALLOUT = f"{_inch(geom.WALL_T, 3)} WALL STOCK"
SLEEVE_FIT_CALLOUT = (
    f"{_inch(geom.SLEEVE_WALL_T, 3)} WALL STOCK\nSEE NOTE {SLEEVE_FIT_NOTE}"
)
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "BendPath": {"BendRadius": BEND_RADIUS_CALLOUT},
    "TubeOdReference": {"TubeOdRef": TUBE_OD_CALLOUT},
    "SleeveProfile": {"SleeveDia": SLEEVE_FIT_CALLOUT},
    "EndPieceProfile": {
        "PlugDia": PLUG_DIA_CALLOUT,
        "PlugShankDia": SHANK_FIT_CALLOUT,
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
# (sm_gooseneck_spring_joint.TAP_DEPTH_BAND), from the end face, the Hole
# Wizard start face.  The drill's wander is a budget term, not a print row
# (sm_gooseneck_spring_joint.DRILL_WANDER_MAX).  Under the native rows: the
# screw it takes and, as a plain manufacturing fact (rule 20), its full-thread
# engagement under 1.5D (owner minor RV-04), floored to .001 and .01D.  Four
# rows in all (the layout audit's tall-block limit).  Inch sheet: the depths
# at .XX (their band), the drill Ø at .XXX (#7, .201).
TAP_CALLOUT_PRECISION = {"hw-tapdrldia": 3, "hw-threaddepth": 2, "hw-tapdrldepth": 2}
ENGAGEMENT_STATEMENT = (
    f"ENGAGEMENT {f'{ENGAGEMENT_CALLOUT_MIN:.3f}'.removeprefix('0')} MIN "
    f"({ENGAGEMENT_CALLOUT_D:.2f}D)"
)
TAP_CALLOUT_BELOW = f"FOR {SCREW_NUMBER}\n{ENGAGEMENT_STATEMENT}"

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
# EndPieceProfile lies on the arm-axis plane, so section A-A (cut along the
# arm axis) carries it. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StationReference": {"LegLength", "ArmStraight"},
    "TubeOdReference": {"TubeOdRef"},
    "OverallReference": {"OverallHeight", "OverallReach"},
    "BendPath": {"BendRadius"},
    "SleeveProfile": {"SleeveLength", "SleeveDia"},
    "EndPieceProfile": {"PlugDia", "PlugHeadLength", "PlugShankDia", "PlugShankLength"},
}
# The tube and sleeve are as supplied: their stock Ø print as reference,
# untoleranced, and the supplier's catalogue tolerance governs (drawing-
# guidelines.md units; machinist review of main 31cea0b73, owner ruling
# 2026-10-31).  Their walls are hidden on the elevation and cut by no
# section, so each reference Ø's callout states its stock wall (rule 9).
# sm_gooseneck_geom proves the sleeve's select fit on the supplier's bands.
# The overall height and reach are references too: the tangent stations
# (16.4, 1.07) lay out the bend and govern; the overall sizes check the
# finished bend from real faces (machinist review r5 of farm run
# 20261101T004958072Z).  The braze shank's Ø is turned to the measured tube
# ID (note 1), so its nominal is a reference and the clearance governs
# (round 2, 20261107T110808280Z: a plain .363 beside the fit note was a
# second controlling value, rule 7).
REFERENCE_DIMENSIONS: dict[str, frozenset[str]] = {
    "TubeOdReference": frozenset({"TubeOdRef"}),
    "SleeveProfile": frozenset({"SleeveDia"}),
    "OverallReference": frozenset({"OverallHeight", "OverallReach"}),
    "EndPieceProfile": frozenset({"PlugShankDia"}),
}
# Where TubeOdReference's line runs on the bare leg: TUBE_OD_REF_SPAN long,
# centred mid-way between the sleeve's top and the bend's entry tangent.
TUBE_OD_REF_Y = round((geom.SLEEVE_TOP + geom.LEG_TOP) / 2.0, 1)
TUBE_OD_REF_SPAN = 20.0
# Inch places (#290).  The leg and sleeve are sawn tube lengths and the bend
# radius the die's: the title block's .X band (drawing-guidelines.md rule 3).
# The two overall references print at two places (the snapped leg puts the
# height at 19.650, a one-place tie).  The stock Ø (REF) print at their
# three-place sizes; the braze shank at three, the places its band needs
# (sm_gooseneck_spring_joint); the arm straight (the spring eye's station)
# and the end piece's head Ø and lengths at the title block's .XX.
ONE_PLACE_DIMENSIONS = frozenset({"LegLength", "BendRadius", "SleeveLength"})
THREE_PLACE_DIMENSIONS = frozenset({"TubeOdRef", "SleeveDia", "PlugShankDia"})


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

# Three lines (drawing-guidelines.md rule 7), each linked from its features
# by SEE NOTE n except the last: the shank's matched fit in the tube and the
# sleeve's on it (the joint's window, braze or retaining compound, owner
# ruling 2026-10-27 on #1997; the sleeve's lower end flush with the tube's,
# LEG_BOTTOM in sm_gooseneck_geom, which no view shows inside the sleeve),
# then the order the owner ruled (2026-10-27, #1997: join the end piece
# before bending, cooled or fully cured; recorded as RV-02 in
# sm-gooseneck.yaml) with the bend's acceptance.  Sizes are on the features
# and the bend radius is native, so no line names a tool.  Each line ends
# left of the title block.
DRAWING_NOTES = "\n".join(
    (
        f"{SHANK_FIT_NOTE}. TURN TO MEASURED TUBE ID, CLEARANCE "
        f"{SHANK_CLEARANCE_WINDOW}; BAg-7 FULL LAP OR LOCTITE 638",
        f"{SLEEVE_FIT_NOTE}. SELECT-FIT ON TUBE, CLEARANCE {SLEEVE_CLEARANCE_WINDOW}; "
        "LOWER ENDS FLUSH; BAg-7 FILLETS",
        "3. JOIN END PIECE, COOL OR FULLY CURE, THEN BEND: OVALITY 5% MAX, NO KINKS",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
