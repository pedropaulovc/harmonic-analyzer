r"""Dimensional contract shared by the crank-eccentric-bushing part and drawing.

PURE DATA, same shape as ``cone_tip_bushing_spec``: the part owns exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` and the fit bands
(``build_crank_eccentric_bushing``), and the drawing reads them back.

#906 R1: MHA-149 lines MHA-016's crank bore, and the crankshaft's 3/8 in core
runs in it.  Its bore is offset from its OD by the throw, so turning the
bushing in the post moves the crank axis on a circle of that radius about the
post bore.  At fit-up the bushing is turned by the wrench flats on its south
end until the 16T:64T mesh reads its acceptance at the tight spot, and is then
bonded; that is how the centre distance absorbs the whole mesh stack instead
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
ECCENTRICITY = 0.60
ECCENTRICITY_BAND = (0.025, -0.025)  # (upper, lower)
# The north end is set flush with the boss's spot face, where the 16T's south
# face bears; the south end stands SOUTH_PROTRUSION proud of the boss's south
# face so the fitter can turn the bushing.  The length is not a fit, so it
# prints at one place.
POST_BORE_LENGTH = 72.0  # MHA-016's crank boss, CRANK_BOSS_LENGTH at .X
SOUTH_PROTRUSION = 5.0
LENGTH = POST_BORE_LENGTH + SOUTH_PROTRUSION  # 77.0
# Two wrench flats on the protrusion, square to the throw so the throw never
# thins the wall under a flat.  Across-flats prints at .XX: an open-end wrench
# only needs the flats parallel.
FLATS_ACROSS = 13.5
FLATS_LENGTH = SOUTH_PROTRUSION
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
    "FlatsProfile": {"FlatsAcross"},
    "Flats": {"FlatsDepth"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2.  Three places on the OD, the bore and the throw: each carries
# an explicit band.  Two on the flats, one on the lengths (above).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {"ODDim": 3},
    "BoreProfile": {"BoreDiaDim": 3, "BoreOffsetDim": 3},
    "Body": {"Depth": 1},
    "FlatsProfile": {"FlatsAcross": 2},
    "Flats": {"FlatsDepth": 1},
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

# The sheet states its named exception itself (drawing-simplicity-policy.md,
# "Named exceptions"), so the blind review reads the thin wall as accepted.
WALL_EXCEPTION = "WALL UNDER TARGET AT THROW AND FLATS: ACCEPTED EXCEPTION (POST WEBS)."
DRAWING_NOTES = "\n".join(
    (
        f"BORE RUNS ON THE {SHAFT_MATE_NUMBER} SHAFT; OD SEATS IN THE "
        f"{POST_MATE_NUMBER} CRANK BORE.",
        WALL_EXCEPTION,
    )
)
