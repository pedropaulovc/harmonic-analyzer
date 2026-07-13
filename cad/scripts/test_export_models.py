"""Offline regression tests for export staleness and render cleanup."""

from __future__ import annotations

import os
import time
from pathlib import Path

import _common
import export_models


def _write(path: Path, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))


def test_assembly_fallback_does_not_require_retired_step(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "sldasm" / "frame.SLDASM"
    boxes = tmp_path / "boxes"
    stl = tmp_path / "stl"
    step = tmp_path / "step"
    now = time.time()
    _write(src, now - 10)
    _write(boxes / "frame.json", now)
    _write(stl / "frame.STL", now)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_STL", stl)
    monkeypatch.setattr(export_models, "OUT_STEP", step)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed("frame", src, {})


def test_assembly_fallback_still_requires_current_scene_and_stl(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "sldasm" / "frame.SLDASM"
    boxes = tmp_path / "boxes"
    stl = tmp_path / "stl"
    now = time.time()
    _write(src, now)
    _write(boxes / "frame.json", now - 10)
    _write(stl / "frame.STL", now + 10)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_STL", stl)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert export_models.asm_source_changed("frame", src, {})


def test_routine_view_cleanup_preserves_configuration_renders(tmp_path: Path) -> None:
    part = "cone-gear"
    generic_iso = tmp_path / f"{part}_isometric.png"
    stale_front = tmp_path / f"{part}_front.png"
    stale_top = tmp_path / f"{part}_top.png"
    configured = tmp_path / f"{part}_T006_isometric.png"
    for path in (generic_iso, stale_front, stale_top, configured):
        path.write_bytes(b"png")

    _common._prune_stale_part_views(tmp_path, part, ["isometric"])

    assert generic_iso.exists()
    assert configured.exists()
    assert not stale_front.exists()
    assert not stale_top.exists()
