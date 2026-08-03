r"""Pure-data dimensional contract shared by the top-frame casting and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_top_frame`` imports the marked-
dimension NAME map + notes from here; ``draw_top_frame`` keeps exactly
``DRAWING_DIMENSIONS`` and imports the casting's plan geometry (column
stations, bore diameters) from ``build_top_frame`` for its view math.

2026-08-02 rederive (ch30 px measurement anchored on the 394x224 column pitch
+ GT bundle rescale + ch19 closeups): the ring absorbed the old top-crossbar
(full-height integral bar) and the gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side), grew its rails to 34.2/38.0, gained webbed
faces, proud corner bosses, side-screw taps, hanger-stud holes and the
west-rail fulcrum-keeper taps.
"""

from __future__ import annotations


OUTER_PROFILE_TOLERANCE_MM = 0.25


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The rail outside profile (OuterProfile Width/Depth) is marked;
# limits and the datum-controlled bore pattern stay together in the notes rather
# than being duplicated by isolated native diameter dimensions. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. GREEN-PAINTED GRAY IRON CASTING; MACHINE DATUM FACES, BORES AND",
        "   SEATS; CAST SURFACES ELSEWHERE, 1.5 MAX DRAFT, FILLETS R3 UNLESS NOTED.",
        "2. PLAN PROFILE: 428.20 X 262.00 OUTER RAIL RING; SIDE RAILS 34.20 WIDE,",
        "   FRONT/REAR RAILS 38.00 WIDE; CLEAR WINDOW 359.80 X 186.00 BETWEEN",
        "   STRAIGHT INNER FACES. INTEGRAL CROSSBAR 22.00 WIDE AT X -26.00..-4.00",
        "   SPANNING THE WINDOW, FLUSH BOTH FACES, 18X18 GUSSETS AT ALL FOUR",
        "   JUNCTIONS. RING BAND 36.50 TALL; ENVELOPE 446.20 +/-0.25 X 276.20",
        "   +/-0.25 X 47.30.",
        "3. 4X CORNER BOSSES DIA52.20, 47.30 TALL (PROUD 4.50 ABOVE / 6.30 BELOW",
        "   THE RAIL BAND), BORED DIA25.50 +0.05/0 THRU; POSITION <MOD-DIAM>0.20",
        "   A|B|C ON 394.00 X 224.00 BASIC PITCH.",
        "4. DATUM A = RAIL BOTTOM FACE; B = EAST (-X) OUTER RAIL FACE;",
        "   C = REAR OUTER RAIL FACE.",
        "5. WEBBED FACES: PANELS RECESSED 3.50 INTO EVERY INNER AND OUTER RAIL",
        "   FACE BETWEEN 8.00 TOP/BOTTOM FLANGES; FULL-THICKNESS LANDS AT BOSSES,",
        "   HUB RIB AND CROSSBAR JUNCTIONS. CAST FINISH INSIDE PANELS.",
        "6. GOOSENECK HUB, EAST RAIL AT Z +3.09: RIB 27.00 WIDE FULL HEIGHT,",
        "   BORE <MOD-DIAM>17.00 +0.20/0 THRU; UNDERSIDE BOSS DIA30 X 8.00 WITH",
        "   TWIN GUSSETS; DRILL + TAP 1/4-20 UNC-2B THRU RIB TO BORE ON THE BAND",
        "   MID-PLANE, 16X16X2 SPOT POCKET.",
        "7. 4X DRILL + TAP #10-24 UNC-2B X 14.00 DEEP INTO THE BOSS Z-FACES ON",
        "   THE BAND MID-PLANE (FRONT PAIR FROM FRONT, REAR PAIR FROM REAR),",
        "   DIA9.00 X 0.90 SPOT-FACE EACH.",
        "8. 2X <MOD-DIAM>13.49 (1/2 CLOSE) HANGER-STUD HOLES THRU THE CROSSBAR AT",
        "   Z -83.97 / +90.15; POSITION <MOD-DIAM>0.20 A|B|C.",
        "9. ALL BORES Ra 1.6. MASK DATUMS, BORES, BOSS END LANDS AND TAPPED",
        "   HOLES BEFORE COATING; DIMENSIONS/GD&T APPLY BEFORE COATING.",
        "10. 2X DRILL + TAP #10-24 UNC-2B X 10.00 DEEP INTO THE WEST RAIL TOP",
        "   FACE AT (X +199.90, Z +77.09 / -70.91): FULCRUM-KEEPER FEET.",
    )
)
INSPECTION_NOTES = "\n".join(
    (
        "INSPECTION NOTES — 4X BOSS OD/BORE:",
        "FIT LEAST-SQUARES CYLINDERS TO EACH EXPOSED OD ARC",
        "AND FULL BORE.",
        "USE 8 EQUALLY SPACED AXIAL SECTIONS OVER 47.30 AND",
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


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "column-bore true position": "0.20",
    "column-boss true position": "0.20",
    "gooseneck-bore true position": "0.20",
    "hanger-stud-hole true position": "0.20",
}
