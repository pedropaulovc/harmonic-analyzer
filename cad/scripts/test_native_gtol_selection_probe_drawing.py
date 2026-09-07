"""Save3 must prove both success and a zero error bank before cold replay."""

import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

import probe_native_gtol_selection as probe


@pytest.mark.parametrize("saved", [(True, 0, 0), (True, 0, 2), (True, 8, 0), (False, 0, 0), True, (True, 0)])
def test_actual_worker_retains_native_save_result_and_never_reopens_failed_save(monkeypatch, tmp_path, saved):
    source, part = tmp_path / "cone-gear.SLDDRW", tmp_path / "cone-gear.SLDPRT"
    source.write_bytes(b"original drawing")
    part.write_bytes(b"original part")
    part_model = NS(GetPathName=lambda: str(part))
    annotations = [NS(GetName=lambda role=role: role) for role in ("front_face", "bore")]
    views = {
        name: NS(GetAnnotationsByType=lambda kind, item=item: (item,))
        for name, item in zip(("Drawing View1", "Drawing View2"), annotations, strict=True)
    }
    model = NS(Save3=Mock(return_value=saved))
    adapter = NS(
        currentModel=model,
        ownership=NS(register_directory=Mock(), register_source=Mock(), assert_current_owned=Mock()),
    )

    async def open_model(path):
        model.GetPathName = lambda: path
        adapter.currentModel = model
        return NS(is_success=True, data=None)

    async def close_model(*, save):
        assert save is False
        adapter.currentModel = None
        return NS(is_success=True, data=None)

    adapter.open_model, adapter.close_model = AsyncMock(side_effect=open_model), AsyncMock(side_effect=close_model)
    resolver = Mock(return_value=NS(resolve=Mock(return_value={"front_face": object(), "bore": object()})))
    monkeypatch.setattr(probe, "CAD_ROOT", tmp_path / "cad")
    monkeypatch.setattr(probe, "_early_bound", lambda item, _: item)
    monkeypatch.setattr(probe, "_views", lambda _: views)
    monkeypatch.setattr(probe, "referenced_document", lambda _: part_model)
    monkeypatch.setattr(probe, "ModelEntities", resolver)
    monkeypatch.setattr(probe, "add_feature_control_frame", Mock(side_effect=[NS(GetAnnotation=lambda item=item: item) for item in annotations]))
    monkeypatch.setattr(probe, "_annotation_state", lambda adapter, item, entity: {"name": item.GetName(), "position_m": (0.1, 0.1, 0)})
    monkeypatch.setattr(probe, "run_copy_diagnostic", lambda callback: asyncio.run(callback(adapter)))
    monkeypatch.setattr(probe._telemetry, "set_service", Mock())
    monkeypatch.setenv("HARMONIC_COM_SEAT", "offline")
    monkeypatch.setattr(probe.sys, "argv", ["probe", str(source), "--worker"])
    if saved in ((True, 0, 0), (True, 0, 2)):
        result = probe.main()
        assert result["copy"] == adapter.open_model.call_args.args[0]
        assert adapter.open_model.await_count == adapter.close_model.await_count == 2
    else:
        with pytest.raises(RuntimeError, match="diagnostic copy save failed"):
            probe.main()
        adapter.open_model.assert_awaited_once()
        adapter.close_model.assert_awaited_once_with(save=False)
        resolver.assert_called_once_with(part_model)
    adapter.ownership.assert_current_owned.assert_called_once_with()
    model.Save3.assert_called_once_with(1, 0, 0)
    folder = adapter.ownership.register_directory.call_args.args[0]
    report = json.loads((folder / "projection.json").read_text(encoding="utf-8"))
    assert report["save_result"] == (list(saved) if isinstance(saved, tuple) else saved)
    assert all(row["before"] == row["after"] for row in report["source_hashes"].values())
    assert source.read_bytes() == b"original drawing"
    assert part.read_bytes() == b"original part"
