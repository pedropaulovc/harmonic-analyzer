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
BORE_DIA = 0.375 * MM_PER_IN  # 9.525: the 3/8 in cylinder-arbor journal
BORE_DIA_BAND = (0.055, 0.025)  # running bore; (upper, lower) deviations
BORE_HEIGHT = 39.718  # v2 post journal axis: 6.35 platform + 33.368 boss height
SCREW_HOLE_SPEC = HoleSpec("clearance", "#4")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)

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
    # BoreHeight is recreated in the drawing between the actual foot-seat edge
    # and the bore circle so its witness cannot collapse onto the nearby flange top.
    "BoreProfile": {"BoreDia"},
    # The straight flanks terminate at this modeled 20 mm top width. The crown
    # radius is drawn separately, so both primitives are unambiguous at the bench.
    "StrapProfile": {"StrapTopWidth"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST STOCK; REMOVE AS-CAST SKIN.",
        "MASK ARBOR BORE, FOOT SEAT, AND HOLD-DOWN HOLE BEFORE COATING.",
    )
)
