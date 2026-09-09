r"""Pure-data dimensional contract shared by the arbor-pedestal part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_arbor_pedestal.py for the geometry).
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


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
BORE_DIA_BAND = (0.055, 0.025)  # running bore; (upper, lower) deviations
BORE_HEIGHT = 39.718  # v2 post journal axis: 6.35 platform + 33.368 boss height
SCREW_HOLE_SPEC = HoleSpec("clearance", "#4")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)
# Existing drawing view geometry consumes this descriptive public name.
SCREW_CLEARANCE_DIA = SCREW_HOLE_DIA

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
    ),
)

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
        f"DIA {SCREW_HOLE_DIA:.2f}",
        "HOLE, FOOT SEAT A, LEFT SIDE B, AND PROFILE-CONTROLLED SURFACES.",
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "datum-A seat flatness": "0.05",
    "datum-B side perpendicularity": "0.05",
    "arbor bore true position": "0.10",
    "controlled exterior surface profile": "0.10",
    "datum-D face perpendicularity": "0.05",
    "flange-hole true position": "0.20",
    "strap near-face profile": "0.10",
    "coplanar far-face profile": "0.10",
}
