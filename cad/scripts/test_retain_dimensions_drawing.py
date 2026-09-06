"""Native model-dimension curation preserves names, never recipe text coordinates."""

from types import SimpleNamespace
from unittest.mock import Mock
import importlib
import inspect

import pytest

import _drawing_common as drawing


def context(monkeypatch, imported):
    monkeypatch.setattr(drawing, "insert_marked_dimensions", Mock(return_value=imported))
    monkeypatch.setattr(drawing, "delete_unnamed_imports", lambda _adapter, values: values)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    curate = Mock(side_effect=lambda _adapter, values, *, delete: [
        item for item in values if item.name not in delete
    ])
    monkeypatch.setattr(drawing, "curate_dimensions", curate)
    return curate


def test_native_retention_does_not_request_any_coordinate_writes(monkeypatch):
    retained = SimpleNamespace(name="BoreDia")
    rejected = SimpleNamespace(name="ConstructionRadius")
    curate = context(monkeypatch, [retained, rejected])
    adapter, view = object(), object()
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
    assert drawing.retain_view_dimensions(
        object(), object(), keep=(), view_label="end"
    ) == []


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
