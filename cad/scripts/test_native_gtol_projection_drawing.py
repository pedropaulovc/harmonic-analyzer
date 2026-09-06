"""Native GTol points follow view transforms without changing selected geometry."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import _drawing_common as drawing


def context(monkeypatch, scale=2.0, translation=(0.2, 0.1)):
    entity = Mock()
    point = (0.003, 0.005, -0.002)
    entity.GetCurveParams3.return_value.StartPoint = point
    view = SimpleNamespace(title="Front", scale=scale, translation=translation)
    selection = Mock()
    selection.GetSelectedObjectCount2.return_value = 1
    selection.GetSelectedObject6.return_value = entity
    selection.GetSelectedObjectsDrawingView2.return_value = view
    selection.GetSelectionPoint2.return_value = point

    def set_point(_index, _mark, *coordinates):
        selection.GetSelectionPoint2.return_value = coordinates
        return True

    selection.SetSelectionPoint2.side_effect = set_point
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(SelectionManager=selection), swApp=Mock()
    )
    adapter.swApp.IsSame.side_effect = lambda first, second: int(first is second)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, item: item.title)
    projection = Mock(side_effect=lambda _adapter, owner, xyz, **_kwargs: (
        owner.translation[0] + owner.scale * xyz[0],
        owner.translation[1] + owner.scale * xyz[1],
    ))
    monkeypatch.setattr(drawing, "model_point_in_view", projection)
    return adapter, view, entity, selection, projection, point


@pytest.mark.parametrize("entity_type", ["EDGE", "FACE"])
@pytest.mark.parametrize("scale,translation", [(2, (0.2, 0.1)), (7, (0.08, 0.19))])
def test_native_gtol_projects_kernel_point_using_owning_view(
    monkeypatch, entity_type, scale, translation
):
    adapter, view, entity, selection, projection, point = context(monkeypatch, scale, translation)
    drawing._project_native_gtol_selection(adapter, view, entity, entity_type=entity_type, label="control")
    projection.assert_called_once_with(adapter, view, point, label="control")
    selection.SetSelectionPoint2.assert_called_once_with(
        1, -1, translation[0] + scale * point[0], translation[1] + scale * point[1], 0.0
    )
    adapter.swApp.IsSame.assert_called_once_with(entity, entity)
    if entity_type == "EDGE":
        assert entity.mock_calls[:2] == [call.GetCurve(), call.GetCurveParams3()]
    else:
        entity.GetCurve.assert_not_called()


def test_closed_edge_can_project_without_native_selection_point(monkeypatch):
    adapter, view, entity, selection, _projection, _point = context(monkeypatch)
    selection.GetSelectionPoint2.return_value = None
    drawing._project_native_gtol_selection(adapter, view, entity, entity_type="EDGE", label="rim")
    # Only the projected readback needs SelectionMgr's point for an edge.
    selection.GetSelectionPoint2.assert_called_once_with(1, -1)


@pytest.mark.parametrize("failure", ["count", "owner", "missing_owner", "face_point", "nan_point", "curve", "parameters", "nan_projection"])
def test_invalid_model_context_is_rejected_before_changing_selection(monkeypatch, failure):
    adapter, view, entity, selection, projection, _point = context(monkeypatch)
    entity_type = "FACE"
    if failure == "count":
        selection.GetSelectedObjectCount2.return_value = 2
    if failure == "owner":
        selection.GetSelectedObjectsDrawingView2.return_value = SimpleNamespace(title="Wrong")
    if failure == "missing_owner":
        selection.GetSelectedObjectsDrawingView2.return_value = None
    if failure == "face_point":
        selection.GetSelectionPoint2.return_value = None
    if failure == "nan_point":
        selection.GetSelectionPoint2.return_value = (0, float("nan"), 0)
    if failure in {"curve", "parameters"}:
        entity_type = "EDGE"
        if failure == "curve":
            entity.GetCurve.return_value = None
        if failure == "parameters":
            entity.GetCurveParams3.return_value = None
    if failure == "nan_projection":
        projection.side_effect = None
        projection.return_value = (float("nan"), 0)
    with pytest.raises(RuntimeError, match="control"):
        drawing._project_native_gtol_selection(adapter, view, entity, entity_type=entity_type, label="control")
    selection.SetSelectionPoint2.assert_not_called()


@pytest.mark.parametrize("failure", ["reject", "readback", "nan_readback", "count", "entity", "missing_entity", "unknown_identity"])
def test_projection_must_persist_without_changing_selected_identity(monkeypatch, failure):
    adapter, view, entity, selection, _projection, _point = context(monkeypatch)
    if failure == "reject":
        selection.SetSelectionPoint2.side_effect = None
        selection.SetSelectionPoint2.return_value = False
    if failure in {"readback", "nan_readback"}:
        selection.GetSelectionPoint2.side_effect = [
            (0.003, 0.005, -0.002),
            (0.9, 0, 0) if failure == "readback" else (float("nan"), 0, 0),
        ]
    if failure == "count":
        selection.GetSelectedObjectCount2.side_effect = [1, 2]
    if failure == "entity":
        selection.GetSelectedObject6.return_value = object()
    if failure == "missing_entity":
        selection.GetSelectedObject6.return_value = None
    if failure == "unknown_identity":
        adapter.swApp.IsSame.side_effect = None
        adapter.swApp.IsSame.return_value = -1
    with pytest.raises(RuntimeError, match="control"):
        drawing._project_native_gtol_selection(adapter, view, entity, entity_type="FACE", label="control")
