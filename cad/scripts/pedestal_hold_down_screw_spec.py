r"""Stock arbor-pedestal hold-down screw (McMaster 90280A197) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the numbers other parts and assemblies read. The dims are the
90280A197 row of the shared McMaster fillister table
(``diagnostics/diag_mcmaster_fillister.py``, SolidWorks-free at import).
Consumers read them here, not from ``build_pedestal_hold_down_screw``, whose stock build
recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZES["90280A197"]
