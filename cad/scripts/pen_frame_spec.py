r"""Pure-data dimensional contract shared by the pen frame and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_pen_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_pen_frame`` keeps exactly
``DRAWING_DIMENSIONS`` and imports the ring's envelope from ``build_pen_frame``
for its view math.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The outer ring envelope (trimmed width + height) and the window
# opening (inner span X/Y) are shown on the front ring face; the rail widths
# derive from those and are echoed in the notes.  The #4-40 set-screw hole is
# drilled UP the bottom rail with its axis IN the front-view plane (edge-on), so
# it is carried in a note, not a fragile in-plane hole callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"OuterSpanX", "OuterHeightDim", "InnerSpanX", "InnerSpanY"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block; it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. BRASS YOKE (STIRRUP) WRAPPING THE PEN V-BLOCK + MARKER.",
        "2. FLAT BRASS RING 10 THICK; WINDOW RAILS: FAR SIDE 4,",
        "   NEAR SIDE 3.25 (AFTER TRIM, NOTE 3), ENDS 5.",
        "3. NEAR (PLATEN-SIDE) EDGE TRIMMED BACK 0.75 (SEE WIDTH DIM).",
        "4. SET-SCREW HOLE #4-40 TAPPED UP THRU THE BOTTOM RAIL, INTO",
        "   THE WINDOW (TOP RAIL SPARED), TO SET THE PEN ANGLE.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
