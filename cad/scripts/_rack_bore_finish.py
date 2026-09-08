"""Author the rack bore finish from its part-owned manufacturing control."""

from __future__ import annotations

import math
from typing import Any

from _common import _early_bound
from _drawing_common import _validate_surface_finish_control_face, model_point_in_view
from _surface_finish import surface_finish_by_key
from rack_pinion_spec import BORE_DIA, FACE_WIDTH, SURFACE_FINISHES


def add_rack_bore_finish(adapter: Any, front: Any, bore_edge: Any, *, symbol_xy: tuple[float, float]) -> Any:
    """Insert on the selected right rim; reject detached or displaced leaders."""
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    control = surface_finish_by_key(SURFACE_FINISHES, "bore")
    _validate_surface_finish_control_face(
        bore_edge, entity_type="EDGE", control=control, label="rack pinion bore finish",
    )
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(str(front.GetName2())):
        raise RuntimeError("rack bore finish view activation failed")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    raw_data = manager.CreateSelectData()
    if raw_data is None:
        raise RuntimeError("rack bore finish has no selection data")
    data = _early_bound(raw_data, "ISelectData")
    data.View = front
    rim_xy = model_point_in_view(
        adapter, front, (BORE_DIA / 2000.0, 0.0, FACE_WIDTH / 1000.0),
        label="rack bore finish semantic rim point",
    )
    data.X, data.Y = rim_xy
    data.Z = FACE_WIDTH / 2000.0
    if not _early_bound(bore_edge, "IEntity").Select4(False, data):
        raise RuntimeError("rack bore finish semantic edge selection failed")
    if int(manager.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError("rack bore finish requires exactly one selected edge")
    selected = manager.GetSelectedObject6(1, -1)
    if selected is None or int(adapter.swApp.IsSame(selected, bore_edge)) != 1:
        raise RuntimeError("rack bore finish selected the wrong semantic edge")
    raw_finish = draw.Extension.InsertSurfaceFinishSymbol3(
        1, 2, *symbol_xy, 0.0, 0, 10, "", "", "", "", "", "", "",
    )  # machining required, bent leader, no lay, no initial arrowhead
    if raw_finish is None:
        raise RuntimeError("rack bore finish insertion returned null")
    finish = _early_bound(raw_finish, "ISFSymbol")
    if not draw.EditRebuild3():
        raise RuntimeError("rack bore finish insertion rebuild failed")
    if not finish.SetText(8, f"Ra {control.roughness_ra}"):
        raise RuntimeError("rack bore finish roughness assignment failed")
    if control.production_method and not finish.SetText(2, control.production_method):
        raise RuntimeError("rack bore finish production method assignment failed")
    raw_annotation = finish.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("rack bore finish has no annotation")
    finish_annotation = _early_bound(raw_annotation, "IAnnotation")
    if int(finish_annotation.SetLeader3(2, 0, True, False, False, False)) != 0:
        raise RuntimeError("rack bore finish leader style failed")
    draw.ClearSelection2(True)
    if not draw.EditRebuild3():
        raise RuntimeError("rack bore finish rebuild failed")
    annotations = [_early_bound(raw, "IAnnotation") for raw in front.GetAnnotations() or ()]
    finishes = [item for item in annotations if int(item.GetType()) == 7]
    if len(finishes) != 1 or int(adapter.swApp.IsSame(finishes[0], finish_annotation)) != 1:
        raise RuntimeError("rack bore finish insertion inventory mismatch")
    finish_annotation = finishes[0]
    finish_entities = tuple(finish_annotation.GetAttachedEntities3() or ())
    if (
        tuple(finish_annotation.GetAttachedEntityTypes() or ()) != (1,)
        or len(finish_entities) != 1 or finish_entities[0] is None
        or int(adapter.swApp.IsSame(finish_entities[0], bore_edge)) != 1
        or finish_annotation.IsDangling()
    ):
        raise RuntimeError("rack bore finish lost its semantic edge attachment")
    if int(finish.GetSymbol()) != 1 or str(finish.GetText(8) or "").strip() != f"Ra {control.roughness_ra}":
        raise RuntimeError("rack bore finish manufacturing content changed")
    if control.production_method and str(finish.GetText(2) or "").strip() != control.production_method:
        raise RuntimeError("rack bore finish production method changed")
    if int(finish_annotation.GetLeaderCount()) != 1:
        raise RuntimeError("rack bore finish requires exactly one leader")
    points = tuple(finish_annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) not in (6, 9) or not all(math.isfinite(value) for value in points):
        raise RuntimeError("rack bore finish leader points are invalid")
    if math.dist(points[-3:-1], rim_xy) > 1e-8:
        raise RuntimeError("rack bore finish leader moved off the intended right rim")
    return finish
