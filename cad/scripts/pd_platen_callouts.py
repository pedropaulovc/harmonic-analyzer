"""Sheet text for the MHA-PD-02 platen drawing.

Drawing-only: imported by ``draw_pd_platen`` (and its test), never by the
part builder, so rewording the sheet re-keys only the drawing.
``pd_platen_spec``, which the part, the clip, the paper-drive assembly and
the recording geometry import, keeps the geometry and limits; every value
printed here is read from it.
"""

from __future__ import annotations

from pd_platen_spec import SOCKET_ENGAGEMENT_PRINTED_D

# The clip screws' full-thread engagement in the plate alone, less both tap
# mouths' title-block breaks, falls under rule 18's 1.5D; the tap callout
# states its worst case as plain fact (rule 20, pd-platen RV-03, #2411).
SOCKET_ENGAGEMENT_LINE = f"THREAD ENGAGEMENT {SOCKET_ENGAGEMENT_PRINTED_D:.2f}D MIN"
