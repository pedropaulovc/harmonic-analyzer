from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from diagnostics import diag_mcmaster_lib as diag


class _Model:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def ClearSelection2(self, _all_selections: bool) -> None:
        self._events.append("clear")

    def SaveAs3(self, path: str, _version: int, _options: int) -> int:
        self._events.append(f"save_as:{Path(path).name}")
        return 0


class _SwApp:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def CloseAllDocuments(self, include_unsaved: bool) -> bool:
        assert include_unsaved is True
        self._events.append("close")
        return True


class _Adapter:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.swApp = _SwApp(events)
        self.currentModel = _Model(events)

    def _attempt(self, call, default=None):
        try:
            return call()
        except Exception:
            return default

    async def save_file(self, _path: str):
        self._events.append("save_file")
        return SimpleNamespace(is_success=True, data=None, error=None)

    async def open_model(self, path: str):
        assert self.currentModel is None, "previous document was not closed"
        self._events.append(f"open:{Path(path).name}")
        self.currentModel = _Model(self._events)
        return SimpleNamespace(is_success=True, data=None, error=None)


def test_stl_arbitration_closes_each_document_before_open_or_compare(
    tmp_path: Path, monkeypatch,
) -> None:
    events: list[str] = []
    adapter = _Adapter(events)
    part_no = "TEST"

    monkeypatch.setattr(diag, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(diag, "MCMASTER_DIR", tmp_path / "vendor")
    monkeypatch.setattr(
        diag,
        "mass_properties",
        lambda _adapter: {
            "volume_mm3": 101.0,
            "surface_mm2": 1000.0,
            "com_mm": [0.0, 0.0, 0.0],
        },
    )
    monkeypatch.setattr(diag, "face_areas", lambda _adapter: [1200.0])
    monkeypatch.setattr(diag, "vendor_face_areas", lambda _truth: [1200.0])
    monkeypatch.setattr(diag, "_early_bound", lambda obj, _name: obj)

    async def _export_views(_adapter, _stem: str) -> dict[str, str]:
        events.append("export_views")
        return {}

    monkeypatch.setattr(diag, "export_views", _export_views)

    def _load(path: str):
        assert adapter.currentModel is None, "last STL document was not closed"
        events.append(f"load:{Path(path).name}")
        return SimpleNamespace(volume=100.0, area=1000.0)

    monkeypatch.setitem(sys.modules, "trimesh", SimpleNamespace(load=_load))
    truth = {
        "mass": {
            "volume_mm3": 100.0,
            "surface_area_mm2": 1000.0,
            "com_mm": [0.0, 0.0, 0.0],
        },
    }

    asyncio.run(diag.gate_and_save(adapter, part_no, truth))

    assert events == [
        "save_file",
        "export_views",
        "close",
        "open:TEST-replica.SLDPRT",
        "clear",
        "save_as:TEST-replica.stl",
        "close",
        "open:TEST.SLDPRT",
        "clear",
        "save_as:TEST-vendor.stl",
        "close",
        "load:TEST-replica.stl",
        "load:TEST-vendor.stl",
    ]
