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

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. SUPPLY STRAIGHT CUT-WIRE BLANK <MOD-DIAM>0.80 +/-0.02 X",
        "   62.70 +/-0.20 LONG. LENGTH IS BEFORE ASSEMBLY FORMING.",
        "2. EACH END FACE SQUARE TO THE WIRE AXIS WITHIN 0.05.",
        "   THE TITLE-BLOCK R0.25/CHAMFER 0.25 LIMIT DOES NOT APPLY",
        "   TO WIRE ENDS; END EDGE R0.05 MAX.",
        "3. AXIS STRAIGHT WITHIN 0.50 OVER FULL LENGTH: LAY FREE",
        "   WIRE ON A FLAT SURFACE PLATE AND ROLL THROUGH ONE FULL",
        "   TURN; 0.50 MAX GAP AT ANY ORIENTATION.",
        "   FORM + TERMINATE ENDS AT ASSEMBLY.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
