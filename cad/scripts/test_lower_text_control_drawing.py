"""One diagnostic field delta; source-save and production callout gates stay intact."""

from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _drawing_lower_text_control as control


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "_early_bound", lambda value, _: value)
    monkeypatch.setattr("_drawing_native_callouts._early_bound", lambda value, _: value)
    source_path = tmp_path / "alignment-copy.SLDPRT"
    dimension = NS(
        Name="ArborBoreDia@ArborBoreProfile",
        FullName="ArborBoreDia@ArborBoreProfile@alignment-copy.Part",
        GetType=lambda: 0,
        GetSystemValue3=Mock(return_value=(0.008000000001785,)),
    )
    source = NS(GetPathName=lambda: str(source_path))
    state = NS(lower="", native_kind=3)
    entities = (object(), object())
    view = NS(
        GetName2=lambda: "Drawing View1",
        ReferencedDocument=source,
        ReferencedConfiguration="Default",
    )
    annotation = NS(
        GetName=lambda: "ArborBoreDia",
        GetType=lambda: 4,
        OwnerType=0,
        Owner=view,
        Visible=1,
        IsDangling=lambda: False,
        GetAttachedEntityCount3=lambda: len(entities),
        GetAttachedEntities3=lambda: entities,
        GetAttachedEntityTypes=lambda: (1, 1),
    )

    def lower(text):
        state.lower = text
        return None  # Documented void: not a Boolean success result.

    display = NS(
        Type2=6,
        IsReferenceDim=lambda: False,
        IsHoleCallout=lambda: False,
        GetDimension2=lambda index: dimension,
        GetAnnotation=lambda: annotation,
        GetLowerText=Mock(side_effect=lambda: state.lower),
        SetLowerText=Mock(side_effect=lower),
        SetText=Mock(side_effect=AssertionError("no legacy callout setter")),
    )
    annotation.GetSpecificAnnotation = lambda: display
    view.GetAnnotations = Mock(return_value=(annotation,))
    model = NS(
        GetType=lambda: state.native_kind,
        GetViews=Mock(return_value=((view,),)),
        EditRebuild3=Mock(return_value=True),
    )
    adapter = NS(
        currentModel=model,
        swApp=NS(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
        ownership=NS(assert_current_owned=Mock()),
    )
    original = Mock(side_effect=AssertionError("production SetText must not run"))
    monkeypatch.setattr(control.common, "set_dimension_callouts", original)
    module = NS(set_dimension_callouts=original)
    trial = {
        "target": "alignment_pinion",
        "copy_source": str(source_path),
        "source_before": {"configuration": "Default"},
    }
    handles = {control.DIMENSION: dimension}
    annotations = {
        "Drawing View1/ArborBoreDia": {
            "generic": {
                "texts": [
                    {"value": "8.00 "},
                    {"value": "THRU - REAM"},
                    {"value": "PRESS FIT"},
                ]
            },
        }
    }
    instance = control.LowerTextControl(adapter, module, trial, handles)
    return NS(**locals())


def apply(scene, **kwargs):
    scene.module.set_dimension_callouts(
        scene.adapter, (scene.annotation,), dict(control.CALLOUT), **kwargs
    )


def test_void_setter_one_rebuild_both_aliases_and_exact_live_witness(scene):
    with scene.instance.observe():
        assert (
            scene.module.set_dimension_callouts is control.common.set_dimension_callouts
        )
        apply(scene)
    scene.instance.require_used()
    assert scene.module.set_dimension_callouts is scene.original
    assert control.common.set_dimension_callouts is scene.original
    scene.original.assert_not_called()
    scene.display.SetText.assert_not_called()
    scene.display.SetLowerText.assert_called_once_with(control.TEXT)
    scene.model.EditRebuild3.assert_called_once_with()
    assert scene.trial["lower_text_control"]["operation"]["status"] == "passed"
    assert scene.trial["lower_text_control"]["operation"]["before"]["lower_text"] == ""


@pytest.mark.parametrize("failure", ["setter", "readback", "rebuild", "caller"])
def test_failure_restores_both_aliases_and_preserves_primary(scene, failure):
    primary = RuntimeError(f"{failure} failure")
    if failure == "setter":
        scene.display.SetLowerText.side_effect = primary
    if failure == "readback":
        scene.display.GetLowerText.side_effect = ["", "not requested"]
    if failure == "rebuild":
        scene.model.EditRebuild3.side_effect = primary
    with pytest.raises(RuntimeError) as caught:
        with scene.instance.observe():
            apply(scene)
            if failure == "caller":
                raise primary
    if failure != "readback":
        assert caught.value is primary
    assert control.common.set_dimension_callouts is scene.original
    assert scene.module.set_dimension_callouts is scene.original
    if failure in ("setter", "readback"):
        scene.model.EditRebuild3.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        "target",
        "manifest",
        "alias",
        "adapter",
        "above",
        "mapping",
        "missing",
        "duplicate",
        "part",
        "active",
        "ownership",
        "owner",
        "type",
        "hidden",
        "reference",
        "hole",
        "parameter",
        "roundtrip",
        "source",
        "configuration",
        "attachment_count",
    ],
)
def test_wrong_scope_refuses_before_setter_and_rebuild(scene, mode):
    annotations, mapping, actual = (
        [scene.annotation],
        dict(control.CALLOUT),
        scene.adapter,
    )
    kwargs = {}
    if mode == "target":
        scene.trial["target"] = "arbor_pedestal"
    if mode == "manifest":
        scene.handles["unrelated"] = object()
    if mode == "alias":
        scene.module.set_dimension_callouts = Mock()
    if mode == "adapter":
        actual = object()
    if mode == "above":
        kwargs["location"] = "above"
    if mode == "mapping":
        mapping["ArborBoreDia"] = "changed"
    if mode == "missing":
        annotations = []
    if mode == "duplicate":
        annotations.append(scene.annotation)
    if mode == "part":
        scene.state.native_kind = 1
    if mode == "active":
        scene.adapter.swApp.ActiveDoc = object()
    if mode == "ownership":
        scene.adapter.ownership.assert_current_owned.side_effect = RuntimeError(
            "unowned"
        )
    if mode == "owner":
        scene.annotation.OwnerType = 3
    if mode == "type":
        scene.display.Type2 = 10
    if mode == "hidden":
        scene.annotation.Visible = 3
    if mode == "reference":
        scene.display.IsReferenceDim = lambda: True
    if mode == "hole":
        scene.display.IsHoleCallout = lambda: True
    if mode == "parameter":
        scene.display.GetDimension2 = lambda _: NS(**vars(scene.dimension))
    if mode == "roundtrip":
        scene.display.GetAnnotation = lambda: object()
    if mode == "source":
        scene.source.GetPathName = lambda: str(
            scene.source_path.with_name("foreign.SLDPRT")
        )
    if mode == "configuration":
        scene.view.ReferencedConfiguration = "Other"
    if mode == "attachment_count":
        scene.annotation.GetAttachedEntityCount3 = lambda: 3
    with pytest.raises((ValueError, RuntimeError)):
        instance = control.LowerTextControl(
            scene.adapter, scene.module, scene.trial, scene.handles
        )
        with instance.observe():
            scene.module.set_dimension_callouts(actual, annotations, mapping, **kwargs)
    scene.display.SetLowerText.assert_not_called()
    scene.model.EditRebuild3.assert_not_called()


@pytest.mark.parametrize(
    "mutation", ["parameter", "annotation", "owner", "entity", "value"]
)
def test_rebuild_cannot_change_exact_semantic_or_attachment_witness(scene, mutation):
    def rebuild():
        if mutation == "parameter":
            scene.display.GetDimension2 = lambda _: NS(**vars(scene.dimension))
        if mutation == "annotation":
            scene.display.GetAnnotation = lambda: NS(**vars(scene.annotation))
        if mutation == "owner":
            scene.annotation.Owner = NS(**vars(scene.view))
        if mutation == "entity":
            scene.annotation.GetAttachedEntities3 = lambda: (
                object(),
                scene.entities[1],
            )
        if mutation == "value":
            scene.dimension.GetSystemValue3.return_value = (0.008000000001786,)
        return True

    scene.model.EditRebuild3.side_effect = rebuild
    with pytest.raises(RuntimeError):
        with scene.instance.observe():
            apply(scene)
    assert scene.trial["lower_text_control"]["operation"]["status"] == "failed"


def test_requires_one_completed_use_and_rejects_duplicate_or_reentry(scene):
    with pytest.raises(RuntimeError, match="one completed"):
        scene.instance.require_used()
    with scene.instance.observe():
        apply(scene)
        with pytest.raises(RuntimeError, match="once"):
            apply(scene)
    with pytest.raises(RuntimeError, match="once"):
        with scene.instance.observe():
            pytest.fail("expired")
    scene.display.SetLowerText.assert_called_once()


def test_snapshot_fresh_handles_after_cold_reopen_and_no_source_lower_getter(scene):
    with scene.instance.observe():
        apply(scene)
    built = scene.instance.snapshot(
        scene.adapter, scene.handles, phase="built", annotations=scene.annotations
    )
    old_dimension = scene.dimension
    fresh_dimension = NS(**vars(old_dimension))
    fresh_annotation = NS(**vars(scene.annotation))
    fresh_view = NS(**vars(scene.view))
    fresh_annotation.Owner = fresh_view
    fresh_display = NS(**vars(scene.display))
    fresh_display.GetDimension2 = lambda _: fresh_dimension
    fresh_display.GetAnnotation = lambda: fresh_annotation
    fresh_annotation.GetSpecificAnnotation = lambda: fresh_display
    fresh_view.GetAnnotations = lambda: (fresh_annotation,)
    scene.model.GetViews.return_value = ((fresh_view,),)
    cold = scene.instance.snapshot(
        scene.adapter,
        {control.DIMENSION: fresh_dimension},
        phase="reopened",
        annotations=scene.annotations,
    )
    assert cold == built
    assert cold["Drawing View1/ArborBoreDia"]["lower_text"] == control.TEXT
    assert not hasattr(scene.source, "GetLowerText")
    assert not hasattr(old_dimension, "GetLowerText")


def test_boundary_snapshot_observes_lower_loss_without_requiring_completed_use(scene):
    with scene.instance.observe():
        before = scene.instance.boundary_snapshot()
        apply(scene)
        after = scene.instance.boundary_snapshot()
        scene.state.lower = ""
        lost = scene.instance.boundary_snapshot()
    key = "Drawing View1/ArborBoreDia"  # Exact all_annotation_layout native key.
    assert set(before) == set(after) == set(lost) == {key}
    assert before[key]["lower_text"] == lost[key]["lower_text"] == ""
    assert after[key]["lower_text"] == control.TEXT
    assert before[key]["parameters"] == after[key]["parameters"] == lost[key]["parameters"]
    assert scene.model.GetViews.call_count == 3
    scene.display.SetLowerText.assert_called_once_with(control.TEXT)
    scene.model.EditRebuild3.assert_called_once_with()


@pytest.mark.parametrize("mode", ["part", "active", "parameter", "duplicate"])
def test_boundary_snapshot_keeps_owned_drawing_and_exact_native_identity_guards(scene, mode):
    if mode == "part":
        scene.state.native_kind = 1
    if mode == "active":
        scene.adapter.swApp.ActiveDoc = object()
    if mode == "parameter":
        scene.display.GetDimension2 = lambda _: NS(**vars(scene.dimension))
    if mode == "duplicate":
        scene.view.GetAnnotations.return_value = (scene.annotation, scene.annotation)
    with scene.instance.observe():
        with pytest.raises(RuntimeError):
            scene.instance.boundary_snapshot()
    scene.display.SetLowerText.assert_not_called()
    scene.model.EditRebuild3.assert_not_called()
    if mode in ("part", "active"):
        scene.display.GetLowerText.assert_not_called()


def test_boundary_snapshot_rejects_closed_lifetime_without_native_reads(scene):
    with scene.instance.observe():
        apply(scene)
    scene.display.GetLowerText.reset_mock()
    with pytest.raises(RuntimeError, match="active context"):
        scene.instance.boundary_snapshot()
    scene.model.GetViews.assert_not_called()
    scene.display.GetLowerText.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    ["lost", "hidden_text", "one_line", "wrong_key", "sheet_prefix", "duplicate", "stale_id", "part"],
)
def test_fresh_snapshot_retains_observed_failure_without_accepting_hidden_storage(
    scene, mode
):
    with scene.instance.observe():
        apply(scene)
    rows, handles = deepcopy(scene.annotations), scene.handles.copy()
    if mode == "lost":
        scene.state.lower = ""
    if mode == "hidden_text":
        rows["Drawing View1/ArborBoreDia"]["generic"]["texts"] = []
    if mode == "one_line":
        rows["Drawing View1/ArborBoreDia"]["generic"]["texts"].pop()
    if mode == "wrong_key":
        rows["Drawing View2/ArborBoreDia"] = rows.pop("Drawing View1/ArborBoreDia")
    if mode == "sheet_prefix":
        rows["Sheet1/Drawing View1/ArborBoreDia"] = rows.pop("Drawing View1/ArborBoreDia")
    if mode == "duplicate":
        scene.view.GetAnnotations.return_value = (scene.annotation, scene.annotation)
    if mode == "stale_id":
        handles[control.DIMENSION] = object()
    if mode == "part":
        scene.state.native_kind = 1
    with pytest.raises(RuntimeError):
        scene.instance.snapshot(
            scene.adapter, handles, phase="reopened", annotations=rows
        )
    receipt = scene.trial["lower_text_control"]["snapshots"]["reopened"]
    assert receipt["status"] == "failed"
    assert "error" in receipt
    if mode == "lost":
        assert receipt["rows"]["Drawing View1/ArborBoreDia"]["lower_text"] == ""


def test_source_observer_identity_check_accepts_nested_aliases(scene, monkeypatch):
    from diagnostics._source_save_boundaries import SourceSaveBoundaries

    precision = Mock()
    monkeypatch.setattr(control.common, "set_dimension_precision", precision)
    scene.module.set_dimension_precision = precision
    # Real observer context implementation: only its unrelated raw source reads
    # are mocked, not the identity check or nested alias lifecycle.
    observer = object.__new__(SourceSaveBoundaries)
    observer.adapter, observer.module = scene.adapter, scene.module
    from diagnostics._callout_recipe_contract import CalloutContract

    observer.callout_contract = CalloutContract.DRAWING_SETTER_V1
    observer.drawing_reader = None
    observer.capture = Mock()
    observer.stages, observer.report = [], {}
    with scene.instance.observe(), observer.observe():
        apply(scene)
    assert observer.stages == ["callouts"]
    assert [call.args for call in observer.capture.call_args_list] == [
        ("initial",),
        ("before_callouts",),
        ("after_callouts",),
    ]
    assert scene.module.set_dimension_callouts is scene.original
    assert control.common.set_dimension_callouts is scene.original
