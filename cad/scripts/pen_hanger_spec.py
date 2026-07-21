r"""Pure-data dimensional contract shared by the pen hanger and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_pen_hanger`` imports the marked-
dimension NAME map + notes from here; ``draw_pen_hanger`` imports the same plus
the strap/block geometry from ``build_pen_hanger`` for its view math, and keeps
exactly ``DRAWING_DIMENSIONS`` across its per-view keep map.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The guide-block width and the tapered strap (bottom width, top
# run, rise) are marked -- all Front-plane sketch dims, so they import cleanly
# into the single front profile view.  The 5.4 square pen-rod channel, the block
# depth/reach and the #6-32 hanger hole are carried in the notes / native callout
# (the channel dim lives on a Top-plane sketch and the hole is a native Hole
# Wizard feature, neither a clean front-view import). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth"},
    "StrapProfile": {"StrapBotWidth", "StrapTopRun", "StrapTaperDy"},
}

# Lines kept short (<~60 chars) so the note block stays clear of the title block
# (x >= 0.264 m) and the tall front view; it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. GUIDE BLOCK 12.00 W X 12.00 H X 16.60 DEEP. CUT 5.40",
        "   +0.10/0.00 SQUARE HOLE THRU 12.00 H; INTERNAL R0.25 MAX.",
        "   SIDE WALLS 3.30 NOM; WALL-THICKNESS DIFFERENCE 0.10 MAX.",
        "   HOLE CENTER 4.00 +/-0.05 FROM FRONT DEPTH FACE; FRONT",
        "   IS THE FACE OPPOSITE THE STRAP-FLUSH BACK FACE.",
        "2. STRAP 3.00 THICK: 10.00 WIDE AT BLOCK, 16.00 AT TOP,",
        "   OVER 69.70 VERTICAL RISE. TOP-EDGE CENTER IS 8.00 LEFT",
        "   OF BLOCK CENTERLINE +/-0.10; DO NOT MIRROR. LOWER STRAP",
        "   EDGES ARE 1.00 +/-0.10 INBOARD OF BLOCK SIDES.",
        "3. SILVER-BRAZE WITH AWS A5.8 BAg-7; STRAP FLUSH WITH",
        "   BACK DEPTH FACE. CONTINUOUS 1.0 MIN FRONT FILLET ACROSS",
        "   FULL 10.00 WIDTH; COPLANAR BACK SEAM HAS A CONTINUOUS",
        "   VISIBLE BRAZE LINE. NO VISIBLE GAPS OR VOIDS.",
        "4. DRILL + TAP #6-32 UNC-2B THRU 3.00 STRAP FROM BACK.",
        "   AXIS 5.00 +/-0.05 VERTICALLY BELOW TOP EDGE + 7.50",
        "   +/-0.05 HORIZONTALLY RIGHT OF FRONT-VIEW TOP-LEFT CORNER.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
TOP_VIEW_NOTE = "TOP VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
