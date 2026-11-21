"""MHA-DT-17 pinion lift rod: the sheet's manufacturing notes, read by the
feature export (export_features) only.

Kept out of ``dt_pinion_lift_rod_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_wheel_axle_spacer_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note (dt_pinion_lift_rod_spec: "The sheet
# carries no general notes"), so the feature manifest's notes are empty.
DRAWING_NOTES = ""
