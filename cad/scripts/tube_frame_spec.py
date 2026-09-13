r"""Pure-data dimensional contract shared by the tube frame column and drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_tube_frame`` imports the tube nominals + the marked-dimension
NAME map from here; ``draw_tube_frame`` imports the same nominals for its view
math and keeps exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from frame_attachment_spec import (
    BASE_SCREW_Y,
    COLUMN_BOTTOM_Y,
    TUBE_CROSS_HOLE_DIAMETER,
    TUBE_CUT_LENGTH,
    TUBE_TOP_CHAMFER,
    TOP_SCREW_Y,
)


MM_PER_IN = 25.4

# --- Regular open steel tube. The lower end enters the base socket; the upper
# end receives a separately purchased recessed cap. The tube cut length follows
# the shared installed cap stack, keeping the finished cap top at Y=1044.8. ---
OUTER_DIA = 1.0 * MM_PER_IN  # 25.4
OUTER_DIA_BAND = (0.00, -0.05)  # (upper, lower) deviations
WALL_THICKNESS = 0.12 * MM_PER_IN  # 3.048
INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS  # 19.304
COLUMN_LENGTH = TUBE_CUT_LENGTH
COLUMN_LENGTH_TOLERANCE_MM = 0.25
TOP_END_CHAMFER = TUBE_TOP_CHAMFER

# --- Matched cross-drilling stations, part-local Y from the inserted end. ---
LOWER_CROSS_HOLE_Y = BASE_SCREW_Y - COLUMN_BOTTOM_Y
UPPER_CROSS_HOLE_Y = TOP_SCREW_Y - COLUMN_BOTTOM_Y
CROSS_HOLE_DIAMETER = TUBE_CROSS_HOLE_DIAMETER

# --- Marked-dimension contract: feature -> parametric dimensions kept by the
# drawing. The hole diameter is shown once with a 2-station THRU BOTH WALLS
# callout; both axial stations remain independently inspectable from the bottom. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia"},
    "Column": {"Length"},
    "CrossHoleProfile": {"LowerHoleY", "UpperHoleY", "CrossHoleDia"},
    "TopEndBreak": {"TopChamfer"},
}

# Part-specific facts that cannot be inferred from the native views/dimensions.
DRAWING_NOTES = "\n".join(
    (
        "ID AS SUPPLIED.",
        "MATCH-DRILL WITH BASE MHA-035 AND TOP FRAME MHA-077.",
        "MATCH-MARK COLUMN, CORNER AND ORIENTATION.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:10"

# Frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
