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


# --- Marked-dimension contract. The plan keeps the outside profile; the
# section keeps the purchased-cap recess diameter/depth. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth"},
    "CapRecessProfile": {"CapRecessDia"},
    "CapRecesses": {"CapRecessDepth"},
}

# Two linked note blocks keep the existing geometry legible while the section
# view exposes the interrupted cross-thread path.
DRAWING_NOTES = "\n".join(
    (
        "1. GREEN-PAINTED GRAY IRON CASTING; MACHINE FINISHED FACES, BORES, SEATS;",
        "   CAST ELSEWHERE, 1.5 MAX DRAFT. T-ROOT FILLETS R3; TOP-FACE RIM EDGES",
        "   C2.00 X 45 DEG; ALL OTHER CAST EDGES (BAND BOTTOM, BOSSES) SHARP.",
        "2. PLAN PROFILE: 428.20 X 262.00 OUTER RAIL RING; SIDE RAILS 34.20 WIDE,",
        "   FRONT/REAR RAILS 38.00 WIDE; CLEAR WINDOW 359.80 X 186.00 BETWEEN",
        "   STRAIGHT INNER FACES. INTEGRAL CROSSBAR 22.00 WIDE AT X -26.00..-4.00",
        "   SPANNING THE WINDOW, FLUSH BOTH FACES, 18X18 GUSSETS AT ALL FOUR",
        "   JUNCTIONS. RING BAND 36.50 TALL; ENVELOPE 446.20 +/-0.25 X 276.20",
        "   +/-0.25 X 47.30.",
        "3. 4X CORNER BOSSES DIA52.20, 47.30 TALL (PROUD 4.50 ABOVE / 6.30 BELOW",
        "   THE RAIL BAND), BORED DIA25.50 +0.05/0 THRU; MATCH FIT MHA-083",
        "   TUBE-FRAME COLUMN FOR 0.10 TO 0.20 DIAMETRAL CLEARANCE, WITHOUT BINDING;",
        "   BORES ON 394.00 X 224.00 RECTANGULAR PITCH CENTRED ON THE RAIL RING.",
        "   4X CAP-SKIRT RECESSES DIA27.50 +0.20/0 X 16.30 +0.30/0 DEEP FROM",
        "   BOSS TOP; FIT INTACT MHA-133 CAP. CAP SEATS ON TUBE END, NOT RECESS FLOOR.",
        "4. WEBBED FACES: 12.70 WEB CENTRED ON EACH RAIL -- PANELS RECESSED",
        "   10.75 INTO THE SIDE-RAIL FACES / 12.65 INTO THE FRONT/REAR-RAIL",
        "   FACES FROM 8.00 BELOW THE TOP FACE THROUGH THE BOTTOM EDGE (TOP",
        "   FLANGE ONLY -- THE WEB THINS AND STAYS THIN TO THE BOTTOM);",
        "   FULL-THICKNESS LANDS AT BOSSES, HUB RIB AND CROSSBAR JUNCTIONS.",
        "   CAST FINISH INSIDE PANELS.",
    )
)
DRAWING_NOTES_B = "\n".join(
    (
        "5. GOOSENECK HUB, EAST RAIL AT Z +3.09: RIB 27.00 WIDE FULL HEIGHT,",
        "   BORE <MOD-DIAM>17.00 +0.20/0 THRU; UNDERSIDE BOSS DIA30 X 8.00 WITH",
        "   TWIN GUSSETS; DRILL + TAP 1/4-20 UNC-2B THRU RIB TO BORE ON THE BAND",
        "   MID-PLANE, 16X16X2 SPOT POCKET.",
        "6. 4X #10-32 UNF-2B BOTTOMING TAP: 46.00 FULL THREAD / 48.00",
        "   CYLINDRICAL TAP-DRILL DEPTH FROM THE BOSS Z-FACE SPOT SEAT;",
        "   DIA9.00 X 0.90 SPOT-FACE EACH. SEE SECTION A-A.",
        "7. 2X <MOD-DIAM>13.49 (1/2 CLOSE) HANGER-STUD HOLES THRU THE CROSSBAR AT",
        "   Z -83.97 / +90.15.",
        "8. ALL BORES Ra 1.6, TOP ENDS BROKEN C1.00 X 45 DEG. MASK BORES,",
        "   BOSS END LANDS AND TAPPED HOLES BEFORE COATING;",
        "   DIMENSIONS APPLY BEFORE COATING.",
        "9. 2X DRILL + TAP #8-32 UNC-2B X 10.00 DEEP INTO THE WEST RAIL TOP",
        "   FACE AT (X +199.90, Z +77.09 / -70.91): FULCRUM-KEEPER FEET.",
    )
)
INSPECTION_NOTES = ""
SECTION_VIEW_NOTE = "SECTION A-A SCALE 1:4"
TOP_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 1:4"

# Frame parts carry no datums or feature-control frames under the drawing
# simplicity policy.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {}
