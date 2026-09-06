"""Isolated recipe inputs and coherent copied-control orchestration contracts."""

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import draw_channel_lever as recipe
import probe_fresh_lever_column as control
from _buildgraph import module_deps_of


def test_production_defaults_and_dependency_closure_exclude_diagnostics():
    inputs = inspect.signature(recipe.build).parameters
    assert inputs["source"].default == recipe.SPEC.source
    assert inputs["outputs"].default is recipe.OUTPUTS
    assert inputs["layout"].default is recipe.repair_project_drawing_layout
    dependencies = module_deps_of(Path(recipe.__file__))
    assert all(not Path(path).name.startswith("probe_") for path in dependencies)
    assert (
        str(Path(recipe.__file__).with_name("_drawing_project_layout.py"))
        in dependencies
    )


@pytest.mark.asyncio
async def test_explicit_source_is_used_before_recipe_drives_native_application(
    tmp_path,
):
    missing = tmp_path / "unique-missing.SLDPRT"
    adapter = SimpleNamespace(open_model=AsyncMock())
    with pytest.raises(FileNotFoundError, match="unique-missing"):
        await recipe.build(adapter, source=missing)
    adapter.open_model.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "basic", "source_bytes", "wrong_output"])
async def test_fresh_baseline_uses_unique_outputs_and_preserves_source_witnesses(
    monkeypatch, tmp_path, change
):
    root = tmp_path / "cad"
    (root / "out/reports").mkdir(parents=True)
    source, original = tmp_path / "current.SLDPRT", tmp_path / "original.SLDDRW"
    source.write_bytes(b"current-native-part")
    original.write_bytes(b"unchanged-old-native-drawing")
    state = {"path": "", "basic_reads": 0}
    adapter = SimpleNamespace()

    async def open_model(path):
        state["path"] = path
        adapter.currentModel = SimpleNamespace(GetPathName=lambda: state["path"])
        return {"status": "success"}

    async def close_model(*, save):
        assert save is False
        adapter.currentModel = None
        return {"status": "success"}

    adapter.open_model, adapter.close_model = open_model, close_model
    calls = []

    async def build(actual_adapter, *, source, outputs, layout):
        assert actual_adapter is adapter
        assert layout is control.diagnostic_layout
        assert outputs is not recipe.OUTPUTS
        assert outputs.slddrw.parent.parent == root / "out/reports"
        assert outputs.slddrw != original
        outputs.slddrw.write_bytes(b"fresh-coherent-native-drawing")
        state["path"] = str(outputs.slddrw if change != "wrong_output" else original)
        calls.append(("build", source, outputs.slddrw))

    async def probe_column(actual_adapter, drawing, requested):
        assert actual_adapter is adapter and requested is None
        assert drawing == calls[0][2]
        calls.append(("column", drawing))
        if change == "source_bytes":
            source.write_bytes(b"unexpected-source-mutation")
        return {"report": "nested-native-witness.json"}

    def basic(*_):
        state["basic_reads"] += 1
        return {
            "dimension": {
                "type": 1,
                "value": 2 if change == "basic" and state["basic_reads"] == 2 else 1,
            }
        }

    monkeypatch.setattr(control, "CAD_ROOT", root)
    monkeypatch.setattr(control, "build_lever", build)
    monkeypatch.setattr(control, "probe_column", probe_column)
    monkeypatch.setattr(control, "source_basic", basic)
    monkeypatch.setattr(
        control, "drawing_dimensions", lambda *_: {"current_BASIC": "witnessed"}
    )
    monkeypatch.setattr(control, "check", lambda *_: None)
    if change != "none":
        pattern = {
            "basic": "source BASIC",
            "source_bytes": "source bytes",
            "wrong_output": "unique diagnostic",
        }[change]
        with pytest.raises(RuntimeError, match=pattern):
            await control.probe(adapter, source, original)
    if change == "none":
        result = await control.probe(adapter, source, original)
        assert Path(result["report"]).is_file()
        assert [row[0] for row in calls] == ["build", "column"]
        assert adapter.currentModel is None
    assert original.read_bytes() == b"unchanged-old-native-drawing"
