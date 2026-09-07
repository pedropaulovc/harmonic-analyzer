"""Foundation diagnostic errors must survive cleanup and report-write failures."""

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import probe_gtol_leader_override as gtol
from diagnostics import probe_datum_shoulder as shoulder
from diagnostics import probe_retained_drawing_export as retained


@pytest.mark.asyncio
async def test_gtol_owner_construction_failure_still_finalizes_evidence(
    monkeypatch, tmp_path
):
    source, part = tmp_path / "source.SLDDRW", tmp_path / "part.SLDPRT"
    source.write_bytes(b"drawing")
    part.write_bytes(b"part")
    primary = RuntimeError("hidden pre-existing document; ownership refused")
    monkeypatch.setattr(gtol, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(gtol, "ExistingSessionCopy", Mock(side_effect=primary))
    adapter = NS(swApp=object(), open_model=AsyncMock(), close_model=AsyncMock())
    with pytest.raises(RuntimeError) as caught:
        await gtol.probe(adapter, source, part, tmp_path)
    assert caught.value is primary
    adapter.open_model.assert_not_awaited()
    adapter.close_model.assert_not_awaited()
    report = json.loads((tmp_path / "gtol-leader-override.json").read_text())
    assert report["error"] == repr(primary)
    assert report["source_hashes_after"] == report["source_hashes"]
    assert "cleanup_error" not in report


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary", ["cleanup", "source", "report", "all"])
async def test_finalizer_preserves_original_error_and_all_secondary_evidence(
    monkeypatch, tmp_path, secondary
):
    source, path = tmp_path / "part.SLDPRT", tmp_path / "report.json"
    source.write_bytes(b"before")
    report = {"source_hashes": {str(source): shoulder.file_digest(source)}}
    primary = RuntimeError("original probe failure")
    cleanup_error = RuntimeError("owned cleanup refused")
    cleanup = AsyncMock(
        side_effect=cleanup_error if secondary in ("cleanup", "all") else None
    )
    if secondary in ("source", "all"):
        source.write_bytes(b"changed")
    written = []
    original_write = Path.write_text

    def write(target, text, *args, **kwargs):
        if target == path:
            written.append(json.loads(text))
            if secondary in ("report", "all"):
                raise OSError("report volume unavailable")
        return original_write(target, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)

    async def failing():
        try:
            raise primary
        finally:
            await shoulder.finalize_probe(cleanup, report, path)

    with pytest.raises(RuntimeError) as caught:
        await failing()
    assert caught.value is primary
    cleanup.assert_awaited_once()
    assert written
    if secondary in ("cleanup", "all"):
        assert report["cleanup_error"] == repr(cleanup_error)
    if secondary in ("source", "all"):
        assert report["source_hashes_after"] != report["source_hashes"]
        assert "source_guard_error" in report
    if secondary in ("report", "all"):
        assert "volume unavailable" in report["report_error"]
    assert primary.__notes__


@pytest.mark.asyncio
async def test_gtol_existing_owner_is_closed_once_on_early_probe_failure(
    monkeypatch, tmp_path
):
    source, part = tmp_path / "source.SLDDRW", tmp_path / "part.SLDPRT"
    source.write_bytes(b"drawing")
    part.write_bytes(b"part")
    primary = RuntimeError("owned open authorization refused")
    owner = NS(baseline=[], expect_open=Mock(side_effect=primary), close=AsyncMock())
    monkeypatch.setattr(gtol, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(gtol, "ExistingSessionCopy", lambda *_: owner)
    with pytest.raises(RuntimeError) as caught:
        await gtol.probe(NS(swApp=object()), source, part, tmp_path)
    assert caught.value is primary
    owner.close.assert_awaited_once()
    report = json.loads((tmp_path / "gtol-leader-override.json").read_text())
    assert report["source_hashes_after"] == report["source_hashes"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["checkpoint", "hash_read", "both"])
async def test_retained_export_finalization_cannot_replace_probe_error(
    monkeypatch, tmp_path, failure
):
    source = tmp_path / "protected.SLDPRT"
    source.write_bytes(b"protected")
    expected = {str(source): retained.pilot.attachments.file_digest(source)}
    monkeypatch.setattr(
        retained, "read_retained", lambda _: ({}, {}, {"pdf": source}, source, expected)
    )
    monkeypatch.setattr(retained.pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(retained.pilot, "adapter_fingerprints", lambda: {})
    primary = RuntimeError("original PDF reader failed")
    monkeypatch.setattr(retained, "pdf_title", Mock(side_effect=primary))
    original_final = retained.final_hashes
    calls = []

    def hashes(paths):
        calls.append(tuple(paths))
        if failure in ("hash_read", "both") and len(calls) == 1:
            raise ValueError("unexpected hash reader failure")
        return original_final(paths)

    monkeypatch.setattr(retained, "final_hashes", hashes)
    written = []
    original_write = Path.write_text

    def write(path, text, *args, **kwargs):
        if path.name == "retained-export.json":
            written.append(json.loads(text))
            if len(written) > 1 and failure in ("checkpoint", "both"):
                raise OSError("final checkpoint unavailable")
        return original_write(path, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    adapter = NS(ownership=NS(register_directory=Mock(), register_source=Mock()))
    with pytest.raises(RuntimeError) as caught:
        await retained.probe(adapter, source, tmp_path / "reports")
    assert caught.value is primary
    assert len(calls) == 2  # A failed protected hash bank must not skip the copy bank.
    assert len(written) == 2
    assert written[-1]["error"] == repr(primary)
    assert written[-1]["status"] == "failed"
    assert "copy_after" in written[-1]
    if failure in ("hash_read", "both"):
        assert "unexpected hash reader failure" in written[-1]["inputs_after"]["error"]
    assert primary.__notes__


def test_final_hashes_already_records_oserror_without_throwing(monkeypatch):
    missing = OSError("missing native input")
    monkeypatch.setattr(
        retained.pilot.attachments, "file_digest", Mock(side_effect=missing)
    )
    assert retained.final_hashes(("missing.SLDPRT",)) == {
        "missing.SLDPRT": {"error": repr(missing)}
    }


@pytest.mark.asyncio
async def test_finalizer_report_failure_without_primary_still_fails(
    monkeypatch, tmp_path
):
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"protected")
    report = {"source_hashes": {str(source): shoulder.file_digest(source)}}
    failure = OSError("report unavailable")
    monkeypatch.setattr(Path, "write_text", Mock(side_effect=failure))
    cleanup = AsyncMock()
    with pytest.raises(OSError) as caught:
        await shoulder.finalize_probe(cleanup, report, tmp_path / "report.json")
    assert caught.value is failure
    assert report["source_hashes_after"] == report["source_hashes"]
    assert report["report_error"] == repr(failure)
    cleanup.assert_awaited_once()
