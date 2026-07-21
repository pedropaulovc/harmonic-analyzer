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
        "1. MACHINE FROM SOLID STOCK TO THE FINISHED PROFILE SHOWN; NO DRAFT",
        "   OR CAST FILLETS.",
        "2. RECTANGULAR RING: RAILS 22.00 WIDE X 41.00 TALL; CORNER BOSSES",
        "   <MOD-DIAM>48.00.",
        "3. COLUMN BORES 4X <MOD-DIAM>25.50 +0.05/-0.00 THRU ON 394.00 X 224.00",
        "   PITCH (+/-0.10); CENTRE PATTERN ON OUTER ENVELOPE WITHIN 0.20.",
        "4. GOOSENECK BORE <MOD-DIAM>17.00 +0.20/-0.00 THRU LEFT RAIL IN PLAN",
        "   VIEW; CENTRE AT RAIL MID-SPAN WITHIN 0.10.",
    )
)
TOP_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
