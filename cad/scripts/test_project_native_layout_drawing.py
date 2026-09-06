"""Project layout must run native spacing before measured fit and fail unsaved."""

from dataclasses import dataclass
import json
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import _drawing_project_layout as drawing
import _drawing_native_callouts as callouts
import _drawing_native_gtol as gtol
import _drawing_native_layout as native
import _drawing_measurement_handoff as handoff_module
import _drawing_annotation_bounds as bounds_module
import _drawing_leader_clearance as clearance_module


@dataclass
class Report:
    status: native.NativeLayoutStatus
    reason: str


@pytest.mark.parametrize("status", list(native.NativeLayoutStatus))
def test_project_layout_orders_spacing_and_rejects_unfit_sheet(monkeypatch, status):
    from _drawing_annotation_bounds import annotation_box

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    sheet = SimpleNamespace(GetProperties2=lambda: (8, 12, 1, 1, 0, 0.4318, 0.2794, 0))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet)
    )
    calls = []
    handoff, obstacle = Mock(), Mock()
    handoff.seal.side_effect = lambda: calls.append("packing-seal")
    handoff.close.side_effect = lambda: calls.append("packing-close")
    obstacle.seal.side_effect = lambda: calls.append("obstacle-seal")
    obstacle.close.side_effect = lambda: calls.append("obstacle-close")
    factory = Mock(side_effect=(handoff, obstacle))
    monkeypatch.setattr(handoff_module, "AnnotationMeasurementHandoff", factory)
    position = Mock(side_effect=lambda *args, **kwargs: calls.append("callouts"))
    monkeypatch.setattr(callouts, "arrange_native_callouts", position)
    arrange = Mock(side_effect=lambda *args, **kwargs: calls.append("spacing"))
    report = Report(status=status, reason="measured witness")

    def pack(*args, **kwargs):
        calls.append("packing")
        return report

    repair = Mock(side_effect=pack)
    monkeypatch.setattr(gtol, "arrange_native_gtol_columns", arrange)
    monkeypatch.setattr(native, "repair_native_layout", repair)
    views = {"front": object()}
    notes = (SimpleNamespace(annotation=object()),)
    alignments, orderings = (), ()
    if status in (
        native.NativeLayoutStatus.NO_FIT,
        native.NativeLayoutStatus.SEARCH_LIMIT,
    ):
        with pytest.raises(RuntimeError, match=status.value):
            drawing.repair_project_drawing_layout(adapter, views=views, notes=notes)
    else:
        assert (
            drawing.repair_project_drawing_layout(adapter, views=views, notes=notes)
            is report
        )
    assert calls == [
        "callouts",
        "obstacle-seal",
        "spacing",
        "packing-seal",
        "packing",
        "obstacle-close",
        "packing-close",
    ]
    position.assert_called_once_with(
        adapter,
        views=views,
        measure_annotation=annotation_box,
        record_measurement=obstacle.record,
        gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        deferred_notes=(notes[0].annotation,),
    )
    assert factory.call_args_list == [
        call(
            adapter,
            views=views,
            measure_annotation=annotation_box,
            purpose=handoff_module.HandoffPurpose.INITIAL_PACKING,
        ),
        call(
            adapter,
            views=views,
            measure_annotation=annotation_box,
            purpose=handoff_module.HandoffPurpose.GTOL_OBSTACLES,
        ),
    ]
    arrange.assert_called_once_with(
        adapter,
        views=views,
        measure_annotation=annotation_box,
        measure_obstacle=obstacle.initial_measure,
        record_measurement=handoff.record,
    )
    arguments = dict(repair.call_args.kwargs)
    assert callable(arguments.pop("final_annotation_validation"))
    assert arguments == {
        "views": views,
        "title_block": native.Rect(
            drawing._TITLE_BLOCK_LEFT_M, 0, 0.4318, drawing._TITLE_BLOCK_TOP_M
        ),
        "measure_annotation": annotation_box,
        "initial_measure_annotation": handoff.initial_measure,
        "planning_headroom_m": 0.0005,
        "alignments": alignments,
        "orderings": orderings,
        "notes": notes,
    }


def test_project_layout_rejects_missing_sheet_contract_before_mutation(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    sheet = SimpleNamespace(GetProperties2=lambda: ())
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet)
    )
    arrange = Mock()
    position = Mock()
    monkeypatch.setattr(callouts, "arrange_native_callouts", position)
    monkeypatch.setattr(gtol, "arrange_native_gtol_columns", arrange)
    with pytest.raises(RuntimeError, match="complete sheet properties"):
        drawing.repair_project_drawing_layout(adapter, views={"front": object()})
    arrange.assert_not_called()
    position.assert_not_called()


@pytest.mark.parametrize("stage", ["callouts", "spacing", "packing"])
def test_project_layout_expires_handoff_after_native_failure(monkeypatch, stage):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _: value)
    sheet = SimpleNamespace(GetProperties2=lambda: (8, 12, 1, 1, 0, 0.4318, 0.2794, 0))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet)
    )
    handoff, obstacle = Mock(), Mock()
    monkeypatch.setattr(
        handoff_module,
        "AnnotationMeasurementHandoff",
        Mock(side_effect=(handoff, obstacle)),
    )
    position, arrange, repair = Mock(), Mock(), Mock()
    {"callouts": position, "spacing": arrange, "packing": repair}[
        stage
    ].side_effect = RuntimeError("native failure")
    monkeypatch.setattr(callouts, "arrange_native_callouts", position)
    monkeypatch.setattr(gtol, "arrange_native_gtol_columns", arrange)
    monkeypatch.setattr(native, "repair_native_layout", repair)
    with pytest.raises(RuntimeError, match="native failure"):
        drawing.repair_project_drawing_layout(adapter, views={"front": object()})
    handoff.close.assert_called_once_with()
    obstacle.close.assert_called_once_with()
    if stage != "packing":
        handoff.seal.assert_not_called()
        repair.assert_not_called()
    if stage == "callouts":
        arrange.assert_not_called()


@pytest.mark.parametrize(
    "status", [native.NativeLayoutStatus.APPLIED, native.NativeLayoutStatus.UNCHANGED]
)
@pytest.mark.parametrize("outcome", ["clear", "crossing"])
def test_final_clearance_logs_fresh_report_once_without_remeasurement(
    monkeypatch, status, outcome
):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _: value)
    sheet = SimpleNamespace(GetProperties2=lambda: (8, 12, 1, 1, 0, 0.4318, 0.2794, 0))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet)
    )
    handoff, obstacle = Mock(), Mock()
    monkeypatch.setattr(
        handoff_module,
        "AnnotationMeasurementHandoff",
        Mock(side_effect=(handoff, obstacle)),
    )
    monkeypatch.setattr(callouts, "arrange_native_callouts", Mock())
    monkeypatch.setattr(gtol, "arrange_native_gtol_columns", Mock())
    measure = Mock(side_effect=AssertionError("final callback must not remeasure"))
    monkeypatch.setattr(bounds_module, "annotation_box", measure)
    measurements = {"front": {"native-frame": object()}, "side": {}}
    result = {
        "front": {"gtol_count": 1, "displayed_stroke_count": 2, "crossings": []},
        "side": {"gtol_count": 0, "displayed_stroke_count": 0, "crossings": []},
    }
    validator = Mock(return_value=result)
    if outcome == "crossing":
        validator.side_effect = RuntimeError("exact final crossing coordinates")
    monkeypatch.setattr(clearance_module, "validate_gtol_leader_clearance", validator)
    log = Mock()
    monkeypatch.setattr(drawing._telemetry, "info", log)
    report = Report(status=status, reason="fresh final witness")

    def pack(*args, **kwargs):
        kwargs["final_annotation_validation"](measurements)
        return report

    monkeypatch.setattr(native, "repair_native_layout", Mock(side_effect=pack))
    if outcome == "crossing":
        with pytest.raises(RuntimeError, match="exact final crossing coordinates"):
            drawing.repair_project_drawing_layout(adapter, views={"front": object()})
    else:
        assert (
            drawing.repair_project_drawing_layout(adapter, views={"front": object()})
            is report
        )
    validator.assert_called_once_with(measurements)
    assert validator.call_args.args[0] is measurements
    measure.assert_not_called()
    handoff.close.assert_called_once_with()
    obstacle.close.assert_called_once_with()
    records = [
        call.kwargs
        for call in log.call_args_list
        if call.args[0] == "final native GTol clearance witnessed"
    ]
    if outcome == "crossing":
        assert records == []
        return
    assert len(records) == len(result)
    assert {
        row["view"]: json.loads(row["clearance_report"]) for row in records
    } == result
    assert all(row["measurement_source"] == "fresh_final_packing" for row in records)
