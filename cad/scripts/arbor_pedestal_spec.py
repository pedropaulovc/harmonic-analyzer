r"""Pure-data dimensional contract shared by the arbor-pedestal part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_arbor_pedestal.py for the geometry).
"""

from __future__ import annotations


MM_PER_IN = 25.4

# Black japanned gray-iron bearing post that clamps the south end of the
# stationary cylinder arbor: a low rectangular foot flange, a tapered strap
# rising to a semicircular dome around the arbor clamp bore, and a #4 flange
# hold-down hole.
FOOT_WIDTH = 24.0  # X plan width of the foot flange
FOOT_DEPTH = 16.0  # Z plan depth of the foot flange
FOOT_HEIGHT = 5.0  # low flange height under the strap
STRAP_T = 10.0  # strap depth; far face is coplanar with the foot far face
TOP_RADIUS = 10.0  # dome radius = strap half-width at the top
DOME_DIA = 2.0 * TOP_RADIUS  # 20.0: the round head around the clamp bore
BORE_DIA = 0.375 * MM_PER_IN  # 9.525: the 3/8 in cylinder-arbor journal
BORE_HEIGHT = 54.0  # arbor axis above the foot seat (drive height)
SCREW_THREAD = "#4"  # flange hold-down clearance hole
SCREW_CLEARANCE_DIA = 3.264

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    # BoreHeight is recreated in the drawing between the actual datum-A foot
    # edge and the bore circle so its BASIC witness cannot collapse onto the
    # visually adjacent top of the flange.
    "BoreProfile": {"BoreDia"},
    "DomeProfile": {"DomeDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST STOCK; REMOVE AS-CAST SKIN.",
        "DATUM A IS FOOT SEAT; DATUM B IS LEFT FOOT SIDE FACE SHOWN.",
        "MATING ARBOR LIMITS DIA 9.505-9.525.",
        "2X STRAIGHT FLANKS RUN FROM TOP CORNERS OF BOXED 24.00 X 5.00 FOOT",
        "TO DIA 20.00 CROWN AT ITS HORIZONTAL CENTERLINE; NO TANGENCY.",
        "PROFILE 0.10 A-B APPLIES TO CROWN, 2X FLANKS, FOOT TOP + RIGHT SIDE;",
        "DO NOT BREAK THE CROWN/FLANK OR FLANK/FOOT PROFILE JUNCTIONS.",
        "BOXED 12.00 LOCATES BOTH BORE AND FLANGE-HOLE AXES FROM DATUM B.",
        "BOXED 6.00 LOCATES STRAP NEAR FACE FROM D; PROFILE 0.10 TO D.",
        "BOXED 16.00 LOCATES COPLANAR FOOT/STRAP FAR FACES FROM D;",
        "PROFILE 0.10 TO D; RESULTING STRAP THICKNESS 10.00 REF.",
    )
)
