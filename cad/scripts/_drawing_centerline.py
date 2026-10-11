"""Drawing-view centerline authoring.

Axis and section drawings author native centerlines here without pulling
section creation into centerline-only sheets.
"""

from __future__ import annotations

from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_selection import _select_view_entity
import _telemetry


@_telemetry.traced("drawing.centerline", label_param="label")
def add_view_centerline(
    adapter: Any,
    view: Any,
    *,
    face_xy: tuple[float, float] | None = None,
    label: str,
    entity: Any | None = None,
    face: Any | None = None,
) -> Any:
    """Insert the axis centerline of a cylindrical face shown in ``view``.

    A rectangular side view of a turned part is ambiguous without its axis
    (which pair of edges is the end faces vs the OD silhouette); the ASME
    centerline disambiguates. The cylinder's straight outline is a SILHOUETTE,
    not a selectable EDGE, so — per the API's own centerline example — select
    the cylindrical FACE and let ``InsertCenterLine2`` derive its axis.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    _select_view_entity(
        adapter,
        view,
        "FACE",
        face_xy,
        label=label,
        entity=entity if entity is not None else face,
    )
    centerline = adapter._attempt(lambda: ddoc.InsertCenterLine2())
    if centerline is None:
        raise RuntimeError(f"failed to insert view centerline ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_view_centerline")
    return centerline
