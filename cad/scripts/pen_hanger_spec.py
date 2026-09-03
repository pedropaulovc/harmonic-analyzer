r"""Pure-data dimensional contract shared by the pen hanger and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_pen_hanger`` imports the marked-
dimension NAME map + notes from here; ``draw_pen_hanger`` imports the same plus
the strap/block geometry from ``build_pen_hanger`` for its view math, and keeps
exactly ``DRAWING_DIMENSIONS`` across its per-view keep map.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  FRONT view (Front-plane sketches): the guide block's width and
# height, the tapered strap's bottom width, top run, rise and the right edge's
# lean (StrapTaperDx -- with the two widths it fixes both sloping edges).  TOP
# view (Top-plane sketch): the 5.4 square pen-rod channel's two sides.  The
# block depth, the strap thickness, the channel's two stations and the #6-32
# hanger hole's stations are drawing-added on real edges; the hole size is a
# native Hole Wizard callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockWidth", "BlockDepth"},
    "ChannelProfile": {"ChannelWidth", "ChannelDepth"},
    "StrapProfile": {"StrapBotWidth", "StrapTaperDx", "StrapTaperDy", "StrapTopRun"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Lines kept short
# (<~68 chars) so the mid-band block stays clear of the isometric.  Every
# number is on a view; the three lines are the bench fit (naming the mating
# rod), the brazed joint's registration (the two faces that are flush) and
# the strap foot's centring, the one relationship no single dimension states.
DRAWING_NOTES = "\n".join(
    (
        "CHANNEL: FILE TO A SLIDING FIT ON THE PEN ROD (MATES WITH MHA-051).",
        "SILVER-BRAZE THE STRAP TO THE BLOCK, BACK FACES FLUSH.",
        "STRAP FOOT CENTRED ON THE BLOCK WIDTH.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
TOP_VIEW_NOTE = "TOP VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
