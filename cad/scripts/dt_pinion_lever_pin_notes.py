"""MHA-DT-30 pinion lever pin: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``dt_pinion_lever_pin_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``dt_crank_pinion_pin_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: the diameter's stock callout and the
# cut length are its requirements, so the manifest's notes are empty.
DRAWING_NOTES = ""
