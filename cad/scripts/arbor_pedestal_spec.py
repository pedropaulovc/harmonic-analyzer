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
# The #4 NORMAL clearance the wizard ACTUALLY cuts on this seat: the created
# feature's ThruHoleDiameter reads 3.2512 (build log "1x #4 clearance
# (Ø3.251)"; the screw-hole volume gate's +0.3 mm^3 offset was exactly this
# hole). _holes.CLEARANCE_MM pins 3.264 for ("#4", "normal") — a
# wizard-database dump this seat no longer matches — so resolver-sourcing
# would print a masking note (3.26) contradicting the sheet's own native hole
# callout (3.25). build_arbor_pedestal asserts the created hole matches this
# pin to 0.005 mm, failing loud if the seat's wizard table ever moves again.
SCREW_CLEARANCE_DIA = 3.2512

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
        "MATING ARBOR LIMITS DIA 9.505-9.525 (REF).",
        "2X STRAIGHT FLANKS JOIN BOXED 24.00 X 5.00 FOOT TOP CORNERS TO",
        "DIA 20.00 CROWN HORIZONTAL CL; NO TANGENCY; KEEP JUNCTIONS SHARP.",
        "PROFILE 0.10 A | B: CROWN, 2X FLANKS, FOOT TOP + RIGHT SIDE.",
        "BOXED 12.00 LOCATES BOTH BORE AND FLANGE-HOLE AXES FROM DATUM B.",
        "BOXED 6.00/16.00 LOCATE STRAP NEAR/FAR FACES FROM D; PROFILE 0.10",
        "A | B | D; RESULTING STRAP THICKNESS 10.00 REF.",
        "DIMENSIONS AND GD&T APPLY BEFORE COATING; MASK ARBOR BORE, "
        f"DIA {SCREW_CLEARANCE_DIA:.2f}",
        "HOLE, FOOT SEAT A, LEFT SIDE B, AND PROFILE-CONTROLLED SURFACES.",
    )
)
