"""MHA-MG-03 magnifying lever: the sheet's manufacturing notes, read by the feature
export (export_features) only.

Kept out of ``mg_magnifying_lever_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no general note: its dimensions, their callouts, the screw
# seat's finish and the detail label are its requirements, so the manifest's
# notes are empty.
DRAWING_NOTES = ""
