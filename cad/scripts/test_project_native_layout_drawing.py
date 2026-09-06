"""Project layout must run native spacing before measured fit and fail unsaved."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_project_layout as drawing
import _drawing_native_callouts as callouts
import _drawing_native_gtol as gtol
import _drawing_native_layout as native
import _drawing_measurement_handoff as handoff_module


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
    handoff = Mock()
    handoff.seal.side_effect = lambda: calls.append("seal")
    handoff.close.side_effect = lambda: calls.append("close")
    factory = Mock(return_value=handoff)
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
    assert calls == ["callouts", "spacing", "seal", "packing", "close"]
    position.assert_called_once_with(
        adapter,
        views=views,
        measure_annotation=annotation_box,
        gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        deferred_notes=(notes[0].annotation,),
    )
    factory.assert_called_once_with(
        adapter, views=views, measure_annotation=annotation_box
    )
    arrange.assert_called_once_with(
        adapter,
        views=views,
        measure_annotation=annotation_box,
        record_measurement=handoff.record,
    )
    assert repair.call_args.kwargs == {
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
    handoff = Mock()
    monkeypatch.setattr(
        handoff_module, "AnnotationMeasurementHandoff", Mock(return_value=handoff)
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
    if stage != "packing":
        handoff.seal.assert_not_called()
        repair.assert_not_called()
    if stage == "callouts":
        arrange.assert_not_called()
