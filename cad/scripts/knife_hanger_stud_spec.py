"""Native controls for the modified McMaster 91247A720 hanger stud."""

from __future__ import annotations

import _config
from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91247A720 import (
    GB_LEN,
    GB_MAJOR_R,
    GB_PITCH,
    GB_UNDERSIDE,
    GB_WASHER_T,
)

# The purchased bolt is cut at the threaded end after its complete supplier
# geometry is built.  The assembly datum is the lower face of the supplied
# washer boss, not the hex underside.
STOCK_UNDERHEAD_MM = GB_LEN - GB_WASHER_T
TRIM_LENGTH_MM = 5.5
FINISHED_UNDERHEAD_MM = 45.100
if abs(STOCK_UNDERHEAD_MM - TRIM_LENGTH_MM - FINISHED_UNDERHEAD_MM) > 1e-9:
    raise ValueError("modified stud length does not equal stock length minus trim")

# Preserve the vendor's 45-degree tip treatment at the new cut end.  The
# explicit band leaves the cut flat smaller than the receiver tap drill.
CHAMFER_WIDTH_MM = GB_PITCH * 0.75
CHAMFER_WIDTH_TOLERANCE_MM = 0.05
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]
# The nominal drill diameter comes from the shared ANSI hole table. The
# support's drilling depth and full-thread acceptance belong to the mount
# package, not this modified purchased-bolt sheet.
TAP_DRILL_DIA_MM = TAP_DRILL_MM["1/2-13"]
MIN_CHAMFER_WIDTH_MM = (2.0 * GB_MAJOR_R - TAP_DRILL_DIA_MM) / 2.0
if CHAMFER_WIDTH_MM - CHAMFER_WIDTH_TOLERANCE_MM <= MIN_CHAMFER_WIDTH_MM:
    raise ValueError("stud deburr band does not clear the mating tap drill")

FINISHED_UNDERHEAD_TOLERANCE_MM = (
    _config.title_block("linear_3pl")["value_in"] * 25.4
)
DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DIMENSION_PRECISION = {"FinishedOverall": 3, "ChamferWidth": 2, "ChamferAngle": 0}
DIMENSION_TOLERANCE_TYPES = {
    "FinishedOverall": 11,
    "ChamferWidth": 4,
    "ChamferAngle": 11,
}
DRAWING_NOTES = "UNDIMENSIONED PURCHASED HEAD/THREAD GEOMETRY IS REFERENCE."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
