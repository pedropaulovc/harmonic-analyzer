"""PR680 diagnostic failures retain their cause and complete final evidence."""

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import probe_gtol_autoarrange as arrange
from diagnostics import probe_source_basic_dimensions as basic


@pytest.mark.asyncio
async def test_displaced_control_without_dimension_records_named_failure(
    monkeypatch, tmp_path
):
    source = tmp_path / "original.SLDDRW"
    source.write_bytes(b"original")
    model = NS(GetViews=lambda: (), ClearSelection2=Mock())
    adapter = NS(
        swApp=object(),
        currentModel=model,
        ownership=NS(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=AsyncMock(),
    )

    async def open_model(path):
        model.GetPathName = lambda: path
        return NS(is_success=True, data=None)

    adapter.open_model = open_model
    monkeypatch.setattr(arrange, "_early_bound", lambda value, _: value)
    save = Mock()
    monkeypatch.setattr(owned, "save_drawing", save)
    monkeypatch.setattr(arrange, "render_pdf_png", Mock())
    with pytest.raises(
        RuntimeError, match="displaced-dimensions control requires one native dimension"
    ):
        await arrange.probe(adapter, source, tmp_path)
    row = json.loads((tmp_path / "autoarrange.json").read_text(encoding="utf-8"))
    assert "requires one native dimension" in row["operation_error"]
    assert len(row["trials"]) == 3
    assert save.call_count == 2
    assert adapter.close_owned_documents.await_count == 3
    assert row["source_hashes"] == row["source_hashes_after"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["drawing_hash", "part_hash", "cleanup", "checkpoint", "all"]
)
async def test_basic_probe_keeps_primary_error_and_per_source_final_evidence(
    monkeypatch, tmp_path, fault
):
    source, part = tmp_path / "original.SLDDRW", tmp_path / "original.SLDPRT"
    source.write_bytes(b"drawing")
    part.write_bytes(b"part")
    primary = RuntimeError("drawing semantic witness refused")
    cleanup_error = RuntimeError("owned cleanup refused")
    state = {"phase": "initial"}
    model = NS()
    adapter = NS(
        swApp=object(),
        currentModel=model,
        ownership=NS(register_directory=Mock(), register_source=Mock()),
    )

    async def close():
        if state["phase"] == "final" and fault in {"cleanup", "all"}:
            raise cleanup_error

    async def open_model(path):
        model.GetPathName = lambda: path
        return NS(is_success=True, data=None)

    adapter.open_model = open_model
    adapter.close_owned_documents = AsyncMock(side_effect=close)
    monkeypatch.setattr(basic, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(basic.attachments, "views", lambda _: {"view": object()})
    monkeypatch.setattr(
        basic.attachments,
        "referenced_model",
        lambda _: {"path": str(part), "configuration": "Default"},
    )

    def fail_snapshot(*_):
        state["phase"] = "final"
        raise primary

    monkeypatch.setattr(basic, "drawing_dimensions", fail_snapshot)
    original_digest = basic.file_digest
    final_reads = []

    def digest(path):
        if state["phase"] == "final":
            final_reads.append(path)
            if (path == source and fault in {"drawing_hash", "all"}) or (
                path == part and fault in {"part_hash", "all"}
            ):
                raise OSError(f"unreadable {path.name}")
        return original_digest(path)

    monkeypatch.setattr(basic, "file_digest", digest)
    writes = []
    original_write = Path.write_text

    def write(path, text, *args, **kwargs):
        if path.name == "source-basic-dimensions.json":
            writes.append(json.loads(text))
            if fault in {"checkpoint", "all"}:
                raise OSError("checkpoint unavailable")
        return original_write(path, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(RuntimeError) as caught:
        await basic.probe(adapter, source, tmp_path)
    assert caught.value is primary
    assert final_reads == [source, part]
    assert len(writes) == 1
    report = writes[0]
    assert report["operation_error"] == repr(primary)
    assert report["status"] == "failed"
    assert set(report["source_hashes_after"]) == {str(source), str(part)}
    for path, hash_fault in ((source, "drawing_hash"), (part, "part_hash")):
        after = report["source_hashes_after"][str(path)]
        if fault in {hash_fault, "all"}:
            assert "unreadable" in after["error"]
        else:
            assert after == report["source_hashes"][str(path)]
    if fault in {"cleanup", "all"}:
        assert report["cleanup_error"] == repr(cleanup_error)
    assert primary.__notes__
