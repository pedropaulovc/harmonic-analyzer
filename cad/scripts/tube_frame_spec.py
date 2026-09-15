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
WALL_THICKNESS = 0.12 * MM_PER_IN  # 3.048
INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS  # 19.304
COLUMN_LENGTH = TUBE_CUT_LENGTH
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

TOP_END_CALLOUT = "TOP OD EDGE; MHA-133 CAP\nMUST SEAT FULLY BY HAND"

# Part-specific assembly acceptance that native dimensions cannot express.
DRAWING_NOTES = "\n".join(
    (
        "MATCH-MARK EACH COLUMN,",
        "CORNER AND ORIENTATION.",
        "FIT BASE MHA-035 AND TOP MHA-077.",
        "SET TOP CROSS-BORE AXIS HEIGHT",
        "PER FRAME ASSEMBLY MHA-A04;",
        "MAINTAIN HEIGHT DURING FIT.",
        "FINAL MATCH-CUT EACH IDENTIFIED TUBE",
        "TO ACTUAL BASE/TOP/CAP STACK:",
        "INTACT MHA-133 CAPS FULLY SEATED,",
        "SKIRTS CLEAR OF RECESS FLOORS.",
        "MATCH-DRILL UPPER STATION AT",
        "SET HEIGHT WITH TOP MHA-077;",
        "LOWER STATION WITH BASE MHA-035.",
        "THRU BOTH WALLS; RETAIN MATCH MARKS.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:10"

# Frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
