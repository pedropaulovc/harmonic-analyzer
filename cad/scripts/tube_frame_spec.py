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
WALL_THICKNESS = 0.12 * MM_PER_IN  # 3.048
INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS  # 19.304
COLUMN_LENGTH = 989.9  # top flush with the top-frame ring top face

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_tube_frame`` marks exactly these; ``draw_tube_frame`` keeps
# exactly their union across its per-view keep maps. The two annulus diameters
# are on-axis sketch dimensions; the column LENGTH is the extrude depth, named
# and marked in the build so it imports into the length view. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia", "BoreDia"},
    "Column": {"Depth"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block; it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "STANDARD 1 IN OD x 0.12 IN WALL STEEL TUBE STOCK.",
        "POLISH OD FULL LENGTH; NO FLUTES, FLATS OR STEPS.",
        "BOTH ENDS FACED SQUARE TO AXIS A WITHIN 0.10; DEBURR BORE.",
        "TOP END SEATS FLUSH IN THE TOP-FRAME CORNER BOSS (Ø25.5 BORE).",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 2:1"
LENGTH_VIEW_NOTE = "LENGTH VIEW SCALE 1:5"
