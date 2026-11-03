"""Manufacturing controls for the modified McMaster 9490T1 anchor."""

import _config
import sm_vn_boss_hook_jam_nut_spec as jam_nut
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm, printed_deviations
from stock_anchor_geom import ANCHOR_9490T1, trim
from sm_summing_lever_spec import ANCHOR_H
from _supplier_screw_reference_names import FEATURE_BY_PLANE

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/sm-vn-boss-hook", _config.parts("sm-vn-boss-hook"))

# The MHA-SM-VN-55 jam nut locks the anchor on the boss top face (#1189), so
# the shank is trimmed longer than the boss by the nut's height plus one
# pitch: the nut runs on full thread a pitch clear of the thread's start at
# the eye neck, and the cut end still finishes flush with the boss underside
# (full ANCHOR_H engagement in the lever's through tap).
JAM_NUT_THREAD_MM = jam_nut.THICKNESS + ANCHOR_9490T1.thread_pitch_mm
SHANK_LENGTH_MM = round(ANCHOR_H + JAM_NUT_THREAD_MM, 3)
TRIM = trim(ANCHOR_9490T1, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = ANCHOR_9490T1.eye_od_mm / 2 - TRIM.shank_end_y_mm
# #290: the trim sets the counter anchor's eye station (spring_mount_geom
# reads SHANK_LENGTH_MM), calibrated spring geometry, so it keeps its mm
# nominal and prints rounded at .XX (1.59): the acceptance size, never .X.
# Checks charge the printed band about the model (lower, upper);
# the native General record stores the same deviations.
FINISHED_OVERALL_PLACES = 2
FINISHED_OVERALL_TOLERANCE_MM = printed_band_mm(FINISHED_OVERALL_PLACES, unit=UNIT)
FINISHED_OVERALL_DEVIATIONS = printed_deviations(
    FINISHED_OVERALL_MM, FINISHED_OVERALL_PLACES, unit=UNIT
)
# The restored deburr is a lead-in on the title block's .XX band (an .X band,
# +/-.1, would swallow the whole thread). Its nominal is the smallest .XX
# whose short leg still brings the cut end under the 3.797-mm (#25) tap
# drill, which needs at least (4.826 - 3.797) / 2 = 0.5145 (.0203): .04 - .01
# = .03 clears it, .03 - .01 = .02 (0.508) would not.
CHAMFER_WIDTH_MM = 1.016  # .04
CHAMFER_WIDTH_TOLERANCE_MM = printed_band_mm(2, unit=UNIT)
CHAMFER_WIDTH_DEVIATIONS = printed_deviations(CHAMFER_WIDTH_MM, 2, unit=UNIT)
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]

# The short leg clears the mating tap drill (above). The long .05 leg still
# leaves a 1.14 end flat inside the 2.413 major radius; including the adverse
# angular corner it leaves >17 mm full thread at the short overall limit.
DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DIMENSION_PRECISION = {
    "FinishedOverall": FINISHED_OVERALL_PLACES,
    "ChamferWidth": 2,
    "ChamferAngle": 0,
}
DIMENSION_TOLERANCE_TYPES = {
    "FinishedOverall": 11,
    "ChamferWidth": 11,
    "ChamferAngle": 11,
}
DRAWING_NOTES = (
    "FINISHED OVERALL TO EYE CROWN IS THE ACCEPTANCE SIZE.\n"
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

# McMaster 9490T1 engineering drawing (2026-01-14):
# https://www.mcmaster.com/mvC/Library/CAD2/20260114/77F834CD/9490T1_Zinc-Plated%20Steel%20Routing%20Eyebolt-Not%20for%20LiftingX.GIF
# Installed vendor-CAD eye OD/wire remain 17.5895/4.826 mm. The source's
# 11/16 / 3/16 in sizes belong only to this separate nominal stock profile.
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
# Coordinates only seed the associative profile: crown/root are on the eye
# OD, root/end are shank-edge midpoints, width follows the wire circle, and
# overall is a driven crown-to-end span rather than a redundant control.
SUPPLIER_STOCK_FEATURE = "SupplierNominalStockProfile"
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
    "SupplierThreadMajor": 3,
}
SUPPLIER_FRACTION_DENOMINATOR = 16
SUPPLIER_THREAD = ANCHOR_9490T1.thread_size
SUPPLIER_THREAD_MAJOR_MM = ANCHOR_9490T1.thread_major_dia_mm
SUPPLIER_THREAD_FEATURE = FEATURE_BY_PLANE["Front"]
SUPPLIER_THREAD_DIMENSIONS = {SUPPLIER_THREAD_FEATURE: {"SupplierThreadMajor"}}
SUPPLIER_THREAD_START_MM = (
    -SUPPLIER_THREAD_MAJOR_MM / 2.0,
    (ANCHOR_9490T1.thread_start_y_mm + TRIM.shank_end_y_mm) / 2.0,
)
# Saved hidden in the part; each drawing view explicitly opts in.
REFERENCE_SKETCHES = (SUPPLIER_STOCK_FEATURE, SUPPLIER_THREAD_FEATURE)
