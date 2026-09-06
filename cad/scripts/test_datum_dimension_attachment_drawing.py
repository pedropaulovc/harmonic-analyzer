"""Named datum-to-dimension experiments preserve exact native selection gates."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_datum_dimension_attachment as probe


def context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(probe, "null_callout", lambda: None)
    view = SimpleNamespace(GetName2=lambda: "Front")
    annotation = SimpleNamespace(
        OwnerType=0, Owner=view, Select2=Mock(return_value=True)
    )
    dimension = object()
    display = SimpleNamespace(
        GetNameForSelection=lambda: "BoreCutDia@DrawingView1",
        GetAnnotation=lambda: annotation,
        GetDimension2=lambda _: dimension,
    )
    selection = SimpleNamespace(
        GetSelectedObjectCount2=lambda _: 1,
        GetSelectedObjectType3=lambda *_: 14,
        GetSelectedObject6=lambda *_: display,
        GetSelectionPoint2=lambda *_: (0.1, 0.2, 0.0),
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
    bore = {
        "view": view,
        "annotation": annotation,
        "display": display,
        "dimension": dimension,
    }
    return adapter, bore


def test_named_selection_uses_no_coordinate_feature_pick(monkeypatch):
    adapter, bore = context(monkeypatch)
    probe.select_bore(adapter, bore)
    adapter.currentModel.Extension.SelectByID2.assert_called_once_with(
        "BoreCutDia@DrawingView1", "DIMENSION", 0.0, 0.0, 0.0, False, 0, None, 0
    )


def test_annotation_select2_is_the_only_selection_delta(monkeypatch):
    adapter, bore = context(monkeypatch)
    observed = probe.select_bore(adapter, bore, probe.BoreSelector.ANNOTATION_SELECT2)
    bore["annotation"].Select2.assert_called_once_with(False, 0)
    adapter.currentModel.Extension.SelectByID2.assert_not_called()
    assert observed == {
        "selector": "annotation_select2",
        "count": 1,
        "type": 14,
        "selected_interface": "IDisplayDimension",
        "display_identity": "exact",
        "source_dimension_identity": "exact",
        "annotation_owner_identity": "exact",
        "selection_point": (0.1, 0.2, 0.0),
    }


def test_annotation_select2_false_is_not_retried_with_another_selector(monkeypatch):
    adapter, bore = context(monkeypatch)
    bore["annotation"].Select2.return_value = False
    with pytest.raises(RuntimeError, match="selection rejected: annotation_select2"):
        probe.select_bore(adapter, bore, probe.BoreSelector.ANNOTATION_SELECT2)
    adapter.currentModel.Extension.SelectByID2.assert_not_called()


@pytest.mark.parametrize("selector", tuple(probe.BoreSelector))
@pytest.mark.parametrize("change", ["annotation_returned", "source_dimension"])
def test_selector_preserves_display_and_source_dimension_distinction(
    monkeypatch, selector, change
):
    adapter, bore = context(monkeypatch)
    if change == "annotation_returned":
        adapter.currentModel.SelectionManager.GetSelectedObject6 = lambda *_: bore[
            "annotation"
        ]
    else:
        bore["display"].GetDimension2 = lambda _: object()
    with pytest.raises(RuntimeError):
        probe.select_bore(adapter, bore, selector)


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


def test_raw_capture_retains_nonempty_text_plane_before_calibration(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda obj, _: obj)
    data = SimpleNamespace(
        GetLineCount=lambda: 0,
        GetArcCount=lambda: 0,
        GetTextCount=lambda: 1,
        GetTextAtIndex=lambda _: "A",
        GetTextPositionAtIndex=lambda _: (0.003, 0.004, 0),
        GetTextPlaneAtIndex=lambda _: (1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        GetTextHeightAtIndex=lambda _: 0.0035,
        GetTextFontAtIndex=lambda _: "Arial",
        GetTextAngleAtIndex=lambda _: 0.0,
        GetTextRefPositionAtIndex=lambda _: 1,
    )
    record = probe.raw_display_data(SimpleNamespace(GetDisplayData=lambda: data))
    assert record["texts"][0]["plane"] == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    assert record["texts"][0]["position"] == (0.003, 0.004, 0)


@pytest.mark.parametrize("count", [-1, 10001])
def test_raw_capture_rejects_unbounded_native_count(monkeypatch, count):
    monkeypatch.setattr(probe, "_early_bound", lambda obj, _: obj)
    annotation = SimpleNamespace(
        GetDisplayData=lambda: SimpleNamespace(GetLineCount=lambda: count)
    )
    with pytest.raises(RuntimeError, match="primitive count"):
        probe.raw_display_data(annotation)


def test_insertion_target_is_relative_to_measured_dimension_body():
    from _drawing_view_packing import Rect

    position = (0.17, 0.12, 0.0)
    body = Rect(0.16, 0.12, 0.18, 0.127)
    datum = Rect(0.20, 0.20, 0.207, 0.207)
    target = probe.dimension_target_xy(position, body, datum)
    assert target == pytest.approx((0.1535, 0.110, 0.0))
    shifted = probe.dimension_target_xy(
        (0.22, 0.14, 0.0), body.translated((0.05, 0.02)), datum
    )
    assert shifted == pytest.approx((target[0] + 0.05, target[1] + 0.02, 0))


@pytest.mark.parametrize("target", [None, (0.1535, 0.110, 0.0)])
@pytest.mark.parametrize("selector", tuple(probe.BoreSelector))
def test_position_is_the_only_paired_insertion_delta(monkeypatch, target, selector):
    adapter, bore = context(monkeypatch)
    events = []
    old = SimpleNamespace(Select2=lambda *_: True)
    new = SimpleNamespace(
        SetPosition2=lambda *xyz: events.append(("position", xyz)) or True,
        GetPosition=lambda: target,
    )
    tag = SimpleNamespace(
        SetLabel=lambda label: events.append(("label", label)) or True,
        GetAnnotation=lambda: new,
    )
    adapter.currentModel.ClearSelection2 = lambda _: events.append(("clear",))
    adapter.currentModel.EditRebuild3 = lambda: events.append(("rebuild",)) or True
    adapter.currentModel.InsertDatumTag2 = lambda: events.append(("insert",)) or tag
    selection = adapter.currentModel.SelectionManager
    selection.GetSelectedObjectType3 = lambda *_: 36
    selection.GetSelectedObject6 = lambda *_: SimpleNamespace(GetAnnotation=lambda: old)
    adapter.currentModel.Extension.DeleteSelection2 = lambda _: True
    bore["view"].GetAnnotationsByType = lambda _: ()
    select_bore = Mock(return_value={"selector": selector.value})
    monkeypatch.setattr(probe, "select_bore", select_bore)
    observed = {}
    assert (
        probe.replace_on_dimension(
            adapter, bore, old, target=target, observations=observed, selector=selector
        )
        is new
    )
    select_bore.assert_called_once_with(adapter, bore, selector)
    assert observed["selection"] == {"selector": selector.value}
    expected = [("clear",), ("insert",), ("label", "A")]
    if target is not None:
        expected.append(("position", target))
        assert observed["requested"] == observed["actual"] == target
    assert events == [*expected, ("clear",), ("rebuild",)]


def attachment_context(monkeypatch, *, returned=True, kind=1):
    adapter, bore = context(monkeypatch)
    adapter.currentModel.EditRebuild3 = Mock(return_value=True)
    target, tag = object(), object()
    annotation = SimpleNamespace(SetAttachedEntities=Mock(return_value=returned))
    state = {"attachment_types": (kind,), "position": (0.1, 0.2, 0), "label": "A"}
    handles = (annotation, tag, bore["view"], target)
    states = Mock(side_effect=[(dict(state), handles) for _ in range(3)])
    monkeypatch.setattr(probe, "datum_state", states)
    for key in ("full_name", "value_m", "configuration", "source", "view_key"):
        bore[key] = key
    monkeypatch.setattr(probe, "bore_target", lambda _: bore)
    payload = SimpleNamespace(varianttype=8201, value=[target])
    array = Mock(return_value=payload)
    monkeypatch.setattr(probe, "dispatch_array", array)
    return adapter, bore, annotation, target, kind, payload, states, array


@pytest.mark.parametrize("kind", [1, 14])
def test_explicit_attachment_uses_typed_array_and_two_fresh_identity_witnesses(
    monkeypatch, kind
):
    adapter, bore, annotation, target, _, payload, states, array = attachment_context(
        monkeypatch, kind=kind
    )
    observations = {}
    assert probe.explicit_attach(adapter, bore, annotation, target, kind, observations)
    array.assert_called_once_with([target])
    annotation.SetAttachedEntities.assert_called_once_with(payload)
    assert states.call_count == 3  # before, immediate, rebuilt
    adapter.currentModel.EditRebuild3.assert_called_once_with()
    assert (
        observations["immediate_identity"]
        == observations["rebuilt_identity"]
        == "exact"
    )
    probe.require_explicit_attachment(observations)


def test_explicit_false_return_is_captured_but_never_accepted(monkeypatch):
    adapter, bore, annotation, target, kind, _, states, _ = attachment_context(
        monkeypatch, returned=False
    )
    observations = {}
    assert not probe.explicit_attach(
        adapter, bore, annotation, target, kind, observations
    )
    assert states.call_count == 3
    with pytest.raises(RuntimeError, match="returned false"):
        probe.require_explicit_attachment(observations)


@pytest.mark.parametrize("stage", [1, 2])
def test_explicit_true_return_does_not_hide_identity_replacement(monkeypatch, stage):
    adapter, bore, annotation, target, kind, _, states, _ = attachment_context(
        monkeypatch
    )
    tag = object()
    handles = (annotation, tag, bore["view"], target)
    values = [({"attachment_types": (kind,)}, handles) for _ in range(3)]
    values[stage] = (values[stage][0], (*handles[:3], object()))
    states.side_effect = values
    observations = {}
    assert probe.explicit_attach(adapter, bore, annotation, target, kind, observations)
    with pytest.raises(RuntimeError, match="exact-entity witness failed"):
        probe.require_explicit_attachment(observations)


def test_untyped_attachment_array_fails_before_mutation(monkeypatch):
    adapter, bore, annotation, target, kind, payload, _, _ = attachment_context(
        monkeypatch
    )
    payload.varianttype = 8204
    with pytest.raises(RuntimeError, match="typed VT_DISPATCH"):
        probe.explicit_attach(adapter, bore, annotation, target, kind, {})
    annotation.SetAttachedEntities.assert_not_called()


def test_explicit_attachment_cannot_change_the_source_parameter(monkeypatch):
    adapter, bore, annotation, target, kind, _, _, _ = attachment_context(monkeypatch)
    monkeypatch.setattr(probe, "bore_target", lambda _: {**bore, "value_m": 99})
    with pytest.raises(RuntimeError, match="changed the bore source dimension"):
        probe.explicit_attach(adapter, bore, annotation, target, kind, {})


def test_stationary_native_placement_never_calls_position_setter(monkeypatch):
    annotation = SimpleNamespace(
        SetPosition2=Mock(side_effect=AssertionError("unexpected move"))
    )
    monkeypatch.setattr(
        probe,
        "outboard_target",
        Mock(side_effect=AssertionError("unexpected planning")),
    )
    result = probe.place_datum_control(
        annotation, (0.1, 0.2, -0.00315), None, None, probe.DatumPlacement.STATIONARY
    )
    assert result == {
        "requested": (0.1, 0.2, -0.00315),
        "direction": "native_stationary",
    }
    annotation.SetPosition2.assert_not_called()


@pytest.mark.parametrize(
    "texts,label", [([], "A"), (["B"], "A"), (["A"], "B"), (["A", " "], "A")]
)
def test_generic_datum_label_or_render_mutation_fails(texts, label):
    with pytest.raises(RuntimeError, match="exact label"):
        probe.rendered_datum_text({"texts": [{"value": text} for text in texts]}, label)


def test_stale_specific_text_remains_diagnostic_not_semantic():
    rendered = probe.rendered_datum_text({"texts": [{"value": "A"}]}, "A")
    before = {"label": "A", "text": rendered, "specific_data": {"texts": ("B",)}}
    after = {**before, "specific_data": {"texts": ("A",)}}
    probe.same_semantics(before, after)
    assert before["specific_data"]["texts"] == ("B",)
    with pytest.raises(RuntimeError, match="text changed"):
        probe.same_semantics(before, {**after, "text": ("A", "changed quantity")})
