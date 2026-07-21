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
        "1. FINISHED DEPTH 10.00 +/-0.10. FRONT VIEW AS SHOWN: LEFT",
        "   RAIL 3.25 WIDE, RIGHT RAIL 4.00 WIDE, END RAILS 5.00.",
        "2. LEFT OUTER EDGE IS THE 0.75 TRIMMED EDGE; DO NOT MIRROR.",
        "3. DRILL + TAP #4-40 UNC-2B THRU BOTTOM RAIL INTO WINDOW.",
        "   HOLE AXIS 10.25 FROM LEFT OUTER EDGE AND CENTERED IN DEPTH",
        "   (5.00 FROM EITHER DEPTH FACE). TOP RAIL MUST REMAIN INTACT.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
RIGHT_VIEW_NOTE = "RIGHT-SIDE VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
