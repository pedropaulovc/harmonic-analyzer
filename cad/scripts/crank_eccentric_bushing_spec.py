r"""Dimensional contract shared by the crank-eccentric-bushing part and drawing.

PURE DATA, same shape as ``cone_tip_bushing_spec``: the part owns exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` and the fit bands
(``build_crank_eccentric_bushing``), and the drawing reads them back.

#906 A2 (user, 2026-09-26): MHA-149 lines MHA-016's crank bore, and the
crankshaft runs in it.  Its bore is offset from its OD by the throw, so turning
the bushing in the post moves the crank axis on a circle of that radius about
the post bore.  At fit-up the bushing is turned until the 16T:64T mesh reads its
acceptance at the tight spot and is then bonded; that is how the centre
distance absorbs the whole mesh stack instead of a tight print band.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


# The OD seats in MHA-016's Ø15.45 H7 crank bore (cone_pivot_post_spec
# CRANK_BORE_DIA), the bore runs on MHA-026's journal (crankshaft_spec
# JOURNAL_BORE_DIA).  Hard-coded rather than imported so neither neighbour's
# spec is a rebuild input of this one; the offline test pins both.
OUTER_DIA = 15.45
BORE_DIA = 11.438
# The throw, bore axis to OD axis.  2e = 0.90 covers the 0.809 crank-mesh stack
# (the user's A2 ruling).  The bore is centred on its length and runs straight
# through, so the throw is the same at both ends.
ECCENTRICITY = 0.45
# The throw's print band.  At its low end 2e is still 0.85, over the stack; at
# its high end the thin side of the wall stays over the floor (build asserts
# both).
ECCENTRICITY_BAND = (0.025, -0.025)  # (upper, lower)
# Its length is not a fit: the north end is set flush with the boss's spot
# face, where the 16T's south face bears, and the south end only has to keep
# the journal's outboard land inside the bushing.  One place: the loosest row.
LENGTH = 72.0
WALL_FLOOR_MM = 1.5  # drawing-simplicity-policy rule 12

# Rule 5: the bore runs on the journal, so it carries the finish.  The OD is a
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
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2.  Three places on the OD, the bore and the throw: each carries
# an explicit band.  One on the length (above).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {"ODDim": 3},
    "BoreProfile": {"BoreDiaDim": 3, "BoreOffsetDim": 3},
    "Body": {"Depth": 1},
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

DRAWING_NOTES = (
    f"BORE RUNS ON THE {SHAFT_MATE_NUMBER} JOURNAL; OD SEATS IN THE "
    f"{POST_MATE_NUMBER} CRANK BORE."
)
