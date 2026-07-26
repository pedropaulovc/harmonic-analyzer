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
# The #4 NORMAL clearance the wizard ACTUALLY cuts on this seat.
#
# 2026-07-26: the seat's wizard table moved BACK to the canonical value and this
# pin followed it, 3.2512 -> 3.264. History, because the direction matters: the
# pin was originally 3.2512 because the seat's created feature read
# ThruHoleDiameter 3.2512 (build log "1x #4 clearance (Ø3.251)") while
# _holes.CLEARANCE_MM pins 3.264 for ("#4", "normal") -- so resolver-sourcing
# would have printed a masking note (3.26) contradicting the sheet's own native
# hole callout (3.25). The seat now cuts 3.2639, i.e. it AGREES with
# _holes.CLEARANCE_MM, so that contradiction is gone: note and callout both read
# 3.26.
#
# The guard that caught this worked exactly as written -- build_arbor_pedestal
# asserts the created hole matches this pin to 0.005 mm. It stayed silent for
# months only because part:arbor_pedestal was being restored from the remote
# cache; the first real rebuild after a _common.py change surfaced it at once.
# Kept as a literal rather than sourced from _holes.CLEARANCE_MM on purpose:
# this module is pure data with no imports, and pulling in _holes would drag
# _common/_telemetry into its dependency closure and re-key both the part and
# the drawing.
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
        f"MATING ARBOR LIMITS DIA {BORE_DIA - 0.02:.3f}-{BORE_DIA:.3f} (REF).",
        f"2X STRAIGHT FLANKS JOIN BOXED {FOOT_WIDTH:.2f} X {FOOT_HEIGHT:.2f} "
        "FOOT TOP CORNERS TO",
        f"DIA {DOME_DIA:.2f} CROWN HORIZONTAL CL; NO TANGENCY; KEEP JUNCTIONS SHARP.",
        "PROFILE 0.10 A | B: CROWN, 2X FLANKS, FOOT TOP + RIGHT SIDE.",
        f"BOXED {FOOT_WIDTH / 2.0:.2f} LOCATES BOTH BORE AND FLANGE-HOLE AXES FROM DATUM B.",
        f"BOXED {FOOT_DEPTH - STRAP_T:.2f}/{FOOT_DEPTH:.2f} LOCATE STRAP "
        "NEAR/FAR FACES FROM D; PROFILE 0.10",
        f"A | B | D; RESULTING STRAP THICKNESS {STRAP_T:.2f} REF.",
        "DIMENSIONS AND GD&T APPLY BEFORE COATING; MASK ARBOR BORE, "
        f"DIA {SCREW_CLEARANCE_DIA:.2f}",
        "HOLE, FOOT SEAT A, LEFT SIDE B, AND PROFILE-CONTROLLED SURFACES.",
    )
)
