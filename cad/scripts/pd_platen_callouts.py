"""Sheet text for the MHA-PD-02 platen drawing.

Drawing-only: imported by ``draw_pd_platen`` (and its test), never by the
part builder, so rewording the sheet re-keys only the drawing.
``pd_platen_spec``, which the part, the clip, the paper-drive assembly and
the recording geometry import, keeps the geometry and limits; every value
printed here is read from it.
"""

from __future__ import annotations

from pd_platen_spec import SOCKET_MOUTH_BREAK_MAX

# Both clip-screw tap mouths break SOCKET_MOUTH_BREAK_MAX at most, not the
# title block's .010: the clip screws' rule-18 engagement is the plate less
# both breaks (pd_platen_spec.SOCKET_THREAD_ENGAGEMENT_MIN, #2411).
SOCKET_MOUTH_BREAK_LINE = (
    f"BREAK EDGES {f'{SOCKET_MOUTH_BREAK_MAX / 25.4:.3f}'.lstrip('0')} MAX"
)
