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

import math

import _config
from _hole_spec import DRILL_POINT_H, HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

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

# Adjuster stud tap in the top face, on the rod axis. #0-80 is the largest
# thread whose major leaves the drawing-guidelines.md rule 17 (walls and webs)
# 1.5 mm floor in the 5 mm square (#2-56 leaves 1.38 even centred). Located
# from two adjacent flats at the .XXX band, it leaves 1.55 at the worst case
# (STUD_TAP_WALL_MIN below): under rule 17's 2.0 target, a shortfall the
# owner accepted.
STUD_THREAD = "#0-80"
STUD_TAP_SPEC = HoleSpec(
    "tapped", STUD_THREAD, end="blind", depth_mm=6.0, overrides_mm={"ThreadDepth": 4.5}
)
STUD_TAP_DRILL_DIA = TAP_DRILL_MM[STUD_THREAD]
# The stud threads this far into the tap (rule 18: >= 1.5 D full thread):
# the centre of the measured-length setting band (pn_pen_assembly_spec,
# code review C05), which keeps 3.2 ±0.4 short of the 3.99 the tap's printed
# depth guarantees.
STUD_ENGAGEMENT = 3.2

TOTAL_LENGTH = SQUARE_LENGTH + PIVOT_LENGTH

# Rule 10: the tap is located from two adjacent flats of the square (the -X
# and +Z faces), each station half the square at the .XXX band (the .XX
# band's +/-0.51 would leave 1.18, under the floor; any 4-jaw or collet
# setup holds +/-0.13).  The stations
# are construction dimensions in the hidden StudTapReference sketch; the Hole
# Wizard point itself stays on the axis.
STUD_TAP_STATION = ROD_SECTION / 2.0
STUD_TAP_STATION_PLACES = 3
_STATION_BAND = printed_band_mm(STUD_TAP_STATION_PLACES)
# Worst-case wall from the tap's thread major to a flat: the nearer flat at
# the shortest station, the far flat of the smallest square at the longest.
_TAP_MAJOR_R = THREAD_MAJOR_MM[STUD_THREAD] / 2.0
STUD_TAP_WALL_MIN = min(
    STUD_TAP_STATION - _STATION_BAND - _TAP_MAJOR_R,
    ROD_SECTION + SECTION_BAND[1] - (STUD_TAP_STATION + _STATION_BAND) - _TAP_MAJOR_R,
)
if STUD_TAP_WALL_MIN < 1.5:  # drawing-guidelines.md rule 17 (walls and webs) floor
    raise AssertionError(f"rod stud tap leaves a {STUD_TAP_WALL_MIN:.2f} mm wall")
# Named exception RV-01 (pn-pen-rod.yaml, owner ruling 2026-10-24 on #1903)
# declares this worst case, floored at two places (1.558 -> 1.55); a
# different wall is outside the declaration.
STUD_TAP_WALL_ACCEPTED = 1.55
if math.floor(STUD_TAP_WALL_MIN * 100 + 1e-9) / 100 != STUD_TAP_WALL_ACCEPTED:
    raise AssertionError(
        f"rod stud tap wall {STUD_TAP_WALL_MIN:.3f} is not RV-01's declared "
        f"{STUD_TAP_WALL_ACCEPTED}"
    )
# Rule 20: the tap callout's last row states the shortfall, floored at one
# place so the sheet never overstates the minimum (named exception RV-01).
STUD_TAP_WALL_CALLOUT = f"WALL {math.floor(STUD_TAP_WALL_MIN * 10 + 1e-9) / 10:.1f} MIN"
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
# to the limit is good). 0.2 leaves the seat face a land on every flat and
# clears the v-block's broken bore mouth (cross-part assert in
# pn_pen_carriage_geom).
SHOULDER_FILLET_R = 0.2
# (upper, lower) deviations: the nominal IS the limit, down to sharp.
SHOULDER_FILLET_BAND = (0.0, -SHOULDER_FILLET_R)
SHOULDER_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R0.2 MAX"
SHOULDER_FILLET_PLACES = 1
if SHOULDER_FILLET_BAND[0] != 0.0 or SHOULDER_FILLET_BAND[1] != -SHOULDER_FILLET_R:
    raise AssertionError("the shoulder radius band must run from sharp to the nominal")
if round(SHOULDER_FILLET_R, SHOULDER_FILLET_PLACES) != SHOULDER_FILLET_R:
    raise AssertionError("the shoulder radius must print exactly at its places")
if PIVOT_DIA / 2.0 + SHOULDER_FILLET_R >= (ROD_SECTION + SECTION_BAND[1]) / 2.0:
    raise AssertionError("shoulder fillet must end inside the square's seat face")

# The overall length, end face to end face, is a reference only (rule 10):
# the square and pivot lengths own it. Printed at one place, in parentheses.
DRAWING_REFERENCE_PRECISION = 1
if round(TOTAL_LENGTH, DRAWING_REFERENCE_PRECISION) != TOTAL_LENGTH:
    raise AssertionError("the overall reference must print exactly at its places")

# Side view (2:1, rod axis horizontal as in the lathe): the square's length,
# the pivot's length and banded diameter, and the shoulder root's MAX radius.
# End view (5:1) of the tapped top face: the square's banded depth, which the
# SQ in its callout makes the size of both flats (Section and Depth are one
# "RodSection" global, so the model holds the square), and the stud-tap
# wizard callout with the tap's two stations from adjacent flats (rule 10).
# Section keeps its model band but is not printed: one SQ size defines a
# square (fr_rocker_arm_support's WinWidth "SQ POCKET").
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Length"},
    "Rod": {"Depth"},
    "PivotProfile": {"PivotDia"},
    "Pivot": {"PivotLength"},
    "ShoulderFillet": {"ShoulderRadius"},
    "StudTapReference": {"TapStationX", "TapStationZ"},
}
# The part saves its dimension-carrying construction sketch hidden (#880);
# the end view shows it per view to import its stations.
REFERENCE_SKETCHES = ("StudTapReference",)
# Places (drawing-guidelines.md rule 3): the banded square and pivot print at
# their bands' places; the overall length and the pivot length (1.0 clear of
# the v-block relief roof) are near-enough sizes; the shoulder radius prints
# its MAX limit at one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"Length": 1},
    "Rod": {"Depth": 2},
    "PivotProfile": {"PivotDia": 3},
    "Pivot": {"PivotLength": 1},
    "ShoulderFillet": {"ShoulderRadius": SHOULDER_FILLET_PLACES},
    "StudTapReference": {
        "TapStationX": STUD_TAP_STATION_PLACES,
        "TapStationZ": STUD_TAP_STATION_PLACES,
    },
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
# shoulder radius names the part its seat face lands on.
DIMENSION_CALLOUTS: dict[str, str] = {
    "Depth": f"SQ, SLIDING FIT IN PEN\nHANGER {PEN_HANGER_NUMBER} GUIDES",
    "PivotDia": f"SLIP FIT IN PEN V-BLOCK\n{PEN_V_BLOCK_NUMBER} PIVOT BORE",
    "ShoulderRadius": f"SEATS ON PEN V-BLOCK\n{PEN_V_BLOCK_NUMBER}",
}

# The 5:1 end view stands off projection (under the side view, rescaled), so
# its label names the end it looks at: "*Top" looks down the rod axis onto
# the tapped top face (machinist review 2026-10-23: unnamed, the tap's end
# read only from the missing Ø4 circle and the isometric).
END_VIEW_NOTE = "VIEW FROM SQUARE END SCALE 5:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
