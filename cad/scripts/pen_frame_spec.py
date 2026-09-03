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
# a redundant dimension chain.  The #4-40 set-screw hole is
# drilled UP the bottom rail with its axis IN the front-view plane (edge-on), so
# it is carried in a note, not a fragile in-plane hole callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"OuterSpanX", "OuterHeightDim"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Short lines keep the
# left-anchored block clear of the title block.
DRAWING_NOTES = "\n".join(
    (
        "RAILS: LEFT 3.25, RIGHT 4.00, ENDS 5.00 WIDE; WINDOW THRU. DO NOT MIRROR.",
        "DRILL AND TAP #4-40 UNC UP THE BOTTOM RAIL INTO THE WINDOW,",
        "12.25 FROM THE LEFT OUTER FACE, ON THE MID-DEPTH PLANE.",
    )
)
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
RIGHT_VIEW_NOTE = "RIGHT-SIDE VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
