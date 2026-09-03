r"""Pure-data dimensional contract shared by the pen wire and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_pen_wire`` imports the marked-
dimension NAME map + notes from here; ``draw_pen_wire`` keeps exactly
``DRAWING_DIMENSIONS`` for its single-view import.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the straight rest-run LENGTH (the Wire extrude depth) is
# marked; the Ø0.8 wire diameter is a note (a 0.8 mm circle is below the ink
# width of the view, and the book wire is hair-thin -- a renderable stand-in,
# low confidence), and the form is a plain straight run. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "Wire": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "STRAIGHT CUT-WIRE BLANK, <MOD-DIAM>0.80; ENDS CUT SQUARE.",
        "FORM AND TERMINATE THE ENDS AT ASSEMBLY.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
