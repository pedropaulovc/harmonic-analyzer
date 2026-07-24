"""Offline contracts for comparison-gallery Blender discovery."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "comparisons" / "tools" / "render_offline.py"


def _load_render_offline():
    spec = importlib.util.spec_from_file_location("render_offline_tested", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_explicit_blender_accepts_any_existing_version(tmp_path: Path) -> None:
    renderer = _load_render_offline()
    executable = tmp_path / "Blender 4.5" / "blender.exe"
    executable.parent.mkdir()
    executable.touch()

    assert renderer.resolve_blender(str(executable)) == str(executable)


def test_windows_discovery_chooses_highest_available_version(monkeypatch) -> None:
    renderer = _load_render_offline()
    installs = [
        "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe",
        "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe",
    ]
    monkeypatch.delenv("HARMONIC_BLENDER", raising=False)
    monkeypatch.setattr(renderer.glob, "glob", lambda _pattern: installs)
    monkeypatch.setattr(renderer.shutil, "which", lambda _name: None)

    assert renderer.resolve_blender() == installs[1]


def test_path_fallback_accepts_unversioned_blender(monkeypatch) -> None:
    renderer = _load_render_offline()
    executable = "/opt/blender/blender"
    monkeypatch.delenv("HARMONIC_BLENDER", raising=False)
    monkeypatch.setattr(renderer.glob, "glob", lambda _pattern: [])
    monkeypatch.setattr(renderer.shutil, "which", lambda _name: executable)

    assert renderer.resolve_blender() == executable


def test_align_change_stales_the_pair(monkeypatch, tmp_path: Path) -> None:
    renderer = _load_render_offline()
    monkeypatch.setattr(renderer.composite, "COMP", tmp_path)
    pair = {
        "id": "pair",
        "camera": {"zoom": 1.0},
        "reference": {"path": "reference.png"},
        "align": {"scale": 1.0, "dx_px": 0, "dy_px": 0},
    }
    src = tmp_path / "model.SLDASM"
    src.touch()
    render = renderer.composite.pair_paths(pair["id"])["render"]
    render.parent.mkdir(parents=True)
    render.touch()
    paths = renderer.composite.pair_paths(pair["id"])
    paths["cad"].parent.mkdir(parents=True)
    paths["cad"].touch()
    paths["blend"].touch()
    sidecar = renderer._sidecar(pair["id"])
    sidecar.write_text(json.dumps({
        "camera": pair["camera"],
        "reference": pair["reference"],
        "align": {"scale": 1.13, "dx_px": 20, "dy_px": -247},
        "model_mtime": src.stat().st_mtime,
    }))

    assert renderer.composite.stale_stage(pair, src.stat().st_mtime) == "composite"
    assert renderer.is_stale(pair, src)

    meta = json.loads(sidecar.read_text())
    meta["align"] = pair["align"]
    sidecar.write_text(json.dumps(meta))

    assert renderer.composite.stale_stage(pair, src.stat().st_mtime) is None
    assert not renderer.is_stale(pair, src)


def test_stale_only_refreshes_align_without_launching_blender(
    monkeypatch, tmp_path: Path
) -> None:
    renderer = _load_render_offline()
    monkeypatch.setattr(renderer.composite, "COMP", tmp_path)
    pair = {
        "id": "pair",
        "model": "harmonic_analyzer",
        "camera": {"zoom": 1.0},
        "reference": {"path": "reference.png"},
        "align": {"scale": 1.0, "dx_px": 0, "dy_px": 0},
    }
    src = tmp_path / "model.SLDASM"
    src.touch()
    paths = renderer.composite.pair_paths(pair["id"])
    for name in ("render", "cad", "blend"):
        paths[name].parent.mkdir(parents=True, exist_ok=True)
        paths[name].touch()
    sidecar = renderer._sidecar(pair["id"])
    sidecar.write_text(json.dumps({
        "camera": pair["camera"],
        "reference": pair["reference"],
        "align": {"scale": 1.13, "dx_px": 20, "dy_px": -247},
        "model_mtime": src.stat().st_mtime,
    }))
    refreshed: list[set[str]] = []

    def fail_worker(*_args, **_kwargs):
        raise AssertionError("align-only refresh launched Blender")

    monkeypatch.setattr(renderer.sys, "argv", ["render_offline.py", "--stale-only"])
    monkeypatch.setattr(
        renderer.composite,
        "load_manifest",
        lambda *_args, **_kwargs: {"pairs": [pair]},
    )
    monkeypatch.setattr(renderer, "model_source", lambda _model: src)
    monkeypatch.setattr(
        renderer.composite,
        "regenerate",
        lambda only: refreshed.append(only),
    )
    monkeypatch.setattr(renderer, "_run_worker", fail_worker)

    assert renderer.main() == 0
    assert refreshed == [{pair["id"]}]
    assert json.loads(sidecar.read_text())["align"] == pair["align"]
