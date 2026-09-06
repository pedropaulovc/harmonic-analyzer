"""One-use measured-bound handoff; neither final witness is memoized."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_measurement_handoff as handoff_module
import _drawing_native_gtol as gtol
from _drawing_view_packing import Rect
from test_native_gtol_drawing import native_context


def context(monkeypatch):
    monkeypatch.setattr(handoff_module, "_early_bound", lambda value, _: value)
    view, annotation, model = Mock(), Mock(), Mock()
    view.GetName2.return_value = "Drawing View1"
    view.Position, view.ScaleRatio = (0.1, 0.2), (1.0, 2.0)
    view.GetReferencedModelName.return_value = "part.SLDPRT"
    view.ReferencedConfiguration = "Default"
    annotation.OwnerType, annotation.Owner = 0, view
    annotation.GetName.return_value = "Control"
    annotation.GetType.return_value = 5
    annotation.GetPosition.return_value = (0.02, 0.03, 0.0)
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    measured = SimpleNamespace(
        name="Control",
        kind=5,
        anchor=(0.02, 0.03),
        body=Rect(0.02, 0.01, 0.07, 0.03),
        envelope=Rect(0.02, 0.0, 0.1, 0.03),
        text_runs=("quantity below frame",),
    )
    fresh = Mock(return_value=object())
    handoff = handoff_module.AnnotationMeasurementHandoff(
        adapter, views={"front": view}, measure_annotation=fresh
    )
    return handoff, adapter, view, annotation, measured, fresh


def test_actual_complete_measurement_consumed_once_without_reading_text_again(
    monkeypatch,
):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    fresh.assert_not_called()
    handoff.seal()
    assert handoff.initial_measure(adapter, annotation) is measured
    fresh.assert_not_called()
    assert handoff.initial_measure(adapter, annotation) is fresh.return_value
    fresh.assert_called_once_with(adapter, annotation)
    assert handoff._reused == 1


def test_unmeasured_and_sheet_owned_annotations_still_use_fresh_callback(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.seal()
    handoff.initial_measure(adapter, annotation)
    annotation.OwnerType = 1
    handoff.initial_measure(adapter, annotation)
    assert fresh.call_count == 2


@pytest.mark.parametrize("phase", ["unsealed", "closed"])
def test_transaction_lifetime_rejects_reuse(monkeypatch, phase):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    if phase == "closed":
        handoff.seal()
        handoff.close()
    with pytest.raises(RuntimeError, match="not ready"):
        handoff.initial_measure(adapter, annotation)
    fresh.assert_not_called()


@pytest.mark.parametrize(
    "field", ["position", "scale", "model", "configuration", "name"]
)
@pytest.mark.parametrize("stage", ["seal", "initial"])
def test_view_context_drift_is_not_a_silent_fresh_baseline(monkeypatch, field, stage):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    if stage == "initial":
        handoff.seal()
    if field == "position":
        view.Position = (0.2, 0.2)
    if field == "scale":
        view.ScaleRatio = (2.0, 2.0)
    if field == "model":
        view.GetReferencedModelName.return_value = "other.SLDPRT"
    if field == "configuration":
        view.ReferencedConfiguration = "Other"
    if field == "name":
        view.GetName2.return_value = "Changed"
    with pytest.raises(RuntimeError, match="view context changed"):
        handoff.seal() if stage == "seal" else handoff.initial_measure(
            adapter, annotation
        )
    fresh.assert_not_called()


@pytest.mark.parametrize(
    "field", ["drawing", "sheet", "annotation", "owner", "position"]
)
def test_exact_identity_and_anchor_required_at_consumption(monkeypatch, field):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    handoff.seal()
    if field == "drawing":
        adapter.currentModel = Mock()
    if field == "sheet":
        adapter.currentModel.GetCurrentSheet.return_value = Mock()
    if field == "annotation":
        replacement = Mock()
        replacement.OwnerType, replacement.Owner = 0, view
        replacement.GetName.return_value = annotation.GetName()
        replacement.GetType.return_value = 5
        annotation = replacement
    if field == "owner":
        replacement = Mock()
        replacement.GetName2.return_value = view.GetName2()
        annotation.Owner = replacement
    if field == "position":
        annotation.GetPosition.return_value = (0.021, 0.03, 0.0)
    with pytest.raises(RuntimeError, match="changed"):
        handoff.initial_measure(adapter, annotation)
    fresh.assert_not_called()


def test_duplicate_or_nonactual_measurement_cannot_be_recorded(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    wrong_anchor = SimpleNamespace(**vars(measured))
    wrong_anchor.anchor = (0.0, 0.0)
    with pytest.raises(RuntimeError, match="anchor changed"):
        handoff.record(view, annotation, wrong_anchor)
    handoff.record(view, annotation, measured)
    with pytest.raises(RuntimeError, match="duplicate"):
        handoff.record(view, annotation, measured)
    handoff.seal()
    with pytest.raises(RuntimeError, match="no longer recording"):
        handoff.record(view, annotation, measured)


def test_same_annotation_name_in_distinct_views_never_aliases(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    other_view = Mock()
    other_view.GetName2.return_value = "Drawing View2"
    other_view.Position, other_view.ScaleRatio = (0.3, 0.2), (1.0, 2.0)
    other_view.GetReferencedModelName.return_value = "part.SLDPRT"
    other_view.ReferencedConfiguration = "Default"
    other_annotation = Mock()
    other_annotation.OwnerType, other_annotation.Owner = 0, other_view
    other_annotation.GetName.return_value = "Control"
    other_annotation.GetType.return_value = 5
    other_annotation.GetPosition.return_value = annotation.GetPosition()
    handoff = handoff_module.AnnotationMeasurementHandoff(
        adapter, views={"front": view, "right": other_view}, measure_annotation=fresh
    )
    other_measurement = SimpleNamespace(**vars(measured))
    handoff.record(view, annotation, measured)
    handoff.record(other_view, other_annotation, other_measurement)
    handoff.seal()
    assert handoff.initial_measure(adapter, other_annotation) is other_measurement
    assert handoff.initial_measure(adapter, annotation) is measured


def test_context_change_during_initial_inventory_cannot_serve_a_later_entry(
    monkeypatch,
):
    handoff, adapter, view, annotation, measured, fresh = context(monkeypatch)
    handoff.record(view, annotation, measured)
    handoff.seal()
    unrecorded = Mock()
    unrecorded.OwnerType = 1
    handoff.initial_measure(adapter, unrecorded)
    view.Position = (0.15, 0.2)
    with pytest.raises(RuntimeError, match="view context changed"):
        handoff.initial_measure(adapter, annotation)
    fresh.assert_called_once_with(adapter, unrecorded)


def test_complete_gtol_handoff_saves_initial_reads_but_never_final_reads(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=3)
    monkeypatch.setattr(handoff_module, "_early_bound", lambda value, _: value)
    view.Position, view.ScaleRatio = (0.5, 0.5), (1.0, 1.0)
    view.GetReferencedModelName.return_value = "part.SLDPRT"
    view.ReferencedConfiguration = "Default"
    outputs = []

    def fresh(adapter, annotation):
        measured = measure(adapter, annotation)
        measured.name, measured.kind = annotation.GetName(), 5
        measured.envelope = measured.body
        measured.text_runs = ()
        outputs.append(measured)
        return measured

    handoff = handoff_module.AnnotationMeasurementHandoff(
        adapter, views={"front": view}, measure_annotation=fresh
    )
    gtol.arrange_native_gtol_columns(
        adapter,
        views={"front": view},
        measure_annotation=fresh,
        record_measurement=handoff.record,
    )
    assert len(outputs) == 6
    handoff.seal()
    initial = [handoff.initial_measure(adapter, annotation) for annotation in rows]
    assert all(a is b for a, b in zip(initial, outputs[3:], strict=True))
    assert len(outputs) == 6
    final = [fresh(adapter, annotation) for annotation in rows]
    assert len(outputs) == 9
    assert all(a is not b for a, b in zip(initial, final, strict=True))
    handoff.close()


def test_gtol_handoff_records_only_fresh_final_bounds_not_derived_states(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=3)
    measured, recorded = [], []

    def fresh(adapter, annotation):
        output = measure(adapter, annotation)
        measured.append((annotation, output))
        return output

    gtol.arrange_native_gtol_columns(
        adapter,
        views={"front": view},
        measure_annotation=fresh,
        record_measurement=lambda *args: recorded.append(args),
    )
    assert len(measured) == 6  # Three initial + three fresh final reads remain.
    assert len(recorded) == 3
    for index, (owner, annotation, output) in enumerate(recorded):
        assert owner is view and annotation is rows[index]
        assert output is measured[index + 3][1]
        assert output is not measured[index][1]
        assert tuple(output.anchor) == annotation.GetPosition()[:2]


def test_gtol_failed_final_guard_never_hands_off_a_new_body_baseline(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    recorded = Mock()
    original = rows[0].SetPosition2.side_effect

    def reflow(x, y, z):
        original(x, y, z)
        rows[0].size = (0.2, 0.1)
        return True

    rows[0].SetPosition2.side_effect = reflow
    with pytest.raises(RuntimeError, match="did not translate rigidly"):
        gtol.arrange_native_gtol_columns(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            record_measurement=recorded,
        )
    recorded.assert_not_called()


def test_obstacle_actual_measurement_is_handed_off_after_commands(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=2)
    obstacle, output = Mock(), SimpleNamespace(body=Rect(0.1, 0.01, 0.15, 0.05))
    view.GetAnnotationsByType.side_effect = lambda kind: (
        rows if kind == 5 else (obstacle,) if kind == 4 else ()
    )
    recorded = []

    def fresh(adapter, annotation):
        if annotation is obstacle:
            assert adapter.swApp.RunCommand.call_count == 1
            return output
        return measure(adapter, annotation)

    gtol.arrange_native_gtol_columns(
        adapter,
        views={"front": view},
        measure_annotation=fresh,
        record_measurement=lambda *args: recorded.append(args),
    )
    assert recorded[0] == (view, obstacle, output)
    assert len(recorded) == 3
