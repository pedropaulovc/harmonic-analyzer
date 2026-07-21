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
        "1. GRAY-IRON CASTING; MACHINE THE BORE AND MATING FACES.",
        "2. CLAMPS THE <MOD-DIAM>16 GOOSENECK POST IN A <MOD-DIAM>16.5",
        "   VERTICAL BORE THRU (SLIDING SPRING-TENSION ADJUST).",
        "3. BLOCK 30 WIDE X 29 TALL X 24 DEEP.",
        "4. SIDE-ENTRY SQUARE-HEAD PINCH SCREW (10 SQ HEAD SHOWN);",
        "   DRILL + TAP AT ASSEMBLY TO PINCH THE POST IN ITS SOCKET.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
