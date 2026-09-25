r"""Stock hanger screw (McMaster 93075A194) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the head and shank dims the pen hanger, the wheel bar and the pen
assembly read. The vendor dims are the named constants of
``diagnostics/diag_build_93075A194.py`` (SolidWorks-free at import). Consumers
read them here, not from ``build_hanger_screw``, whose stock build recipe would
otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from diagnostics.diag_build_93075A194 import (
    HX_HH,
    HX_HW,
    HX_LEN,
    HX_MAJOR_R,
)

HEAD_AF = HX_HW
HEAD_H = HX_HH
SHANK_DIA = 2.0 * HX_MAJOR_R
SHANK_LEN = HX_LEN
