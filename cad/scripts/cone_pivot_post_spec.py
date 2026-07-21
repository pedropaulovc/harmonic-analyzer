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

CRANK_AXIS_BASIC_NOTE = "\n".join(
    (
        "BASIC CRANK-BORE AXIS DEFINITION (mm)",
        "O = INTERSECTION OF DATUM A AND DATUM AXIS B",
        "+Y ALONG B AWAY FROM A; +Z PARALLEL C, DOWN IN UPPER PLAN",
        "+X RIGHT IN UPPER PLAN",
        f"LINE = ({CRANK_AXIS_POINT_X:.3f}, {CRANK_BORE_HEIGHT:.3f}, "
        f"{CRANK_AXIS_POINT_Z:.3f})",
        f"     + t({CRANK_AXIS_DIRECTION_X:.5f}, 0, "
        f"+{CRANK_AXIS_DIRECTION_Z:.5f})",
    )
)

# The oblique, offset crank bore is a running-clearance feature on a cast column.
# Its size is an arrowed feature callout and its theoretical axis is the boxed
# point-vector definition above, controlled by a native position frame.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockDia"},
    "Block": {"BlockHt"},
    "BoreProfile": {"BoreDia", "BoreZ"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST ROUND STOCK; REMOVE AS-CAST SKIN.",
        "DATUM A IS FOOT SEAT; B IS COLUMN OD; C IS JOURNAL-BORE AXIS.",
        "JOURNAL BORE LIMITS DIA 9.545-9.555; FINISH RA 1.6;",
        "AXIS BASICALLY INTERSECTS DATUM AXIS B AT BOXED 47.65 ABOVE A.",
        "MATING SHAFT LIMITS DIA 9.505-9.525.",
        "JOURNAL IS LOWER CIRCLE; CRANK BORE IS UPPER ELLIPSE IN FRONT VIEW.",
    )
)
