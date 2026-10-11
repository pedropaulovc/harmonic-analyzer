"""Pure McMaster 91410A538 dimensions shared by recipe and assembly placement.

Separate from the COM recipe and part-save wrapper to limit cache blast radius.
"""

from __future__ import annotations

SQ_MAJOR_R = 6.35 / 2.0
SQ_LEN = 15.875
SQ_HH = 4.7625
SQ_PITCH = 1.27
SQ_CUP_RIM_R = 1.739789  # Sketch2 solved rim; 45/59 deg from its dims
SQ_CHAMFER_DEG = 75.0  # head chamfer cones (Sketch3 D1/D2)


HEAD_AF = 2.0 * SQ_MAJOR_R
HEAD_H = SQ_HH
SHANK_DIA = 2.0 * SQ_MAJOR_R
SHANK_LEN = SQ_LEN
