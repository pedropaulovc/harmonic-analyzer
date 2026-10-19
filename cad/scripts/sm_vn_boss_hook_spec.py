"""Manufacturing controls for the modified McMaster 9490T1 anchor."""

import _config
import sm_vn_boss_hook_jam_nut_spec as jam_nut
from stock_anchor_geom import ANCHOR_9490T1, trim
from sm_summing_lever_spec import ANCHOR_H

# The MHA-SM-VN-55 jam nut locks the anchor on the boss top face (#1189), so
# the shank is trimmed longer than the boss by the nut's height plus one
# pitch: the nut runs on full thread a pitch clear of the thread's start at
# the eye neck, and the cut end still finishes flush with the boss underside
# (full ANCHOR_H engagement in the lever's through tap).
JAM_NUT_THREAD_MM = jam_nut.THICKNESS + ANCHOR_9490T1.thread_pitch_mm
SHANK_LENGTH_MM = round(ANCHOR_H + JAM_NUT_THREAD_MM, 3)
TRIM = trim(ANCHOR_9490T1, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = ANCHOR_9490T1.eye_od_mm / 2 - TRIM.shank_end_y_mm
FINISHED_OVERALL_TOLERANCE_MM = _config.title_block("linear_1pl")["value_in"] * 25.4
CHAMFER_WIDTH_MM = ANCHOR_9490T1.end_chamfer_mm
CHAMFER_WIDTH_TOLERANCE_MM = 0.25
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]

# Minimum radial deburr clears the 3.797-mm mating tap drill. At nominal angle
# the maximum leg is shorter than one factory pitch; including the adverse
# angular corner still leaves >17 mm full thread at the short overall limit.
DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DIMENSION_PRECISION = {"FinishedOverall": 1, "ChamferWidth": 2, "ChamferAngle": 0}
DIMENSION_TOLERANCE_TYPES = {"FinishedOverall": 11, "ChamferWidth": 4, "ChamferAngle": 11}
DRAWING_NOTES = (
    "FINISHED OVERALL TO EYE CROWN IS THE ACCEPTANCE SIZE.\n"
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
