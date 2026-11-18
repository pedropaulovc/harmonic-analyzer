"""MHA-MG-02 magnifying clamp: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``mg_magnifying_clamp_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do).
"""

from __future__ import annotations

# The sheet prints no manufacturing note (drawing-guidelines.md rule 7: every
# requirement is a dimension, its band, a native callout or the seat flag on
# section A-A), so the feature manifest's notes are empty, as
# ch_rocker_strap_notes'.
DRAWING_NOTES = ""
