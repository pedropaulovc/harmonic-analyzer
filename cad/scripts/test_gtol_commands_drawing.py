"""Offline witnesses for the copy-only native annotation-command control."""

import ast
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

import pytest

from diagnostics import probe_gtol_commands as probe


def command_context(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    app, model, drawing = Mock(), Mock(), Mock()
    bank = [("view", Mock()), ("view", Mock())]
    model.SelectionManager.GetSelectedObjectCount2.return_value = len(bank)
    return app, model, drawing, bank


@pytest.mark.parametrize("command", [317, 307, 2976])
def test_native_command_selects_one_exact_bank(monkeypatch, command):
    app, model, drawing, bank = command_context(monkeypatch)
    app.IsCommandEnabled.return_value = False
    app.RunCommand.return_value = True
    result = probe.run_command(app, model, drawing, bank, command)
    assert result["enabled"] is False
    assert result["return"] is True
    assert result["selected"] == 2
    assert result["seconds"] >= 0
    drawing.ActivateView.assert_called_once_with("view")
    for _, item in bank:
        item.Select2.assert_called_once_with(True, 0)
    app.RunCommand.assert_called_once_with(command, "")
    assert model.ClearSelection2.call_count == 2


@pytest.mark.parametrize(
    "failure", ["single", "mixed_view", "activate", "select", "count"]
)
def test_invalid_bank_prevents_command(monkeypatch, failure):
    app, model, drawing, bank = command_context(monkeypatch)
    if failure == "single":
        bank.pop()
    if failure == "mixed_view":
        bank[1] = ("other-view", bank[1][1])
    if failure == "activate":
        drawing.ActivateView.return_value = False
    if failure == "select":
        bank[1][1].Select2.return_value = False
    if failure == "count":
        model.SelectionManager.GetSelectedObjectCount2.return_value = 3
    with pytest.raises(RuntimeError):
        probe.run_command(app, model, drawing, bank, 317)
    app.RunCommand.assert_not_called()


def test_rejected_native_command_is_reported_without_fallback(monkeypatch):
    app, model, drawing, bank = command_context(monkeypatch)
    app.RunCommand.return_value = False
    assert probe.run_command(app, model, drawing, bank, 317)["return"] is False
    app.RunCommand.assert_called_once()


def witness():
    return {
        "view/FCF": {
            "source": "source.SLDPRT",
            "attachment_types": (2,),
            "frame_signature": {"datum": "A", "tolerance": "0.05"},
            "entity_reference": (1, 2, 255),
            "dangling": False,
            "ink": {
                "position": (0.1, 0.1, 0),
                "gtol": {"text": [{"text": "0.05"}, {"text": "DATUM B SIDE"}]},
            },
        }
    }


def comparison_context(monkeypatch):
    app, extension, entity = Mock(), Mock(), Mock()
    app.IsSame.return_value = 1
    resolver = Mock(return_value=entity)
    monkeypatch.setattr(probe, "resolve_reference", resolver)
    handles = {"view/FCF": {"entity": entity, "extension": extension}}
    return app, handles, resolver


def test_actual_motion_not_command_boolean_defines_effect(monkeypatch):
    app, handles, resolver = comparison_context(monkeypatch)
    before = witness()
    after = deepcopy(before)
    assert probe.compare(before, after, handles, app, stage="noop") == {"view/FCF": 0}
    after["view/FCF"]["ink"]["position"] = (0.1, 0.12, 0)
    assert probe.compare(before, after, handles, app, stage="moved")[
        "view/FCF"
    ] == pytest.approx(0.02)
    resolver.assert_called_with(handles["view/FCF"]["extension"], (1, 2, 255))
    app.IsSame.assert_called_with(
        handles["view/FCF"]["entity"], handles["view/FCF"]["entity"]
    )


@pytest.mark.parametrize(
    "failure",
    [
        "coverage",
        "source",
        "attachment_types",
        "frame_signature",
        "belowtext",
        "dangling",
        "entity",
    ],
)
def test_comparison_fails_on_semantic_or_attachment_drift(monkeypatch, failure):
    app, handles, _ = comparison_context(monkeypatch)
    before = witness()
    after = deepcopy(before)
    if failure == "coverage":
        after.clear()
    if failure in ("source", "attachment_types", "frame_signature"):
        after["view/FCF"][failure] = "changed"
    if failure == "belowtext":
        after["view/FCF"]["ink"]["gtol"]["text"][1]["text"] = "WRONG SIDE"
    if failure == "dangling":
        after["view/FCF"]["dangling"] = True
    if failure == "entity":
        app.IsSame.return_value = 0
    with pytest.raises(RuntimeError):
        probe.compare(before, after, handles, app, stage="mutation")


def test_snapshot_uses_drawing_not_source_part_persistent_reference_context(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(probe, "_early_bound", lambda item, name: item)
    monkeypatch.setattr(probe, "file_digest", lambda path: "sha")
    monkeypatch.setattr(probe, "metrics", lambda item: {})

    @dataclass
    class Signature:
        text: str

    monkeypatch.setattr(probe, "gtol_frame_signature", lambda xml: Signature(xml))
    drawing, view, annotation, entity = Mock(), Mock(), Mock(), Mock()
    drawing.GetViews.return_value = [(Mock(), view)]
    drawing.Extension.GetPersistReference3.return_value = (1, 2, 255)
    view.GetName2.return_value = "view"
    view.GetAnnotationsByType.return_value = (annotation,)
    view.ReferencedDocument.GetPathName.return_value = str(tmp_path / "source.SLDPRT")
    annotation.GetName.return_value = "FCF"
    annotation.GetAttachedEntities3.return_value = (entity,)
    annotation.GetAttachedEntityTypes.return_value = (2,)
    annotation.GetSpecificAnnotation.return_value.GetFrame.return_value.GetSymbolXml.return_value = "xml"
    rows, handles = probe.snapshot(drawing, {})
    drawing.Extension.GetPersistReference3.assert_called_once_with(entity)
    view.ReferencedDocument.Extension.GetPersistReference3.assert_not_called()
    assert rows["view/FCF"]["reference_context"] == "drawing"
    assert handles["view/FCF"]["extension"] is drawing.Extension


def test_diagnostic_never_positions_or_recreates_annotations():
    tree = ast.parse(Path(probe.__file__).read_text())
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {
        "SetPosition2",
        "InsertGtol",
        "SetAttachedEntities",
        "SelectByID2",
        "SelectByRay",
    }
    assert {"RunCommand", "IsCommandEnabled", "GetObjectByPersistReference3"} <= calls
