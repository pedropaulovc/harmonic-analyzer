r"""Stock arbor-pedestal hold-down screw (McMaster 90280A197) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the numbers other parts and assemblies read. The dims are the
90280A197 dimensions from the per-SKU vendor source
(``_mcmaster_90280a197.py``, SolidWorks-free at import).
Consumers read them here, not from ``build_dt_vn_pedestal_hold_down_screw``, whose stock build
recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from _mcmaster_90280a197 import FILLISTER_SIZE

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE
# Native source-model end losses (diag_mcmaster_fillister), not stock limits.
TIP_CHAMFER = 0.7 * _PITCH
FULL_THREAD_START = 1.625 * _PITCH
# Existing installed-joint lower length allowance, formerly duplicated in
# build_dt_drive_train_assembly. Do not replace it with a title-block band.
LENGTH_SHORT_ALLOWANCE_MM = 0.76
