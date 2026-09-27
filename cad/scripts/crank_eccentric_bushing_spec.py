r"""Dimensional contract shared by the crank-eccentric-bushing part and drawing.

PURE DATA, same shape as ``cone_tip_bushing_spec``: the part owns exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` and the fit bands
(``build_crank_eccentric_bushing``), and the drawing reads them back.

#906 R1: MHA-149 lines MHA-016's crank bore, and the crankshaft's 3/8 in core
runs in it.  Its bore is offset from its OD by the throw, so turning the
bushing in the post moves the crank axis on a circle of that radius about the
post bore.  At fit-up the bushing is turned by the wrench flats on its south
grip head until the 16T:64T mesh reads its acceptance at the tight spot, and is
then bonded; that is how the centre distance absorbs the whole mesh stack instead
of a tight print band.  ``crank_mesh_stack`` asserts the throw reaches both
ends of that stack.
"""

from __future__ import annotations

import math

from _gtol_spec import CylinderFace, GeometricControl, PartDatum
from _surface_finish import MACHINED_UM, SurfaceFinishControl


# The OD seats in MHA-016's Ø14.6 H7 crank bore (cone_pivot_post_spec
# CRANK_BORE_DIA) and the bore runs on MHA-026's 3/8 in core (crank_hub_geometry
# SHAFT_DIA) at the shaft_in_bushing clearance.  Hard-coded rather than
# imported so neither neighbour's spec is a rebuild input of this one; the
# offline test pins both.
OUTER_DIA = 14.6
BORE_DIA = 9.575
# The OD is g6 in the post's H7 (Main, 2026-09-26; ISO 286, 10-18 mm): 0.006
# to 0.035 of clearance, so the fitter can turn it by hand and then bond it.
# Its lower limit is where the thin side of the wall is taken.
OD_BAND = (-0.006, -0.017)  # (upper, lower) deviations from OUTER_DIA: g6
# The throw, bore axis to OD axis, and its print band.  Its low end is the
# fit-up reach crank_mesh_stack asserts at both ends of the mesh stack; its
# high end is where the thin side of the wall is taken (build asserts it).
# The bore runs straight through, so the throw is the same at both ends.
ECCENTRICITY = 0.625
ECCENTRICITY_BAND = (0.025, -0.025)  # (upper, lower)
# The north end is set flush with the boss's spot face, where the 16T's south
# face bears.  South of the boss the bushing carries a grip head the fitter
# turns it by, standing HEAD_STANDOFF off the boss's south face: the head is a
# grip, not a stop, so the bore's direction never depends on how square that
# face is.  The overall and head lengths print at .XX so the stand-off holds
# with the boss length at its .X row (the offline test takes that worst case).
# The boss is 2.5 shorter than it was harvested (its spot face retreated from
# the 64T, cone_pivot_post_spec CRANK_SPOT_FACE_RETREAT); its south face did
# not move, so neither does the head: the bushing is 2.5 shorter with it.
POST_BORE_LENGTH = 69.5  # MHA-016's crank boss, CRANK_BOSS_LENGTH at .X
HEAD_STANDOFF = 2.0
HEAD_LENGTH = 6.0
HEAD_DIA = 18.0
SOUTH_PROTRUSION = HEAD_STANDOFF + HEAD_LENGTH
LENGTH = POST_BORE_LENGTH + SOUTH_PROTRUSION  # 77.5
# Two wrench flats on the head, square to the throw so the throw never thins
# the wall under a flat; 16 across flats takes a stock open-end wrench.
# Across-flats prints at .XX: the wrench only needs the flats parallel.  The
# flats run the head's length and no further, since the body is smaller than
# the flats are across.
FLATS_ACROSS = 16.0
FLATS_LENGTH = HEAD_LENGTH
WALL_TARGET_MM = 2.0  # drawing-simplicity-policy rule 12
WALL_FLOOR_MM = 1.5
# The throw's direction on the flats' 90-degree clocking is held by the title
# block's angular grade; at that limit the throw leans this far toward a flat.
FLATS_CLOCKING_TOLERANCE_DEG = 1.0
FLATS_THROW_LEAN = math.sin(math.radians(FLATS_CLOCKING_TOLERANCE_DEG))

# The bore's direction to the OD is part of the crank axis's angle budget
# (crank_mesh_stack): the bore is bored in a second, offset chucking, so its
# parallelism to the OD is held by one diametral frame to the OD (rule 3's
# crank-mesh allowlist entry).  Over the 77 length it is 0.037 deg.
BORE_PARALLELISM_MM = 0.05
PART_DATUMS = (PartDatum("A", CylinderFace(OUTER_DIA, contains_y_mm=LENGTH / 2.0)),)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "bore_parallelism",
        "parallelism",
        f"{BORE_PARALLELISM_MM:.2f}",
        CylinderFace(BORE_DIA, contains_y_mm=LENGTH / 2.0),
        datums=("A",),
        tolerance_zone="diametral",
    ),
)

# Rule 5: the bore runs on the shaft, so it carries the finish.  The OD is a
# bonded seat on a turned part and carries nothing.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bushing_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=LENGTH / 2.0),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"ODDim"},
    "BoreProfile": {"BoreDiaDim", "BoreOffsetDim"},
    "Body": {"Depth"},
    "HeadProfile": {"HeadDiaDim"},
    "Head": {"HeadDepth"},
    "FlatsProfile": {"FlatsAcross"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2.  Three places on the OD, the bore and the throw: each carries
# an explicit band.  Two on the flats and on the two lengths that set the
# head's stand-off (above); one on the head's diameter, which only clears.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {"ODDim": 3},
    "BoreProfile": {"BoreDiaDim": 3, "BoreOffsetDim": 3},
    "Body": {"Depth": 2},
    "HeadProfile": {"HeadDiaDim": 1},
    "Head": {"HeadDepth": 2},
    "FlatsProfile": {"FlatsAcross": 2},
}

DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )

# The mates, quoted only to identify them (rule 6).  Hard-coded, not read from
# ``_config.parts``, so no other part's yaml is a rebuild input; the offline
# test checks them against the registry.
SHAFT_MATE_NUMBER = "MHA-026"
POST_MATE_NUMBER = "MHA-016"

# The thin wall at the throw is the policy's named MHA-149 exception
# (drawing-simplicity-policy.md, "Named exceptions"; user, R1,
# 2026-09-26).  The policy requires the sheet to state it, but exception and
# ruling labels never print, so the build appends the shortfall as a plain
# fact (``build_crank_eccentric_bushing.WALL_NOTE``, from its print-worst
# wall) and this row and comment keep the provenance.
DRAWING_NOTES = (
    f"BORE RUNS ON THE {SHAFT_MATE_NUMBER} SHAFT; OD SEATS IN THE "
    f"{POST_MATE_NUMBER} CRANK BORE."
)
