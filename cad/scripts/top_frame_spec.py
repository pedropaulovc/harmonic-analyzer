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
        "1. MACHINE FROM SOLID STOCK TO FINISHED PROFILE; NO DRAFT OR CAST FILLETS.",
        "2. PLAN PROFILE: 416.00 X 281.42 OUTER RAIL RING; 372.00 X 237.42 CLEAR OPENING",
        "   MEANS STRAIGHT INNER-RAIL-FACE SPACING ONLY; CORNER BOSSES INTRUDE.",
        "   4X FULL DIA48.00 BOSSES ON BORE AXES; NO BLENDS OR",
        "   CHAMFERS AT BOSS/RAIL INTERSECTIONS. THESE EDGES ARE EXEMPT FROM",
        "   THE TITLE-BLOCK EDGE BREAK; LEAVE SHARP, 0.25 MAX ROOT RADIUS. ENVELOPE",
        "   442.00 +/-0.25 X 307.42 +/-0.25 X 41.00 +/-0.10; RAILS 22.00",
        "   +/-0.10 WIDE. ALL FEATURES FULL THICKNESS.",
        "3. DATUM A = BOTTOM FACE; B = LEFT OUTER RAIL FACE; C = REAR OUTER RAIL FACE.",
        "   REAR-LEFT BORE AXIS BASIC 11.00 FROM B/C; OTHERS ON 394.00 X 259.42 BASIC PITCH.",
        "4. COLUMN BORES 4X <MOD-DIAM>25.50 +0.05/0 THRU; POSITION <MOD-DIAM>0.20 A|B|C.",
        "5. BOSSES 4X <MOD-DIAM>48.00 +/-0.10; DIMENSIONS/GD&T APPLY BEFORE COATING.",
        "   BOSS OD/BORE COAXIALITY AND WALL CHECK: SEE INSPECTION NOTES.",
        "6. GOOSENECK BORE <MOD-DIAM>17.00 +0.20/0 THRU; AXIS BASIC ON",
        "   LEFT RAIL, 123.00 BASIC FROM DATUM C; POSITION",
        "   <MOD-DIAM>0.20 A|B|C. ALL BORES Ra 1.6.",
        "7. MASK DATUM A/B/C FACES, ALL BORES, 4X BOSS ANNULI (BOTH PLANAR END",
        "   LANDS), AND 4X CYLINDRICAL ODS OF THE BOSSES.",
    )
)
INSPECTION_NOTES = "\n".join(
    (
        "INSPECTION NOTES — 4X BOSS OD/BORE:",
        "FIT LEAST-SQUARES CYLINDERS TO EACH EXPOSED OD ARC",
        "AND FULL BORE.",
        "USE 8 EQUALLY SPACED AXIAL SECTIONS OVER 41.00 AND",
        "8 EQUALLY SPACED ACCESSIBLE-ARC POINTS PER SECTION.",
        "AXIS OFFSET 0.05 MAX = GREATEST AXIS SEPARATION AT",
        "EITHER END PLANE.",
        "RADIAL WALL = POINT-TO-BORE-AXIS DISTANCE MINUS",
        "FITTED BORE RADIUS.",
        "MAX-MIN RADIAL WALL THICKNESS SHALL NOT EXCEED 0.10",
        "ACROSS ALL 64 OD POINTS. THIS CHECK IS ADDITIONAL TO",
        "NATIVE SIZE/POSITION CONTROLS.",
    )
)
TOP_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:4"
