"""Diagnostic section views resolve the real base model before touching annotations."""

import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import probe_drawing_attachments as attachments


def section_reference(path, mode):
    model = NS(GetPathName=lambda: str(path))
    base = NS(
        GetUniqueName=lambda: "Base", GetName2=lambda: "Base", ReferencedDocument=model
    )
    view = NS(
        GetUniqueName=lambda: "Section",
        GetName2=lambda: "Section",
        ReferencedConfiguration="SectionConfiguration",
        ReferencedDocument=None,
        GetBaseView=lambda: base,
        GetAnnotationsByType=lambda _: (object(),),
    )
    if mode == "missing":
        view.GetBaseView = lambda: None
    if mode == "cycle":
        base.ReferencedDocument = None
        base.GetBaseView = lambda: view
    return view, model


@pytest.mark.parametrize(
    "name",
    [
        "probe_drawing_annotation_layout",
        "probe_drawing_mixed_commands",
        "probe_native_gtol_selection",
    ],
)
@pytest.mark.parametrize("mode", ["section", "missing", "cycle"])
@pytest.mark.parametrize("temporary_path", ["direct", "parent_alias"])
def test_actual_worker_resolves_base_source_or_names_failure_before_mutation(
    monkeypatch, tmp_path, name, mode, temporary_path
):
    module = importlib.import_module(name)
    original_mkdtemp = module.tempfile.mkdtemp

    def temporary_directory(**kwargs):
        path = Path(original_mkdtemp(**kwargs))
        if temporary_path == "parent_alias":
            return str(path / ".." / path.name)
        return str(path)

    monkeypatch.setattr(module.tempfile, "mkdtemp", temporary_directory)
    source, part = tmp_path / "cone-gear.SLDDRW", tmp_path / "cone-gear.SLDPRT"
    source.write_bytes(b"source drawing")
    part.write_bytes(b"source part")
    view, part_model = section_reference(part, mode)
    model = NS(
        Extension=object(),
        SelectionManager=object(),
        GetViews=lambda: ((object(), view),),
    )
    directories = []
    adapter = NS(
        currentModel=model,
        swApp=object(),
        ownership=NS(register_directory=directories.append, register_source=Mock()),
    )

    async def open_model(path):
        model.GetPathName = lambda: path
        adapter.currentModel = model
        return NS(is_success=True, data=None)

    async def close_model(*, save):
        assert save is False
        adapter.currentModel = None
        return NS(is_success=True, data=None)

    adapter.open_model = AsyncMock(side_effect=open_model)
    adapter.close_model = AsyncMock(side_effect=close_model)
    reached = RuntimeError("passed source hashing; stop before mutation")
    after_hash = Mock(side_effect=reached)
    monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(attachments, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(module, "CAD_ROOT", tmp_path / "cad")
    monkeypatch.setenv("HARMONIC_COM_SEAT", "offline-fixture")
    monkeypatch.setattr(module.sys, "argv", [name, str(source), "--worker"])
    monkeypatch.setattr(module._telemetry, "set_service", Mock())
    monkeypatch.setattr(
        module, "run_copy_diagnostic", lambda callback: asyncio.run(callback(adapter))
    )
    if name == "probe_drawing_annotation_layout":
        monkeypatch.setattr(module, "_document_formats", after_hash)
    if name == "probe_drawing_mixed_commands":
        monkeypatch.setattr(module, "snapshot", after_hash)
    if name == "probe_native_gtol_selection":
        monkeypatch.setattr(
            module, "_views", lambda _: {"Drawing View1": view, "Drawing View2": view}
        )
        monkeypatch.setattr(module, "ModelEntities", after_hash)
    pattern = {
        "section": "passed source hashing",
        "missing": "no resolved source model",
        "cycle": "cycle in base views",
    }[mode]
    with pytest.raises(RuntimeError, match=pattern) as caught:
        module.main()
    if mode == "section":
        assert caught.value is reached
        after_hash.assert_called_once()
        if name == "probe_native_gtol_selection":
            after_hash.assert_called_once_with(part_model)
    if mode != "section":
        after_hash.assert_not_called()
    adapter.close_model.assert_awaited_once_with(save=False)
    assert source.read_bytes() == b"source drawing"
    assert part.read_bytes() == b"source part"
    report_paths = list(directories[0].glob("*.json"))
    assert len(report_paths) == 1
    report = json.loads(report_paths[0].read_text(encoding="utf-8"))
    assert report["error"] == repr(caught.value)


@pytest.mark.parametrize("suffix", [".SLDASM", ".txt"])
def test_base_document_extraction_retains_part_only_contract(
    monkeypatch, tmp_path, suffix
):
    path = tmp_path / f"source{suffix}"
    path.write_bytes(b"protected")
    view, _ = section_reference(path, "section")
    monkeypatch.setattr(attachments, "_early_bound", lambda value, _: value)
    with pytest.raises(ValueError, match="part drawings only"):
        attachments.referenced_document(view)


def test_base_resolution_returns_current_native_handle_and_child_configuration(
    monkeypatch, tmp_path
):
    path = tmp_path / "source.SLDPRT"
    path.write_bytes(b"protected")
    view, first = section_reference(path, "section")
    monkeypatch.setattr(attachments, "_early_bound", lambda value, _: value)
    assert attachments.referenced_document(view) is first
    assert attachments.referenced_model(view) == {
        "path": str(path),
        "configuration": "SectionConfiguration",
    }
    reopened = NS(GetPathName=lambda: str(path))
    view.GetBaseView().ReferencedDocument = reopened
    assert attachments.referenced_document(view) is reopened


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["probe_gtol_autoarrange", "probe_gtol_rigid_body", "probe_gtol_commands"])
@pytest.mark.parametrize("mode", ["direct", "section", "section_empty_string", "missing", "cycle"])
async def test_gtol_probe_source_inventory_uses_existing_base_resolver(
    monkeypatch, tmp_path, name, mode
):
    from diagnostics import _owned_native_documents as owned

    module = importlib.import_module(f"diagnostics.{name}")
    source, part = tmp_path / "source.SLDDRW", tmp_path / "source.SLDPRT"
    source.write_bytes(b"protected drawing")
    part.write_bytes(b"protected part")
    view, native_source = section_reference(part, mode)
    if mode == "direct":
        view.ReferencedDocument = native_source
    if mode == "section_empty_string":
        view.ReferencedDocument = ""
    reached = RuntimeError("source bank complete; stop before native mutation")
    after_hash = Mock(side_effect=reached)
    if name == "probe_gtol_autoarrange":
        view.GetAnnotationsByType = after_hash
    if name == "probe_gtol_commands":
        view.GetAnnotationsByType = lambda _: (NS(GetName=lambda: "FCF", GetAttachedEntities3=after_hash),)
    drawing = NS(GetViews=lambda: ((object(), view),), Extension=object())
    adapter = NS(
        currentModel=drawing,
        swApp=object(),
        ownership=NS(register_source=Mock(), register_directory=Mock()),
        close_owned_documents=AsyncMock(),
    )

    async def open_model(path):
        drawing.GetPathName = lambda: path
        return NS(is_success=True, data=None)

    adapter.open_model = AsyncMock(side_effect=open_model)
    monkeypatch.setattr(module, "_early_bound", lambda item, _: item)
    monkeypatch.setattr(attachments, "_early_bound", lambda item, _: item)
    save = after_hash if name == "probe_gtol_rigid_body" else Mock()
    monkeypatch.setattr(owned, "save_drawing", save)
    render = Mock()
    monkeypatch.setattr(module, "render_pdf_png", render)
    pattern = {
        "missing": "no resolved source model", "cycle": "cycle in base views"
    }.get(mode, "source bank complete")
    with pytest.raises(RuntimeError, match=pattern) as caught:
        await module.probe(adapter, source, tmp_path)
    if mode in {"missing", "cycle"}:
        after_hash.assert_not_called()
    else:
        assert caught.value is reached
        after_hash.assert_called_once()
    if name != "probe_gtol_rigid_body":
        save.assert_not_called()
    render.assert_not_called()
    adapter.close_owned_documents.assert_awaited_once_with()
    report_name = {"probe_gtol_autoarrange": "autoarrange.json", "probe_gtol_commands": "commands.json", "probe_gtol_rigid_body": "rigid-body.json"}[name]
    report = json.loads((tmp_path / report_name).read_text(encoding="utf-8"))
    assert report["operation_error"] == repr(caught.value)
    assert report["source_hashes"] == report["source_hashes_after"]
    assert (str(part) in report["source_hashes"]) == (mode not in {"missing", "cycle"})
    assert source.read_bytes() == b"protected drawing"
    assert part.read_bytes() == b"protected part"
