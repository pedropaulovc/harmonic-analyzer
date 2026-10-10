r"""Stock clamp screw (McMaster 90280A201) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the numbers other parts and assemblies read. The dims are the
90280A201 dimensions from the per-SKU vendor source
(``_mcmaster_90280a201.py``, SolidWorks-free at import).
Consumers read them here, not from ``build_vn_clamp_screw``, whose stock build
recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from _mcmaster_90280a201 import FILLISTER_SIZE

SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE
