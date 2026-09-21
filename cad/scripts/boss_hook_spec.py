"""Manufacturing controls for the modified McMaster 9490T1 anchor."""

import _config
from stock_anchor_geom import ANCHOR_9490T1, trim
from summing_lever_spec import ANCHOR_H, COUNTER_HOLE_SPEC

SHANK_LENGTH_MM = round(ANCHOR_H, 3)
TRIM = trim(ANCHOR_9490T1, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = ANCHOR_9490T1.eye_od_mm / 2 - TRIM.shank_end_y_mm
FINISHED_OVERALL_TOLERANCE_MM = _config.title_block("linear_1pl")["value_in"] * 25.4
CHAMFER_WIDTH_MM = ANCHOR_9490T1.end_chamfer_mm
CHAMFER_WIDTH_TOLERANCE_MM = 0.25
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]
# Minimum radial deburr clears the #10-24 mating tap drill; the adverse
# angular corner still leaves more than 17 mm of full thread at the short
# finished-overall limit.

# The part owns the three manufacturing dimensions shown on the sheet.  The
# nested form is consumed by ``apply_drawing_precision`` in the part build;
# the flattened form is only for drawing readback.
DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DRAWING_PRECISION = {
    "StockTrimProfile": {"FinishedOverall": 1},
    "StockDeburrProfile": {"ChamferWidth": 2, "ChamferAngle": 0},
}
DRAWING_PRECISION_BY_NAME = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
DIMENSION_TOLERANCE_TYPES = {"FinishedOverall": 11, "ChamferWidth": 4, "ChamferAngle": 11}

MATING_PART_NUMBER = _config.parts("summing-lever")["number"]
MATING_THREAD_SIZE = COUNTER_HOLE_SPEC.size
NUT_INSTALLED = False

# The dimensions define the cut; these notes carry only the post-purchase
# operation and the direct installation interface, not duplicate tolerances.
DRAWING_NOTES = (
    "POST-PURCHASE: TRIM FREE SHANK END TO FINISHED OVERALL; RESTORE DEBURR.\n"
    f"THREAD DIRECTLY INTO SUMMING LEVER {MATING_PART_NUMBER}'S "
    f"{MATING_THREAD_SIZE} TAPPED BOSS; NO NUT.\n"
    "CLOCK EYE TO PULL PLANE; USE REMOVABLE MEDIUM-STRENGTH THREADLOCKER.\n"
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
