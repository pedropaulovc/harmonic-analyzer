"""Output fixture (MHA-MG-06): the sheet's numbered general notes, read by
the feature export (export_features).

``draw_mg_output_fixture`` prints none: every requirement rides a dimension,
its callout or the title block. Kept out of ``mg_output_fixture_spec`` so the
part build, which imports the spec, does not re-key on a notes-only change,
as ``ch_pivot_bracket_notes``.
"""

from __future__ import annotations

DRAWING_NOTES = ""
