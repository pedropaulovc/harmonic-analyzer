r"""Pure-data dimensional contract shared by the tube frame column and drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_tube_frame`` imports the tube nominals + the marked-dimension
NAME map from here; ``draw_tube_frame`` imports the same nominals for its view
math and keeps exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations


MM_PER_IN = 25.4

# --- Hollow steel column (legacy part; book ch. 5-6). Ø1.0 in tube, 0.12 in
# wall, capped flush with the top-frame ring. OD rederived from the ch30 eight
# views (Ø23.8 +/-1.0 -> 1 in stock); wall + length as in build_tube_frame. ---
OUTER_DIA = 1.0 * MM_PER_IN       # 25.4
OUTER_DIA_BAND = (0.00, -0.05)  # (upper, lower) deviations
WALL_THICKNESS = 0.12 * MM_PER_IN  # 3.048
INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS  # 19.304
COLUMN_LENGTH = 989.9  # top flush with the top-frame ring top face
COLUMN_LENGTH_TOLERANCE_MM = 0.25

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_tube_frame`` marks exactly these; ``draw_tube_frame`` keeps
# exactly their union across its per-view keep maps. The finished OD and column
# length are acceptance dimensions. The stock-result ID is deliberately not
# dimensioned; the title-block material specification owns the tube wall. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia"},
    "Column": {"Depth"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block; it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. ID IS THE AS-PROCURED STOCK RESULT; NOT AN ACCEPTANCE DIMENSION;",
        "   DO NOT MACHINE THE ID EXCEPT THE TITLE-BLOCK EDGE BREAK.",
        "2. OD ACCEPTANCE REQUIRES THE SIZE LIMITS / ASME RULE 1 AND THE",
        "   FULL-LENGTH CYLINDRICITY CONTROL; FORM DOES NOT OVERRIDE SIZE.",
        "3. SELECT STOCK WITH AS-RECEIVED OD 25.40 MIN; FINISH TO SIZE/FORM.",
        "4. TOP/BOTTOM ORIENTATION IS NONFUNCTIONAL; BOTH END FACES ARE CONTROLLED.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"
