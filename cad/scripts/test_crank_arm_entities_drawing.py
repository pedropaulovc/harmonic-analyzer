"""Offline evidence/ownership contracts for the crank-arm-only native probe."""

import asyncio
from contextlib import asynccontextmanager
from enum import Enum
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_crank_arm_entities as probe


class EvidenceKind(Enum):
    DIMENSION = "dimension"


@pytest.fixture
def native(monkeypatch, tmp_path):
    source = tmp_path / "crank-arm.SLDPRT"
    source.write_bytes(b"isolated source fixture")
    token = source.with_name(".crank-arm.execution")
    token.write_text(probe.sha(source), encoding="utf-8")
    directory = tmp_path / "evidence"
    directory.mkdir()
    model = SimpleNamespace(
        GetType=lambda: 1, GetPathName=lambda: str(source),
        GetSaveFlag=Mock(return_value=False),
    )
    app = SimpleNamespace(
        GetOpenDocumentByName=Mock(return_value=model),
        IsSame=Mock(side_effect=lambda left, right: int(left is right)),
        GetProcessID=lambda: 123, RevisionNumber=lambda: "34.3.0",
    )
    ownership = SimpleNamespace(
        register_directory=Mock(), register_source=Mock(), evidence=lambda: {"owned": []},
    )

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=model)

    adapter = SimpleNamespace(currentModel=model, swApp=app, ownership=ownership, open_model=open_model)
    observed = {"configuration": "Default", "dimensions": {"Depth@Arm": {"raw": 0.008, "kind": EvidenceKind.DIMENSION}}}
    required = {"Depth@Arm": {"value_system": 0.008, "tolerance_type": EvidenceKind.DIMENSION}}
    snapshot = Mock(return_value=(observed, {}))
    dimensions = Mock(return_value=(required, {}))
    monkeypatch.setattr(probe, "SOURCE", source)
    monkeypatch.setattr(probe, "TOKEN", token)
    monkeypatch.setattr(probe, "EXPECTED_SOURCE_SHA", probe.sha(source), raising=False)
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "revision", lambda path: f"revision:{Path(path).name}")
    monkeypatch.setattr(probe, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(probe, "dimension_snapshot", snapshot)
    monkeypatch.setattr(probe, "part_dimensions", dimensions)
    return SimpleNamespace(
        source=source, token=token, directory=directory, model=model, adapter=adapter,
        observed=observed, required=required, snapshot=snapshot, dimensions=dimensions,
    )


def test_source_snapshot_preserves_full_and_required_readbacks(native):
    result = probe.source_snapshot(native.adapter, native.source)
    assert result == {
        "dirty_before": False, "dirty_after": False,
        "observed_dimensions": native.observed, "required_dimensions": native.required,
    }
    native.snapshot.assert_called_once_with(
        native.adapter.swApp, native.model, native.source, required=probe.DRAWING_DIMENSIONS
    )
    native.dimensions.assert_called_once_with(
        native.adapter, native.source, "Default", targets=probe.DRAWING_DIMENSIONS
    )


@pytest.mark.parametrize("fault", ["document_type", "path", "different", "indeterminate"])
def test_source_snapshot_rejects_wrong_exact_owner_before_reading(native, fault):
    if fault == "document_type":
        native.model.GetType = lambda: 2
    if fault == "path":
        native.model.GetPathName = lambda: str(native.source.with_name("foreign.SLDPRT"))
    if fault in {"different", "indeterminate"}:
        native.adapter.swApp.IsSame.side_effect = None
        native.adapter.swApp.IsSame.return_value = 0 if fault == "different" else -1
    with pytest.raises(RuntimeError, match="wrong exact source owner"):
        probe.source_snapshot(native.adapter, native.source)
    native.snapshot.assert_not_called()
    native.dimensions.assert_not_called()
    native.model.GetSaveFlag.assert_not_called()


def test_provenance_requires_original_source_token_and_records_imports(native):
    record = probe.provenance()
    assert record["source_sha256"] == record["execution_token"] == probe.sha(native.source)
    assert record["source_size"] == native.source.stat().st_size
    assert Path(record["recipe_import"]).name == "draw_crank_arm.py"
    assert Path(record["adapter_import"]).name == "pywin32_adapter.py"
    assert record["root_commit"] and record["adapter_commit"]
    native.token.write_text("different identity", encoding="utf-8")
    with pytest.raises(RuntimeError, match="token"):
        probe.provenance()


def test_matching_replacement_source_and_token_cannot_replace_original_pin(native):
    native.source.write_bytes(b"different source even though its token matches")
    native.token.write_text(probe.sha(native.source), encoding="utf-8")
    with pytest.raises(RuntimeError):
        probe.provenance()


def test_capture_source_serializes_enum_evidence_without_losing_readbacks(native):
    result = asyncio.run(probe.capture_source(native.adapter, native.directory))
    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert report["status"] == "captured"
    assert report["source_snapshot"]["observed_dimensions"]["dimensions"]["Depth@Arm"]["kind"] == "dimension"
    assert report["source_snapshot"]["required_dimensions"]["Depth@Arm"]["tolerance_type"] == "dimension"
    assert report["source_sha256_after"] == report["provenance"]["source_sha256"]
    assert report["execution_token_after"] == report["provenance"]["execution_token"]
    native.adapter.ownership.register_directory.assert_called_once_with(native.directory)
    native.adapter.ownership.register_source.assert_called_once_with(native.source)


def test_json_evidence_rejects_unsupported_values_instead_of_stringifying_them():
    with pytest.raises(TypeError, match="unsupported evidence type"):
        json.dumps({"opaque": object()}, default=probe.json_default)


def test_capture_source_records_failed_snapshot_and_reraises_original(native):
    failure = RuntimeError("raw dimension read failed")
    native.snapshot.side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(probe.capture_source(native.adapter, native.directory))
    assert raised.value is failure
    report = json.loads((native.directory / "measurements.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["error"] == repr(failure)
    assert report["provenance"]["source_sha256"] == report["source_sha256_after"]


def test_report_write_failure_does_not_replace_original_snapshot_error(native, monkeypatch):
    failure = RuntimeError("original dimension read failure")
    native.snapshot.side_effect = failure
    original_write = Path.write_text

    def write(path, *args, **kwargs):
        if path.name == "measurements.json":
            raise OSError("report disk unavailable")
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(Exception) as raised:
        asyncio.run(probe.capture_source(native.adapter, native.directory))
    errors = getattr(raised.value, "exceptions", (raised.value,))
    assert errors[0] is failure, "report persistence must not hide the native failure"


@pytest.mark.parametrize("snapshot_failure", [None, RuntimeError("attachment snapshot failed")])
def test_capture_drawing_uses_owned_copy_and_retains_partial_evidence(native, monkeypatch, snapshot_failure):
    import draw_crank_arm as recipe
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics import probe_datum_shoulder as shoulder

    original = native.directory.parent / "baseline.SLDDRW"
    original.write_bytes(b"original drawing")
    monkeypatch.setattr(recipe, "OUTPUTS", SimpleNamespace(slddrw=original))
    drawing = object()
    opened = []

    @asynccontextmanager
    async def open_drawing(adapter, path):
        assert adapter is native.adapter
        assert path.parent == native.directory and path != original
        assert path.read_bytes() == original.read_bytes()
        opened.append(("open", path))
        try:
            yield drawing
        finally:
            opened.append(("close", path))

    def snapshot(model, *, app):
        assert model is drawing and app is native.adapter.swApp
        if snapshot_failure is not None:
            raise snapshot_failure
        return {"kind": EvidenceKind.DIMENSION}

    monkeypatch.setattr(attachments, "open_drawing", open_drawing)
    monkeypatch.setattr(attachments, "snapshot", snapshot)
    monkeypatch.setattr(attachments, "layout", lambda model: {"sheet_scale": [2, 1]})
    monkeypatch.setattr(shoulder, "all_annotation_layout", lambda adapter: ({"annotations": []}, {}))
    if snapshot_failure is None:
        asyncio.run(probe.capture_drawing(native.adapter, native.directory))
    if snapshot_failure is not None:
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(probe.capture_drawing(native.adapter, native.directory))
        assert raised.value is snapshot_failure
    report = json.loads((native.directory / "measurements.json").read_text(encoding="utf-8"))
    assert report["status"] == ("captured" if snapshot_failure is None else "failed")
    assert [operation for operation, _ in opened] == ["open", "close"]
    assert original.read_bytes() == b"original drawing"
    assert [call.args[0] for call in native.adapter.ownership.register_source.call_args_list] == [native.source, original]
    if snapshot_failure is None:
        assert report["attachments"] == {"kind": "dimension"}
        assert report["source_snapshot"]["dirty_after"] is False
    if snapshot_failure is not None:
        assert report["error"] == repr(snapshot_failure)


def test_worker_dispatches_complete_source_capture_through_owned_runner(native, monkeypatch):
    calls = []
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setenv("HARMONIC_COM_SEAT", "offline-parent-fixture")

    def runner(callback):
        calls.append("owned runner")
        return asyncio.run(callback(native.adapter))

    monkeypatch.setattr(probe, "run_copy_diagnostic", runner)
    result = probe.main(["source", "--worker"])
    assert calls == ["owned runner"]
    report_path = Path(result["report"])
    assert report_path.is_relative_to(probe.ROOT / "cad/out/reports")
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "captured"
