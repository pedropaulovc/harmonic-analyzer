"""Native controls for the modified McMaster 91247A720 hanger stud."""

from __future__ import annotations

import _config
from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91247A720 import (
    GB_LEN,
    GB_MAJOR_R,
    GB_UNDERSIDE,
    GB_WASHER_T,
    ROOT_CHAMFER_MM,
)

# The purchased bolt is cut at the threaded end after its complete supplier
# geometry is built.  The assembly datum is the lower face of the supplied
# washer boss, not the hex underside.
STOCK_UNDERHEAD_MM = GB_LEN - GB_WASHER_T
TRIM_LENGTH_MM = 5.5
FINISHED_UNDERHEAD_MM = 45.100
if abs(STOCK_UNDERHEAD_MM - TRIM_LENGTH_MM - FINISHED_UNDERHEAD_MM) > 1e-9:
    raise ValueError("modified stud length does not equal stock length minus trim")

# The cut-end deburr reaches the diagnostic recipe's modeled thread root.  This
# is a native radial control, not an arbitrary fraction of the stock pitch.
CHAMFER_WIDTH_MM = ROOT_CHAMFER_MM
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]
# The nominal drill diameter comes from the shared ANSI hole table. The
# support's drilling depth and full-thread acceptance belong to the mount
# package, not this modified purchased-bolt sheet.
TAP_DRILL_DIA_MM = TAP_DRILL_MM["1/2-13"]
MIN_CHAMFER_WIDTH_MM = (2.0 * GB_MAJOR_R - TAP_DRILL_DIA_MM) / 2.0
if CHAMFER_WIDTH_MM <= MIN_CHAMFER_WIDTH_MM:
    raise ValueError("stud root chamfer does not clear the mating tap drill")

DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferAngle"},
}
DIMENSION_PRECISION = {"FinishedOverall": 1, "ChamferWidth": 2, "ChamferAngle": 0}
# Rule 2's one exception (see top_frame_spec): the sheet's 45 deg is a DRAWING
# dimension between the drawn chamfer and end face, so no model dimension
# carries its places. It prints the driving ChamferAngle's. Left to the
# drawing default it follows the document (-2), and the document's angular
# default read 2 places (leaf 20260922T205948Z).
DRAWING_REFERENCE_PRECISION = {"ChamferAngle": DIMENSION_PRECISION["ChamferAngle"]}
DIMENSION_TOLERANCE_TYPES = {
    "ChamferAngle": 11,
}
DRAWING_NOTES = (
    "TRIM/INSPECT TO MHA-A07 SHEET 4, HANGER FIT + INSPECTION, DETAIL B.\n"
    "MARK EACH BOLT FRONT/REAR AND KEEP WITH ITS MHA-037/MHA-131 HANGER "
    "POSITION.\n"
    "UNDIMENSIONED PURCHASED HEAD/THREAD GEOMETRY IS REFERENCE.\n"
    "1/2-13 UNC THREAD PER McMASTER-CARR 91247A720."
)
ISOMETRIC_VIEW_NOTE = "ISO SCALE 1.5:1"
