"""MHA-DT-02 arbor pedestal: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``dt_arbor_pedestal_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no numbered manufacturing note (drawing-guidelines.md rule
# 7: every requirement is a dimension, its band, a native callout or the words
# under one -- REAM THRU / SLIDING FIT ON ARBOR, SIDES TANGENT, PARALLEL SIDES
# OK, TO BORE -- which draw_dt_arbor_pedestal owns), so the feature manifest's
# notes are empty, as mg_magnifying_clamp_notes'.
DRAWING_NOTES = ""
