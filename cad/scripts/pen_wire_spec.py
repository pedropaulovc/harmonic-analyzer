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
        "1. STEEL WIRE <MOD-DIAM>0.8; STRAIGHT REST-POSE RUN.",
        "2. AMPLIFICATION WIRE 2: FROM THE MAGNIFYING-WHEEL RIM",
        "   GROOVE DOWN TO THE PEN ROD AT THE LOWER END.",
        "3. WHEEL-END RIM WRAP AND TIE-OFF KNOT SET AT ASSEMBLY.",
        "4. STRAIGHTEN FULL LENGTH; NO KINKS OR PERMANENT SET.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
