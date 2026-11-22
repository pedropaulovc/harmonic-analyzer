"""MHA-MG-04 magnifying vertical rod: the sheet's manufacturing notes, read by
the feature export (export_features) only.

Kept out of ``mg_magnifying_vertical_rod_spec`` so the part's native recipe
does not re-key on a notes-only change (the drawing and the feature bundle
do), as ``mg_magnifying_lever_notes``.
"""

from __future__ import annotations

# The sheet prints no general note (mg_magnifying_vertical_rod_spec): the
# overall, the seat on MHA-MG-02 and the hemisphere each ride their own
# callout, so the manifest's notes are empty.
DRAWING_NOTES = ""
