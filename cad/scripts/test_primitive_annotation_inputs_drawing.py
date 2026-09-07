"""Primitive-copy worker inputs retain distinct, unsaved diagnostic drawings."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import probe_drawing_primitive_annotations as probe


def test_worker_retains_distinct_copies_for_equal_source_filenames(
    monkeypatch, tmp_path
):
    sources = tuple(tmp_path / directory / "same.SLDDRW" for directory in ("a", "b"))
    contents = (b"first original drawing", b"second original drawing")
    for source, content in zip(sources, contents, strict=True):
        source.parent.mkdir()
        source.write_bytes(content)
    ownership = SimpleNamespace(register_directory=Mock(), register_source=Mock())
    adapter = SimpleNamespace(currentModel=None, ownership=ownership)
    opened = []
    closed = []

    async def open_model(path):
        opened.append((Path(path), Path(path).read_bytes()))
        adapter.currentModel = SimpleNamespace(
            GetPathName=lambda: path, GetViews=lambda: ()
        )
        return SimpleNamespace(is_success=True, data=None)

    async def close_model(*, save):
        assert save is False
        closed.append(Path(adapter.currentModel.GetPathName()))
        adapter.currentModel = None
        return SimpleNamespace(is_success=True, data=None)

    adapter.open_model = AsyncMock(side_effect=open_model)
    adapter.close_model = AsyncMock(side_effect=close_model)
    monkeypatch.setattr(probe, "CAD_ROOT", tmp_path / "cad")
    monkeypatch.setattr(probe, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(probe._telemetry, "set_service", Mock())
    monkeypatch.setattr(
        probe, "run_copy_diagnostic", lambda callback: asyncio.run(callback(adapter))
    )
    monkeypatch.setattr(
        probe.sys, "argv", [probe.__file__, *map(str, sources), "--worker"]
    )
    monkeypatch.setenv("HARMONIC_COM_SEAT", "offline-test")

    result = probe.main()

    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    rows = report["drawings"]
    copies = tuple(Path(row["copy"]) for row in rows)
    assert len(rows) == len(set(copies)) == 2
    assert tuple(row["source"] for row in rows) == tuple(map(str, sources))
    assert tuple(copy.read_bytes() for copy in copies) == contents
    assert tuple(source.read_bytes() for source in sources) == contents
    assert report["source_unchanged"] == dict.fromkeys(map(str, sources), True)
    assert opened == list(zip(copies, contents, strict=True))
    assert closed == list(copies)
    assert adapter.currentModel is None
    adapter.close_model.assert_has_awaits([call(save=False), call(save=False)])
    ownership.register_source.assert_has_calls([call(source) for source in sources])
    folder = Path(result["report"]).parent
    ownership.register_directory.assert_called_once_with(folder)
    assert all(copy.parent == folder and copy not in sources for copy in copies)
