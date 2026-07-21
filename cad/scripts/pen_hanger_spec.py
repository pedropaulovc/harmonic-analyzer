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
        "1. FLAT STEEL STRAP HANGER, 3 THICK.",
        "2. GUIDE BLOCK 12 X 12 X 16.6 DEEP; 5.4 SQUARE CHANNEL",
        "   THRU (VERTICAL) FOR THE 5 SQUARE PEN ROD.",
        "3. STRAP TAPERS 10 -> 16 WIDE OVER A 69.7 RISE TO THE",
        "   WHEEL-SUPPORT BAR; LEANS MACHINE-EAST (SEE ISO).",
        "4. HANGER-SCREW HOLE #6-32 TAPPED THRU THE STRAP FROM",
        "   BEHIND; SEE CALLOUT.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
