"""Manufacturing controls for the modified McMaster 9490T1 anchor."""

import _config
import vn_boss_hook_jam_nut_spec as jam_nut
from stock_anchor_geom import ANCHOR_9490T1, trim
from sm_summing_lever_spec import ANCHOR_H

# The MHA-VN-072 jam nut locks the anchor on the boss top face (#1189), so
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

# McMaster 9490T1 engineering drawing (2026-01-14):
# https://www.mcmaster.com/mvC/Library/CAD2/20260114/77F834CD/9490T1_Zinc-Plated%20Steel%20Routing%20Eyebolt-Not%20for%20LiftingX.GIF
# The supplier's 11/16 eye OD and 3/16 wire are NOMINAL stock sizes, not the
# native replica's .6925 and .190 in. Keep the exact vendor-model solid and
# put those source fractions on a separate sketch-only stock diagram.
SUPPLIER_EYE_ID_MM = ANCHOR_9490T1.eye_id_mm
SUPPLIER_NOMINAL_EYE_OD_MM = (11.0 / 16.0) * 25.4
SUPPLIER_NOMINAL_WIRE_MM = (3.0 / 16.0) * 25.4
SUPPLIER_STOCK_WIRE_CENTER_MM = (30.0, 0.0)
SUPPLIER_STOCK_SHANK_MM = ANCHOR_9490T1.shank_length_mm
SUPPLIER_STOCK_OVERALL_MM = SUPPLIER_NOMINAL_EYE_OD_MM + SUPPLIER_STOCK_SHANK_MM
SUPPLIER_STOCK_AXIS_MM = (
    (0.0, SUPPLIER_NOMINAL_EYE_OD_MM / 2.0),
    (0.0, -SUPPLIER_NOMINAL_EYE_OD_MM / 2.0),
    (0.0, -SUPPLIER_NOMINAL_EYE_OD_MM / 2.0 - SUPPLIER_STOCK_SHANK_MM),
)
SUPPLIER_STOCK_SHANK_OUTLINE_MM = (
    (-SUPPLIER_NOMINAL_WIRE_MM / 2.0, SUPPLIER_STOCK_AXIS_MM[1][1]),
    (SUPPLIER_NOMINAL_WIRE_MM / 2.0, SUPPLIER_STOCK_AXIS_MM[1][1]),
    (SUPPLIER_NOMINAL_WIRE_MM / 2.0, SUPPLIER_STOCK_AXIS_MM[2][1]),
    (-SUPPLIER_NOMINAL_WIRE_MM / 2.0, SUPPLIER_STOCK_AXIS_MM[2][1]),
)
# These coordinates seed the source sketch only: its crown/root are constrained
# to the eye OD, its ends to the shank-edge midpoints, and its width is driven by
# SupplierNominalWire. SupplierStockOverall is a driven crown-to-end measurement.
SUPPLIER_STOCK_FEATURE = "SupplierNominalStockProfile"
# Saved hidden; drawing views opt in to these reference dimensions.
REFERENCE_SKETCHES = (SUPPLIER_STOCK_FEATURE,)
SUPPLIER_STOCK_CONFIGURATION = "SupplierNominalStock"
SUPPLIER_STOCK_DIMENSIONS = {
    SUPPLIER_STOCK_FEATURE: {
        "SupplierNominalEyeOD", "SupplierNominalWire",
        "SupplierStockShank", "SupplierStockOverall",
    },
}
SUPPLIER_REFERENCE_PRECISION = {
    "EyeID": 0,
    "SupplierNominalEyeOD": 0,
    "SupplierNominalWire": 0,
    "SupplierStockShank": 0,
    "SupplierStockOverall": 0,
}
SUPPLIER_FRACTION_DENOMINATOR = 16
SUPPLIER_THREAD = ANCHOR_9490T1.thread_size
SUPPLIER_THREAD_MAJOR_MM = ANCHOR_9490T1.thread_major_dia_mm
# The original source lengths belong only to the separate stock envelope,
# never to the physically trimmed finished solid.
