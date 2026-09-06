"""Exact native save call-shape tests; positive persistence remains live-only."""

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import probe_drawing_template_save as probe


def test_control_keeps_exact_production_and_failed_candidate_argument_shapes(
    monkeypatch, tmp_path
):
    calls, options = [], object()
    extension = SimpleNamespace(
        GetAdvancedSaveAsOptions=lambda flag: (
            calls.append(("options", flag)) or options
        ),
        SaveAs3=lambda *args: calls.append(("extension", args)) or (True, 0, 0),
    )
    model = SimpleNamespace(
        Extension=extension, SaveAs3=lambda *args: calls.append(("model", args)) or 0
    )
    monkeypatch.setattr(probe, "_early_bound", lambda raw, kind: raw)
    target = tmp_path / "owned.DRWDOT"
    first, second = {}, {}
    probe.invoke_save(model, target, "model_save_as3", first)
    probe.invoke_save(model, target, "extension_save_as3", second)
    assert calls == [
        ("model", (str(target), 0, 0)),
        ("options", 0),
        ("extension", (str(target), 0, 1, None, options, 0, 0)),
    ]
    assert first["returned"] == 0  # Raw legacy integer is not interpreted.
    assert second["returned"] == (True, 0, 0)


def test_file_witness_does_not_turn_success_tuple_into_a_file(tmp_path):
    assert probe.file_witness(tmp_path / "absent.DRWDOT") == {"status": "absent"}
    target = tmp_path / "partial.DRWDOT"
    target.write_bytes(b"")
    assert probe.file_witness(target)["bytes"] == 0


def test_unknown_save_shape_does_not_call_native_api(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        probe.invoke_save(object(), tmp_path / "owned.DRWDOT", "unknown", {})


def test_production_positive_format_precedes_all_other_cells():
    assert probe.CELLS == (
        ("model_save_as3", ".SLDDRW"),
        ("model_save_as3", ".DRWDOT"),
        ("extension_save_as3", ".SLDDRW"),
        ("extension_save_as3", ".DRWDOT"),
    )


@pytest.mark.parametrize("production", ["persists", "no_output"])
def test_capture_keeps_failed_cells_and_requires_the_first_positive(
    monkeypatch, tmp_path, production
):
    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"fixture template")
    adapter = SimpleNamespace(currentModel=None)
    directories, closes = [], []

    class Model:
        path = ""
        Extension = SimpleNamespace(
            GetAdvancedSaveAsOptions=lambda flag: object(),
            SaveAs3=lambda *args: (True, 0, 0),
        )

        def GetPathName(self):
            return self.path

        def GetTitle(self):
            return Path(self.path).name if self.path else "owned blank"

        def GetType(self):
            return 3

        def GetSaveFlag(self):
            return False

        def ClearSelection2(self, ignored):
            pass

        def SaveAs3(self, path, version, options):
            if production == "persists":
                Path(path).write_bytes(b"owned native fixture")
                self.path = path
            return 0

    @contextmanager
    def creating(kind, output):
        yield

    @contextmanager
    def saving(output):
        yield
        if adapter.currentModel.GetPathName() != str(output):
            raise RuntimeError("native SaveAs did not reach the requested output path")

    def new_drawing(current, **kwargs):
        adapter.currentModel = Model()
        return adapter.currentModel

    async def close_model(*, save):
        assert save is False
        closes.append(adapter.currentModel)
        adapter.currentModel = None
        return object()

    async def close_owned():
        closes.append(adapter.currentModel)
        adapter.currentModel = None

    async def open_model(path):
        adapter.currentModel = Model()
        adapter.currentModel.path = path
        return object()

    adapter.close_model, adapter.close_owned_documents = close_model, close_owned
    adapter.open_model = open_model
    adapter.ownership = SimpleNamespace(
        register_directory=directories.append,
        register_source=lambda path: None,
        creating_document=creating,
        saving_as=saving,
    )
    monkeypatch.setattr(probe.common, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe, "revision", lambda revision: "frozen")
    monkeypatch.setattr(probe, "_early_bound", lambda raw, kind: raw)
    monkeypatch.setattr(probe, "sheet_witness", lambda model: {"sheet": "unchanged"})
    monkeypatch.setattr(probe, "check", lambda *args: None)
    monkeypatch.setattr(probe.drawing, "new_drawing", new_drawing)
    if production == "no_output":
        with pytest.raises(RuntimeError, match="positive control failed"):
            asyncio.run(probe.capture(adapter, tmp_path / "reports"))
    else:
        asyncio.run(probe.capture(adapter, tmp_path / "reports"))
    report = json.loads((directories[0] / "save.json").read_text())
    assert adapter.currentModel is None
    assert original.read_bytes() == b"fixture template"
    if production == "no_output":
        assert len(report["cells"]) == 1
        assert report["status"] == "failed"
        return
    assert report["status"] == "captured"
    assert [row["status"] for row in report["cells"]] == [
        "persisted",
        "persisted",
        "rejected",
        "rejected",
    ]
    for row in report["cells"][2:]:
        assert row["returned"] == [True, 0, 0]
        assert row["after"]["path"] == ""
        assert row["file"] == {"status": "absent"}
        assert "requested output path" in row["error"]
