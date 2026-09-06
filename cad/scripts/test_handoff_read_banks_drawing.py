"""Read-only bank boundaries reject changed context before native mutation."""

from copy import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_measurement_handoff as module
from test_measurement_handoff_drawing import context


@pytest.mark.parametrize("count", [1, 8])
def test_context_is_checked_twice_per_read_bank_not_per_entry(monkeypatch, count):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    annotations = []
    for index in range(count):
        item, bounds = Mock(), copy(measured)
        item.OwnerType, item.Owner = 0, view
        item.GetName.return_value = bounds.name = f"item{index}"
        item.GetType.return_value = 5
        item.GetPosition.return_value = (*bounds.anchor, 0.0)
        handoff.record(view, item, bounds)
        annotations.append((item, bounds))
    handoff.seal()
    contexts = Mock(wraps=module._view_context)
    monkeypatch.setattr(module, "_view_context", contexts)
    with handoff.read_scope():
        for item, bounds in annotations:
            assert handoff.initial_measure(adapter, item) is bounds
    assert contexts.call_count == 2
    fresh.assert_not_called()


@pytest.mark.parametrize(
    "field", ["drawing", "sheet", "position", "scale", "model", "configuration"]
)
@pytest.mark.parametrize(
    "stage", ["before_begin", "during_fresh_read", "after_cached_read"]
)
def test_changed_context_rejects_bank_completion_before_following_mutation(
    monkeypatch, field, stage
):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    handoff.seal()
    mutation = Mock()

    def change():
        if field == "drawing":
            adapter.currentModel = Mock()
        if field == "sheet":
            adapter.currentModel.GetCurrentSheet.return_value = Mock()
        if field == "position":
            view.Position = (0.3, 0.2)
        if field == "scale":
            view.ScaleRatio = (2.0, 1.0)
        if field == "model":
            view.GetReferencedModelName.return_value = "wrong.SLDPRT"
        if field == "configuration":
            view.ReferencedConfiguration = "wrong"

    if stage == "before_begin":
        change()
    with pytest.raises(RuntimeError, match="changed"):
        with handoff.read_scope():
            if stage == "during_fresh_read":
                fresh.side_effect = lambda *_: change() or object()
                handoff.initial_measure(adapter, SimpleNamespace(OwnerType=1))
            handoff.initial_measure(adapter, annotation)
            if stage == "after_cached_read":
                change()
        mutation()
    mutation.assert_not_called()


def test_consumer_cannot_forget_begin_or_completion(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    handoff.seal()
    with pytest.raises(RuntimeError, match="read bank"):
        handoff.initial_measure(adapter, annotation)
    handoff.begin_read()
    assert handoff.initial_measure(adapter, annotation) is measured
    with pytest.raises(RuntimeError, match="completion"):
        handoff.close()
    handoff.end_read()
    handoff.close()


def test_nested_read_banks_and_duplicate_completion_are_rejected(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.seal()
    with handoff.read_scope():
        with pytest.raises(RuntimeError, match="read bank"):
            handoff.begin_read()
    with pytest.raises(RuntimeError, match="read bank"):
        handoff.end_read()


def test_consumer_exception_does_not_leave_an_uncompleted_bank(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    handoff.seal()
    with pytest.raises(ValueError, match="original reader failure"):
        with handoff.read_scope():
            raise ValueError("original reader failure")
    handoff.close()


def test_failed_completion_prevents_reuse_of_the_partially_consumed_bank(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    handoff.seal()
    with pytest.raises(RuntimeError, match="view context changed"):
        with handoff.read_scope():
            handoff.initial_measure(adapter, annotation)
            view.ReferencedConfiguration = "changed"
    with pytest.raises(RuntimeError, match="cannot begin"):
        handoff.begin_read()
    with pytest.raises(RuntimeError, match="no active read bank"):
        handoff.initial_measure(adapter, annotation)
    handoff.close()


@pytest.mark.parametrize("xmin", [-1, 1, 30])
@pytest.mark.parametrize(
    "field", ["drawing", "sheet", "position", "scale", "model", "configuration"]
)
def test_real_packing_rejects_fresh_reader_context_drift_before_planning_or_movement(
    monkeypatch, xmin, field
):
    import _drawing_native_layout as layout
    from _drawing_view_packing import Rect
    from test_native_layout_drawing import Annotation, View, measure, scene

    view = View("front", Rect(xmin, 2, xmin + 2, 4))
    cached = Annotation("cached", Rect(xmin, 2, xmin + 1, 3), owner=view, kind=5)
    uncached = Annotation("uncached", Rect(xmin, 3, xmin + 1, 4), owner=view, kind=5)
    view.annotations = [cached, uncached]
    adapter, options, _ = scene(monkeypatch, {"front": view})
    monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    model = adapter.currentModel
    plan, move, accepted = Mock(), Mock(), Mock()
    monkeypatch.setattr(layout, "pack_view_groups", plan)
    monkeypatch.setattr(layout, "_apply_targets", move)

    def fresh(adapter, annotation):
        result = measure(adapter, annotation)
        if field == "drawing":
            adapter.currentModel = object()
        if field == "sheet":
            model.GetCurrentSheet = lambda: object()
        if field == "position":
            view._position = (40.0, 40.0)
        if field == "scale":
            view.ScaleRatio = (2.0, 1.0)
        if field == "model":
            view.reference = "changed.SLDPRT"
        if field == "configuration":
            view.ReferencedConfiguration = "changed"
        return result

    handoff = module.AnnotationMeasurementHandoff(
        adapter,
        views=options["views"],
        measure_annotation=fresh,
        purpose=module.HandoffPurpose.INITIAL_PACKING,
    )
    measured = measure(adapter, cached)
    measured.anchor = cached.GetPosition()[:2]
    handoff.record(view, cached, measured)
    handoff.seal()
    with pytest.raises(RuntimeError, match="changed"):
        layout.repair_native_layout(
            adapter,
            **options,
            initial_measure_annotation=handoff.initial_measure,
            initial_measure_scope=handoff.read_scope,
            final_annotation_validation=accepted,
        )
    plan.assert_not_called()
    move.assert_not_called()
    accepted.assert_not_called()
    handoff.close()


def test_real_gtol_bank_rejects_completion_before_column_placement(monkeypatch):
    import _drawing_native_gtol as gtols
    from test_callout_handoff_drawing import scene

    adapter, view, frames, symbols, measure, reads, outputs = scene(monkeypatch)
    calls_at_drift = []

    def fresh(adapter, annotation):
        result = measure(adapter, annotation)
        view.ReferencedConfiguration = "changed during fixed-obstacle inventory"
        calls_at_drift.append(adapter.swApp.RunCommand.call_count)
        return result

    handoff = module.AnnotationMeasurementHandoff(
        adapter,
        views={"front": view},
        measure_annotation=fresh,
        purpose=module.HandoffPurpose.GTOL_OBSTACLES,
    )
    # The uncached dimension changes context after a cached datum read. The
    # later cached SF read may return; the read bank cannot complete.
    for annotation in (symbols[0], symbols[2]):
        handoff.record(view, annotation, measure(adapter, annotation))
    handoff.seal()
    placement = Mock()
    monkeypatch.setattr(gtols, "_place_clear_column", placement)
    with pytest.raises(RuntimeError, match="view context changed"):
        gtols.arrange_native_gtol_columns(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            measure_obstacle=handoff.initial_measure,
            obstacle_read_scope=handoff.read_scope,
        )
    assert calls_at_drift == [2]
    assert adapter.swApp.RunCommand.call_count == calls_at_drift[0]
    placement.assert_not_called()
    assert reads[5] == 3  # no accepted/final GTol witness after failed completion
    handoff.close()


@pytest.mark.parametrize("xmin", [-1, 1])
def test_real_packing_completes_read_bank_before_applied_or_unchanged_plan(
    monkeypatch, xmin
):
    import _drawing_native_layout as layout
    from _drawing_view_packing import Rect
    from test_native_layout_drawing import Annotation, View, measure, scene

    view = View("front", Rect(xmin, 2, xmin + 2, 4))
    annotation = Annotation("frame", Rect(xmin, 2, xmin + 1, 3), owner=view, kind=5)
    view.annotations = [annotation]
    adapter, options, _ = scene(monkeypatch, {"front": view})
    monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    fresh = Mock(wraps=measure)
    handoff = module.AnnotationMeasurementHandoff(
        adapter,
        views=options["views"],
        measure_annotation=fresh,
        purpose=module.HandoffPurpose.INITIAL_PACKING,
    )
    measured = measure(adapter, annotation)
    measured.anchor = annotation.GetPosition()[:2]
    handoff.record(view, annotation, measured)
    handoff.seal()
    completed = Mock(wraps=handoff.end_read)
    monkeypatch.setattr(handoff, "end_read", completed)
    native_pack = layout.pack_view_groups

    def checked_pack(*args, **kwargs):
        assert completed.call_count == 1
        assert handoff._phase is module._Phase.SEALED
        return native_pack(*args, **kwargs)

    monkeypatch.setattr(layout, "pack_view_groups", checked_pack)
    options["measure_annotation"] = fresh
    result = layout.repair_native_layout(
        adapter,
        **options,
        initial_measure_annotation=handoff.initial_measure,
        initial_measure_scope=handoff.read_scope,
    )
    assert result.status is (
        layout.NativeLayoutStatus.APPLIED
        if xmin < 0
        else layout.NativeLayoutStatus.UNCHANGED
    )
    completed.assert_called_once_with()
    fresh.assert_called_once_with(adapter, annotation)  # final witness remains fresh
    handoff.close()
