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
        "1. MACHINE ALL SIX OUTER FACES OF CASTING BLANK TO",
        "   30.00 +/-0.10 W X 29.00 +/-0.10 H X 24.00 +/-0.10 D.",
        "2. BORE <MOD-DIAM>16.50 +0.05/0.00 THRU TOP + BOTTOM. AXIS",
        "   15.00 +/-0.05 FROM LEFT FACE AND 12.00 +/-0.05 FROM",
        "   FRONT FACE. OUT-OF-SQUARE TO BOTTOM 0.05 MAX OVER 29.00.",
        "3. FRONT FACE SHOWN IS SCREW-ENTRY FACE. DRILL + TAP",
        "   1/4-20 UNC-2B THRU TO BORE; AXIS 15.00 +/-0.05 FROM",
        "   LEFT FACE + 15.00 +/-0.05 ABOVE BOTTOM. 3.0 MIN FULL THREAD.",
        "4. SUPPLY 1/4-20 UNC-2A X 16.00 UNDER-HEAD-LENGTH SCREW,",
        "   FULLY THREADED; 10.00 +/-0.13 SQ X 6.00 +/-0.13 HEAD;",
        "   FLAT POINT, AISI 1018 STEEL, BLACK OXIDE.",
        "5. MASK BORE + BOTTOM FACE DURING COATING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
