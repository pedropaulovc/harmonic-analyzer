"""MHA-DT-26 cylinder end disc: the sheet's manufacturing notes, read by the feature
export (export_features) only.

Kept out of ``dt_cylinder_end_disc_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: every requirement is a dimension,
# its band or its native callout, so the feature manifest's notes are empty.
DRAWING_NOTES = ""
