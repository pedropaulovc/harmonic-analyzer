"""Measuring-stick stop plate (MHA-MS-03): the sheet's numbered note, printed by
``draw_ms_stop_plate`` and read by the feature export (export_features).

Kept out of ``ms_stop_spec``, which the plate's and its stop block's native
recipes share, so neither re-keys on a notes-only change (the drawing and the
feature bundle do), as ``ms_stop_block_notes``.
"""

from __future__ import annotations

import _config
from ms_stop_spec import MATCH_DRILL_DATUM_ALIGNMENT

# Rule 4: the matched pair, its screws and the thickness that sets their reach
# are named once, in note 1; the thickness and the hole callout link it, and
# the three hole locations carry only their value (title block .XXX). The
# pilot-and-open sequence is the assembly sheet's step 1.
NOTE_NUMBER = 1
MATCHED_PAIR_NOTE = (
    f"{NOTE_NUMBER}. MATCHED PAIR WITH {_config.parts('ms-stop-block')['number']} STOP BLOCK:"
    f" {MATCH_DRILL_DATUM_ALIGNMENT}.\n"
    f"    2X {_config.parts('ms-vn-stop-plate-screw')['number']} SCREWS ENTER FREELY;"
    f" THICKNESS SETS THEIR REACH IN\n"
    f"    {_config.parts('ms-stop-block')['number']} TAPS."
)
DRAWING_NOTES = MATCHED_PAIR_NOTE
