r"""Dimensional contract shared by the cone-tip-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


OUTER_DIA = 6.0
BORE_DIA = 0.03125 * 25.4  # 0.79375: the cone shaft's 1/32 in tip stub
BORE_DIA_BAND = (0.05, 0.00)  # (upper, lower) deviations
LENGTH = 4.0
LENGTH_TOLERANCE_MM = 0.03

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

DRAWING_NOTES = "\n".join(
    (
        "AVOID BORE BELL-MOUTH.",
        "TURN OD/FACES IN ONE SETUP; DRILL 1/32 IN (0.794) BORE THRU; SLIP FIT ON TIP "
        "STUB.",
    )
)


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "bushing OD runout": "0.05",
    "bushing end-face parallelism": "0.03",
}
