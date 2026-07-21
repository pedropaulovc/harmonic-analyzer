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
TOP_RADIUS = 10.0  # dome radius = strap half-width at the top
DOME_DIA = 2.0 * TOP_RADIUS  # 20.0: the round head around the clamp bore
BORE_DIA = 0.375 * MM_PER_IN  # 9.525: the 3/8 in cylinder-arbor journal
BORE_HEIGHT = 54.0  # arbor axis above the foot seat (drive height)
SCREW_THREAD = "#4"  # flange hold-down clearance hole
SCREW_CLEARANCE_DIA = 3.264

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    "BoreProfile": {"BoreHeight", "BoreDia"},
    "DomeProfile": {"DomeDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST STOCK; REMOVE AS-CAST SKIN.",
        "DATUM A IS FOOT SEAT. MATING ARBOR LIMITS DIA 9.505-9.525.",
        "TAPER FLANKS PROJECT TO 24.00 WIDTH AT DATUM A AND REACH 20.00",
        "AT THE BORE CENTERLINE; VISIBLE TAPER STARTS AT THE TOP OF THE",
        "5.00 FOOT (23.63 REF) AND TERMINATES AT THE DOME DIAMETER.",
        "STRAP 10.00 +/-0.10 THICK; ITS FACE FARTHEST FROM THE TOP-VIEW",
        "FLANGE HOLE IS FLUSH WITH THAT 16.00-DEEP FOOT FACE; 6.00 +/-0.10",
        "EXPOSED FLANGE REMAINS ON THE HOLE SIDE SHOWN IN THE TOP VIEW.",
        f"FLANGE HOLE DIA {SCREW_CLEARANCE_DIA:.3f} +0.10/-0.00 "
        f"({SCREW_THREAD} NORMAL CLEARANCE) THRU;",
        "AXIS ON THE 24.00 WIDTH CENTERLINE +/-0.05 AND 5.00 +/-0.10",
        "FROM THE FOOT CENTER PLANE TOWARD THE EXPOSED FLANGE.",
    )
)
