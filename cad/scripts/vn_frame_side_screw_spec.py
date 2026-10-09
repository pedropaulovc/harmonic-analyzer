r"""Stock frame-side screw (McMaster 90280A194) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the numbers other parts and assemblies read. The dims are the
90280A194 row of the shared McMaster fillister table
(``vn_fillister_screw_spec.py``, a pure supplier-data authority).
Consumers read them here, not from ``build_vn_frame_side_screw``, whose stock build
recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from vn_fillister_screw_spec import FILLISTER_SIZES

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZES["90280A194"]
