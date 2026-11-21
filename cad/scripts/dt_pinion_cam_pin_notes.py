"""MHA-DT-25 pinion cam-follower pin: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``dt_pinion_cam_pin_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no general note (dt_pinion_cam_pin_spec: the assembly step
# owns the bond): its dimensions, their callouts and the shank's finish are
# its requirements, so the manifest's notes are empty.
DRAWING_NOTES = ""
