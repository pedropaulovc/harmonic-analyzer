r"""Purchased cone pivot screw (McMaster 91829A560) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread and the head/shoulder/thread dims the harmonic base, the
drive train and the verify sweep read. The vendor dims are the named constants
of ``diagnostics/diag_build_91829A560.py`` (SolidWorks-free at import),
exported here through ``__all__``. Consumers read them here, not from
``build_cone_pivot_screw``, whose stock build recipe would otherwise ride their
cache keys (#880).
"""

from __future__ import annotations

from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91829A560 import (
    HEAD_DIA,
    HEAD_T,
    SHOULDER_DIA,
    SHOULDER_LEN,
    THREAD_LEN,
    THREAD_MAJOR,
    UNDERHEAD_LEN,
)

__all__ = [
    "HEAD_DIA",
    "HEAD_H",
    "SHOULDER_DIA",
    "SHOULDER_LEN",
    "THREAD",
    "THREAD_SOLID_DIA",
    "THREAD_TAIL_LEN",
    "THREAD_TAP_DRILL_DIA",
    "UNDERHEAD_LEN",
]

THREAD = "#10-24"
HEAD_H = HEAD_T
THREAD_TAIL_LEN = THREAD_LEN
THREAD_SOLID_DIA = THREAD_MAJOR
THREAD_TAP_DRILL_DIA = TAP_DRILL_MM[THREAD]
