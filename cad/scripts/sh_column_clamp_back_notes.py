"""Column clamp, back arc (MHA-SH-02): the sheet's flag notes, printed by
``draw_sh_column_clamp_back`` and read by the feature export (export_features).

Kept out of ``sh_column_clamp_back_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

import _config
from sh_column_clamp_back_spec import BORE_CLEARANCE_TEXT, FRONT_ARC_MATE

# The grip offset cites note 1 (it keeps the faces apart); the bore's fit
# names its mate by number and name and says which clearance (rule 4), too
# long for the lane beside the bore, so the bore cites note 2
# (draw_sh_column_clamp_back.DIMENSION_CALLOUTS).
GRIP_NOTE = 1
BORE_NOTE = 2
COLUMN_NUMBER = _config.parts("fr-tube-frame")["number"]
GRIP_NOTE_TEXT = f"KEEPS A GAP TO {FRONT_ARC_MATE} WHEN CLAMPED."
BORE_NOTE_TEXT = (
    f"SLIDING FIT ON {COLUMN_NUMBER} COLUMN, DIAMETRAL CLEARANCE {BORE_CLEARANCE_TEXT}."
)
DRAWING_NOTES = f"{GRIP_NOTE}. {GRIP_NOTE_TEXT}\n{BORE_NOTE}. {BORE_NOTE_TEXT}"
