"""MHA-DT-29 crank pinion pin: the sheet's manufacturing notes, read by the feature
export (export_features) only.

Kept out of ``dt_crank_pinion_pin_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: the diameter's STOCK, AS SUPPLIED
# callout and the length are its requirements, so the manifest's notes are empty.
DRAWING_NOTES = ""
