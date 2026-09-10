r"""Pure-data dimensional contract shared by the arbor-pedestal part and drawing.

The marked-dimension map lives here so a change rebuilds both the SLDPRT and the
SLDDRW recipes from one source (see build_arbor_pedestal.py for the geometry).
"""

from __future__ import annotations
from math import atan2, degrees, sqrt

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl


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
BORE_DIA = 9.55  # finished running bore for the 3/8 in cylinder-arbor journal
BORE_DIA_BAND = (0.03, 0.0)  # 9.550–9.580 mm running-bore limits
BORE_HEIGHT = 39.718  # v2 post journal axis: 6.35 platform + 33.368 boss height
_ROOT_HALF_WIDTH = FOOT_WIDTH / 2.0
_CENTER_RISE = BORE_HEIGHT - FOOT_HEIGHT
_TANGENT_DISC = sqrt(_ROOT_HALF_WIDTH**2 + _CENTER_RISE**2 - TOP_RADIUS**2)
_TANGENT_DENOM = _ROOT_HALF_WIDTH**2 + _CENTER_RISE**2
TAPER_TANGENT_X = (
    TOP_RADIUS**2 * _ROOT_HALF_WIDTH + TOP_RADIUS * _CENTER_RISE * _TANGENT_DISC
) / _TANGENT_DENOM
TAPER_TANGENT_Y = (
    BORE_HEIGHT
    + (-(TOP_RADIUS**2) * _CENTER_RISE + TOP_RADIUS * _ROOT_HALF_WIDTH * _TANGENT_DISC)
    / _TANGENT_DENOM
)
TAPER_ANGLE_DEG = degrees(
    atan2(_ROOT_HALF_WIDTH - TAPER_TANGENT_X, TAPER_TANGENT_Y - FOOT_HEIGHT)
)
SCREW_HOLE_SPEC = HoleSpec("clearance", "#4")
SCREW_HOLE_DIA = blind_cut_dia_mm(SCREW_HOLE_SPEC)

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "arbor_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=BORE_HEIGHT),
    ),
    # The foot seat mates the pedestal to harmonic-base: on a part that may be
    # left as-cast elsewhere, the one face that MUST be cut says so.
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"Width", "Depth"},
    "Foot": {"FootHt"},
    # BoreHeight plus a concentric R10 crown and tangent sides defines the
    # complete upright profile without redundant endpoint widths.
    "BoreProfile": {"BoreDia"},
}
