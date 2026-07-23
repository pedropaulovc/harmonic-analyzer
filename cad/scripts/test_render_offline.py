"""Offline contracts for comparison-gallery Blender discovery."""

from __future__ import annotations

import importlib.util
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
