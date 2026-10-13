"""MHA-VN-024 knife-hanger bolt: 92314A253 stock, cut to length.

Catalogue checked 2026-10-13: https://www.mcmaster.com/92314A253/.
18-8 stainless plain external hex, #10-24 UNC-2A, fully threaded, flat tip,
2 in under head, 5/16 in AF, 1/8 in head height, 80 ksi. The SKU omits a
specification standard and head/length tolerances. Published UNC-2A thread
major limits are separate from those unspecified supplier tolerances.

The finished cut band and thread-tail MIN below are MODIFIED-PART acceptance,
not supplier tolerances. Retain a continuous usable tail through at least
10.62 mm from the finished tip, with at most one pitch of incomplete thread
at that tip. Gauge the rest of that tail as UNC-2A.
The native model depicts catalogue fully-threaded geometry; inspection,
not that depiction, certifies the tail used by the worst-case reach stack.

Part frame: finished tip Y=0, axis +Y, bearing face Y=45.70.
"""

from _mcmaster_92314a253 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_DIMENSIONAL_TOLERANCES as CATALOG_DIMENSIONAL_TOLERANCES,
    CATALOG_STANDARD as CATALOG_STANDARD,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    THREAD_MAJOR_MAX,
    THREAD_MAJOR_MIN,
)

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
CHAMFER_WIDTH = 0.60
CHAMFER_WIDTH_TOLERANCE = 0.05
CHAMFER_ANGLE = 45.0
CHAMFER_ANGLE_TOLERANCE = 1.0

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
    "ChamferAngle": 4,
    "ThreadLengthMin": 5,
}
DIMENSION_CALLOUTS = {
    "CutLength": (
        "UNDER HEAD TO FINISHED TIP\n"
        "MATE: MHA-SM-002 KNIFE MOUNT\n"
        "SETS THREAD ENGAGEMENT AND TIP CLEARANCE"
    ),
    "ChamferWidth": "CUT-END CHAMFER",
    "ThreadLengthMin": (
        "#10-24 UNC-2A CONTINUOUS TAIL FROM TIP\n"
        "INCOMPLETE CUT-END THREAD 1 PITCH MAX\n"
        "ALL REMAINING TAIL FULL FORM"
    ),
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
