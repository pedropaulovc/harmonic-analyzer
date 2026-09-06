"""Native annotation placement keeps geometry/value truth, not old coordinates."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_common as drawing


def native_context(monkeypatch):
    entity = object()
    model = Mock()
    model.SelectionManager.GetSelectedObjectCount2.return_value = 1
    model.SelectionManager.GetSelectedObject6.return_value = entity
    model.GetCurrentSheet.return_value.GetProperties2.return_value = (
        0,
        0,
        1,
        1,
        0,
        0.4318,
        0.2794,
        0,
    )
    annotation = Mock()
    annotation.GetPosition.return_value = (0.12, 0.18, 0.0)
    annotation.GetAttachedEntities3.return_value = (entity,)
    annotation.GetAttachedEntityCount3.return_value = 1
    annotation.SetLeader3.return_value = 0
    tag = model.InsertDatumTag2.return_value
    tag.GetLabel.return_value = "A"
    tag.GetAnnotation.return_value = annotation
    gtol = model.InsertGtol.return_value
    gtol.GetFrameCount.return_value = 1
    gtol.GetFrame.return_value.GetSymbolXml.return_value = drawing._gtol_frame_xml(
        "parallelism",
        "0.05",
        datums=("A",),
        diameter=False,
    )
    gtol.GetFormat.return_value = 2
    gtol.GetAnnotation.return_value = annotation
    gtol.IsAttached.return_value = True
    gtol.GetLeaderCount.return_value = 1
    surface = model.Extension.InsertSurfaceFinishSymbol3.return_value
    surface.GetSymbol.return_value = 1
    surface.GetText.return_value = "Ra 1.6"
    surface.GetAnnotation.return_value = annotation
    application = Mock()
    application.IsSame.side_effect = lambda first, second: int(first is second)
    adapter = SimpleNamespace(currentModel=model, swApp=application)
    view = SimpleNamespace(SelectEntity=Mock(return_value=True))
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(
        drawing._sw_type_info,
        "early_bound_or_flag",
        lambda obj, *_args: obj,
    )
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "Front")
    return adapter, view, entity, annotation


def insert(kind, adapter, view, entity, **kwargs):
    if kind == "datum":
        return drawing.add_datum_feature(
            adapter,
            view,
            entity=entity,
            datum="A",
            label="bore",
            **kwargs,
        )
    if kind == "frame":
        return drawing.add_feature_control_frame(
            adapter,
            view,
            entity=entity,
            characteristic="parallelism",
            tolerance="0.05",
            datums=("A",),
            label="bore",
            **kwargs,
        )
    return drawing.add_surface_finish(
        adapter,
        view,
        entity=entity,
        roughness_ra="1.6",
        label="bore",
        **kwargs,
    )


@pytest.mark.parametrize("kind", ["datum", "frame", "surface"])
def test_native_placement_keeps_created_position_and_validates_attachment(
    monkeypatch, kind
):
    adapter, view, entity, annotation = native_context(monkeypatch)
    insert(kind, adapter, view, entity)
    view.SelectEntity.assert_called_once_with(entity, False)
    annotation.SetPosition2.assert_not_called()
    annotation.SetLeaderAttachmentPointAtIndex.assert_not_called()
    annotation.GetAttachedEntities3.assert_called_once_with()
    adapter.swApp.IsSame.assert_called_once_with(entity, entity)
    adapter.currentModel.Extension.SelectByID2.assert_not_called()
    adapter.currentModel.SelectionManager.SetSelectionPoint2.assert_not_called()


def test_native_surface_finish_uses_documented_location_ignored_no_leader_mode(
    monkeypatch,
):
    adapter, view, entity, annotation = native_context(monkeypatch)
    insert("surface", adapter, view, entity)
    args = adapter.currentModel.Extension.InsertSurfaceFinishSymbol3.call_args.args
    assert args[1:5] == (0, 0.0, 0.0, 0.0)  # swNO_LEADER ignores location
    annotation.SetLeader3.assert_not_called()


@pytest.mark.parametrize("kind", ["datum", "frame", "surface"])
@pytest.mark.parametrize(
    "failure", ["empty", "dangling", "wrong", "unknown", "position"]
)
def test_native_annotation_rejects_lost_geometry_or_unreadable_position(
    monkeypatch, kind, failure
):
    adapter, view, entity, annotation = native_context(monkeypatch)
    if failure == "empty":
        annotation.GetAttachedEntities3.return_value = ()
    if failure == "dangling":
        annotation.GetAttachedEntities3.return_value = (None,)
    if failure == "wrong":
        annotation.GetAttachedEntities3.return_value = (object(),)
    if failure == "unknown":
        adapter.swApp.IsSame.side_effect = None
        adapter.swApp.IsSame.return_value = -1
    if failure == "position":
        annotation.GetPosition.return_value = (float("nan"), 0, 0)
    with pytest.raises(RuntimeError, match="bore"):
        insert(kind, adapter, view, entity)


@pytest.mark.parametrize("kind", ["datum", "frame", "surface"])
def test_native_placement_requires_explicit_model_entity(monkeypatch, kind):
    adapter, view, _entity, _annotation = native_context(monkeypatch)
    with pytest.raises(ValueError, match="native placement.*entity"):
        insert(kind, adapter, view, None, edge_xy=(0.1, 0.2))
    view.SelectEntity.assert_not_called()


@pytest.mark.parametrize("kind", ["frame", "surface"])
def test_native_placement_rejects_fixed_leader_endpoint(monkeypatch, kind):
    adapter, view, entity, _annotation = native_context(monkeypatch)
    with pytest.raises(ValueError, match="native placement.*leader"):
        insert(kind, adapter, view, entity, leader_attach_xy=(0.1, 0.2))
    view.SelectEntity.assert_not_called()


def test_native_off_sheet_anchor_is_diagnosed_without_forcing_old_position(monkeypatch):
    adapter, view, entity, annotation = native_context(monkeypatch)
    annotation.GetPosition.return_value = (0.45, 0.18, 0.0)
    warn = Mock()
    monkeypatch.setattr(drawing._telemetry, "warn", warn)
    insert("datum", adapter, view, entity)
    assert "outside" in warn.call_args.args[0]
    annotation.SetPosition2.assert_not_called()


@pytest.mark.parametrize(
    "kind,keyword",
    [("datum", "symbol_xy"), ("frame", "frame_xy"), ("surface", "symbol_xy")],
)
def test_explicit_placement_remains_available_for_unmigrated_recipes(
    monkeypatch, kind, keyword
):
    adapter, view, entity, annotation = native_context(monkeypatch)
    insert(kind, adapter, view, entity, **{keyword: (0.12, 0.18)})
    annotation.SetPosition2.assert_called_once_with(0.12, 0.18, 0.0)
    if kind == "surface":
        assert (
            adapter.currentModel.Extension.InsertSurfaceFinishSymbol3.call_args.args[1]
            == 2
        )
        annotation.SetLeader3.assert_called_once()


@pytest.mark.parametrize("kind", ["datum", "frame", "surface"])
def test_native_placement_preserves_label_or_manufacturing_value_assertions(
    monkeypatch, kind
):
    adapter, view, entity, _annotation = native_context(monkeypatch)
    model = adapter.currentModel
    if kind == "datum":
        model.InsertDatumTag2.return_value.GetLabel.return_value = "WRONG"
    if kind == "frame":
        model.InsertGtol.return_value.GetFrame.return_value.GetSymbolXml.return_value = "WRONG"
    if kind == "surface":
        model.Extension.InsertSurfaceFinishSymbol3.return_value.GetText.return_value = (
            "Ra 9.9"
        )
    with pytest.raises(RuntimeError, match="bore"):
        insert(kind, adapter, view, entity)


def arrange_context(monkeypatch, counts):
    model = Mock()
    model.Extension.AlignDimensions.return_value = True
    model.SelectionManager.GetSelectedObjectCount2.return_value = sum(counts)
    views = []
    dimensions = []
    for count in counts:
        annotations = [Mock() for _index in range(count)]
        dimensions.extend(annotations)
        view = Mock()
        view.GetAnnotationsByType.return_value = annotations
        views.append(view)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _kind: obj)
    monkeypatch.setattr(drawing, "null_callout", lambda: None)
    return SimpleNamespace(currentModel=model), views, dimensions


def test_auto_arrange_queries_only_dimensions_and_arranges_once_for_all_views(
    monkeypatch,
):
    adapter, views, dimensions = arrange_context(monkeypatch, [2, 1, 0])
    assert drawing.auto_arrange_view_dimensions(adapter, views) == 3
    for view in views:
        view.GetAnnotationsByType.assert_called_once_with(4)
        view.GetAnnotations.assert_not_called()
    for annotation in dimensions:
        annotation.Select3.assert_called_once_with(True, None)
        annotation.SetPosition2.assert_not_called()
    adapter.currentModel.Extension.AlignDimensions.assert_called_once_with(0, 0.001)
    assert adapter.currentModel.ClearSelection2.call_count == 2
    adapter.currentModel.EditRebuild3.assert_not_called()


def test_auto_arrange_skips_empty_dimension_bank(monkeypatch):
    adapter, views, _dimensions = arrange_context(monkeypatch, [0, 0])
    assert drawing.auto_arrange_view_dimensions(adapter, views) == 0
    adapter.currentModel.Extension.AlignDimensions.assert_not_called()


@pytest.mark.parametrize("failure", ["selection", "count", "arrange", "com"])
def test_auto_arrange_fails_loud_and_clears_selections_without_fallback(
    monkeypatch, failure
):
    adapter, views, dimensions = arrange_context(monkeypatch, [2])
    model = adapter.currentModel
    if failure == "selection":
        dimensions[1].Select3.return_value = False
    if failure == "count":
        model.SelectionManager.GetSelectedObjectCount2.return_value = 1
    if failure == "arrange":
        model.Extension.AlignDimensions.return_value = False
    if failure == "com":
        model.Extension.AlignDimensions.side_effect = RuntimeError(
            "native arrange COM failure"
        )
    with pytest.raises(RuntimeError, match="dimension|arrange"):
        drawing.auto_arrange_view_dimensions(adapter, views)
    assert model.ClearSelection2.call_count == 2
    model.Extension.SelectByID2.assert_not_called()
    for dimension in dimensions:
        dimension.SetPosition2.assert_not_called()


@pytest.mark.parametrize("spacing", [0, -1, float("nan"), float("inf")])
def test_auto_arrange_rejects_invalid_spacing_without_touching_drawing(
    monkeypatch, spacing
):
    adapter, views, _dimensions = arrange_context(monkeypatch, [1])
    with pytest.raises(ValueError, match="spacing"):
        drawing.auto_arrange_view_dimensions(adapter, views, spacing_m=spacing)
    adapter.currentModel.ClearSelection2.assert_not_called()
