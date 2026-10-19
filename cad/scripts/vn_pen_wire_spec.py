r"""Pure-data dimensional contract shared by the pen wire and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_vn_pen_wire`` imports the marked-
dimension NAME map + notes from here; ``draw_vn_pen_wire`` keeps exactly
``DRAWING_DIMENSIONS`` for its single-view import.
"""

from __future__ import annotations

from _mcmaster_9666k56 import SKU
from _mcmaster_9666k56_reference import SUPPLIER_REFERENCE_DIMENSIONS

# The finished rest run retains its own length; the supplier nominal diameter
# belongs only to the separate, sketch-only stock cross-section, never the
# installed 0.8 mm envelope.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "Wire": {"Depth"},
    **SUPPLIER_REFERENCE_DIMENSIONS,
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        f"1. PURCHASED WIRE: McMASTER-CARR {SKU}.",
        "2. LENGTH SHOWN IS THE STRAIGHT REST RUN, NOT A CUT",
        "   LENGTH.",
        "3. RIM WRAP, EYE TIE-OFF, AND DEVELOPED CUT LENGTH ARE",
        "   NOT DEFINED BY THE SOURCE MODEL. DO NOT RELEASE",
        "   UNTIL THOSE DETAILS ARE SPECIFIED.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
