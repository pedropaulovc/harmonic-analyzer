"""MHA-PD-27 platen bottom guide: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``pd_platen_bottom_guide_spec`` so the part's native recipe does
not re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: every requirement is a dimension,
# its band or a native hole callout with its rows (draw_pd_platen_bottom_guide),
# so the feature manifest's notes are empty, as mg_magnifying_clamp_notes'.
DRAWING_NOTES = ""
