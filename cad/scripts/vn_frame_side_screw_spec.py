r"""Stock frame-side screw (McMaster 90280A110) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the numbers other parts and assemblies read. The dims are the
90280A110 row (#4-40 x 1/2) of the shared McMaster fillister table
(``diagnostics/diag_mcmaster_fillister.py``, SolidWorks-free at import).
Consumers read them here, not from ``build_vn_frame_side_screw``, whose stock build
recipe would otherwise ride their cache keys (#880).
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

SKU = "90280A110"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZES[SKU]
# The UN size whose major diameter and pitch the SKU row carries (#4-40).
(THREAD,) = (
    size
    for size, major in THREAD_MAJOR_MM.items()
    if abs(major - SHANK_DIA) < 1e-3
    and abs(25.4 / float(size.split("-")[1]) - _PITCH) < 1e-9
)
