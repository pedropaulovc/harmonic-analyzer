r"""Pure-data dimensional contract shared by the pen rod build and drawing.

PURE DATA, no SolidWorks/COM imports. ``build_pn_pen_rod`` models this
geometry and applies the bands and places below to its model dimensions;
``draw_pn_pen_rod`` keeps exactly ``DRAWING_DIMENSIONS`` across its per-view
keep maps.

Part frame: the origin is the SHOULDER -- the square bar's bottom face, where
it rests on the v-block top -- on the rod axis. The 5 mm square runs +Y to the
top face (tapped for the adjuster stud); the turned pivot end runs -Y into the
v-block's pivot bore, so the carriage hangs from the shoulder and can be
turned (yawed) on the rod and then locked by the v-block set screw.

Mate references: Top Plane IS the shoulder face (y 0); Front Plane (z 0) and
Right Plane (x 0) both contain the rod axis, and the square's faces sit at
x, z = +/- ROD_SECTION / 2 (square to them). ``Axis1`` is the rod axis (Front
Plane ∩ Right Plane), the part's only reference axis.
"""

from __future__ import annotations

import _config
from _hole_spec import DRILL_POINT_H, HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM

PEN_HANGER_NUMBER = _config.parts("pn-pen-hanger")["number"]
PEN_V_BLOCK_NUMBER = _config.parts("pn-pen-v-block")["number"]

ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
SECTION_BAND = (0.00, -0.05)
# Square length: the shoulder sits on the v-block top and the top face carries
# the jam nut + adjuster stud under the wheel rim. 112 puts the top at the
# engineerguy 4/4 (9:15-10:34) photo ratio -- rod top ~1.6 rod-lengths of
# block-top-to-guide spacing above the lower U guide -- and keeps the square
# engaged in both hanger U guides over the full pen travel
# (pn_pen_carriage_geom asserts the engagement).
SQUARE_LENGTH = 112.0

# Turned pivot end: a slip fit in the v-block's reamed 4 mm pivot bore
# (pn_pen_v_block_spec.PIVOT_BORE_DIA), turned concentric with the square.
PIVOT_DIA = 4.0
PIVOT_BAND = (-0.010, -0.025)  # g6-like running clearance on the 4.000/4.012 bore
PIVOT_LENGTH = 10.5  # shoulder to end: stops 1.0 above the v-block relief roof

# Adjuster stud tap in the top face. #0-80 is the largest thread whose tap
# drill leaves the drawing-guidelines.md rule 17 (walls and webs) 1.5 mm floor
# in the 5 mm square: (5 - 1.524 major) / 2 = 1.74 mm (#2-56 leaves 1.38).
STUD_THREAD = "#0-80"
STUD_TAP_SPEC = HoleSpec(
    "tapped", STUD_THREAD, end="blind", depth_mm=6.0, overrides_mm={"ThreadDepth": 4.5}
)
STUD_TAP_DRILL_DIA = TAP_DRILL_MM[STUD_THREAD]
# The stud threads this far into the tap (rule 18: >= 1.5 D full thread).
STUD_ENGAGEMENT = 4.0

TOTAL_LENGTH = SQUARE_LENGTH + PIVOT_LENGTH

_WALL = (ROD_SECTION + SECTION_BAND[1] - THREAD_MAJOR_MM[STUD_THREAD]) / 2.0
if _WALL < 1.5:  # drawing-guidelines.md rule 17 (walls and webs) floor
    raise AssertionError(f"rod stud tap leaves a {_WALL:.2f} mm wall")
if STUD_ENGAGEMENT < 1.5 * THREAD_MAJOR_MM[STUD_THREAD]:  # rule 18
    raise AssertionError("adjuster stud engagement is under 1.5 D")
if STUD_ENGAGEMENT >= STUD_TAP_SPEC.overrides_mm["ThreadDepth"]:
    raise AssertionError("adjuster stud bottoms in its tap")
if STUD_TAP_SPEC.depth_mm + STUD_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H >= SQUARE_LENGTH:
    raise AssertionError("stud tap runs out of the square")
if PIVOT_DIA >= ROD_SECTION:
    raise AssertionError("pivot end must turn down inside the square (a shoulder)")

# Front view (1:1): the square's width and length, the pivot length. Top view
# (4:1): the square's depth and the stud-tap wizard callout. Bottom view (4:1):
# the pivot diameter, seen end-on inside the square.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Section", "Length"},
    "Rod": {"Depth"},
    "PivotProfile": {"PivotDia"},
    "Pivot": {"PivotLength"},
}
# Places (drawing-guidelines.md rule 3): the banded square and pivot print at
# their bands' places; the overall length and the pivot length (1.0 clear of
# the v-block relief roof) are near-enough sizes.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"Section": 2, "Length": 1},
    "Rod": {"Depth": 2},
    "PivotProfile": {"PivotDia": 3},
    "Pivot": {"PivotLength": 1},
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
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("RodProfile", "Section"): SECTION_BAND,
    ("Rod", "Depth"): SECTION_BAND,
    ("PivotProfile", "PivotDia"): PIVOT_BAND,
}
# Every tight band names its mate on the dimension it governs (rule 4).
DIMENSION_CALLOUTS: dict[str, str] = {
    "Section": f"SLIDING FIT IN PEN HANGER\n{PEN_HANGER_NUMBER} GUIDES",
    "Depth": f"SLIDING FIT IN PEN HANGER\n{PEN_HANGER_NUMBER} GUIDES",
    "PivotDia": f"SLIP FIT IN PEN V-BLOCK\n{PEN_V_BLOCK_NUMBER} PIVOT BORE",
}

DRAWING_NOTES = (
    "SHOULDER: KEEP SHARP AND SQUARE - IT SEATS THE CARRIAGE ON THE V-BLOCK."
)
TOP_VIEW_NOTE = "TOP VIEW SCALE 4:1"
BOTTOM_VIEW_NOTE = "BOTTOM VIEW SCALE 4:1"
