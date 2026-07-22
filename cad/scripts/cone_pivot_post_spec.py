r"""Pure-data dimensional contract shared by the cone pivot post and drawing."""

from __future__ import annotations

import math


MM_PER_IN = 25.4

# Round green casting standing on the swing platform: the cone shaft's big-end
# journal bore (along Z at BORE_HEIGHT) and the crank pedestal's oblique crank
# bore (at CRANK_BORE_HEIGHT, tipped INCLINE_DEG off vertical, offset east). See
# build_cone_pivot_post.py for the derivation; this module is only the drawing's
# single source of the marked dimensions.
BLOCK_DIA = 24.0  # round column outside diameter
BLOCK_HEIGHT = 100.5  # column height, foot (platform seat) to top
BORE_DIA = 9.550  # 9.545..9.555 finished bore over shaft max 9.525
BORE_HEIGHT = 47.65  # journal-bore axis above the foot
# Mating cone-shaft OD limits in the journal fit (the cone_gear_shaft datum-A
# seat that rides this bore) -- a distinct feature from CRANK_SHAFT_MAX_DIA
# despite the shared 3/8" nominal.
JOURNAL_SHAFT_MAX_DIA = 9.525  # upper limit
JOURNAL_SHAFT_MIN_DIA = JOURNAL_SHAFT_MAX_DIA - 0.02  # 9.505: lower limit (0.02 band)
CRANK_SHAFT_MAX_DIA = 9.525
CRANK_BORE_DIA = CRANK_SHAFT_MAX_DIA + 0.5  # 10.025: 0.25 radial clearance
CRANK_BORE_HEIGHT = 85.835  # crank-bore axis above the foot
CRANK_BORE_OFFSET = 0.95  # crank-bore axis east of the column axis
INCLINE_DEG = 12.5182  # crank bore tips this far off the column's vertical axis

# Datum-coordinate definition of the crank-bore theoretical axis.  The point is
# the unique point on the axis closest to datum B; the direction is a unit
# vector.  Signs refer to the coordinate directions stated in the boxed drawing
# note, so neither the sheet image scale nor an inferred hidden-line quadrant is
# part of the manufacturing definition.
_CRANK_SIN = math.sin(math.radians(INCLINE_DEG))
_CRANK_COS = math.cos(math.radians(INCLINE_DEG))
CRANK_AXIS_POINT_X = -CRANK_BORE_OFFSET * _CRANK_COS
CRANK_AXIS_POINT_Z = -CRANK_BORE_OFFSET * _CRANK_SIN
CRANK_AXIS_DIRECTION_X = -_CRANK_SIN
CRANK_AXIS_DIRECTION_Z = _CRANK_COS
CRANK_AXIS_SECOND_POINT_DISTANCE = 100.0
CRANK_AXIS_POINTS = (
    ("P", CRANK_AXIS_POINT_X, CRANK_BORE_HEIGHT, CRANK_AXIS_POINT_Z),
    (
        "Q",
        CRANK_AXIS_POINT_X
        + CRANK_AXIS_SECOND_POINT_DISTANCE * CRANK_AXIS_DIRECTION_X,
        CRANK_BORE_HEIGHT,
        CRANK_AXIS_POINT_Z
        + CRANK_AXIS_SECOND_POINT_DISTANCE * CRANK_AXIS_DIRECTION_Z,
    ),
)
CRANK_AXIS_ORIENTATION_NOTE = "\n".join(
    (
        "O = A/B INTERSECTION; +Y ALONG B AWAY FROM A",
        "+X RIGHT; +Z PARALLEL C, DOWN IN UPPER PLAN",
    )
)

# The oblique, offset crank bore is a running-clearance feature on a cast column.
# Its size is an arrowed feature callout and its theoretical axis is the BASIC
# two-point coordinate table above, controlled by a native position frame.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockDia"},
    "Block": {"BlockHt"},
    "BoreProfile": {"BoreDia", "BoreZ"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST ROUND STOCK; REMOVE AS-CAST SKIN.",
        "DATUM A IS FOOT SEAT; B IS COLUMN OD; C IS JOURNAL-BORE AXIS.",
        f"JOURNAL BORE LIMITS DIA {BORE_DIA - 0.005:.3f}-{BORE_DIA + 0.005:.3f}; "
        "FINISH RA 1.6;",
        f"AXIS BASICALLY INTERSECTS DATUM AXIS B AT BOXED {BORE_HEIGHT:.2f} ABOVE A.",
        f"MATING SHAFT LIMITS DIA {JOURNAL_SHAFT_MIN_DIA:.3f}-{JOURNAL_SHAFT_MAX_DIA:.3f}.",
        "JOURNAL IS LOWER CIRCLE; CRANK BORE IS UPPER ELLIPSE IN FRONT VIEW.",
    )
)
