r"""Top-down rocker-support screw nominals, at its catalog row's SKU.

1/4-20 UNC-2A, fully threaded, ASME B18.2.1; the 2026-09-25 machinist
review specified the 3/4 in 92240A540 over the 5/8 in 92240A539.
PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread identity and the head/shank/bearing dims the frame
assembly and the harmonic base's hold-down seats read. The vendor dims are the
named constants of ``diagnostics/diag_build_92240A539.py`` (SolidWorks-free at
import). Consumers read them here, not from ``build_lag_screw``, whose stock
build recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from diagnostics import diag_build_92240A539, diag_build_92240A540
from diagnostics.diag_build_92240A539 import (
    HEX_HEIGHT_MM,
    HEX_WIDTH_MM,
    MAJOR_DIAMETER_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
)

# The 2026-09-25 machinist review specified the 3/4 screw: the 5/8
# (92240A539) engaged the base 1.456D, under 1.5D. The frame placement and the
# base seats are sized for this SKU, so it is pinned here rather than read from
# the catalog row (which would fold that row into every consumer's key);
# build_lag_screw refuses a catalog row that names another SKU.
SPECIFIED_SKU = "92240A540"
LENGTHS_MM = {
    "92240A539": diag_build_92240A539.LENGTH_MM,
    "92240A540": diag_build_92240A540.LENGTH_MM,
}
LENGTH_MM = LENGTHS_MM[SPECIFIED_SKU]

HEAD_AF = HEX_WIDTH_MM
HEAD_H = HEX_HEIGHT_MM
SHANK_DIA = MAJOR_DIAMETER_MM
SHANK_LEN = LENGTH_MM
THREAD_LEN = LENGTH_MM
THREAD_SIZE = "1/4-20"
THREAD_CLASS = "2A"
THREAD_PITCH = PITCH_MM
BEARING_OFFSET = WASHER_DEPTH_MM
