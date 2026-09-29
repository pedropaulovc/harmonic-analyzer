r"""Dimensional contract shared by the cone-tip-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation. Recreated under
``cad/docs/drawing-simplicity-policy.md``: the part owns exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` and the bore band
(``build_cone_tip_bushing.BORE_DIA_BAND``, derived from the fit class),
``draw_cone_tip_bushing`` keeps the same names and reads the decimal places
back, and ``test_cone_tip_bushing_drawing`` fails the moment one side drifts.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


OUTER_DIA = 6.0
BORE_DIA = 0.0625 * 25.4  # 1.5875: round bore around the flatted shaft tip
LENGTH = 4.0  # thrust spacer between T006 and the feeler-set tip block

# The bore can run against the shaft tip's remaining cylindrical arc; the
# D-flat now continues through the tip. Keep the bore finish on that bearing
# arc, not on the free OD or thrust faces.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bushing_bore",
        MACHINED_UM,
        CylinderFace(BORE_DIA, contains_y_mm=LENGTH / 2.0),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"ODDim"},
    "BoreProfile": {"BoreDiaDim"},
    "Body": {"Depth"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: the places a dimension prints are part of the tolerance it
# carries, so the part build applies them (``apply_drawing_precision``) and the
# drawing only reads them back (``assert_imported_precision``). Three places
# on the bore: it carries the running-fit band. One on the free OD; three on
# the length, which locates the thrust face of the solid gear stack under the
# tip block's feeler (the .X band would consume the set gap).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {"ODDim": 1},
    "BoreProfile": {"BoreDiaDim": 3},
    "Body": {"Depth": 3},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
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

# The seat's owner, quoted only to identify the mate (rule 6). Hard-coded
# rather than read from ``_config.parts``: a cross-part config read would make
# cone-gear-shaft.yaml a rebuild dependency of this bushing. The offline test
# checks it against the registry.
SHAFT_MATE_NUMBER = "MHA-014"

# Rule 6: name the mating shaft tip and its slip clearance without implying
# a continuous round journal. The bore stays round around the shaft's D-flat.
DRAWING_NOTES = (
    f"BORE SLIP-FITS THE {SHAFT_MATE_NUMBER} CONE GEAR SHAFT TIP."
)
