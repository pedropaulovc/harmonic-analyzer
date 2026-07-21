r"""Pure-data dimensional contract shared by the top-frame ring and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_top_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_top_frame`` keeps exactly
``DRAWING_DIMENSIONS`` and imports the ring's plan geometry (column stations,
bore diameters) from ``build_top_frame`` for its view math.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The rail outside profile (OuterProfile Width/Depth) is marked;
# limits and the datum-controlled bore pattern stay together in the notes rather
# than being duplicated by isolated native diameter dimensions. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. MACHINE FROM SOLID STOCK TO THE FINISHED PROFILE SHOWN; NO DRAFT",
        "   OR CAST FILLETS.",
        "2. OVERALL FINISHED ENVELOPE 442.00 +/-0.25 X 272.00 +/-0.25 X",
        "   41.00 +/-0.10. OPPOSING OUTER RAIL FACES 416.00 X 246.00; RAILS",
        "   22.00 +/-0.10 WIDE. ALL RAILS AND BOSSES FULL 41.00 THICKNESS.",
        "3. DATUM A = BOTTOM FACE; B = LEFT OUTER RAIL FACE; C = LOWER",
        "   OUTER RAIL FACE. FOUR COLUMN-BORE AXES ARE BASIC 11.00 FROM",
        "   B/C WITH 394.00 X 224.00 BASIC PITCH.",
        "4. COLUMN BORES 4X <MOD-DIAM>25.50 +0.05/0 THRU; POSITION",
        "   <MOD-DIAM>0.20 A|B|C. BOSSES 4X <MOD-DIAM>48.00 +/-0.10.",
        "5. EACH BOSS/BORE PAIR: MAX-MIN RADIAL WALL THICKNESS AT ANY",
        "   CROSS SECTION OVER FULL 41.00 THICKNESS SHALL NOT EXCEED 0.10.",
        "6. GOOSENECK BORE <MOD-DIAM>17.00 +0.20/0 THRU; AXIS BASIC ON",
        "   LEFT COLUMN-BORE CENTRELINE AND MIDWAY BETWEEN LEFT BORE AXES;",
        "   POSITION <MOD-DIAM>0.20 A|B|C. ALL BORES Ra 1.6.",
        "7. MASK DATUM A/B/C FACES, ALL BORES AND 4X BOSS ANNULI",
        "   OD48.00/ID25.50 DURING COATING.",
    )
)
TOP_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:4"
