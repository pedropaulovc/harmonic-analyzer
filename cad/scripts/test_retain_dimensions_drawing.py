"""Native model-dimension curation preserves names, never recipe text coordinates."""

from types import SimpleNamespace
from unittest.mock import Mock
import importlib
import inspect

import pytest

import _drawing_common as drawing


def context(monkeypatch, imported):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "insert_marked_dimensions", Mock(return_value=imported))
    monkeypatch.setattr(drawing, "delete_unnamed_imports", lambda _adapter, values: values)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    curate = Mock(side_effect=lambda _adapter, values, *, delete: [
        item for item in values if item.name not in delete
    ])
    monkeypatch.setattr(drawing, "curate_dimensions", curate)
    return curate


def test_native_retention_does_not_request_any_coordinate_writes(monkeypatch):
    retained = SimpleNamespace(name="BoreDia", Visible=1)
    rejected = SimpleNamespace(name="ConstructionRadius")
    curate = context(monkeypatch, [retained, rejected])
    adapter, view = object(), Mock()
    view.GetAnnotationsByType.return_value = [retained]
    assert drawing.retain_view_dimensions(
        adapter, view, keep=("BoreDia",), view_label="front"
    ) == [retained]
    curate.assert_called_once_with(
        adapter, [retained, rejected], delete=("ConstructionRadius",)
    )


@pytest.mark.parametrize("names", [("BoreDia", "BoreDia"), ("",), (None,)])
def test_invalid_name_contract_rejected_before_import(monkeypatch, names):
    context(monkeypatch, [])
    with pytest.raises(ValueError):
        drawing.retain_view_dimensions(object(), object(), keep=names, view_label="front")
    drawing.insert_marked_dimensions.assert_not_called()


@pytest.mark.parametrize("names", [[], ["BoreDia", "BoreDia"]])
def test_missing_or_ambiguous_import_fails(monkeypatch, names):
    context(monkeypatch, [SimpleNamespace(name=name) for name in names])
    with pytest.raises(RuntimeError, match="model dimension mismatch"):
        drawing.retain_view_dimensions(
            object(), object(), keep=("BoreDia",), view_label="front"
        )


def test_empty_contract_removes_all_imported_dimensions(monkeypatch):
    context(monkeypatch, [SimpleNamespace(name="ConstructionRadius")])
    view = Mock()
    view.GetAnnotationsByType.return_value = []
    assert drawing.retain_view_dimensions(
        object(), view, keep=(), view_label="end"
    ) == []


def test_rejected_native_deletion_cannot_pass_retained_inventory(monkeypatch):
    from solidworks_mcp.adapters.solidworks import drawing as native

    retained = SimpleNamespace(name="BoreDia", Visible=1)
    rejected = SimpleNamespace(name="ConstructionRadius", Visible=1, Select2=Mock(return_value=False))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(native._sw_type_info, "early_bound_or_flag", lambda value, *_args: value)
    monkeypatch.setattr(drawing, "insert_marked_dimensions", lambda *_args: [retained, rejected])
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(native, "dimension_name", lambda _adapter, item: item.name)
    adapter = SimpleNamespace(currentModel=Mock(), _attempt=lambda operation, **_kwargs: operation())
    view = Mock()
    view.GetAnnotationsByType.return_value = [retained, rejected]
    with pytest.raises(RuntimeError, match="model dimension mismatch"):
        drawing.retain_view_dimensions(adapter, view, keep=("BoreDia",), view_label="front")
    rejected.Select2.assert_called_once_with(False, 0)
    adapter.currentModel.EditDelete.assert_not_called()


@pytest.mark.parametrize("actual_names", [[], ["BoreDia", "BoreDia"], ["BoreDia", "Extra"], [""]])
def test_actual_view_inventory_must_match_even_when_curated_list_looks_correct(monkeypatch, actual_names):
    retained = SimpleNamespace(name="BoreDia", Visible=1)
    context(monkeypatch, [retained])
    view = Mock()
    view.GetAnnotationsByType.return_value = [SimpleNamespace(name=name, Visible=1) for name in actual_names]
    with pytest.raises(RuntimeError, match="model dimension mismatch"):
        drawing.retain_view_dimensions(object(), view, keep=("BoreDia",), view_label="front")


@pytest.mark.parametrize("visibility", [0, 2, 3])
def test_retained_dimension_must_be_individually_visible(monkeypatch, visibility):
    retained = SimpleNamespace(name="BoreDia", Visible=visibility)
    context(monkeypatch, [retained])
    view = Mock()
    view.GetAnnotationsByType.return_value = [retained]
    with pytest.raises(RuntimeError, match="not individually visible"):
        drawing.retain_view_dimensions(object(), view, keep=("BoreDia",), view_label="front")


def test_retainer_returns_verified_view_objects_not_pre_rebuild_handles(monkeypatch):
    imported = SimpleNamespace(name="BoreDia", Visible=1)
    observed = SimpleNamespace(name="BoreDia", Visible=1)
    context(monkeypatch, [imported])
    view = Mock()
    view.GetAnnotationsByType.return_value = [observed]
    result = drawing.retain_view_dimensions(object(), view, keep=("BoreDia",), view_label="front")
    assert result[0] is observed
    view.GetAnnotationsByType.assert_called_once_with(4)


def test_missing_annotation_handle_in_actual_view_fails_loud(monkeypatch):
    context(monkeypatch, [SimpleNamespace(name="BoreDia", Visible=1)])
    view = Mock()
    view.GetAnnotationsByType.return_value = [None]
    with pytest.raises(RuntimeError, match="model dimension mismatch.*missing annotation"):
        drawing.retain_view_dimensions(object(), view, keep=("BoreDia",), view_label="front")


@pytest.mark.parametrize("stem", [
    "arbor_pedestal", "cone_gear", "channel_lever", "rocker_arm",
    "pen_v_block", "pen_marker",
])
def test_native_pilots_keep_only_dimension_names(stem):
    recipe = importlib.import_module(f"draw_{stem}")
    for name, value in vars(recipe).items():
        if not name.endswith("_KEEP"):
            continue
        assert isinstance(value, tuple), (stem, name)
        assert all(isinstance(item, str) for item in value), (stem, name)
    source = inspect.getsource(recipe)
    assert "retain_view_dimensions(" in source
    assert "curate_view_dimensions" not in source
    assert "auto_arrange_view_dimensions(" in source
