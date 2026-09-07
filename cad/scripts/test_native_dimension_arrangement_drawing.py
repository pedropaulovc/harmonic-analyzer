"""Offline safety/semantic checks for the single retained-view native control."""

from copy import deepcopy
from dataclasses import replace
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_dimension_arrangement as probe
from _drawing_annotation_bounds import AnnotationBounds, Segment, TextRun
from _drawing_view_packing import Rect


def selection_context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe, "null_callout", lambda: None)
    selected = []
    view = SimpleNamespace(GetName2=lambda: "Drawing View1")
    dimensions = {
        name: SimpleNamespace(GetNameForSelection=lambda name=name: name)
        for name in ("first", "second")
    }
    annotations = {
        name: SimpleNamespace(
            GetName=lambda name=name: name,
            Visible=1,
            OwnerType=0,
            Owner=view,
            GetSpecificAnnotation=lambda name=name: dimensions[name],
        )
        for name in dimensions
    }
    view.GetAnnotationsByType = lambda kind: (
        list(annotations.values()) if kind == 4 else ()
    )
    selection = SimpleNamespace(
        GetSelectedObjectCount2=lambda _: len(selected),
        GetSelectedObject6=lambda index, _: selected[index - 1],
    )

    def choose(name, *_):
        selected.append(dimensions[name])
        return True

    extension = SimpleNamespace(
        SelectByID2=Mock(side_effect=choose), AlignDimensions=Mock(return_value=True)
    )
    model = SimpleNamespace(
        SelectionManager=selection,
        Extension=extension,
        ClearSelection2=Mock(side_effect=lambda _: selected.clear()),
        ActivateView=Mock(return_value=True),
    )
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    return SimpleNamespace(currentModel=model, swApp=app), view, annotations, dimensions


def test_exact_bank_calls_autoarrange_once_without_position_or_rebuild(monkeypatch):
    adapter, view, annotations, _ = selection_context(monkeypatch)
    report = probe.arrange_once(adapter, view, set(annotations), annotations)
    assert report["selected"] == ("first", "second")
    adapter.currentModel.Extension.AlignDimensions.assert_called_once_with(0, 0.001)
    assert adapter.currentModel.ClearSelection2.call_count == 2


@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "replacement",
        "selected_identity",
        "select_false",
        "missing",
        "duplicate",
        "activate",
    ],
)
def test_bad_native_bank_aborts_before_arrangement_and_clears_only_selection(
    monkeypatch, fault
):
    adapter, view, annotations, dimensions = selection_context(monkeypatch)
    expected = dict(annotations)
    if fault == "owner":
        annotations["first"].Owner = object()
    if fault == "replacement":
        expected["first"] = object()
    if fault == "selected_identity":
        adapter.currentModel.SelectionManager.GetSelectedObject6 = lambda *_: object()
    if fault == "select_false":
        adapter.currentModel.Extension.SelectByID2 = Mock(return_value=False)
    if fault == "missing":
        expected["third"] = object()
    if fault == "duplicate":
        view.GetAnnotationsByType = lambda _: [
            annotations["first"],
            annotations["first"],
        ]
    if fault == "activate":
        adapter.currentModel.ActivateView.return_value = False
    with pytest.raises(RuntimeError):
        probe.arrange_once(adapter, view, set(expected), expected)
    adapter.currentModel.Extension.AlignDimensions.assert_not_called()
    assert adapter.currentModel.ClearSelection2.call_count == 2


def test_native_false_does_not_retry(monkeypatch):
    adapter, view, annotations, _ = selection_context(monkeypatch)
    adapter.currentModel.Extension.AlignDimensions.return_value = False
    with pytest.raises(RuntimeError, match="AutoArrange rejected"):
        probe.arrange_once(adapter, view, set(annotations), annotations)
    assert adapter.currentModel.Extension.AlignDimensions.call_count == 1


def bounds(name, kind, body, strokes=()):
    text = TextRun("value", (body.xmin, body.ymin), 0.0035, "Century Gothic", 0.0, 1, 0)
    return AnnotationBounds(
        name,
        kind,
        (body.xmin, body.ymin),
        body,
        body,
        (body,),
        (text,),
        (),
        ("font",),
        tuple(strokes),
    )


def test_dimension_stroke_targets_other_datum_body_without_exempting_dimension_family():
    line = Segment((0, 0), (1, 1))
    source = bounds("diameter", 4, Rect(0.7, 0.7, 0.8, 0.8), (line,))
    target = bounds("datum C", 2, Rect(0.4, 0.4, 0.5, 0.5))
    result = probe.dimension_crossings(
        {"view": {"diameter": source, "datum C": target}}
    )["view"]
    assert [(row["leader_annotation"], row["target_annotation"]) for row in result] == [
        ("diameter", "datum C")
    ]


def test_positive_control_requires_both_known_actual_segments():
    hits = [
        {"leader_annotation": source, "target_annotation": target, "segments": [0]}
        for source, target in probe.KNOWN_PAIRS
    ]
    probe.require_positive_baseline({probe.VIEW: hits})
    with pytest.raises(RuntimeError, match="both exact"):
        probe.require_positive_baseline({probe.VIEW: hits[:1]})
    with pytest.raises(RuntimeError, match="both exact"):
        probe.require_positive_baseline(
            {probe.VIEW: [{**row, "segments": []} for row in hits]}
        )


@pytest.mark.parametrize(
    "fault", ["text", "font", "type", "width", "stroke", "inventory"]
)
def test_full_fixed_witness_catches_changes(fault):
    row = bounds("datum", 2, Rect(0.1, 0.1, 0.2, 0.2))
    before = {"view": {"datum": row}}
    changed = row
    if fault == "text":
        changed = replace(row, text_runs=(replace(row.text_runs[0], value="wrong"),))
    if fault == "font":
        changed = replace(row, format_signature=("wrong",))
    if fault == "type":
        changed = replace(row, kind=4)
    if fault == "width":
        changed = replace(row, body=Rect(0.1, 0.1, 0.21, 0.2))
    if fault == "stroke":
        changed = replace(row, native_strokes=(Segment((0.1, 0.1), (0.2, 0.2)),))
    after = {"view": {} if fault == "inventory" else {"datum": changed}}
    with pytest.raises(RuntimeError):
        probe.compare_measured(before, after)


def test_selected_dimension_may_move_but_cannot_change_rendered_text():
    row = bounds("dim", 4, Rect(0.1, 0.1, 0.2, 0.2))
    moved = replace(
        row,
        anchor=(0.4, 0.4),
        body=row.body.translated((0.3, 0.3)),
        text_runs=(replace(row.text_runs[0], position=(0.4, 0.4)),),
    )
    probe.compare_measured(
        {"view": {"dim": row}}, {"view": {"dim": moved}}, {("view", "dim")}
    )
    with pytest.raises(RuntimeError, match="text/format"):
        probe.compare_measured(
            {"view": {"dim": row}},
            {
                "view": {
                    "dim": replace(
                        moved, text_runs=(replace(moved.text_runs[0], value="wrong"),)
                    )
                }
            },
            {("view", "dim")},
        )


def test_unsupported_visible_measurement_is_loud(monkeypatch):
    adapter, view, annotations, _ = selection_context(monkeypatch)
    view.GetAnnotations = lambda: list(annotations.values())
    monkeypatch.setattr(
        probe,
        "annotation_box",
        Mock(side_effect=ValueError("unsupported native symbol")),
    )
    with pytest.raises(ValueError, match="unsupported native symbol"):
        probe.measure_views(adapter, {probe.VIEW: view})


def test_half_hidden_annotation_is_not_silently_treated_as_hidden(monkeypatch):
    adapter, view, annotations, _ = selection_context(monkeypatch)
    annotations["first"].Visible = 2
    view.GetAnnotations = lambda: list(annotations.values())
    with pytest.raises(RuntimeError, match="visible view-owned"):
        probe.measure_views(adapter, {probe.VIEW: view})


def test_full_archived_source_values_and_tolerances_survive_exact_owner_remap(tmp_path):
    trial = {
        "copy_source": str(tmp_path / "old.SLDPRT"),
        "source_before": {
            "configuration": "Default",
            "dimensions": {
                "D@Feature": {
                    "full_name": "D@Feature@old.Part",
                    "value_system": 0.1,
                    "tolerance_type": 1,
                    "designation": "basic",
                }
            },
        },
    }
    expected = probe.copied_source_witness(trial, tmp_path / "copy.SLDPRT")
    assert expected["dimensions"]["D@Feature"]["full_name"] == "D@Feature@copy.Part"
    for key, value in (
        ("value_system", 0.2),
        ("tolerance_type", 0),
        ("full_name", "wrong"),
    ):
        wrong = deepcopy(expected)
        wrong["dimensions"]["D@Feature"][key] = value
        with pytest.raises(RuntimeError, match="parameters/tolerances"):
            probe.pilot.require_same_source(expected, wrong, "copied source baseline")


def test_native_error_cleanup_and_every_final_guard_are_retained(monkeypatch, tmp_path):
    source, drawing = tmp_path / "source.SLDPRT", tmp_path / "source.SLDDRW"
    source.touch()
    drawing.touch()
    expected = probe.retained.hashes((str(source), str(drawing)))
    monkeypatch.setattr(
        probe, "read_inputs", lambda _: ({}, {"drawing": drawing}, source, expected)
    )
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "revision")
    helper = Mock(side_effect=[{"helper": "before"}, {"helper": "after"}])
    adapter_hash = Mock(side_effect=[{"adapter": "before"}, {"adapter": "after"}])
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", helper)
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", adapter_hash)

    def fail_native(*_):
        raise RuntimeError("primary native failure")

    monkeypatch.setattr(probe, "relink_closed_copy", fail_native)

    async def fail_close():
        raise RuntimeError("owned cleanup refusal")

    adapter = SimpleNamespace(
        ownership=SimpleNamespace(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=fail_close,
    )
    with pytest.raises(ExceptionGroup) as caught:
        asyncio.run(
            probe.probe(adapter, tmp_path / "receipt.json", tmp_path / "reports")
        )
    messages = [str(error) for error in caught.value.exceptions]
    assert messages[0] == "primary native failure"
    assert "owned cleanup refusal" in messages
    assert "final helper_fingerprints_after witness changed" in messages
    assert "final imported_adapter_after witness changed" in messages
    receipt = next((tmp_path / "reports").glob("*/dimension-arrange.json"))
    report = json.loads(receipt.read_text())
    assert report["inputs_after"] == expected
    assert len(report["copies_after"]) == 2
    assert report["error"] == "RuntimeError('primary native failure')"
    assert report["status"] == "failed"
    assert helper.call_count == adapter_hash.call_count == 2


def test_archive_remap_changes_only_exact_copied_owner(tmp_path):
    old, new = tmp_path / "old.SLDPRT", tmp_path / "new.SLDPRT"
    row = {
        "semantics": {
            "models": {"view": {"path": str(old), "configuration": "Default"}},
            "dimensions": {
                "D": {
                    "kind": "model_dimension",
                    "components": [
                        {
                            "qualified_name": "D@Feature@old.Part",
                            "value_system": 0.1,
                            "tolerance_type": 1,
                        }
                    ],
                }
            },
        }
    }
    trial = {"copy_source": str(old), "reopened": row}
    result = probe.copied_archive(trial, new)
    assert row["semantics"]["models"]["view"]["path"] == str(old)
    assert result["semantics"]["models"]["view"]["path"] == str(new)
    assert result["semantics"]["dimensions"]["D"]["components"][0] == {
        "qualified_name": "D@Feature@new.Part",
        "value_system": 0.1,
        "tolerance_type": 1,
    }
    wrong = deepcopy(trial)
    wrong["reopened"]["semantics"]["dimensions"]["D"]["components"][0][
        "qualified_name"
    ] = "D@Feature@unrelated.Part"
    with pytest.raises(RuntimeError, match="different source"):
        probe.copied_archive(wrong, new)


@pytest.mark.parametrize("fault", ["unowned", "open", "wrong_bytes", "native_false"])
def test_closed_reference_change_is_scoped_and_fail_loud(monkeypatch, tmp_path, fault):
    drawing, previous, part = (
        tmp_path / "copy.SLDDRW",
        tmp_path / "old.SLDPRT",
        tmp_path / "copy.SLDPRT",
    )
    for path in (drawing, previous, part):
        path.touch()
    adapter = SimpleNamespace(
        ownership=SimpleNamespace(directories={tmp_path}, inventory=Mock()),
        swApp=SimpleNamespace(
            GetOpenDocumentByName=Mock(return_value=None),
            ReplaceReferencedDocument=Mock(return_value=True),
        ),
    )
    if fault == "unowned":
        adapter.ownership.directories = set()
    if fault == "open":
        adapter.swApp.GetOpenDocumentByName.return_value = object()
    if fault == "wrong_bytes":
        monkeypatch.setattr(
            probe.pilot.attachments,
            "file_digest",
            lambda path: "old" if path == previous else "different",
        )
    if fault == "native_false":
        adapter.swApp.ReplaceReferencedDocument.return_value = False
    with pytest.raises(RuntimeError):
        probe.relink_closed_copy(adapter, drawing, previous, part)
    assert adapter.swApp.ReplaceReferencedDocument.call_count == int(
        fault == "native_false"
    )


def test_parent_environment_rejected_before_any_receipt_or_native_wrapper(monkeypatch):
    monkeypatch.delenv("HARMONIC_SW_AUTOSTART", raising=False)
    read = Mock(side_effect=AssertionError("input work must not start"))
    monkeypatch.setattr(probe, "read_inputs", read)
    with pytest.raises(RuntimeError, match="AUTOSTART"):
        probe.main(["--receipt", str(Path("unopened.json"))])
    read.assert_not_called()
