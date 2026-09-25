r"""Top-down rocker-support screw (McMaster 92240A539) nominals.

1/4-20 UNC-2A, 5/8 in under-head length, fully threaded, ASME B18.2.1.
PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread identity and the head/shank/bearing dims the frame
assembly and the harmonic base's hold-down seats read. The vendor dims are the
named constants of ``diagnostics/diag_build_92240A539.py`` (SolidWorks-free at
import). Consumers read them here, not from ``build_lag_screw``, whose stock
build recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from diagnostics.diag_build_92240A539 import (
    HEX_HEIGHT_MM,
    HEX_WIDTH_MM,
    LENGTH_MM,
    MAJOR_DIAMETER_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
)

HEAD_AF = HEX_WIDTH_MM
HEAD_H = HEX_HEIGHT_MM
SHANK_DIA = MAJOR_DIAMETER_MM
SHANK_LEN = LENGTH_MM
THREAD_LEN = LENGTH_MM
THREAD_SIZE = "1/4-20"
THREAD_CLASS = "2A"
THREAD_PITCH = PITCH_MM
BEARING_OFFSET = WASHER_DEPTH_MM
