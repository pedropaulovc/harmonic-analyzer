"""Drawing-view entity selection and annotation activation.

Annotation authors share these view-picking primitives without pulling
dimension-import or BOM-balloon logic into unrelated drawings.
"""

from __future__ import annotations

from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
import _seat_forensics


def _select_view_entity(
    adapter: Any,
    view: Any,
    entity_type: str,
    xy: tuple[float, float] | None,
    *,
    label: str,
    entity: Any | None = None,
) -> Any:
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    selected = False
    if entity is not None:
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        if entity_type == "SILHOUETTE":
            selectable = _sw_type_info.early_bound_or_flag(
                entity, "ISilhouetteEdge", "Select2"
            )
            selected = bool(selectable.Select2(False, selection_data))
        else:
            selectable = _early_bound(entity, "IEntity")
            selected = bool(selectable.Select4(False, selection_data))
    elif xy is not None:
        # Coordinate hit-testing needs current geometry, not a pending repaint.
        _early_bound(view, "IView").UpdateViewDisplayGeometry()
        selected = bool(
            draw.Extension.SelectByID2(
                "", entity_type, xy[0], xy[1], 0.0, False, 0, null_callout(), 0
            )
        )
    if not selected and xy is not None:
        # A coordinate pick is the seat's interactive hit test: name the
        # window it ran in before raising.
        _seat_forensics.capture_pick_miss(
            adapter,
            f"failed to select {label} {entity_type.lower()} at sheet ({xy[0]:g}, {xy[1]:g})",
            view=name,
            entity_type=entity_type,
            sheet_xy=xy,
        )
    if not selected:
        raise RuntimeError(f"failed to select {label} {entity_type.lower()} by entity")
    count = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    if entity is not None and count != 1:
        raise RuntimeError(
            f"selecting {label} {entity_type.lower()} produced {count} entities"
        )
    entity = draw.SelectionManager.GetSelectedObject6(count, -1)
    if entity is None:
        raise RuntimeError(f"selected {label} {entity_type.lower()} has no entity")
    return entity


def _select_annotation_entity(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None,
    edge_entity: Any | None,
    entity: Any | None,
    entity_type: str,
    label: str,
) -> Any:
    """Select one drawing-view entity for a native attached annotation."""
    supplied = sum(value is not None for value in (edge_xy, edge_entity, entity))
    if supplied > 1:
        raise ValueError(
            f"{label} cannot specify more than one of edge_xy, edge_entity, or entity"
        )
    if entity is not None:
        return _select_view_entity(
            adapter, view, entity_type, None, label=label, entity=entity
        )
    if edge_entity is None:
        if edge_xy is None:
            raise ValueError(f"{label} requires edge_xy, edge_entity, or entity")
        return _select_view_entity(adapter, view, entity_type, edge_xy, label=label)

    _select_view_entity(
        adapter, view, entity_type, None, label=label, entity=edge_entity
    )
    return edge_entity


def _select_edge(adapter: Any, x: float, y: float, *, append: bool) -> Any:
    draw = adapter.currentModel
    selected = draw.Extension.SelectByID2(
        "", "EDGE", x, y, 0.0, append, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select hole edge at sheet point ({x}, {y})")
    index = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    edge = draw.SelectionManager.GetSelectedObject6(index, -1)
    if edge is None:
        raise RuntimeError(f"hole-edge selection {index} returned no entity")
    return edge


def _activate_and_select_view(adapter: Any, view: Any, *, label: str) -> str:
    """Activate ``view`` and select it as a DRAWINGVIEW; return its name."""
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select {label} drawing view {name!r}")
    return name
