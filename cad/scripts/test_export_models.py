"""Offline regression tests for export staleness and render cleanup."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

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


def test_subassembly_fallback_does_not_require_a_scene(
    tmp_path: Path, monkeypatch,
) -> None:
    src = tmp_path / "sldasm" / "frame.SLDASM"
    stl = tmp_path / "stl"
    now = time.time()
    _write(src, now - 10)
    _write(stl / "frame.STL", now)
    monkeypatch.setattr(export_models, "OUT_STL", stl)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed(
        "frame", src, {}, require_scene=False,
    )


def test_release_inventory_reuses_build_owned_pngs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(export_models, "OUT_STEP", tmp_path / "step-cache")
    monkeypatch.setattr(export_models, "OUT_STL", tmp_path / "stl-cache")
    monkeypatch.setattr(export_models, "OUT_PNG", tmp_path / "build-renders")

    files = export_models._release_inventory(
        ["sample_part"], ["sample_assembly"],
        {
            "generated-spring": [("Default", "generated-spring")],
            "sample-part": [("C1", "sample-part--c1")],
        },
    )

    assert files == {
        "png/sample-assembly/sample-assembly_isometric.png": (
            tmp_path / "build-renders/sample-assembly/sample-assembly_isometric.png"
        ),
        "png/sample-part/sample-part_isometric.png": (
            tmp_path / "build-renders/sample-part/sample-part_isometric.png"
        ),
        "step/sample-part.STEP": tmp_path / "step-cache/sample-part.STEP",
        "stl/sample-assembly.STL": tmp_path / "stl-cache/sample-assembly.STL",
        "stl/generated-spring.STL": tmp_path / "stl-cache/generated-spring.STL",
        "stl/sample-part--c1.STL": tmp_path / "stl-cache/sample-part--c1.STL",
        "stl/sample-part.STL": tmp_path / "stl-cache/sample-part.STL",
    }


def test_scene_inventory_keeps_generated_default_meshes(tmp_path: Path) -> None:
    scene = tmp_path / "scene.json"
    scene.write_text(
        '{"unit":"mm","components":['
        '{"part":"generated-spring","cfg":"Default","mesh":"generated-spring"},'
        '{"part":"gear","cfg":"T12","mesh":"gear--t12"}'
        ']}',
        encoding="utf-8",
    )

    assert export_models.scene_part_meshes(scene) == {
        "gear": [("T12", "gear--t12")],
        "generated-spring": [("Default", "generated-spring")],
    }
    assert export_models.scene_config_meshes(scene) == {
        "gear": [("T12", "gear--t12")],
    }


def test_invalid_scene_is_not_fresh(tmp_path: Path) -> None:
    scene = tmp_path / "scene.json"
    scene.write_text('{"unit":"mm","components":[', encoding="utf-8")

    assert not export_models.scene_is_valid(scene)


def test_scene_with_retired_component_source_requires_owner_rescan(
    tmp_path: Path, monkeypatch,
) -> None:
    scene = tmp_path / "scene.json"
    native = tmp_path / "sldprt"
    _write(native / "current-part.SLDPRT", time.time())
    scene.write_text(
        '{"unit":"mm","components":['
        '{"part":"current-part","cfg":"Default","mesh":"current-part"},'
        '{"part":"retired-part","cfg":"Default","mesh":"retired-part"}'
        ']}',
        encoding="utf-8",
    )
    monkeypatch.setattr(export_models, "OUT_SLDPRT", native)

    assert export_models.scene_is_valid(scene)
    assert not export_models.scene_sources_exist(scene)


def test_certified_output_hash_detects_same_length_corruption(tmp_path: Path) -> None:
    output = tmp_path / "sample.STL"
    output.write_bytes(b"good")
    certified = {
        output.resolve(): {
            "bytes": output.stat().st_size,
            "sha256": export_models._file_sha256(output),
        },
    }

    assert not export_models._certified_output_changed(output, certified)
    output.write_bytes(b"evil")
    assert export_models._certified_output_changed(output, certified)


def test_certified_output_hash_is_memoized_per_export(
    tmp_path: Path, monkeypatch,
) -> None:
    output = tmp_path / "sample.STL"
    output.write_bytes(b"neutral")
    expected = export_models._file_sha256(output)
    calls = 0
    original = export_models._file_sha256

    def _counted(path: Path) -> str:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(export_models, "_file_sha256", _counted)
    certified = {
        output.resolve(): {"bytes": output.stat().st_size, "sha256": expected},
    }
    cache: dict[Path, bool] = {}

    assert not export_models._certified_output_changed(output, certified, cache)
    assert not export_models._certified_output_changed(output, certified, cache)
    assert calls == 1


def test_zero_byte_neutral_outputs_are_stale(tmp_path: Path, monkeypatch) -> None:
    stl = tmp_path / "stl"
    step = tmp_path / "step"
    native = tmp_path / "sldprt"
    for path in (stl / "sample.STL", step / "sample.STEP"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    _write(native / "sample.SLDPRT", time.time())
    monkeypatch.setattr(export_models, "OUT_STL", stl)
    monkeypatch.setattr(export_models, "OUT_STEP", step)
    monkeypatch.setattr(export_models, "OUT_SLDPRT", native)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: "recipe-v1")

    assert export_models.part_stl_stale(
        "sample", "sample", {"sample": (1, 1, 1)}, {"sample": "recipe-v1"},
    )
    assert export_models.manifest_part_stale(
        "sample", {"sample": (1, 1, 1)}, {"sample": "recipe-v1"},
    )


def test_neutral_save_is_silent_and_suppresses_stl_info(tmp_path: Path) -> None:
    calls: list[tuple[str, int, int]] = []

    class _Doc:
        def SaveAs3(self, path: str, version: int, options: int) -> int:
            calls.append((path, version, options))
            Path(path).write_bytes(b"neutral")
            return 1

    output = tmp_path / "sample.STL"
    assert export_models._save_as(_Doc(), output) == 1
    assert calls == [(str(output), 0, 1 | 8)]
    assert export_models.TOGGLES[export_models.TOGGLE_STL_SHOW_INFO] is False


def test_saved_active_and_configuration_exports_share_one_part_open(
    tmp_path: Path, monkeypatch,
) -> None:
    sldprt = tmp_path / "sldprt"
    sldasm = tmp_path / "sldasm"
    stl = tmp_path / "stl"
    step = tmp_path / "step"
    boxes = tmp_path / "boxes"
    png = tmp_path / "png"
    for path in (sldprt / "sample-part.SLDPRT",
                 sldasm / "harmonic-analyzer.SLDASM",
                 stl / "sample-part.STL",
                 stl / "harmonic-analyzer.STL"):
        _write(path, time.time())
    boxes.mkdir(parents=True)
    _write(png / "harmonic-analyzer/harmonic-analyzer_isometric.png", time.time())
    (boxes / "harmonic-analyzer.json").write_text(
        '{"unit":"mm","components":[{"part":"sample-part",'
        '"cfg":"C1","mesh":"sample-part--c1"}]}',
        encoding="utf-8",
    )

    class _Config:
        Name = "T24"

    class _ConfigManager:
        ActiveConfiguration = _Config()

    class _Doc:
        ConfigurationManager = _ConfigManager()

        def ShowConfiguration2(self, cfg: str) -> bool:
            self.ConfigurationManager.ActiveConfiguration.Name = cfg
            return True

        def ForceRebuild3(self, _top_only: bool) -> bool:
            return True

        def EditRebuild3(self) -> bool:
            return True

        def GetConfigurationNames(self) -> list[str]:
            return ["T24", "C1"]

        def SaveAs3(self, path: str, _version: int, _options: int) -> int:
            Path(path).write_bytes(self.ConfigurationManager.ActiveConfiguration.Name.encode())
            return 1

    class _Sw:
        def CloseAllDocuments(self, _include_unsaved: bool) -> None:
            return None

    class _Adapter:
        swApp = _Sw()
        currentModel = _Doc()
        opened: list[str] = []

        async def open_model(self, path: str):
            self.opened.append(Path(path).name)
            self.currentModel = _Doc()
            return SimpleNamespace(is_success=True, data=None)

        def _attempt(self, call, default=None):
            try:
                return call()
            except Exception:
                return default

    adapter = _Adapter()
    monkeypatch.setattr(export_models, "OUT_SLDPRT", sldprt)
    monkeypatch.setattr(export_models, "OUT_SLDASM", sldasm)
    monkeypatch.setattr(export_models, "OUT_STL", stl)
    monkeypatch.setattr(export_models, "OUT_STEP", step)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_PNG", png)
    monkeypatch.setattr(export_models, "COLORS", stl / "colors.json")
    monkeypatch.setattr(export_models, "SRC_DIGESTS", stl / "export-src.json")
    monkeypatch.setattr(export_models, "part_stems", lambda: ["sample_part"])
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ("harmonic_analyzer",))
    monkeypatch.setattr(export_models, "manifest_models", lambda: ["harmonic_analyzer"])
    monkeypatch.setattr(export_models, "exporter_untrusted", lambda: False)
    monkeypatch.setattr(export_models, "_certified_outputs", lambda: {})
    monkeypatch.setattr(export_models, "load_colors", lambda: {"sample-part": (1, 1, 1)})
    monkeypatch.setattr(
        export_models, "load_src_digests",
        lambda: {"sample-part": "part-v1", "harmonic-analyzer": "asm-v1"},
    )
    monkeypatch.setattr(
        export_models, "src_digest",
        lambda path: "asm-v1" if path.suffix == ".SLDASM" else "part-v1",
    )
    monkeypatch.setattr(export_models, "set_export_prefs", lambda _adapter: {})
    monkeypatch.setattr(export_models, "restore_export_prefs", lambda *_args: None)
    monkeypatch.setattr(export_models, "doc_rgb", lambda _doc: (1, 1, 1))
    monkeypatch.setattr(export_models, "stamp_render_cache_current", lambda _paths: None)
    monkeypatch.setattr(export_models, "refresh_comparison_gallery", lambda: True)
    repaired_pngs: list[str] = []

    async def _repair_png(_adapter, stem: str) -> None:
        repaired_pngs.append(stem)

    monkeypatch.setattr(export_models, "export_build_png", _repair_png)
    monkeypatch.setattr(
        export_models, "run_build",
        lambda build: (asyncio.run(build(adapter)), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py"])

    assert export_models.main() == 0
    assert adapter.opened == ["sample-part.SLDPRT"]
    assert repaired_pngs == ["sample-part"]
    assert (step / "sample-part.STEP").read_bytes() == b"T24"
    assert (stl / "sample-part.STL").read_bytes() == b"T24"
    assert (stl / "sample-part--c1.STL").exists()


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
