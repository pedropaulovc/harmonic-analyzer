r"""Pure-data dimensional contract shared by the gooseneck clamp and drawing.

PURE DATA, no SolidWorks/COM imports (see ``crankshaft_spec`` for the reference
split). ``build_gooseneck_clamp`` imports the marked-dimension NAME map + notes
from here; ``draw_gooseneck_clamp`` imports the block/bore nominals from
``build_gooseneck_clamp`` for its view math and keeps exactly
``DRAWING_DIMENSIONS`` across its per-view keep maps.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The block plan envelope (Width x Height, on the Front sketch) and
# the vertical clamp bore (BoreDia, on the Top sketch) are marked; the block
# depth, the square pinch-screw head, and the clamp function are carried in the
# notes -- a 30 mm block dimensioned in full would repeat what the envelope and
# the bore callout already fix. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Height"},
    "BoreProfile": {"BoreDia"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. FINISHED BLOCK 30 WIDE X 29 HIGH X 24 DEEP. CAST 2-DEG",
        "   DRAFT; R2 ON CAST EDGES EXCEPT WHERE SHOWN; MACHINE BOTTOM",
        "   FACE + BORE.",
        "2. BORE <MOD-DIAM>16.50 +0.05/0.00 THRU, CENTERED IN WIDTH +",
        "   DEPTH; AXIS PERPENDICULAR TO BOTTOM FACE WITHIN 0.05/29.",
        "3. FROM +DEPTH FACE, DRILL + TAP 1/4-20 UNC-2B THRU TO BORE;",
        "   AXIS CENTERED IN WIDTH AND 15 ABOVE BOTTOM FACE.",
        "4. SUPPLY 1/4-20 X 16 SQUARE-HEAD SCREW, 10 SQ X 6 HEAD.",
        "5. MASK BORE + BOTTOM FACE DURING COATING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
