"""MHA-DT-03-TL-02 phasing comb: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``dt_cone_gear_tl_phasing_comb_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``dt_crank_pinion_pin_notes``.
"""

from __future__ import annotations

# The sheet prints no numbered note: its dimensions, their callouts and the
# thickness's SHEET STOCK are its requirements, so the manifest's notes are empty.
DRAWING_NOTES = ""
