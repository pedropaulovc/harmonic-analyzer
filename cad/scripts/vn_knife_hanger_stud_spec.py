"""MHA-VN-024 knife-hanger bolt: 92314A253 stock, cut to length.

Catalogue checked 2026-10-13: https://www.mcmaster.com/92314A253/.
18-8 stainless plain external hex, #10-24 UNC-2A, fully threaded, flat tip,
2 in under head, 5/16 in AF, 1/8 in head height, 80 ksi. The SKU omits a
specification standard and head/length tolerances. Published UNC-2A thread
major limits are separate from those unspecified supplier tolerances.

The finished cut band and thread-tail MIN below are MODIFIED-PART acceptance,
not supplier tolerances. Retain a continuous usable tail through at least
10.62 mm from the finished tip, with at most one pitch of incomplete thread
at that tip. Gauge the rest of that tail to the stock's UNC-2A class; the
print states only #10-24 UNC because the title block's thread row already
gives class 2A.
The native model depicts catalogue fully-threaded geometry; inspection,
not that depiction, certifies the tail used by the worst-case reach stack.

Title-block MATERIAL is the purchased 18-8 family as supplied: nothing in
this static clamp needs one 18-8 grade. ``_fastener_catalog`` keeps AISI 304
only as the SOLIDWORKS library stand-in for rendering and mass; it is not a
supplier grade.

Part frame: finished tip Y=0, axis +Y, bearing face Y=45.70.
"""

import math

from _mcmaster_92314a253 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_DIMENSIONAL_TOLERANCES as CATALOG_DIMENSIONAL_TOLERANCES,
    CATALOG_STANDARD as CATALOG_STANDARD,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    THREAD_MAJOR_MAX,
    THREAD_MAJOR_MIN,
)
from _printed_tolerance import angular_band_deg, printed_band_mm

SKU = DIMS.part_no
THREAD = "#10-24"
THREAD_FIT = "UNC-2A"
SHANK_DIA = DIMS.major_dia
SHANK_DIA_MIN = THREAD_MAJOR_MIN
SHANK_DIA_MAX = THREAD_MAJOR_MAX
PITCH = DIMS.pitch
CATALOG_LENGTH = DIMS.length
LENGTH = 45.70
UNDERHEAD_LEN = LENGTH
LENGTH_BAND = (0.15, -0.15)  # Finished part, (upper, lower), mm.
LENGTH_MIN = LENGTH + LENGTH_BAND[1]
LENGTH_MAX = LENGTH + LENGTH_BAND[0]
HEAD_AF = DIMS.head_af
HEAD_H = DIMS.head_h
THREAD_LENGTH = LENGTH  # Nominal catalogue fully-threaded depiction.
THREAD_LENGTH_MIN = 10.62  # Tail measured from the finished tip.
INCOMPLETE_TIP_LEN_MAX = PITCH
FULL_FORM_TAIL_MIN = THREAD_LENGTH_MIN - INCOMPLETE_TIP_LEN_MAX
# The drawing-guidelines.md rule 18 (thread engagement) thread engagement floor.
ENGAGEMENT_MIN_D = 1.5
TIP_Y = 0.0
HEAD_UNDERFACE_Y = UNDERHEAD_LEN
HEAD_TOP_Y = HEAD_UNDERFACE_Y + HEAD_H
# Radial leg from the native ChamferWidth, measured on the tip face.
CHAMFER_WIDTH = 0.60
CHAMFER_WIDTH_TOLERANCE = 0.05
CHAMFER_WIDTH_MIN = CHAMFER_WIDTH - CHAMFER_WIDTH_TOLERANCE
CHAMFER_WIDTH_MAX = CHAMFER_WIDTH + CHAMFER_WIDTH_TOLERANCE
CHAMFER_ANGLE = 45.0  # Native driving angle between tip face and chamfer.
# Printed natively without a band: the title block's angular row governs it.
CHAMFER_ANGLE_TOLERANCE = angular_band_deg()
# Worst axial tip loss: the widest radial leg at the steepest title-block
# angle. It must stay inside the one incomplete pitch that the worst-case
# engagement (reach MIN less one pitch >= 1.5D) already charges.
CHAMFER_AXIAL_MAX = CHAMFER_WIDTH_MAX * math.tan(
    math.radians(CHAMFER_ANGLE + CHAMFER_ANGLE_TOLERANCE)
)
# The same leg left to the title block's two-place row (0.60 +/-0.51): it
# would cost more than the charged pitch and break the 1.5D engagement, and
# its smallest leg would leave the thread start's feather edge outside the
# MHA-SM-002 tap drill. The explicit band is therefore functional.
CHAMFER_WIDTH_TITLE_BLOCK_BAND = printed_band_mm(2)
CHAMFER_AXIAL_MAX_AT_TITLE_BLOCK = (
    CHAMFER_WIDTH + CHAMFER_WIDTH_TITLE_BLOCK_BAND
) * math.tan(math.radians(CHAMFER_ANGLE + CHAMFER_ANGLE_TOLERANCE))
if not 0.0 < CHAMFER_AXIAL_MAX <= INCOMPLETE_TIP_LEN_MAX:
    raise AssertionError("cut-end chamfer exceeds the charged incomplete pitch")

DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"CutLength"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
    "ThreadTailAcceptance": {"ThreadLengthMin"},
}
DRAWING_PRECISION = {
    "StockTrimProfile": {"CutLength": 2},
    "StockDeburrProfile": {"ChamferWidth": 2, "ChamferAngle": 0},
    "ThreadTailAcceptance": {"ThreadLengthMin": 2},
}
DIMENSION_PRECISION = {
    name: digits
    for dimensions in DRAWING_PRECISION.values()
    for name, digits in dimensions.items()
}
DIMENSION_TOLERANCE_TYPES = {
    "CutLength": 4,
    "ChamferWidth": 4,
    "ChamferAngle": 11,  # swTolGeneral: native band, title-block print.
    "ThreadLengthMin": 5,
}
PRINTED_THREAD = f"{THREAD} UNC"  # Class 2A comes from the title block.
DIMENSION_CALLOUTS = {
    "CutLength": (
        "UNDER HEAD TO FINISHED TIP\n"
        "MATE: MHA-SM-002 KNIFE MOUNT\n"
        "SETS THREAD ENGAGEMENT\n"
        "AND TIP CLEARANCE"
    ),
    # The band on the leg is the engagement reason; the native ChamferAngle
    # prints its own 45 degrees.
    "ChamferWidth": (
        "CUT-END CHAMFER\nSETS FULL-THREAD ENGAGEMENT\nIN MHA-SM-002 KNIFE MOUNT"
    ),
    "ThreadLengthMin": (
        f"{PRINTED_THREAD} CONTINUOUS TAIL FROM TIP\n"
        "INCOMPLETE CUT-END THREAD 1 PITCH MAX\n"
        "ALL REMAINING TAIL FULL FORM"
    ),
}
