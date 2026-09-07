"""Mapping evidence cannot turn a native identity rejection into acceptance."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _annotation_entity_context as context
from diagnostics import _recipe_entity_acceptance as acceptance
from test_shaft_recipe_acceptance_drawing import entity_bank  # noqa: F401


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(context, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(context.attachments, "geometry", lambda *_: ("same circle",))
    source, selected, other_source, other_selected = (object() for _ in range(4))
    reverse = {id(selected): source, id(other_selected): other_source}
    extension = SimpleNamespace(
        GetCorrespondingEntity2=Mock(side_effect=lambda entity: reverse[id(entity)])
    )
    model = SimpleNamespace(
        Extension=extension,
        GetPathName=lambda: "owned-copy.SLDPRT",
        GetType=lambda: 1,
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
    )
    view = SimpleNamespace(
        ReferencedDocument=model,
        GetName2=lambda: "Front",
        GetCorrespondingEntity=Mock(return_value=selected),
    )
    annotation = SimpleNamespace(
        Owner=view,
        OwnerType=0,
        GetName=lambda: "datum A",
        GetAttachedEntityCount3=lambda: 1,
        GetAttachedEntityTypes=lambda: (1,),
        GetAttachedEntities3=Mock(return_value=(selected,)),
    )
    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _: 1,
        GetSelectedObject6=lambda *_: selected,
        GetSelectedObjectsDrawingView2=lambda *_: view,
        GetSelectedObjectType3=lambda *_: 1,
    )
    draw_extension = Mock()
    draw_extension.GetCorrespondingEntity2.side_effect = AssertionError(
        "never use drawing extension"
    )
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        currentModel=SimpleNamespace(
            SelectionManager=manager, Extension=draw_extension
        ),
    )
    observer = context.EntityContextObservations(
        {"label": "datum:A"}, {"datum:A": source}
    )
    return SimpleNamespace(**locals())


def capture(scene, stage, **kwargs):
    scene.observer.capture(
        scene.adapter,
        scene.view,
        scene.source,
        label="label",
        entity_type="EDGE",
        stage=stage,
        **kwargs,
    )
    return scene.observer.report["stages"][-1]


@pytest.mark.parametrize("entity_type", ["VERTEX", "edge", "", None])
def test_unsupported_entity_type_rejects_before_reads_or_observer_mutation(scene, entity_type):
    scene.adapter.swApp.IsSame = Mock()
    before = json.dumps(scene.observer.report)
    with pytest.raises(ValueError, match="unsupported entity context type"):
        scene.observer.capture(
            scene.adapter, scene.view, scene.source,
            label="label", entity_type=entity_type, stage="selected",
            selected=scene.selected,
        )
    assert json.dumps(scene.observer.report) == before
    assert scene.observer.selected == {}
    assert scene.observer.views == {}
    scene.view.GetCorrespondingEntity.assert_not_called()
    scene.extension.GetCorrespondingEntity2.assert_not_called()
    scene.adapter.swApp.IsSame.assert_not_called()


def test_drawing_extension_mapping_guard_rejects_method_calls(scene):
    with pytest.raises(AssertionError, match="never use drawing extension"):
        scene.draw_extension.GetCorrespondingEntity2(scene.selected)


def test_source_view_context_is_distinguished_from_attachment_change(scene):
    selected = capture(scene, "selected", selected=scene.selected)
    immediate = capture(
        scene, "immediate_native_validation", annotation=scene.annotation
    )
    final = capture(scene, "final_explicit_bank", annotation=scene.annotation)
    assert selected["reads"]["source_selected"]["value"] == 0
    assert selected["reads"]["selected_forward"]["value"] == 1
    assert selected["reads"]["source_reverse_selected"]["value"] == 1
    for row in (immediate, final):
        assert row["reads"]["source_attached"]["value"] == 0
        assert row["reads"]["selected_attached"]["value"] == 1
        assert row["reads"]["forward_attached"]["value"] == 1
        assert row["reads"]["source_reverse_attached"]["value"] == 1
        assert row["reads"]["view_owner"]["value"] == 1
    scene.draw_extension.assert_not_called()
    scene.draw_extension.GetCorrespondingEntity2.assert_not_called()
    assert {
        id(call.args[0])
        for call in scene.extension.GetCorrespondingEntity2.call_args_list
    } == {id(scene.selected)}
    report = scene.observer.report
    assert report["read_seconds_total"] == sum(
        row["read_seconds"] for row in report["stages"]
    )
    assert report["wall_seconds_total"] >= report["read_seconds_total"] >= 0
    assert all(
        item["seconds"] >= 0
        for row in report["stages"]
        for item in row["reads"].values()
    )
    json.dumps(report)  # No raw COM handles leak into the receipt.


def test_later_same_geometry_substitution_stays_visible(scene):
    capture(scene, "selected", selected=scene.selected)
    capture(scene, "immediate_native_validation", annotation=scene.annotation)
    scene.annotation.GetAttachedEntities3.return_value = (scene.other_selected,)
    row = capture(scene, "final_explicit_bank", annotation=scene.annotation)
    assert row["reads"]["selected_attached"]["value"] == 0
    assert row["reads"]["source_reverse_attached"]["value"] == 0
    assert (
        row["reads"]["geometry_source"]["value"]
        == row["reads"]["geometry_attached"]["value"]
    )


@pytest.mark.parametrize("failure", ["null", "error", "unknown"])
def test_native_null_read_error_unknown_are_not_converted_to_identity(scene, failure):
    if failure == "null":
        scene.view.GetCorrespondingEntity.return_value = None
    elif failure == "error":
        scene.view.GetCorrespondingEntity.side_effect = RuntimeError("mapping rejected")
    else:
        scene.adapter.swApp.IsSame = lambda *_: -1
    row = capture(scene, "selected", selected=scene.selected)
    if failure == "unknown":
        assert row["reads"]["source_selected"]["value"] == -1
        return
    assert row["reads"]["forward"]["state"] == failure
    assert row["reads"]["selected_forward"]["state"] == "not_run"
    assert row["reads"]["source_reverse_selected"]["value"] == 1


@pytest.mark.parametrize("attached", [(), (None,), (object(), object())])
def test_missing_and_multiple_attachments_are_observations_not_singular_handles(
    scene, attached
):
    capture(scene, "selected", selected=scene.selected)
    scene.annotation.GetAttachedEntities3.return_value = attached
    row = capture(scene, "final_explicit_bank", annotation=scene.annotation)
    assert row["attachment_array_length"] == len(attached)
    assert row["attachment_nulls"] == [item is None for item in attached]
    assert row["reads"]["selected_attached"]["state"] == "not_run"


def test_mapping_interrupt_is_not_masked_by_read_finalization(scene):
    scene.view.GetCorrespondingEntity.side_effect = KeyboardInterrupt("stop")
    with pytest.raises(KeyboardInterrupt, match="stop"):
        capture(scene, "selected", selected=scene.selected)
    assert (
        scene.observer.report["stages"][0]["reads"]["forward"]["state"] == "interrupted"
    )


@pytest.mark.parametrize("mapping_error", [None, "mapping rejected"])
def test_real_validator_failure_survives_observation_and_all_hooks_restore(
    entity_bank, monkeypatch, mapping_error  # noqa: F811 - imported pytest fixture
):
    bank = entity_bank
    monkeypatch.setattr(context, "_early_bound", lambda value, _: value)
    source = bank.source["datum:A"]
    selected = object()
    bank.geometry[id(selected)] = bank.geometry[id(source)]
    bank.view.GetCorrespondingEntity = Mock(return_value=selected)
    if mapping_error:
        bank.view.GetCorrespondingEntity.side_effect = RuntimeError(mapping_error)
    bank.view.ReferencedDocument = SimpleNamespace(
        Extension=SimpleNamespace(GetCorrespondingEntity2=lambda _: source),
        GetPathName=lambda: "owned-copy.SLDPRT",
        GetType=lambda: 1,
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
    )
    annotation = bank.annotations["datum:A"]
    annotation.GetAttachedEntities3 = lambda: (selected,)
    select = Mock(return_value=selected)
    monkeypatch.setattr(acceptance.drawing, "_select_annotation_entity", select)
    originals = tuple(
        getattr(acceptance.drawing, name)
        for name in (
            "_select_annotation_entity",
            "_validate_native_annotation",
            "_validate_explicit_annotation_attachment",
        )
    )
    with pytest.raises(RuntimeError, match="attachment changed entity identity"):
        with bank.witness.observe(bank.adapter, bank.source):
            acceptance.drawing._select_annotation_entity(
                bank.adapter,
                bank.view,
                entity=source,
                edge_entity=None,
                edge_xy=None,
                entity_type="EDGE",
                label="label datum:A",
            )
            acceptance.drawing._validate_native_annotation(
                bank.adapter, annotation, selected, label="label datum:A"
            )
            acceptance.drawing._validate_explicit_annotation_attachment(
                bank.adapter,
                annotation,
                bank.view,
                source,
                entity_type="EDGE",
                entity_context=acceptance.drawing.AnnotationEntityContext.VIEW,
                label="label datum:A",
            )
    assert originals == tuple(
        getattr(acceptance.drawing, name)
        for name in (
            "_select_annotation_entity",
            "_validate_native_annotation",
            "_validate_explicit_annotation_attachment",
        )
    )
    rows = bank.witness.context_report["stages"]
    assert [row["stage"] for row in rows] == [
        stage.value for stage in context.EntityContextStage
    ]
    assert rows[1]["reads"]["selected_attached"]["value"] == 1
    assert rows[-1]["reads"]["source_attached"]["value"] == 0
    assert rows[-1]["reads"]["source_reverse_attached"]["value"] == 1
    if mapping_error:
        assert rows[-1]["reads"]["forward"]["state"] == "error"
    json.dumps(bank.witness.context_report)
