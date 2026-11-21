"""Rocker pivot bracket (MHA-CH-08): the sheet's numbered general notes, read
by the feature export (export_features).

``draw_ch_pivot_bracket`` prints none: every requirement rides a dimension,
its callout or the title block. Kept out of ``ch_pivot_bracket_spec`` so the
section contract that native builds import does not re-key on a notes-only
change, as ``sh_column_clamp_back_notes``.
"""

from __future__ import annotations

DRAWING_NOTES = ""
