"""MHA-SM-02 knife mount: the sheet's numbered general notes, read by the
feature export (export_features) only.

``draw_sm_knife_mount`` prints none: every requirement rides a dimension, its
band, a native callout or its frame, or the title block (the finish, 28-32 HRC
AS SUPPLIED; UNPAINTED, OILED, is the registry row's). Kept out of
``sm_knife_mount_spec`` so the part's native recipe and the MHA-FR-02 closure
that imports that spec do not re-key on a notes-only change, as
``ch_pivot_bracket_notes``.
"""

from __future__ import annotations

DRAWING_NOTES = ""
