r"""Stock guide-lock screw (McMaster 91255A106) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, shank and head dims the paper-drive assembly and the
platen guide read to prove MHA-176 is the screw the lock stack was sized for.
Ruling R9-31: the eight platen-riding lock screws take a #4-40 x 1/4 button
head so the heads clear the hanger arm; every other MHA-030 station keeps the
brass fillister.  The vendor dims are ``DIMS`` in
``diagnostics/diag_build_91255A106.py`` (SolidWorks-free at import).
Consumers read them here, not from ``build_guide_lock_screw``, whose stock
build recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from diagnostics.diag_build_91255A106 import DIMS

SKU = DIMS.part_no
THREAD = "#4-40"
SHANK_DIA = DIMS.major_dia
SHANK_LEN = DIMS.length
HEAD_DIA = DIMS.head_dia
HEAD_H = DIMS.head_h
