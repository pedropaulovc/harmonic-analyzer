"""MHA-CH-13-TL-02 hub plug: the sheet's manufacturing notes, read by the feature
export (export_features) only.

Kept out of ``ch_rocker_strap_tl_hub_plug_spec`` so the part's native recipe does not
re-key on a notes-only change (the drawing and the feature bundle do), as
``mg_magnifying_clamp_notes``.
"""

from __future__ import annotations

# The sheet prints no manufacturing note: every requirement is a dimension,
# its band or its native callout, so the feature manifest's notes are empty.
DRAWING_NOTES = ""
