"""Pinion pivot block (MHA-DT-18): the sheet's numbered note, printed by
``draw_dt_pinion_pivot_block`` and read by the feature export (export_features).

Kept out of ``dt_pinion_pivot_block_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``sh_column_clamp_back_notes``.
"""

from __future__ import annotations

import _config

# The lift bore's .728/.085 locations from the pivot bore carry value and band
# only; their one reason and its mates go in numbered note 1, flagged from the
# lift-bore callout (rule 4: mates by drawing number; rule 26: standard words,
# not a coined "park gap"): the lift rod's eccentric cam MHA-DT-23 parks just
# clear of the follower pin MHA-DT-25 (dt_pinion_pivot_block_geometry;
# build_dt_drive_train_assembly's park-gap band).
CAM_NUMBER = _config.parts("dt-pinion-cam")["number"]
FOLLOWER_PIN_NUMBER = _config.parts("dt-pinion-cam-pin")["number"]
LIFT_BORE_NOTE_NUMBER = 1
LIFT_BORE_NOTE_TEXT = (
    f".728 AND .085 SET {CAM_NUMBER} TO {FOLLOWER_PIN_NUMBER} CLEARANCE."
)
LIFT_BORE_NOTE = f"{LIFT_BORE_NOTE_NUMBER}. {LIFT_BORE_NOTE_TEXT}"
# The sheet's one numbered note.
DRAWING_NOTES = LIFT_BORE_NOTE
