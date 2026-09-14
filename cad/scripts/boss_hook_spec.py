"""Manufacturing controls for the modified McMaster 9490T1 anchor."""

from stock_anchor_geom import ANCHOR_9490T1, trim
from summing_lever_spec import ANCHOR_H

SHANK_LENGTH_MM = round(ANCHOR_H, 3)
TRIM = trim(ANCHOR_9490T1, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = ANCHOR_9490T1.eye_od_mm / 2 - TRIM.shank_end_y_mm
FINISHED_OVERALL_TOLERANCE_MM = 0.51
CHAMFER_WIDTH_MM = ANCHOR_9490T1.end_chamfer_mm
CHAMFER_WIDTH_TOLERANCE_MM = 0.25
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = 1.0

# Minimum radial deburr clears the 3.797-mm mating tap drill. At nominal angle
# the maximum leg is shorter than one factory pitch; including the adverse
# angular corner still leaves >17 mm full thread at the short overall limit.
DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DRAWING_NOTES = (
    "MODIFIED FEATURES: GENERAL SPECIFICATIONS APPLY.\n"
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
