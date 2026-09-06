"""Named datum-to-dimension experiments preserve exact native selection gates."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_datum_dimension_attachment as probe


def context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(probe, "null_callout", lambda: None)
    view = SimpleNamespace(GetName2=lambda: "Front")
    annotation = SimpleNamespace(OwnerType=0, Owner=view)
    display = SimpleNamespace(
        GetNameForSelection=lambda: "BoreCutDia@DrawingView1",
        GetAnnotation=lambda: annotation,
    )
    selection = SimpleNamespace(
        GetSelectedObjectCount2=lambda _: 1,
        GetSelectedObjectType3=lambda *_: 14,
        GetSelectedObject6=lambda *_: display,
    )
    extension = SimpleNamespace(SelectByID2=Mock(return_value=True))
    model = SimpleNamespace(
        SelectionManager=selection,
        Extension=extension,
        ClearSelection2=Mock(),
        ActivateView=Mock(return_value=True),
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    bore = {"view": view, "annotation": annotation, "display": display}
    return adapter, bore


def test_named_selection_uses_no_coordinate_feature_pick(monkeypatch):
    adapter, bore = context(monkeypatch)
    probe.select_bore(adapter, bore)
    adapter.currentModel.Extension.SelectByID2.assert_called_once_with(
        "BoreCutDia@DrawingView1", "DIMENSION", 0.0, 0.0, 0.0, False, 0, None, 0
    )


@pytest.mark.parametrize("change", ["false", "count", "type", "display", "owner"])
def test_wrong_selected_identity_aborts_before_datum_creation(monkeypatch, change):
    adapter, bore = context(monkeypatch)
    selection = adapter.currentModel.SelectionManager
    if change == "false":
        adapter.currentModel.Extension.SelectByID2.return_value = False
    elif change == "count":
        selection.GetSelectedObjectCount2 = lambda _: 2
    elif change == "type":
        selection.GetSelectedObjectType3 = lambda *_: 1
    elif change == "display":
        selection.GetSelectedObject6 = lambda *_: object()
    else:
        bore["annotation"].Owner = object()
    with pytest.raises(RuntimeError):
        probe.select_bore(adapter, bore)


def test_semantics_ignore_only_positions_and_native_drawing_primitives():
    before = {
        "label": "A",
        "shoulder": True,
        "binding": "dimension",
        "position": (0.1, 0.2, 0),
        "display_data": {"lines": "old"},
        "specific_data": {"lines": "old"},
        "measurement": {"body": "old"},
    }
    after = {**before, "position": (0.2, 0.2, 0), "display_data": {"lines": "new"}}
    probe.same_semantics(before, after)
    for field, value in (("label", "B"), ("shoulder", False), ("binding", "edge")):
        with pytest.raises(RuntimeError, match=field):
            probe.same_semantics(before, {**after, field: value})


def test_binding_requires_the_exact_selected_display_dimension():
    dimension = object()
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    assert (
        probe.binding(app, (dimension,), (14,), dimension) == "exact_display_dimension"
    )
    assert probe.binding(app, (object(),), (1,), dimension) == "model_geometry"
    assert probe.binding(app, (None,), (0,), dimension) == "unsupported_null"
    with pytest.raises(RuntimeError, match="different display dimension"):
        probe.binding(app, (object(),), (14,), dimension)


def test_outboard_target_requires_nonzero_motion():
    from _drawing_view_packing import Rect

    target, direction = probe.outboard_target(
        (0.2, 0.2, 0), Rect(0.195, 0.2, 0.205, 0.207), Rect(0.05, 0.05, 0.15, 0.15)
    )
    assert target[:2] != (0.2, 0.2)
    assert target[2] == 0
    assert direction in {"left", "right", "up", "down"}


def test_manufacturing_comparison_removes_only_the_target_datum():
    snapshot = {
        "checked": {"Front/A/2": ["edge"], "Front/dim/4": ["dimension"]},
        "excluded": {},
        "dimensions": {"Front/dim/4": {"value": 0.009525}},
    }
    result = probe.without_datum(snapshot, "Front/A/2")
    assert result["checked"] == {"Front/dim/4": ["dimension"]}
    assert result["dimensions"] == snapshot["dimensions"]
    assert "Front/A/2" in snapshot["checked"]


def test_manufacturing_snapshot_must_contain_the_target_once():
    with pytest.raises(RuntimeError, match="missing or duplicated"):
        probe.without_datum({"checked": {}, "excluded": {}}, "Front/A/2")
    with pytest.raises(RuntimeError, match="missing or duplicated"):
        probe.without_datum({"checked": {"A": 1}, "excluded": {"A": 2}}, "A")


def test_native_frame_size_change_is_rejected():
    before = {"frame_edge_lengths_m": (0.006, 0.006, 0.007, 0.007)}
    with pytest.raises(RuntimeError, match="frame_edge_lengths"):
        probe.same_semantics(
            before, {"frame_edge_lengths_m": (0.006, 0.006, 0.009, 0.009)}
        )


def test_same_type_entity_replacement_is_rejected():
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    annotation, tag, owner, entity = (object() for _ in range(4))
    before = (annotation, tag, owner, entity)
    probe.same_handles(app, before, before)
    with pytest.raises(RuntimeError, match="identity changed"):
        probe.same_handles(app, before, (annotation, tag, owner, object()))
