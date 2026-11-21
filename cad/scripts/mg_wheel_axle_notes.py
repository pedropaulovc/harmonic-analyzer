"""MHA-MG-07 wheel axle: the sheet's manufacturing notes, read by the feature
export (export_features) only.

Kept out of ``mg_wheel_axle_spec`` so the part's native recipe does not re-key
on a notes-only change (the drawing and the feature bundle do), as
``mg_wheel_axle_spacer_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: every requirement is a dimension,
# its band or its native callout, so the feature manifest's notes are empty.
DRAWING_NOTES = ""
