"""MHA-DT-12-TL-01 cam turning fixture: the sheet's manufacturing notes, read by
the feature export (export_features) only.

Kept out of ``dt_cylinder_gear_tl_cam_fixture_spec`` so the part's native
recipe does not re-key on a notes-only change (the drawing and the feature
bundle do), as ``dt_cylinder_end_disc_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: every requirement is a dimension,
# its band or its REAM callout, so the feature manifest's notes are empty.
DRAWING_NOTES = ""
