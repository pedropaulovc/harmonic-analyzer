r"""Dimensional contract shared by the lever-bushing part and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations


OUTER_DIA = 12.0
BORE_DIA = 6.5
LENGTH = 4.0565

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "AnnulusProfile": {"OuterDia", "BoreDia"},
    "Bushing": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: DIAMETERS +/-0.05. DEBURR; BREAK EDGES 0.15 MAX; AVOID "
        "BORE BELL-MOUTH.",
        "TURN OD/FACES IN ONE SETUP; DRILL UNDERSIZE AND REAM BORE THRU.",
    )
)
