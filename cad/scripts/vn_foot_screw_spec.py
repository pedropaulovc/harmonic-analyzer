r"""Pure stock foot-screw dimensions (McMaster 90280A108).

The shared stock row belongs to ``vn_swing_stop_screw_spec``; this same-SKU
reader and the native fillister recipe consume that authority without
importing one another. These are supplier-model nominals, not inferred
supplied tolerance limits.
"""

from __future__ import annotations

from vn_swing_stop_screw_spec import FILLISTER_SIZE

THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE
