r"""Stock pinion-block hold-down slotted screw (McMaster 90280A203) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the numbers other parts and assemblies read. The dims are the
90280A203 catalogue nominals from the per-SKU vendor source
(``_mcmaster_90280a203.py``, SolidWorks-free at import): #8-32 x 1-1/2,
read live 2026-10-08. Consumers read them here, not from
``build_vn_slotted_screw``, whose stock build recipe would otherwise ride their
cache keys (#880).
"""

from __future__ import annotations

from _mcmaster_90280a203 import FILLISTER_SIZE

THREAD = "#8-32"
THREAD_CLASS = "2A"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH = FILLISTER_SIZE
