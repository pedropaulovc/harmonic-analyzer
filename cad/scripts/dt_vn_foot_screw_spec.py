r"""Pure stock foot-screw dimensions (McMaster 90280A108).

The dims are the 90280A108 row of the per-SKU vendor source
(``_mcmaster_90280a108.py``, SolidWorks-free at import), the same row the
swing-stop spec and the native fillister recipe read. These are
supplier-model nominals, not inferred supplied tolerance limits.
"""

from __future__ import annotations

from sh_vn_fillister_screw_90280a108_spec import FILLISTER_SIZE

THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE
