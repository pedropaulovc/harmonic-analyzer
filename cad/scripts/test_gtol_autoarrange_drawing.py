"""Offline controls for native GTol arrangement experiments and their witnesses."""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from diagnostics import probe_gtol_autoarrange as probe


def context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    model, drawing = Mock(), Mock()
    rows = [
        {"view": "native-view", "name": str(kind), "kind": kind, "annotation": Mock()}
        for kind in (4, 5, 5)
    ]
    rows[0][
        "annotation"
    ].GetSpecificAnnotation.return_value.GetNameForSelection.return_value = (
        "Width@source@view"
    )
    model.Extension.AlignDimensions.return_value = True
    return model, drawing, rows


@pytest.mark.parametrize(
    ("kinds", "count", "gtols", "dimensions"),
    [
        ((5,), 2, 2, 0),
        ((4, 5), 3, 2, 1),
        ((4,), 1, 0, 1),
    ],
)
def test_banks_are_selected_exactly_then_one_native_call(
    monkeypatch, kinds, count, gtols, dimensions
):
    model, drawing, rows = context(monkeypatch)
    model.SelectionManager.GetSelectedObjectCount2.return_value = count
    result = probe.select_bank(model, drawing, rows, kinds)
    assert result["selected"] == count
    assert result["gtols"] == gtols
    assert result["dimensions"] == dimensions
    assert result["return"] is True
    model.Extension.AlignDimensions.assert_called_once_with(0, 0.001)
    if dimensions:
        model.Extension.SelectByID2.assert_called_once_with(
            "Width@source@view",
            "DIMENSION",
            0,
            0,
            0,
            True,
            0,
            None,
            0,
        )
    else:
        model.Extension.SelectByID2.assert_not_called()
    for row in rows[1:]:
        assert row["annotation"].Select2.call_count == bool(gtols)


def test_incorrect_bank_count_prevents_native_arrangement(monkeypatch):
    model, drawing, rows = context(monkeypatch)
    model.SelectionManager.GetSelectedObjectCount2.return_value = 1
    with pytest.raises(RuntimeError, match="selection count"):
        probe.select_bank(model, drawing, rows, (4, 5))
    model.Extension.AlignDimensions.assert_not_called()


def test_rejected_selection_prevents_native_arrangement(monkeypatch):
    model, drawing, rows = context(monkeypatch)
    rows[1]["annotation"].Select2.return_value = False
    with pytest.raises(RuntimeError, match="selection failed"):
        probe.select_bank(model, drawing, rows, (5,))
    model.Extension.AlignDimensions.assert_not_called()


def test_native_rejection_is_an_observation_not_a_fallback(monkeypatch):
    model, drawing, rows = context(monkeypatch)
    model.SelectionManager.GetSelectedObjectCount2.return_value = 2
    model.Extension.AlignDimensions.return_value = False
    assert probe.select_bank(model, drawing, rows, (5,))["return"] is False
    model.Extension.AlignDimensions.assert_called_once()


def test_native_exception_is_recorded_with_its_exact_error():
    def reject():
        raise RuntimeError("COM call rejected")

    assert probe.observe(reject) == {"error": "RuntimeError('COM call rejected')"}


def valid_attachment():
    return {
        "view": "native-view",
        "name": "FCF",
        "kind": 5,
        "entity_count_before": 1,
        "entity_count_after": 1,
        "attachment_types_before": (2,),
        "attachment_types_after": (2,),
        "entity_identity": [1],
        "dangling": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entity_count_after", 0),
        ("entity_count_after", 2),
        ("attachment_types_after", (1,)),
        ("entity_identity", [0]),
        ("entity_identity", [-1]),
        ("entity_identity", [None]),
        ("dangling", True),
    ],
)
def test_mutation_does_not_hide_attachment_regressions(field, value):
    record = valid_attachment()
    record[field] = value
    assert probe.attachment_failures([record])


def test_unchanged_native_attachment_passes():
    assert probe.attachment_failures([valid_attachment()]) == []


def test_diagnostic_does_not_recreate_gtols_or_select_geometry_by_coordinates():
    tree = ast.parse(Path(probe.__file__).read_text())
    attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not attributes & {
        "InsertGtol",
        "SetAttachedEntities",
        "SelectByRay",
        "SelectEntity",
    }
    assert "AlignDimensions" in attributes
    assert "GetLineAtIndex3" in attributes
    assert "GetTextPositionAtIndex" in attributes
