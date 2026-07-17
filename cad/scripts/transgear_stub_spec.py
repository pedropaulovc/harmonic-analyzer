r"""Pure-data dimensional contract shared by the transgear stud and drawing.

PURE DATA: keep the turned-part nominals and marked-dimension map here so a
change rebuilds both the SLDPRT and SLDDRW recipes without making the drawing
import the part build implementation.
"""

from __future__ import annotations


MM_PER_IN = 25.4

BASE_DIA = 0.375 * MM_PER_IN  # 9.525 machine-standard stock (low)
BASE_LEN = 9.1  # bracket plate (4) + gap + latch big hub (z -125.9..-135)
SEAT_DIA = 5.0  # turned-down gear seat (feed pinion + disc bores)
SEAT_LEN = 13.8  # feed pinion 9.5 + disc 3 + slack (z -135..-148.8)
COLLAR_DIA = 14.0
COLLAR_LEN = 4.0

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StubProfile": {
        "BaseDia",
        "SeatDia",
        "CollarDia",
        "BaseLength",
        "SeatLength",
        "CollarLength",
    },
}

DRAWING_NOTES = "\n".join(
    (
        "TURN FROM 16 MM (5/8 IN) BAR IN ONE SETUP; SEAT AND COLLAR "
        "CONCENTRIC WITH BASE.",
    )
)
