r"""Pure-data dimensional contract shared by the top-frame ring and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_top_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_top_frame`` keeps exactly
``DRAWING_DIMENSIONS`` and imports the ring's plan geometry (column stations,
bore diameters) from ``build_top_frame`` for its view math.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The overall ring footprint (OuterProfile Width/Depth), one column
# clamp bore (Ø25.5) and the gooseneck bore (Ø17) are marked; the rail width, ring
# height, boss OD and column pitch are carried in the notes (they are relations or
# repeated features that would collide as duplicate-named imported dims). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth"},
    "BoreProfile": {"C0Dia"},
    "GooseneckProfile": {"Dia"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. AS-CAST SURFACES +/-0.8; NO DRAFT MODELLED. SOLID-STOCK",
        "   FABRICATION IS PERMITTED.",
        "2. RECTANGULAR RING: RAILS 22 WIDE X 41 TALL; CORNER BOSSES <MOD-DIAM>48.",
        "3. COLUMN CLAMP BORES 4X <MOD-DIAM>25.5 ON 394 X 224 PITCH (+/-0.10),",
        "   CLAMPING THE <MOD-DIAM>25.4 COLUMNS FLUSH AT THE RING TOP FACE.",
        "4. GOOSENECK BORE <MOD-DIAM>17 THRU EAST RAIL AT MID-SPAN FOR THE",
        "   COUNTER-SPRING POST.",
    )
)
TOP_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
