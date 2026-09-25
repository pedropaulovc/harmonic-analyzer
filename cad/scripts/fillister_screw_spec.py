r"""Purchased brass fillister screw (McMaster 90114A511) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread and the head/shank dims the platen, its clip and guide,
the guide lock, the harmonic base and the assemblies read. The vendor dims are
the named constants of ``diagnostics/diag_build_90114A511.py``
(SolidWorks-free at import). Consumers read them here, not from
``build_fillister_screw``, whose stock build recipe would otherwise ride their
cache keys (#880).
"""

from __future__ import annotations

from diagnostics.diag_build_90114A511 import (
    BF_HEAD_R,
    BF_HH,
    BF_LEN,
    BF_MAJOR_R,
)

THREAD = "#4-40"
HEAD_DIA = 2.0 * BF_HEAD_R
HEAD_H = BF_HH
SHANK_DIA = 2.0 * BF_MAJOR_R
SHANK_LEN = BF_LEN
