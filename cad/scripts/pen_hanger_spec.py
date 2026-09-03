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

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Lines kept short
# (<~60 chars) so the mid-band block stays clear of the isometric.
DRAWING_NOTES = "\n".join(
    (
        "5.40 SQ CHANNEL THRU BLOCK, 4.00 FROM THE FRONT FACE;",
        "FILE TO A SLIDING FIT ON THE PEN ROD.",
        "SILVER-BRAZE STRAP TO BLOCK BACK FACE, FLUSH. DO NOT MIRROR.",
        "DRILL + TAP #6-32 UNC THRU STRAP FROM BACK, 5.00 BELOW TOP EDGE.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
TOP_VIEW_NOTE = "TOP VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
