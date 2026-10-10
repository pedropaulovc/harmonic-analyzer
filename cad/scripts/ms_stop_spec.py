"""Pure dimensional contract for the photo-derived brass measuring-stick stop.

Approved ch16 re-derivation (2026-10-09): X follows the stick, Y points from
its thumbscrew face to the roof, and Z points into the block from the cover.
The cover and block share this frame; stock screw frames have their heads
above Y=0 and their threads extending along -Y. No SolidWorks imports.

User ruling 2026-10-09, option B in stop_roof_options_v1.png: height 14.1
and a directly dimensioned 2.1 roof replace the original 14 / 2 sketch.
Routine +/-0.51 on that direct roof dimension leaves 1.59 minimum; no
rule-12 exception or artificially tightened roof tolerance is required.
"""

from __future__ import annotations

import math

from _hole_spec import DRILL_POINT_H, HoleSpec, TAP_DRILL_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from vn_ms_stop_plate_screw_spec import (
    LENGTH as PLATE_SCREW_LENGTH,
    MAJOR_DIA as PLATE_SCREW_MAJOR_DIA,
    PITCH as PLATE_SCREW_PITCH,
    THREAD as PLATE_SCREW_THREAD,
)
from vn_thumb_screw_spec import SHANK_DIA as THUMB_MAJOR_DIA

BLOCK_LENGTH = 21.0
BLOCK_HEIGHT = 14.1
BLOCK_DEPTH = 11.0
PLATE_THICKNESS = 1.0
PLATE_Z_MAX = 0.0
PLATE_Z_MIN = PLATE_Z_MAX - PLATE_THICKNESS
TOTAL_DEPTH = BLOCK_DEPTH + PLATE_THICKNESS
WINDOW_WIDTH = 8.4
WINDOW_HEIGHT = 3.4
ROOF_THICKNESS = 2.1
WINDOW_Z_MIN = PLATE_Z_MAX
WINDOW_Z_MAX = WINDOW_Z_MIN + WINDOW_WIDTH
WINDOW_Y_MAX = BLOCK_HEIGHT - ROOF_THICKNESS
WINDOW_Y_MIN = WINDOW_Y_MAX - WINDOW_HEIGHT
FLOOR_THICKNESS = WINDOW_Y_MIN
BACK_WALL_THICKNESS = BLOCK_DEPTH - WINDOW_Z_MAX
ROOF_END_CHAMFER = 1.0
ROOF_CHAMFER_ANGLE = 45.0
CUT_OVERHANG = 1.0

THUMB_AXIS_X = BLOCK_LENGTH / 2.0
THUMB_AXIS_Z = (WINDOW_Z_MIN + WINDOW_Z_MAX) / 2.0
THUMB_TAP_DRILL = TAP_DRILL_MM["#4-40"]
THUMB_TAP_SPEC = HoleSpec("tapped", "#4-40", end="through_next", thread_class="2B")
THUMB_HOLE_POINTS = ((THUMB_AXIS_X, 0.0, THUMB_AXIS_Z),)
THUMB_HOLE_NORMAL = (0.0, -1.0, 0.0)

PLATE_HOLE_EDGE_OFFSET = 3.5
PLATE_HOLE_XS = (PLATE_HOLE_EDGE_OFFSET, BLOCK_LENGTH - PLATE_HOLE_EDGE_OFFSET)
PLATE_HOLE_PITCH = PLATE_HOLE_XS[1] - PLATE_HOLE_XS[0]
PLATE_HOLE_Y = 4.0
PLATE_CLEARANCE_DIA = 2.4
PLATE_TAP_DRILL_DIA = 1.85  # #49, selected for the brass #2-56 receiver
PLATE_TAP_THREAD_DEPTH = 6.3
PLATE_TAP_DRILL_DEPTH = 7.8  # cylindrical depth; the drill point continues past it
PLATE_SCREW_PENETRATION = PLATE_SCREW_LENGTH - PLATE_THICKNESS
PLATE_TAP_SPEC = HoleSpec(
    "tapped_bottoming", PLATE_SCREW_THREAD, end="blind", depth_mm=PLATE_TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": PLATE_TAP_THREAD_DEPTH,
                  "TapDrillDiameter": PLATE_TAP_DRILL_DIA},
)
PLATE_CLEARANCE_SPEC = HoleSpec(
    "clearance", "#2", fit="close",
    overrides_mm={"HoleDiameter": PLATE_CLEARANCE_DIA},
)
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
    "WindowProfile": {"WindowHeight"},
    "ReferenceWindowWidth": {"WindowWidth"},
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
# Functional clamp-joint bands; the axes locate a MATCH-DRILLED pair, not two
# independently interchangeable patterns. Pilot both parts in one clamped
# pass, then open the plate clearance and bottoming-tap the block.
PLATE_THICKNESS_TOLERANCE_MM = 0.1
PLATE_HOLE_POSITION_TOLERANCE_MM = 0.1
PLATE_LOCATION_DIMENSIONS = frozenset({
    "PlateLeftFromEnd", "PlateRightFromEnd", "PlateFromHeadFace",
})
BLOCK_DRAWING_PRECISION = {
    feature: {name: 2 for name in names}
    for feature, names in BLOCK_DRAWING_DIMENSIONS.items()
}
PLATE_DRAWING_PRECISION = {
    feature: {name: 2 for name in names}
    for feature, names in PLATE_DRAWING_DIMENSIONS.items()
}
# The stock bands remain loose wherever the actual worst-case web permits it.
# Depth and cover length still need .XX; their .X bands would breach 1.5 mm.
BLOCK_DRAWING_PRECISION["BlockProfile"].update(BlockLength=1, BlockHeight=1)
PLATE_DRAWING_PRECISION["PlateProfile"]["PlateHeight"] = 1
BLOCK_DRAWING_PRECISION_BY_NAME = {name: places for dims in BLOCK_DRAWING_PRECISION.values() for name, places in dims.items()}
PLATE_DRAWING_PRECISION_BY_NAME = {name: places for dims in PLATE_DRAWING_PRECISION.values() for name, places in dims.items()}
BLOCK_MATING_FACE_NOTE = "STOP-PLATE MATING FACE"
BLOCK_DRAWING_NOTES = (
    "KEEP MATCHED PAIR TOGETHER; NOT INTERCHANGEABLE.\n"
    f"BLIND DEPTHS FROM {BLOCK_MATING_FACE_NOTE}."
)
PLATE_DRAWING_NOTES = "KEEP MATCHED PAIR TOGETHER; NOT INTERCHANGEABLE."
HOLE_CALLOUT_PRECISION = 2
WINDOW_SIZE_TOLERANCE_MM = (0.0, 0.1)

assert 0.0 < WINDOW_Y_MIN < WINDOW_Y_MAX < BLOCK_HEIGHT
assert WINDOW_Z_MIN == 0.0 < WINDOW_Z_MAX < BLOCK_DEPTH
assert PLATE_TAP_BACK_WALL > 2.0
assert PLATE_TAP_WINDOW_WEB > 2.0 and PLATE_TAP_THUMB_WEB > 2.0
assert PLATE_SCREW_PENETRATION > 1.5 * PLATE_SCREW_MAJOR_DIA
assert PLATE_SCREW_PENETRATION < PLATE_TAP_THREAD_DEPTH < PLATE_TAP_DRILL_DEPTH

BLOCK_DRAWING_VALUES_BY_NAME = {
    "BlockLength": BLOCK_LENGTH, "BlockHeight": BLOCK_HEIGHT,
    "BlockDepth": BLOCK_DEPTH, "WindowHeight": WINDOW_HEIGHT,
    "RoofThickness": ROOF_THICKNESS, "WindowWidth": WINDOW_WIDTH,
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
HOLE_LINEAR_TOLERANCE_MM = printed_band_mm(HOLE_CALLOUT_PRECISION)
BLOCK_PRINTED_BANDS_MM = {
    name: printed_band_mm(BLOCK_DRAWING_PRECISION_BY_NAME[name])
    for name in ("BlockLength", "BlockHeight", "BlockDepth", "RoofThickness")
}
PLATE_PRINTED_BANDS_MM = {
    name: printed_band_mm(PLATE_DRAWING_PRECISION_BY_NAME[name])
    for name in ("PlateLength", "PlateHeight")
}
DRILL_OVERSIZE_MM = drilled_oversize_mm()
PLATE_SCREW_LENGTH_RESERVE_MM = 0.254
PLATE_THICKNESS_MIN = PLATE_THICKNESS - PLATE_THICKNESS_TOLERANCE_MM
PLATE_THICKNESS_MAX = PLATE_THICKNESS + PLATE_THICKNESS_TOLERANCE_MM
PLATE_SCREW_PENETRATION_MIN = PLATE_SCREW_LENGTH - PLATE_SCREW_LENGTH_RESERVE_MM - PLATE_THICKNESS_MAX
PLATE_SCREW_PENETRATION_MAX = PLATE_SCREW_LENGTH + PLATE_SCREW_LENGTH_RESERVE_MM - PLATE_THICKNESS_MIN
PLATE_FULL_THREAD_MIN = PLATE_TAP_THREAD_DEPTH - HOLE_LINEAR_TOLERANCE_MM
PLATE_FULL_THREAD_MAX = PLATE_TAP_THREAD_DEPTH + HOLE_LINEAR_TOLERANCE_MM
PLATE_TAP_LEAD_MIN = PLATE_TAP_DRILL_DEPTH - HOLE_LINEAR_TOLERANCE_MM - PLATE_FULL_THREAD_MAX
PLATE_TAP_BACK_WALL_MIN = BLOCK_DEPTH - BLOCK_PRINTED_BANDS_MM["BlockDepth"] - (
    PLATE_TAP_DRILL_DEPTH + HOLE_LINEAR_TOLERANCE_MM
    + (PLATE_TAP_DRILL_DIA + DRILL_OVERSIZE_MM) / 2.0 * DRILL_POINT_H
)
ROOF_THICKNESS_MIN = ROOF_THICKNESS - BLOCK_PRINTED_BANDS_MM["RoofThickness"]
WINDOW_FLOOR_MIN = BLOCK_HEIGHT - BLOCK_PRINTED_BANDS_MM["BlockHeight"] - (
    ROOF_THICKNESS + BLOCK_PRINTED_BANDS_MM["RoofThickness"]
    + WINDOW_HEIGHT + WINDOW_SIZE_TOLERANCE_MM[1]
)
PLATE_TAP_WINDOW_WEB_MIN = WINDOW_FLOOR_MIN - (
    PLATE_HOLE_Y + PLATE_HOLE_POSITION_TOLERANCE_MM + PLATE_SCREW_MAJOR_DIA / 2.0
)
PLATE_TAP_END_WEB_MIN = BLOCK_LENGTH - BLOCK_PRINTED_BANDS_MM["BlockLength"] - (
    PLATE_HOLE_XS[1] + PLATE_HOLE_POSITION_TOLERANCE_MM + PLATE_SCREW_MAJOR_DIA / 2.0
)
WINDOW_BACK_WALL_MIN = BLOCK_DEPTH - BLOCK_PRINTED_BANDS_MM["BlockDepth"] - (
    WINDOW_WIDTH + WINDOW_SIZE_TOLERANCE_MM[1]
)
PLATE_CLEARANCE_END_WEB_MIN = BLOCK_LENGTH - PLATE_PRINTED_BANDS_MM["PlateLength"] - (
    PLATE_HOLE_XS[1] + PLATE_HOLE_POSITION_TOLERANCE_MM
    + (PLATE_CLEARANCE_DIA + DRILL_OVERSIZE_MM) / 2.0
)
PLATE_CLEARANCE_HEAD_WEB_MIN = BLOCK_HEIGHT - PLATE_PRINTED_BANDS_MM["PlateHeight"] - (
    PLATE_HOLE_Y + PLATE_HOLE_POSITION_TOLERANCE_MM
    + (PLATE_CLEARANCE_DIA + DRILL_OVERSIZE_MM) / 2.0
)
PLATE_RADIAL_CLEARANCE_MIN = (PLATE_CLEARANCE_DIA - PLATE_SCREW_MAJOR_DIA) / 2.0
ROOF_OPEN_END_EDGE = ROOF_THICKNESS - ROOF_END_CHAMFER  # 1.1 at the approved end-edge break, not the structural roof

assert PLATE_SCREW_PENETRATION_MIN >= 1.5 * PLATE_SCREW_MAJOR_DIA
assert PLATE_SCREW_PENETRATION_MAX < PLATE_FULL_THREAD_MIN
assert PLATE_TAP_LEAD_MIN >= PLATE_SCREW_PITCH  # one-pitch bottoming-tap lead
assert PLATE_TAP_BACK_WALL_MIN >= 1.5
assert ROOF_THICKNESS_MIN >= 1.5
assert PLATE_TAP_WINDOW_WEB_MIN >= 1.5 and PLATE_TAP_END_WEB_MIN >= 1.5
assert WINDOW_BACK_WALL_MIN >= 1.5
assert PLATE_CLEARANCE_END_WEB_MIN >= 1.5 and PLATE_CLEARANCE_HEAD_WEB_MIN >= 1.5
assert PLATE_RADIAL_CLEARANCE_MIN > 0.0
