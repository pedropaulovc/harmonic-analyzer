"""Pure dimensional contract for the photo-derived brass measuring-stick stop.

Approved ch16 re-derivation (2026-10-09): X follows the stick, Y points from
its thumbscrew face to the roof, and Z points into the block from the cover.
The cover and block share this frame; stock screw frames have their heads
above Y=0 and their threads extending along -Y. No SolidWorks imports.

User ruling 2026-10-09, option B in stop_roof_options_v1.png: a directly
dimensioned roof over the rebate replaces the original sketch's 14 / 2.

Issue #290 (decimal-inch pilot): both stop parts print decimal inch
(``drawing_unit: in`` on both registry rows; the matched pair shares one
unit). Every length below is physical millimetres, authored as the exact
decimal of the inch value its sheet prints (.84 x .56 x .44 block, .040
cover), snapped to the printed grid: .01 in where a size prints .XX, .001 in
where it prints .XXX. The roof (.09), back wall (.11) and hole stations (.15
from each end) were set on that grid so every worst-case web meets the rule-17
target of .080 in at the inch title block's bands; no web needs a stated
shortfall. Drill and thread sizes are the native inch drill table's
(#49 .073 tap drill for the brass #2-56 receiver, #2 close .094 clearance).
"""

from __future__ import annotations

import math

import _config
from _drawing_units import drawing_unit
from _gtol_planar import PlanarFace
from _hole_spec import DRILL_POINT_H, HoleSpec, TAP_DRILL_MM, blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _mcmaster_90114a124 import (
    LENGTH as PLATE_SCREW_LENGTH,
    MAJOR_DIA as PLATE_SCREW_MAJOR_DIA,
    PITCH as PLATE_SCREW_PITCH,
    THREAD as PLATE_SCREW_THREAD,
)
from sh_vn_thumb_screw_spec import SHANK_DIA as THUMB_MAJOR_DIA

# The sheet unit each registry row declares; the matched pair prints one.
BLOCK_UNIT = drawing_unit("parts/ms-stop-block", _config.parts("ms-stop-block"))
PLATE_UNIT = drawing_unit("parts/ms-stop-plate", _config.parts("ms-stop-plate"))
if BLOCK_UNIT != PLATE_UNIT:
    raise AssertionError(
        f"the matched stop pair must print one unit: block {BLOCK_UNIT}, plate {PLATE_UNIT}"
    )
UNIT = BLOCK_UNIT

# drawing-guidelines.md rule 17 (walls and webs) on the inch sheet: .080 in
# target, .060 in floor.
WALL_TARGET_MM = 2.032
WALL_FLOOR_MM = 1.524
# A worst case computed from exact inch decimals may land a float ulp short.
_WALL_SLACK_MM = 1e-9

BLOCK_LENGTH = 21.336  # .84
BLOCK_HEIGHT = 14.224  # .56
BLOCK_DEPTH = 11.176  # .44, the rebate plus the back wall
PLATE_THICKNESS = 1.016  # .040
PLATE_Z_MAX = 0.0
PLATE_Z_MIN = PLATE_Z_MAX - PLATE_THICKNESS
TOTAL_DEPTH = BLOCK_DEPTH + PLATE_THICKNESS
WINDOW_WIDTH = 8.382  # .330
WINDOW_HEIGHT = 3.4036  # .134
ROOF_THICKNESS = 2.286  # .09
WINDOW_Z_MIN = PLATE_Z_MAX
WINDOW_Z_MAX = WINDOW_Z_MIN + WINDOW_WIDTH
WINDOW_Y_MAX = BLOCK_HEIGHT - ROOF_THICKNESS
WINDOW_Y_MIN = WINDOW_Y_MAX - WINDOW_HEIGHT
FLOOR_THICKNESS = WINDOW_Y_MIN
BACK_WALL_THICKNESS = BLOCK_DEPTH - WINDOW_Z_MAX  # .11
ROOF_END_CHAMFER = 1.016  # .04
ROOF_CHAMFER_ANGLE = 45.0
CUT_OVERHANG = 1.0

THUMB_AXIS_X = BLOCK_LENGTH / 2.0  # .42
THUMB_AXIS_Z = (WINDOW_Z_MIN + WINDOW_Z_MAX) / 2.0  # .165
THUMB_TAP_DRILL = TAP_DRILL_MM["#4-40"]
THUMB_TAP_SPEC = HoleSpec("tapped", "#4-40", end="through_next", thread_class="2B")
THUMB_HOLE_POINTS = ((THUMB_AXIS_X, 0.0, THUMB_AXIS_Z),)
THUMB_HOLE_NORMAL = (0.0, -1.0, 0.0)

PLATE_HOLE_EDGE_OFFSET = 3.81  # .150
PLATE_HOLE_XS = (PLATE_HOLE_EDGE_OFFSET, BLOCK_LENGTH - PLATE_HOLE_EDGE_OFFSET)
PLATE_HOLE_PITCH = PLATE_HOLE_XS[1] - PLATE_HOLE_XS[0]
PLATE_HOLE_Y = 4.064  # .160
PLATE_TAP_DRILL_DIA = 1.8542  # #49 (.0730), selected for the brass #2-56 receiver
PLATE_TAP_THREAD_DEPTH = 6.35  # .250
PLATE_TAP_DRILL_DEPTH = 7.62  # .300 cylindrical depth; the drill point continues past it
PLATE_SCREW_PENETRATION = PLATE_SCREW_LENGTH - PLATE_THICKNESS
PLATE_TAP_SPEC = HoleSpec(
    "tapped_bottoming", PLATE_SCREW_THREAD, end="blind", depth_mm=PLATE_TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": PLATE_TAP_THREAD_DEPTH,
                  "TapDrillDiameter": PLATE_TAP_DRILL_DIA},
)
# The native #2 close clearance, .094: the wizard table's own size (its
# pinned 2.388 is the same drill rounded to the table's thousandth of a mm).
PLATE_CLEARANCE_SPEC = HoleSpec("clearance", "#2", fit="close")
PLATE_CLEARANCE_DIA = 2.3876  # .094
if abs(PLATE_CLEARANCE_DIA - blind_cut_dia_mm(PLATE_CLEARANCE_SPEC)) > 0.001:
    raise AssertionError("the cover clearance is the native #2 close drill, .094")
BLOCK_PLATE_HOLE_POINTS = tuple((x, PLATE_HOLE_Y, PLATE_Z_MAX) for x in PLATE_HOLE_XS)
PLATE_HOLE_POINTS = tuple((x, PLATE_HOLE_Y, PLATE_Z_MIN) for x in PLATE_HOLE_XS)
PLATE_HOLE_NORMAL = (0.0, 0.0, -1.0)
STOP_MARK = 2.0

# The standard-tap drill points and the major-thread envelopes never meet
# either the window or the orthogonal thumbscrew bore.
PLATE_TAP_TIP_Z = PLATE_TAP_DRILL_DEPTH + PLATE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
PLATE_TAP_BACK_WALL = BLOCK_DEPTH - PLATE_TAP_TIP_Z
PLATE_TAP_WINDOW_WEB = WINDOW_Y_MIN - PLATE_HOLE_Y - PLATE_SCREW_MAJOR_DIA / 2.0
PLATE_TAP_THUMB_WEB = min(abs(x - THUMB_AXIS_X) for x in PLATE_HOLE_XS) - (
    PLATE_SCREW_MAJOR_DIA + THUMB_MAJOR_DIA
) / 2.0

BLOCK_VOLUME = BLOCK_LENGTH * BLOCK_HEIGHT * BLOCK_DEPTH
WINDOW_VOLUME = BLOCK_LENGTH * WINDOW_HEIGHT * WINDOW_WIDTH
BLOCK_CHAMFER_VOLUME = ROOF_END_CHAMFER**2 * BLOCK_DEPTH
THUMB_HOLE_VOLUME = math.pi * (THUMB_TAP_DRILL / 2.0)**2 * FLOOR_THICKNESS
PLATE_TAP_VOLUME = 2.0 * math.pi * (PLATE_TAP_DRILL_DIA / 2.0)**2 * (
    PLATE_TAP_DRILL_DEPTH + PLATE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H / 3.0
)
BLOCK_FINISHED_VOLUME = BLOCK_VOLUME - WINDOW_VOLUME - BLOCK_CHAMFER_VOLUME - THUMB_HOLE_VOLUME - PLATE_TAP_VOLUME
PLATE_VOLUME = BLOCK_LENGTH * BLOCK_HEIGHT * PLATE_THICKNESS
PLATE_CHAMFER_VOLUME = ROOF_END_CHAMFER**2 * PLATE_THICKNESS
PLATE_HOLE_VOLUME = 2.0 * math.pi * (PLATE_CLEARANCE_DIA / 2.0)**2 * PLATE_THICKNESS
PLATE_FINISHED_VOLUME = PLATE_VOLUME - PLATE_CHAMFER_VOLUME - PLATE_HOLE_VOLUME

BLOCK_DRAWING_DIMENSIONS = {
    "BlockProfile": {"BlockLength", "BlockHeight"},
    "Block": {"BlockDepth"},
    # The consumed rebate profile owns all three: its lines never draw.
    "WindowProfile": {"WindowHeight", "WindowWidth", "BackWall"},
    "RoofThicknessReference": {"RoofThickness"},
    "RoofChamfers": {"RoofChamferSize", "RoofChamferAngle"},
    "ThumbLocationReference": {"ThumbFromEnd", "ThumbFromPlate"},
    "PlateLocationReference": {"PlateLeftFromEnd", "PlateRightFromEnd", "PlateFromHeadFace"},
}
PLATE_DRAWING_DIMENSIONS = {
    "PlateProfile": {"PlateLength", "PlateHeight"},
    "Plate": {"PlateThickness"},
    "RoofChamfers": {"RoofChamferSize", "RoofChamferAngle"},
    "PlateLocationReference": {"PlateLeftFromEnd", "PlateRightFromEnd", "PlateFromHeadFace"},
    "PilotDrillReference": {"PilotDrillDiameter"},
}
# The PLATE is the match-drill master. Its three absolute location bands
# transfer to the block only when the X=0 ends and Y=0 edges, both labelled on
# each sheet, are flush; the block's nominal locations are reference-only.
MATCH_DRILL_MASTER = "MS-STOP-PLATE"
LOCATING_END_NOTE = "LOCATING END"
LOCATING_EDGE_NOTE = "LOCATING EDGE"
MATCH_DRILL_DATUM_ALIGNMENT = "LOCATING ENDS AND EDGES FLUSH"
PLATE_LOCATION_DIMENSIONS = frozenset({
    "PlateLeftFromEnd", "PlateRightFromEnd", "PlateFromHeadFace",
})
# The back wall is dimensioned directly, as the 2026-10-09 ruling did for the
# roof, so its .XX band lands on the wall; the .44 envelope depth follows
# from the rebate and the wall and prints as a reference "(.44)".
BLOCK_REFERENCE_DIMENSIONS = frozenset({"BlockDepth"})
# Decimal-inch places, authored on the parts. The envelope, roof, back wall,
# chamfer and the thumb tap's station along the bar take the title block's
# .XX; a size that needs .XXX prints it: the rebate (its own +.004/0 for the
# stick), the thumb tap's mid-rebate station (.165), the cover thickness and
# the match-drill stations the cover masters (title-block .XXX +/-.005). The
# block repeats those stations at the cover's places as reference labels.
# Angles print whole degrees against the title block's +/-1 deg.
_THREE_PLACE = frozenset({
    "WindowWidth", "WindowHeight", "ThumbFromPlate", "PlateThickness",
    "PilotDrillDiameter", *PLATE_LOCATION_DIMENSIONS,
})


def _places(name: str) -> int:
    if name == "RoofChamferAngle":
        return 0
    return 3 if name in _THREE_PLACE else 2


BLOCK_DRAWING_PRECISION = {
    feature: {name: _places(name) for name in names}
    for feature, names in BLOCK_DRAWING_DIMENSIONS.items()
}
PLATE_DRAWING_PRECISION = {
    feature: {name: _places(name) for name in names}
    for feature, names in PLATE_DRAWING_DIMENSIONS.items()
}
BLOCK_DRAWING_PRECISION_BY_NAME = {name: places for dims in BLOCK_DRAWING_PRECISION.values() for name, places in dims.items()}
PLATE_DRAWING_PRECISION_BY_NAME = {name: places for dims in PLATE_DRAWING_PRECISION.values() for name, places in dims.items()}
BLOCK_MATING_FACE_NOTE = "STOP-PLATE MATING FACE"
# Rule 7: the matched pair is flagged at both match-drill callouts, which
# already name the mate, not in a loose general note.
MATCHED_PAIR_NOTE = "MATCHED PAIR; NOT INTERCHANGEABLE"
# Every native Hole Wizard length (drill diameter, drill depth, thread depth,
# clearance diameter) prints .XXX: the drill table's own sizes and the depths
# the receiver's engagement and lead are counted at.
HOLE_CALLOUT_PRECISION = 3
# The stick slides in the rebate: its sizes may only grow, by .004.
WINDOW_SIZE_TOLERANCE_MM = (0.0, 0.1016)

assert 0.0 < WINDOW_Y_MIN < WINDOW_Y_MAX < BLOCK_HEIGHT
assert WINDOW_Z_MIN == 0.0 < WINDOW_Z_MAX < BLOCK_DEPTH
assert PLATE_TAP_BACK_WALL > WALL_TARGET_MM
assert PLATE_TAP_WINDOW_WEB > WALL_TARGET_MM and PLATE_TAP_THUMB_WEB > WALL_TARGET_MM
assert PLATE_SCREW_PENETRATION > 1.5 * PLATE_SCREW_MAJOR_DIA
assert PLATE_SCREW_PENETRATION < PLATE_TAP_THREAD_DEPTH < PLATE_TAP_DRILL_DEPTH

BLOCK_DRAWING_VALUES_BY_NAME = {
    "BlockLength": BLOCK_LENGTH, "BlockHeight": BLOCK_HEIGHT,
    "BlockDepth": BLOCK_DEPTH, "WindowHeight": WINDOW_HEIGHT,
    "RoofThickness": ROOF_THICKNESS, "WindowWidth": WINDOW_WIDTH,
    "BackWall": BACK_WALL_THICKNESS,
    "RoofChamferSize": ROOF_END_CHAMFER, "RoofChamferAngle": ROOF_CHAMFER_ANGLE,
    "ThumbFromEnd": THUMB_AXIS_X, "ThumbFromPlate": THUMB_AXIS_Z,
    "PlateLeftFromEnd": PLATE_HOLE_XS[0], "PlateRightFromEnd": PLATE_HOLE_XS[1],
    "PlateFromHeadFace": PLATE_HOLE_Y,
}
PLATE_DRAWING_VALUES_BY_NAME = {
    "PlateLength": BLOCK_LENGTH, "PlateHeight": BLOCK_HEIGHT,
    "PlateThickness": PLATE_THICKNESS,
    "RoofChamferSize": ROOF_END_CHAMFER, "RoofChamferAngle": ROOF_CHAMFER_ANGLE,
    "PlateLeftFromEnd": PLATE_HOLE_XS[0], "PlateRightFromEnd": PLATE_HOLE_XS[1],
    "PlateFromHeadFace": PLATE_HOLE_Y,
    "PilotDrillDiameter": PLATE_TAP_DRILL_DIA,
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

# Arithmetic print-worst proof, using the title block the sheets actually
# print. The additional stock-length allowance is a design reserve requested
# for this joint, NOT a claim that McMaster certifies that length tolerance.
HOLE_LINEAR_TOLERANCE_MM = printed_band_mm(HOLE_CALLOUT_PRECISION, unit=UNIT)
BLOCK_PRINTED_BANDS_MM = {
    name: printed_band_mm(BLOCK_DRAWING_PRECISION_BY_NAME[name], unit=UNIT)
    for name in ("BlockLength", "BlockHeight", "RoofThickness", "BackWall")
}
PLATE_PRINTED_BANDS_MM = {
    name: printed_band_mm(PLATE_DRAWING_PRECISION_BY_NAME[name], unit=UNIT)
    for name in ("PlateLength", "PlateHeight")
}
# The cover's thickness and its master stations ride the title block's .XXX.
PLATE_THICKNESS_TOLERANCE_MM = printed_band_mm(
    PLATE_DRAWING_PRECISION_BY_NAME["PlateThickness"], unit=UNIT
)
PLATE_HOLE_POSITION_TOLERANCE_MM = printed_band_mm(
    PLATE_DRAWING_PRECISION_BY_NAME["PlateLeftFromEnd"], unit=UNIT
)
DRILL_OVERSIZE_MM = drilled_oversize_mm(unit=UNIT)
PLATE_SCREW_LENGTH_RESERVE_MM = 0.254
PLATE_THICKNESS_MIN = PLATE_THICKNESS - PLATE_THICKNESS_TOLERANCE_MM
PLATE_THICKNESS_MAX = PLATE_THICKNESS + PLATE_THICKNESS_TOLERANCE_MM
PLATE_SCREW_PENETRATION_MIN = PLATE_SCREW_LENGTH - PLATE_SCREW_LENGTH_RESERVE_MM - PLATE_THICKNESS_MAX
PLATE_SCREW_PENETRATION_MAX = PLATE_SCREW_LENGTH + PLATE_SCREW_LENGTH_RESERVE_MM - PLATE_THICKNESS_MIN
PLATE_FULL_THREAD_MIN = PLATE_TAP_THREAD_DEPTH - HOLE_LINEAR_TOLERANCE_MM
PLATE_FULL_THREAD_MAX = PLATE_TAP_THREAD_DEPTH + HOLE_LINEAR_TOLERANCE_MM
PLATE_TAP_LEAD_MIN = PLATE_TAP_DRILL_DEPTH - HOLE_LINEAR_TOLERANCE_MM - PLATE_FULL_THREAD_MAX
# The reference depth is the rebate plus the directly toleranced back wall.
BLOCK_DEPTH_MIN = (WINDOW_WIDTH + WINDOW_SIZE_TOLERANCE_MM[0]
                   + BACK_WALL_THICKNESS - BLOCK_PRINTED_BANDS_MM["BackWall"])
PLATE_TAP_BACK_WALL_MIN = BLOCK_DEPTH_MIN - (
    PLATE_TAP_DRILL_DEPTH + HOLE_LINEAR_TOLERANCE_MM
    + (PLATE_TAP_DRILL_DIA + DRILL_OVERSIZE_MM) / 2.0 * DRILL_POINT_H
)
ROOF_THICKNESS_MIN = ROOF_THICKNESS - BLOCK_PRINTED_BANDS_MM["RoofThickness"]
WINDOW_FLOOR_MIN = BLOCK_HEIGHT - BLOCK_PRINTED_BANDS_MM["BlockHeight"] - (
    ROOF_THICKNESS + BLOCK_PRINTED_BANDS_MM["RoofThickness"]
    + WINDOW_HEIGHT + WINDOW_SIZE_TOLERANCE_MM[1]
)
# Reference labels do not make the transferred axes float: retain the plate
# master's absolute .XXX band in both the receiver and cover worst-case proofs.
# A 2B internal thread has no specified maximum major; the tap that cuts it
# does. ASME/ANSI B94.9-1987 machine screw taps, #2-56: cut-thread major max
# 0.0887 in (Table 7), ground-thread 0.0883 in (Table 6). The larger bounds
# the tapped major whichever tap the shop uses.
PLATE_TAP_MAJOR_DIA_MAX = 0.0887 * 25.4
PLATE_TAP_MAJOR_RADIUS_MAX = PLATE_TAP_MAJOR_DIA_MAX / 2.0
PLATE_TAP_WINDOW_WEB_MIN = WINDOW_FLOOR_MIN - (
    PLATE_HOLE_Y + PLATE_HOLE_POSITION_TOLERANCE_MM + PLATE_TAP_MAJOR_RADIUS_MAX
)


def transferred_tap_end_web_min(master_position_band_mm: float) -> float:
    """Receiver end web after transfer from the edge-aligned plate master."""
    radius = PLATE_TAP_MAJOR_RADIUS_MAX
    return min(
        PLATE_HOLE_XS[0] - master_position_band_mm - radius,
        BLOCK_LENGTH - BLOCK_PRINTED_BANDS_MM["BlockLength"] - (
            PLATE_HOLE_XS[1] + master_position_band_mm + radius
        ),
    )


PLATE_TAP_END_WEB_MIN = transferred_tap_end_web_min(PLATE_HOLE_POSITION_TOLERANCE_MM)
WINDOW_BACK_WALL_MIN = BACK_WALL_THICKNESS - BLOCK_PRINTED_BANDS_MM["BackWall"]
PLATE_CLEARANCE_END_WEB_MIN = BLOCK_LENGTH - PLATE_PRINTED_BANDS_MM["PlateLength"] - (
    PLATE_HOLE_XS[1] + PLATE_HOLE_POSITION_TOLERANCE_MM
    + (PLATE_CLEARANCE_DIA + DRILL_OVERSIZE_MM) / 2.0
)
PLATE_CLEARANCE_HEAD_WEB_MIN = BLOCK_HEIGHT - PLATE_PRINTED_BANDS_MM["PlateHeight"] - (
    PLATE_HOLE_Y + PLATE_HOLE_POSITION_TOLERANCE_MM
    + (PLATE_CLEARANCE_DIA + DRILL_OVERSIZE_MM) / 2.0
)
PLATE_RADIAL_CLEARANCE_MIN = (PLATE_CLEARANCE_DIA - PLATE_SCREW_MAJOR_DIA) / 2.0
ROOF_OPEN_END_EDGE = ROOF_THICKNESS - ROOF_END_CHAMFER  # .05 at the end-edge break, not the structural roof

# Every worst-case wall and web, each at its printed bands: all meet the
# rule-17 target, so no sheet states a shortfall (rule 20).
WORST_CASE_WALLS_MM = {
    "roof": ROOF_THICKNESS_MIN,
    "rebate back wall": WINDOW_BACK_WALL_MIN,
    "tap drill point to opposite face": PLATE_TAP_BACK_WALL_MIN,
    "tap thread to end face": PLATE_TAP_END_WEB_MIN,
    "tap thread to rebate floor": PLATE_TAP_WINDOW_WEB_MIN,
    "clearance hole to end face": PLATE_CLEARANCE_END_WEB_MIN,
    "clearance hole to head edge": PLATE_CLEARANCE_HEAD_WEB_MIN,
}
_SHORT = {
    name: wall for name, wall in WORST_CASE_WALLS_MM.items()
    if wall < WALL_TARGET_MM - _WALL_SLACK_MM
}
if _SHORT:
    raise AssertionError(f"stop walls below the {WALL_TARGET_MM} rule-17 target: {_SHORT}")

assert PLATE_SCREW_PENETRATION_MIN >= 1.5 * PLATE_SCREW_MAJOR_DIA
assert PLATE_SCREW_PENETRATION_MAX < PLATE_FULL_THREAD_MIN
assert PLATE_TAP_LEAD_MIN >= PLATE_SCREW_PITCH  # one-pitch bottoming-tap lead
assert PLATE_RADIAL_CLEARANCE_MIN > 0.0

# Rule 6: the stick's graduated face slides on the roof underside (the
# rebate ceiling, outward normal -Y at the window top), so that face is the
# one sliding surface the print grades: Ra 63 uin (1.6 um).
BLOCK_SURFACE_FINISHES = (
    SurfaceFinishControl(
        "rebate_slide", MACHINED_UM, PlanarFace((0, -1, 0), -WINDOW_Y_MAX),
        display_unit=BLOCK_UNIT,
    ),
)
