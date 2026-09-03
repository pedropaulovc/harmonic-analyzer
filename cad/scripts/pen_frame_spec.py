r"""Pure-data dimensional contract shared by the pen frame and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_pen_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_pen_frame`` keeps exactly
``DRAWING_DIMENSIONS`` and imports the ring's envelope from ``build_pen_frame``
for its view math.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The outer ring envelope is shown on the front ring face; the
# window derives from the independently specified rail widths without closing
# a redundant dimension chain.  The #4-40 set-screw hole is drilled UP the
# bottom rail (its axis in the front-view plane), so it is dimensioned where it
# is a visible circle: the BOTTOM view carries its native callout and its two
# stations (from the trimmed left face, from the front face), drawing-added on
# real edges. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"OuterSpanX", "OuterHeightDim"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The tapped hole is
# entirely on the bottom view (callout + stations), so the one line left is
# the rail schedule the window derives from.
DRAWING_NOTES = "RAILS: LEFT 3.25, RIGHT 4.00, ENDS 5.00 WIDE; WINDOW THRU. DO NOT MIRROR."
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
RIGHT_VIEW_NOTE = "RIGHT-SIDE VIEW SCALE 2:1"
BOTTOM_VIEW_NOTE = "BOTTOM VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
