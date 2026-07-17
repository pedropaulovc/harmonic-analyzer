r"""Dimensional contract shared by the cone-tip-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations


OUTER_DIA = 6.0
BORE_DIA = 0.03125 * 25.4  # 0.79375: the cone shaft's 1/32 in tip stub
LENGTH = 4.0

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
