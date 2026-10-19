"""Pure McMaster 91410A538 dimensions for its diagnostic replica.

Separate from the COM recipe and part-save wrapper to limit cache blast radius.
MHA-FR-VN-52 is 91410A540 since 2026-10-12 (``_mcmaster_91410a540``).
"""

from __future__ import annotations

SQ_MAJOR_R = 6.35 / 2.0
SQ_LEN = 15.875
SQ_HH = 4.7625
SQ_PITCH = 1.27
SQ_CUP_RIM_R = 1.739789  # Sketch2 solved rim; 45/59 deg from its dims
SQ_CHAMFER_DEG = 75.0  # head chamfer cones (Sketch3 D1/D2)

SQUARE_SET_SCREW_SIZE = (
    SQ_MAJOR_R,
    SQ_LEN,
    SQ_HH,
    SQ_PITCH,
    SQ_CUP_RIM_R,
    SQ_CHAMFER_DEG,
)
