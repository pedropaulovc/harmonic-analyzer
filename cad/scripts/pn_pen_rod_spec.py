r"""Pure-data dimensional contract shared by the pen rod build and drawing.

PURE DATA, no SolidWorks/COM imports. ``build_pn_pen_rod`` models this
geometry and applies the bands and places below to its model dimensions;
``draw_pn_pen_rod`` keeps exactly ``DRAWING_DIMENSIONS`` across its per-view
keep maps.

Part frame: the origin is the SHOULDER -- the square bar's bottom face, where
it rests on the v-block top -- on the rod axis. The .197 square runs +Y to the
top face (tapped for the adjuster stud); the turned pivot end runs -Y into the
v-block's pivot bore, so the carriage hangs from the shoulder and can be
turned (yawed) on the rod and then locked by the v-block set screw.

Mate references: Top Plane IS the shoulder face (y 0); Front Plane (z 0) and
Right Plane (x 0) both contain the rod axis, and the square's faces sit at
x, z = +/- ROD_SECTION / 2 (square to them). ``Axis1`` is the rod axis (Front
Plane ∩ Right Plane), the part's only reference axis.
"""

from __future__ import annotations

import math

import _config
from _fit_close_running import SHAFT_G6_3_TO_6_MM
from _hole_spec import DRILL_POINT_H, HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit

# #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths stay
# millimetres, each the exact decimal of its printed inch value, except the
# square's length: a closure kept at 112.0 (with the v-block's height it sets
# the stud eye's height, pn_pen_carriage_geom.STUD_HEAD_TOP_REST_Y), printed
# rounded, 4.41.
UNIT = drawing_unit("parts/pn-pen-rod", _config.parts("pn-pen-rod"))

PEN_HANGER_NUMBER = _config.parts("pn-pen-hanger")["number"]
PEN_V_BLOCK_NUMBER = _config.parts("pn-pen-v-block")["number"]

ROD_SECTION = 5.0038  # .197 square section, machined (DIMENSIONS.md ch24)
SECTION_BAND = (0.0, -0.0508)  # +.000/-.002
# Square length: the shoulder sits on the v-block top and the top face carries
# the jam nut + adjuster stud under the wheel rim. 112 puts the top at the
# engineerguy 4/4 (9:15-10:34) photo ratio -- rod top ~1.6 rod-lengths of
# block-top-to-guide spacing above the lower U guide -- and keeps the square
# engaged in both hanger U guides over the full pen travel
# (pn_pen_carriage_geom asserts the engagement).
SQUARE_LENGTH = 112.0  # closure (module docstring); prints 4.41

# Turned pivot end: a close running fit in the v-block's .126 reamed pivot
# bore (pn_pen_v_block_spec.PIVOT_BORE_DIA, #290 owner ruling: 4 mm -> .126),
# turned concentric with the square.
PIVOT_DIA = 3.2004  # .126
PIVOT_BAND = SHAFT_G6_3_TO_6_MM  # -.0002/-.0005: .0002-.0010 in the reamed bore
PIVOT_LENGTH = 10.414  # .41, shoulder to end: stops clear above the v-block relief roof

# Adjuster stud tap in the top face. #0-80 is the largest thread whose tap
# drill leaves the drawing-guidelines.md rule 17 (walls and webs) .060 floor
# in the .197 square (#2-56 would not).
STUD_THREAD = "#0-80"
STUD_TAP_SPEC = HoleSpec(
    "tapped",
    STUD_THREAD,
    end="blind",
    depth_mm=6.096,  # .24
    overrides_mm={"ThreadDepth": 4.572},  # .18
)
STUD_TAP_DRILL_DIA = TAP_DRILL_MM[STUD_THREAD]
# The tap callout prints both depths at the title block's .XX (the drill's Ø
# stays .XXX, a drilled size under DRILLED HOLES).
STUD_TAP_DEPTH_PLACES = 2
# The stud threads this far into the tap (rule 18: >= 1.5 D full thread):
# the centre of the measured-length setting band (pn_pen_assembly_spec,
# code review C05), which stays short of the thread depth the tap's printed
# callout guarantees.
STUD_ENGAGEMENT = 3.2

TOTAL_LENGTH = SQUARE_LENGTH + PIVOT_LENGTH

_WALL = (ROD_SECTION + SECTION_BAND[1] - THREAD_MAJOR_MM[STUD_THREAD]) / 2.0
# drawing-guidelines.md rule 17 (walls and webs): .0675 to each flat of the
# smallest square, between the .060 floor and the .080 target: RV-01 in
# pn-pen-rod.yaml (owner ruling 2026-10-31: no thread is smaller and the
# V-block fixes the square, and rule 17 forbids tightening its band).
if _WALL < WALL_FLOOR_MM:
    raise AssertionError(f"rod stud tap leaves a {_WALL:.3f} mm wall")
# The sheet states that wall natively on the end view (rule 20), as
# pn_pen_frame_spec states the frame's: a hidden reference line in the
# shoulder plane runs from the thread's major diameter toward a flat, as long
# as the printed minimum, and its dimension prints ".067 MIN" over TAP WALL.
# The minimum rounds DOWN to its places (.0675 would round up to .068, over
# the worst case).
TAP_WALL_MIN_PLACES = 3
TAP_WALL_MIN_MM = round(
    math.floor(_WALL / 25.4 * 10**TAP_WALL_MIN_PLACES) / 10**TAP_WALL_MIN_PLACES * 25.4,
    9,
)
if not WALL_FLOOR_MM <= TAP_WALL_MIN_MM <= _WALL < TAP_WALL_MIN_MM + 0.0254:
    raise AssertionError("the stated tap wall is not the printed worst case")
TAP_WALL_MIN_TOL_TYPE = 5  # swTolType_e.swTolMIN
# A MIN single limit whose upper deviation reaches the wall on the largest
# square.
_WALL_MAX = (ROD_SECTION + SECTION_BAND[0] - THREAD_MAJOR_MM[STUD_THREAD]) / 2.0
TAP_WALL_MIN_BAND = (round(_WALL_MAX - TAP_WALL_MIN_MM, 6), 0.0)
TAP_WALL_CALLOUT = "TAP WALL"
# The reference line starts on the thread's major diameter, on the axis's
# side of the flat it runs toward.
TAP_WALL_START_R = THREAD_MAJOR_MM[STUD_THREAD] / 2.0
if TAP_WALL_START_R + TAP_WALL_MIN_MM >= (ROD_SECTION + SECTION_BAND[1]) / 2.0:
    raise AssertionError("the tap wall reference runs out of the square")
if STUD_ENGAGEMENT < 1.5 * THREAD_MAJOR_MM[STUD_THREAD]:  # rule 18
    raise AssertionError("adjuster stud engagement is under 1.5 D")
if STUD_ENGAGEMENT >= STUD_TAP_SPEC.overrides_mm["ThreadDepth"]:
    raise AssertionError("adjuster stud bottoms in its tap")
if STUD_TAP_SPEC.depth_mm + STUD_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H >= SQUARE_LENGTH:
    raise AssertionError("stud tap runs out of the square")
if PIVOT_DIA >= ROD_SECTION:
    raise AssertionError("pivot end must turn down inside the square (a shoulder)")

# Shoulder root: the square's bottom face seats the carriage on the v-block's
# top face, so the internal corner where the pivot turns down from it carries
# a modelled radius, printed as a single MAX limit (sharp is good, anything up
# to the limit is good). .008 leaves the seat face a land on every flat and
# clears the v-block's broken bore mouth (cross-part assert in
# pn_pen_v_block_spec).
SHOULDER_FILLET_R = 0.2032  # .008
# (upper, lower) deviations: the nominal IS the limit, down to sharp.
SHOULDER_FILLET_BAND = (0.0, -SHOULDER_FILLET_R)
SHOULDER_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.008 MAX"
SHOULDER_FILLET_PLACES = 3
if SHOULDER_FILLET_BAND[0] != 0.0 or SHOULDER_FILLET_BAND[1] != -SHOULDER_FILLET_R:
    raise AssertionError("the shoulder radius band must run from sharp to the nominal")
_FILLET_IN = SHOULDER_FILLET_R / 25.4
if not math.isclose(
    round(_FILLET_IN, SHOULDER_FILLET_PLACES), _FILLET_IN, abs_tol=1e-9
):
    raise AssertionError("the shoulder radius must print exactly at its places")
if PIVOT_DIA / 2.0 + SHOULDER_FILLET_R >= (ROD_SECTION + SECTION_BAND[1]) / 2.0:
    raise AssertionError("shoulder fillet must end inside the square's seat face")

# The overall length, end face to end face, is a reference only (rule 10):
# the square and pivot lengths own it. Printed at two places, in parentheses;
# it carries the square's closure length, so it prints rounded, (4.82).
DRAWING_REFERENCE_PRECISION = 2

# Side view (2:1, rod axis horizontal as in the lathe): the square's length,
# the pivot's length and banded diameter, and the shoulder root's MAX radius.
# End view (5:1) of the tapped top face: the square's banded depth, which the
# SQ in its callout makes the size of both flats (Section and Depth are one
# "RodSection" global, so the model holds the square), the stud-tap wizard
# callout, and RV-01's tap wall (TapWallMin on the hidden TapWallReference).
# Section keeps its model band but is not printed: one SQ size defines a
# square (fr_rocker_arm_support's WinWidth "SQ POCKET").
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Length"},
    "Rod": {"Depth"},
    "PivotProfile": {"PivotDia"},
    "Pivot": {"PivotLength"},
    "ShoulderFillet": {"ShoulderRadius"},
    "TapWallReference": {"TapWallMin"},
}
# Places (drawing-guidelines.md rule 3): the banded square and pivot print at
# their bands' places (.XXX, .XXXX); the square's length (the guide
# engagement) and the pivot's length (clear of the v-block relief roof) print
# the title block's .XX; the shoulder radius prints its MAX limit at three,
# the tap wall its MIN limit at three.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"Length": 2},
    "Rod": {"Depth": 3},
    "PivotProfile": {"PivotDia": 4},
    "Pivot": {"PivotLength": 2},
    "ShoulderFillet": {"ShoulderRadius": SHOULDER_FILLET_PLACES},
    "TapWallReference": {"TapWallMin": TAP_WALL_MIN_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked pen-rod dimension needs authored places")
# (feature, dimension) -> (upper, lower) native band.  Section (the width)
# keeps its band on the model; the sheet states it through Depth's SQ.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("RodProfile", "Section"): SECTION_BAND,
    ("Rod", "Depth"): SECTION_BAND,
    ("PivotProfile", "PivotDia"): PIVOT_BAND,
}
if DRAWING_BANDS[("RodProfile", "Section")] != DRAWING_BANDS[("Rod", "Depth")]:
    raise AssertionError("one SQ size can only state a square whose flats share a band")
# Every tight band names its mate on the dimension it governs (rule 4); the
# shoulder radius names the part its seat face lands on, the tap wall what
# it is.
DIMENSION_CALLOUTS: dict[str, str] = {
    "Depth": f"SQ, SLIDING FIT IN PEN\nHANGER {PEN_HANGER_NUMBER} GUIDES",
    "PivotDia": f"SLIP FIT IN PEN V-BLOCK\n{PEN_V_BLOCK_NUMBER} PIVOT BORE",
    "ShoulderRadius": f"SEATS ON PEN V-BLOCK\n{PEN_V_BLOCK_NUMBER}",
    "TapWallMin": TAP_WALL_CALLOUT,
}

# The 5:1 end view stands off projection (under the side view, rescaled), so
# its label names the end it looks at: "*Top" looks down the rod axis onto
# the tapped top face (machinist review 2026-10-23: unnamed, the tap's end
# read only from the missing Ø4 circle and the isometric).
END_VIEW_NOTE = "VIEW FROM SQUARE END SCALE 5:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
