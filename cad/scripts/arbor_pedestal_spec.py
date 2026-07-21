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

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    "BoreProfile": {"BoreHeight", "BoreDia"},
    "DomeProfile": {"DomeDia"},
    "ScrewHole": {"ScrewZ"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE ALL SURFACES SHOWN FROM CONTINUOUS-CAST STOCK.",
        "DATUM A IS FOOT SEAT. BORE/DOME HEIGHTS ARE AXIS-TO-A.",
        "ARBOR BORE DIA 9.525 +/-0.010 THRU THE 10.00 STRAP;",
        "REAM STRAIGHT, AXIS 54.00 +/-0.05 ABOVE AND PARALLEL TO A.",
        f"FLANGE HOLE {SCREW_THREAD} NORMAL CLEARANCE THRU: AXIS ON THE",
        "24.00 WIDTH CENTERLINE AND 5.00 +/-0.10 FROM FOOT CENTER PLANE",
        "TOWARD THE EXPOSED FLANGE.",
    )
)
