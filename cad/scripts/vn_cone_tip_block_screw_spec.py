r"""Stock cone tip block hold-down screw (McMaster 91251A108) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, shank and head dims the drive-train assembly reads to
prove MHA-VN-030 is the screw the tip block and platform were sized for. The
vendor dims are ``DIMS`` in ``diagnostics/diag_build_91251A108.py``
(SolidWorks-free at import). Consumers read them here, not from
``build_vn_cone_tip_block_screw``, whose stock build recipe would otherwise ride
their cache keys (#880).
"""

from __future__ import annotations

from diagnostics.diag_build_91251A108 import DIMS

THREAD = "#4-40"
SHANK_DIA = DIMS.major_dia
SHANK_LEN = DIMS.length
HEAD_DIA = DIMS.head_dia
HEAD_H = DIMS.head_h
