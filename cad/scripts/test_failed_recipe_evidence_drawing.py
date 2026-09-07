"""Failed diagnostics retain ink without changing the failed outcome or ownership."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import probe_datum_policy_recipes as probe
from diagnostics import probe_retained_drawing_export as printed
from test_owned_native_documents_drawing import Model, native  # noqa: F401
from test_datum_policy_recipes_drawing import Adapter, fixture_sources
from test_benchmark_drawing_recipes import recipe

PDF_ONLY_EXPORT = printed.export_pdf_only


@pytest.fixture
def scene(native, monkeypatch):  # noqa: F811
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    user = Model(None, title="Unrelated dirty drawing", dirty=True)
    native.app.documents.append(user)
    native.app.ActiveDoc = user
    adapter = owned.DiagnosticAdapter(native.adapter)
    adapter.ownership.register_directory(native.directory)
    part_path = native.directory / "owned-source.SLDPRT"
    part_path.write_bytes(b"owned source")
    asyncio.run(adapter.open_model(str(part_path)))
    part = adapter.currentModel
    with adapter.ownership.creating_document(owned.DocumentKind.DRAWING, native.copy):
        model = Model(None, title="Failed diagnostic drawing", dirty=True)
        model.references = [part]
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
    annotation, dimension = object(), object()
    drawing = {
        "semantics": {"checked": {"face": "geometry"}},
        "layout": {"view": "same"},
        "annotations": {"front/dimension": {"measurement": {"body": [1, 2, 3, 4]}}},
    }
    witness = Mock(return_value=(drawing, {"dimension": (annotation, dimension)}))
    monkeypatch.setattr(probe, "_drawing_witness", witness, raising=False)
    source = {"configuration": "Default", "dimensions": {"Width": 0.1}}
    source_witness = Mock(return_value=(source, {"Width": dimension}))
    monkeypatch.setattr(probe, "source_dimensions", source_witness)
    monkeypatch.setattr(probe, "compare_drawing", lambda *args: None)
    monkeypatch.setattr(
        probe.shoulder, "compare_all_annotation_layout", lambda *args: {}
    )
    export = Mock(side_effect=lambda _, path: path.write_bytes(b"PDF evidence"))
    render = Mock(side_effect=lambda _, path: path.write_bytes(b"PNG evidence"))
    monkeypatch.setattr(printed, "export_pdf_only", export)
    monkeypatch.setattr(printed, "render_pdf_png", render)
    trial = {
        "target": "channel_lever",
        "copy_source": str(part_path),
        "source_before": source,
        "status": "failed",
        "error": "RuntimeError('primary crossing failure')",
    }
    return SimpleNamespace(
        adapter=adapter,
        native=native,
        model=model,
        part=part,
        user=user,
        trial=trial,
        witness=witness,
        source_witness=source_witness,
        export=export,
        render=render,
    )


def retain(scene):
    probe.retain_failed_drawing(
        scene.adapter, scene.trial, scene.native.copy, lambda: None
    )
    return scene.trial["failure_evidence"]


def test_retains_fresh_scene_source_and_pdf_without_native_save_or_cleanup(scene):
    result = retain(scene)
    assert result["primary_error"] == scene.trial["error"]
    assert not result["errors"]
    assert result["before"]["drawing"] == result["after"]["drawing"]
    assert result["before"]["source"] == result["after"]["source"]
    assert result["hashes_before"] == result["hashes_after"]
    assert result["document_before"] == result["document_after"]
    assert result["document_after"]["path"] == ""
    assert scene.trial["status"] == "failed"
    assert scene.witness.call_count == scene.source_witness.call_count == 2
    scene.export.assert_called_once_with(
        scene.adapter, scene.native.directory / "failure.pdf"
    )
    scene.render.assert_called_once_with(
        scene.native.directory / "failure.pdf", scene.native.directory / "failure.png"
    )
    assert scene.native.app.documents == [scene.user, scene.part, scene.model]
    assert not scene.native.app.closes
    assert scene.user.dirty and scene.user.GetPathName() == ""
    receipt = json.loads((scene.native.directory / "failure-evidence.json").read_text())
    assert receipt["primary_error"] == result["primary_error"]
    assert receipt["pdf"]["sha256"] and receipt["png"]["sha256"]


def test_real_pdf_only_helper_receives_empty_native_target(scene, monkeypatch):
    monkeypatch.setattr(printed, "export_pdf_only", PDF_ONLY_EXPORT)

    def native_save(adapter, native_path, *, pdf_path):
        assert adapter is scene.adapter
        assert native_path == ""
        assert pdf_path == str(scene.native.directory / "failure.pdf")
        Path(pdf_path).write_bytes(b"native PDF")
        return {"pdf": pdf_path}

    save = Mock(side_effect=native_save)
    monkeypatch.setattr(printed, "native_save", save)
    result = retain(scene)
    assert not result["errors"]
    save.assert_called_once()
    assert scene.model.GetPathName() == "" and scene.model.dirty
    assert not scene.native.app.closes


@pytest.mark.parametrize(
    "wrong", ["active", "current", "kind", "other_owned", "hidden"]
)
def test_ownership_refusal_precedes_scene_reads_and_export(scene, wrong):
    if wrong == "active":
        scene.native.app.ActiveDoc = scene.user
    if wrong == "current":
        scene.native.adapter.currentModel = scene.user
    if wrong == "kind":
        scene.model.kind = 1
    if wrong == "other_owned":
        scene.adapter.ownership.current.paths = {
            scene.native.directory / "other.SLDDRW"
        }
    if wrong == "hidden":
        scene.native.app.documents.append(
            Model(None, title="Unknown hidden", visible=False)
        )
    result = retain(scene)
    assert result["errors"][0]["phase"] == "ownership"
    scene.witness.assert_not_called()
    scene.source_witness.assert_not_called()
    scene.export.assert_not_called()
    scene.render.assert_not_called()
    assert not scene.native.app.closes


@pytest.mark.parametrize("failure", ["before", "pdf", "png", "after"])
def test_evidence_phase_failure_is_retained_without_masking_primary(scene, failure):
    if failure in {"before", "after"}:
        good = scene.witness.return_value
        scene.witness.side_effect = (
            [RuntimeError("measurement failed"), good]
            if failure == "before"
            else [good, RuntimeError("measurement failed")]
        )
    if failure == "pdf":
        scene.export.side_effect = RuntimeError("export rejected")
    if failure == "png":
        scene.render.side_effect = RuntimeError("render rejected")
    result = retain(scene)
    assert any(item["phase"] == failure for item in result["errors"])
    assert result["primary_error"] == scene.trial["error"]
    assert scene.trial["status"] == "failed"
    assert "document_after" in result and "hashes_after" in result
    if failure == "pdf":
        scene.render.assert_not_called()
    assert not scene.native.app.closes


@pytest.mark.parametrize(
    "mutation", ["source_bytes", "source_value", "source_identity", "ink", "active"]
)
def test_export_mutation_is_reported_not_accepted(scene, mutation):
    def changed_export(_, path):
        path.write_bytes(b"PDF")
        if mutation == "source_bytes":
            Path(scene.trial["copy_source"]).write_bytes(b"unexpected native save")
        if mutation == "source_value":
            scene.source_witness.return_value = (
                {"configuration": "Default", "dimensions": {"Width": 0.2}},
                scene.source_witness.return_value[1],
            )
        if mutation == "source_identity":
            scene.source_witness.return_value = (
                scene.source_witness.return_value[0],
                {"Width": object()},
            )
        if mutation == "ink":
            original, handles = scene.witness.return_value
            scene.witness.return_value = (
                {**original, "annotations": {"moved": "ink"}},
                handles,
            )
        if mutation == "active":
            scene.native.app.ActiveDoc = scene.user

    scene.export.side_effect = changed_export
    result = retain(scene)
    assert result["errors"]
    assert result["primary_error"] == scene.trial["error"]
    assert scene.trial["status"] == "failed"


def test_existing_evidence_is_not_overwritten_or_exported(scene):
    target = scene.native.directory / "failure-evidence.json"
    target.write_text("previous evidence")
    result = retain(scene)
    assert result["errors"]
    assert target.read_text() == "previous evidence"
    scene.export.assert_not_called()


def test_source_dispatch_is_bound_before_native_document_state_reads(
    scene, monkeypatch
):
    raw = object()
    lookup = scene.native.app.GetOpenDocumentByName
    scene.native.app.GetOpenDocumentByName = lambda path: (
        raw if path == scene.trial["copy_source"] else lookup(path)
    )
    scene.native.app.IsSame = lambda first, second: int(
        (scene.part if first is raw else first)
        is (scene.part if second is raw else second)
    )
    monkeypatch.setattr(
        probe, "_early_bound", lambda value, _: scene.part if value is raw else value
    )
    result = retain(scene)
    assert not result["errors"]
    assert all(
        call.args[0] is scene.part for call in scene.source_witness.call_args_list
    )


@pytest.mark.parametrize("checkpoint_failure", ["pilot", "evidence"])
def test_checkpoint_errors_are_observations_not_new_primary_errors(
    scene, monkeypatch, checkpoint_failure
):
    checkpoint = Mock(side_effect=OSError("pilot report inaccessible"))
    if checkpoint_failure == "evidence":
        checkpoint = Mock()
        write_text = Path.write_text

        def rejecting_write(path, *args, **kwargs):
            if path.name == "failure-evidence.json":
                raise OSError("evidence report inaccessible")
            return write_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", rejecting_write)
    probe.retain_failed_drawing(
        scene.adapter, scene.trial, scene.native.copy, checkpoint
    )
    evidence = scene.trial["failure_evidence"]
    assert any(
        item["phase"] == f"{checkpoint_failure}_checkpoint"
        for item in evidence["errors"]
    )
    assert evidence["primary_error"] == scene.trial["error"]
    assert scene.trial["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "failed", "retention_failed"])
async def test_pilot_preserves_primary_exception_and_success_has_zero_retention_reads(
    tmp_path, monkeypatch, mode
):
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(
        probe.benchmark, "recipe_source", lambda *_: recipe(Path("unused.SLDPRT"))
    )
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "current-fixture")
    monkeypatch.setattr(probe, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(probe, "adapter_fingerprints", lambda: {"adapter": "same"})
    source_handle = object()
    source_reads = Mock(
        return_value=({"configuration": "Default"}, {"d": source_handle})
    )
    drawing_reads = Mock(return_value={"same": "drawing"})
    monkeypatch.setattr(probe, "source_dimensions", source_reads)
    monkeypatch.setattr(probe, "drawing_witness", drawing_reads)
    monkeypatch.setattr(
        probe, "compare_drawing_reopen", lambda *_: {"status": "passed"}
    )
    primary = RuntimeError("exact original crossing exception")
    adapter = Adapter("normal")
    if mode != "success":

        async def fail(*args):
            raise primary

        adapter.draw = fail

    def retention(actual, trial, output, checkpoint):
        assert actual is adapter
        assert trial["status"] == "failed" and trial["error"] == repr(primary)
        if mode == "retention_failed":
            raise OSError("unexpected evidence failure")

    capture = Mock(side_effect=retention)
    monkeypatch.setattr(probe, "retain_failed_drawing", capture)
    arguments = (
        adapter,
        "current-fixture",
        source_root,
        guard_root,
        tmp_path / "reports",
    )
    if mode == "success":
        await probe.pilot(*arguments, targets=("channel_lever",))
        capture.assert_not_called()
        assert drawing_reads.call_count == 2
        assert source_reads.call_count == 3
        return
    with pytest.raises(RuntimeError) as raised:
        await probe.pilot(*arguments, targets=("channel_lever",))
    assert raised.value is primary
    capture.assert_called_once()
    drawing_reads.assert_not_called()
    (path,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(path.read_text())
    assert report["status"] == "failed" and report["error"] == repr(primary)
    assert report["trials"][0]["error"] == repr(primary)
    if mode == "retention_failed":
        assert (
            "unexpected evidence failure"
            in report["trials"][0]["failure_evidence_error"]
        )
