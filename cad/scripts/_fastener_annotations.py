r"""Drawing-view annotations shared by the made-fastener sheets.

The fastener prints (cad/docs/drawing-simplicity-policy.md) put the thread
designation ON the view as a leader to the shank, mark the screw axis with
a centerline and the head rim with a center mark, and end every end-view
diameter leader at the rim it names.  The recipe (``_fastener_drawing``)
only hands its ``decorate`` hook the views, so these helpers re-read what
they need from the view and fail loud when a pick misses.
"""

from __future__ import annotations

from typing import Any, Iterable

import _telemetry
from _common import _early_bound
from _drawing_common import _select_view_entity, add_attached_note
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import dimension_name

_CENTER_MARK_SINGLE = 2  # swCenterMarkStyle_e.swCenterMark_Single
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


def view_dimension_annotations(adapter: Any, view: Any) -> list[Any]:
    """Every display dimension currently on ``view``, as IAnnotation dispatches."""
    drawing_view = _early_bound(view, "IView")
    displays = drawing_view.GetDisplayDimensions() or []
    annotations: list[Any] = []
    for display in displays:
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "GetAnnotation"
        )
        annotation = display.GetAnnotation()
        if annotation is None:
            raise RuntimeError("a view display dimension has no annotation")
        annotations.append(
            _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "GetSpecificAnnotation"
            )
        )
    return annotations


@_telemetry.traced("drawing.thread_leader", label_param="label")
def add_thread_leader(
    adapter: Any,
    view: Any,
    *,
    designation: str,
    silhouette_xy: tuple[float, float],
    note_xy: tuple[float, float],
    label: str,
) -> Any:
    """Leader the catalog thread designation to the shank outline.

    The modeled shank is a plain cylinder (thread minor or tap-drill size),
    so its outline is a drawing SILHOUETTE, not a model edge; the leader
    lands on that outline exactly as a machinist expects a thread callout to.
    """
    return add_attached_note(
        adapter,
        view,
        text=designation,
        entity_xy=silhouette_xy,
        note_xy=note_xy,
        label=label,
        entity_type="SILHOUETTE",
    )


@_telemetry.traced("drawing.center_mark", label_param="label")
def add_circle_center_mark(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    label: str,
) -> Any:
    """Insert one ASME center mark on the circular edge picked at ``edge_xy``.

    ``IView.AutoInsertCenterMarks2`` only marks holes, fillets and slots, so a
    screw head's rim (a boss, not a hole) never gets one; the single-mark
    ``IDrawingDoc.InsertCenterMark3`` on the selected rim edge does.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    mark = adapter._attempt(
        lambda: ddoc.InsertCenterMark3(_CENTER_MARK_SINGLE, False, False)
    )
    if mark is None:
        raise RuntimeError(f"failed to insert center mark ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return mark


@_telemetry.traced("drawing.leaders_to_rim", label_param="label")
def end_diameter_leaders_at_rim(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str], *, label: str
) -> None:
    """End each named diameter leader at the nearest rim, never across it.

    SolidWorks' default runs a diameter dimension line across the circle
    through its centre -- across a driver slot on these sheets.  With the
    arrows OUTSIDE the leader stops at the circumference it names
    (drawing-simplicity-policy.md rule 8: a leader crosses nothing).
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _sw_type_info.early_bound_or_flag(
            annotation.GetSpecificAnnotation(), "IDisplayDimension", "ArrowSide"
        )
        display.ArrowSide = _ARROWS_OUTSIDE
        if int(display.ArrowSide) != _ARROWS_OUTSIDE:
            raise RuntimeError(f"{label}: {name} arrows did not move outside")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(
            f"{label}: diameter dimensions not found: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()
