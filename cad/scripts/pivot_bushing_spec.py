r"""Dimensional contract shared by the pivot-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations


OUTER_DIA = 10.0
BORE_DIA = 6.5
LENGTH = 4.5565

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia", "BoreDia"},
    "Bushing": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "AVOID BORE BELL-MOUTH.",
        "TURN OD/FACES IN ONE SETUP; DRILL UNDERSIZE AND REAM BORE THRU.",
        "19 PCS SET THE CHANNEL PITCH: MAKE AS ONE BATCH, ONE SETTING; LENGTHS "
        "MATCHED WITHIN 0.03 ACROSS THE SET.",
    )
)
