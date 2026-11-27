"""Measuring-stick stop block (MHA-MS-02): the sheet's numbered note, printed by
``draw_ms_stop_block`` and read by the feature export (export_features).

Kept out of ``ms_stop_spec``, which the block's and its stop plate's native
recipes share, so neither re-keys on a notes-only change (the drawing and the
feature bundle do), as ``sh_column_clamp_back_notes``.
"""

from __future__ import annotations

import _config

# Rule 4: the rebate is one feature with two tight size bands and a tight
# roof-to-back corner limit (R.003 MAX), so all three carry SEE NOTE 1 and the
# one numbered note names the stick that slides in it.
REBATE_NOTE_NUMBER = 1
REBATE_NOTE = f"{REBATE_NOTE_NUMBER}. SLIDING FIT ON {_config.parts('ms-stick')['number']} MEASURING STICK"
DRAWING_NOTES = REBATE_NOTE
