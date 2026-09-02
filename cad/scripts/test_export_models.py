"""Offline regression tests for export staleness and render cleanup."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import struct
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    gltf = tmp_path / "gltf"
    step = tmp_path / "step"
    now = time.time()
    _write(src, now - 10)
    _write(boxes / "frame.json", now)
    _write(gltf / "frame.glb", now)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
    monkeypatch.setattr(export_models, "OUT_STEP", step)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed("frame", src, {})


def test_assembly_fallback_still_requires_current_scene_and_glb(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "sldasm" / "frame.SLDASM"
    boxes = tmp_path / "boxes"
    gltf = tmp_path / "gltf"
    now = time.time()
    _write(src, now)
    _write(boxes / "frame.json", now - 10)
    _write(gltf / "frame.glb", now + 10)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert export_models.asm_source_changed("frame", src, {})


def test_subassembly_fallback_does_not_require_a_scene(
    tmp_path: Path, monkeypatch,
) -> None:
    src = tmp_path / "sldasm" / "frame.SLDASM"
    gltf = tmp_path / "gltf"
    now = time.time()
    _write(src, now - 10)
    _write(gltf / "frame.glb", now)
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed(
        "frame", src, {}, require_scene=False,
    )


def test_release_inventory_reuses_build_owned_pngs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(export_models, "OUT_STEP", tmp_path / "step-cache")
    monkeypatch.setattr(export_models, "OUT_STL", tmp_path / "stl-cache")
    monkeypatch.setattr(export_models, "OUT_GLTF", tmp_path / "gltf-cache")
    monkeypatch.setattr(export_models, "OUT_PNG", tmp_path / "build-renders")
    monkeypatch.setattr(export_models, "OUT_BOXES", tmp_path / "scene-cache")

    files = export_models._release_inventory(
        ["sample_part"], ["sample_assembly"],
        {
            "generated-spring": [("Default", "generated-spring")],
            "sample-part": [("C1", "sample-part--c1")],
        },
        {"sample_assembly"},
    )

    assert files == {
        "boxes/sample-assembly.json": tmp_path / "scene-cache/sample-assembly.json",
        "png/sample-assembly/sample-assembly_isometric.png": (
            tmp_path / "build-renders/sample-assembly/sample-assembly_isometric.png"
        ),
        "png/sample-part/sample-part_isometric.png": (
            tmp_path / "build-renders/sample-part/sample-part_isometric.png"
        ),
        "gltf/sample-assembly.glb": tmp_path / "gltf-cache/sample-assembly.glb",
        "step/sample-part.STEP": tmp_path / "step-cache/sample-part.STEP",
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


def test_all_scene_inventory_unions_every_release_scene(
    tmp_path: Path, monkeypatch,
) -> None:
    boxes = tmp_path / "boxes"
    boxes.mkdir()
    (boxes / "assembly-a.json").write_text(
        '{"unit":"mm","components":['
        '{"part":"shared","cfg":"Default","mesh":"shared"},'
        '{"part":"gear","cfg":"T12","mesh":"gear--t12"}]}' ,
        encoding="utf-8",
    )
    (boxes / "assembly-b.json").write_text(
        '{"unit":"mm","components":['
        '{"part":"shared","cfg":"Default","mesh":"shared"},'
        '{"part":"spring","cfg":"C1","mesh":"spring--c1"}]}' ,
        encoding="utf-8",
    )
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)

    assert export_models.all_scene_part_meshes({"assembly_a", "assembly_b"}) == {
        "gear": [("T12", "gear--t12")],
        "shared": [("Default", "shared")],
        "spring": [("C1", "spring--c1")],
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


def test_uncertified_output_is_untrusted(tmp_path: Path) -> None:
    output = tmp_path / "sample.STL"
    output.write_bytes(b"neutral")

    assert export_models._certified_output_changed(output, {})


def test_missing_native_has_no_source_fingerprint(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "missing.SLDPRT"
    monkeypatch.setattr(export_models, "src_digest", lambda _source: "recipe-v1")

    assert export_models._source_fingerprint(source) is None


def test_forced_export_regenerates_existing_certified_png(tmp_path: Path) -> None:
    output = tmp_path / "sample_isometric.png"
    output.write_bytes(b"current")

    assert export_models._png_needs_export(output, True, lambda _path: False)


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
    gltf = tmp_path / "gltf"
    step = tmp_path / "step"
    boxes = tmp_path / "boxes"
    png = tmp_path / "png"
    for path in (sldprt / "sample-part.SLDPRT",
                 sldasm / "harmonic-analyzer.SLDASM",
                 stl / "sample-part.STL",
                 gltf / "harmonic-analyzer.glb"):
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
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
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
    monkeypatch.setattr(
        export_models, "_certified_output_changed", lambda *_args: False,
    )
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


def test_current_gallery_skips_redundant_composite_and_index(
    tmp_path: Path, monkeypatch,
) -> None:
    comparisons = tmp_path / "comparisons"
    tools = comparisons / "tools"
    tools.mkdir(parents=True)
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"reference")
    manifest = {
        "pairs": [{
            "id": "sample",
            "reference": {"path": "reference.png"},
        }],
    }
    (comparisons / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    render_tool = tools / "render_offline.py"
    worker_tool = tools / "blender_worker.py"
    composite_tool = tools / "composite.py"
    gallery_tool = tools / "gallery.py"
    for tool in (render_tool, worker_tool, composite_tool, gallery_tool):
        tool.write_text(tool.name, encoding="utf-8")
    (comparisons / "scores.json").write_text(
        json.dumps({"sample": {"score": 1.0}}), encoding="utf-8",
    )
    for path in (
        comparisons / "index.html",
        comparisons / "ref/sample.jpg",
        comparisons / "render/sample.jpg",
        comparisons / "render/sample.meta.json",
        comparisons / "composite/sample_cad.jpg",
        comparisons / "composite/sample_blend.jpg",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"current")

    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "COMPARISONS_DIR", comparisons)
    monkeypatch.setattr(export_models, "RENDER_OFFLINE", render_tool)
    monkeypatch.setattr(export_models, "BLENDER_WORKER", worker_tool)
    monkeypatch.setattr(export_models, "COMPOSITE_PY", composite_tool)
    monkeypatch.setattr(export_models, "GALLERY_PY", gallery_tool)
    monkeypatch.setattr(export_models, "GALLERY_STAMP", tmp_path / "gallery.json")
    monkeypatch.setattr(export_models, "_prune_stale_gallery", lambda: None)
    messages: list[str] = []
    monkeypatch.setattr(export_models._telemetry, "info", messages.append)
    export_models._write_gallery_stamp(export_models._gallery_input_digest(manifest))
    calls: list[list[str]] = []

    def _run(cmd: list[str], _tag: str) -> list[str]:
        calls.append(cmd)
        return ["nothing to render"]

    monkeypatch.setattr(export_models, "_run_tool", _run)

    old_mtime = time.time() - 100
    os.utime(comparisons / "scores.json", (old_mtime, old_mtime))
    os.utime(comparisons / "index.html", (old_mtime, old_mtime))
    assert export_models.refresh_comparison_gallery()
    assert [Path(cmd[2]).name for cmd in calls] == ["render_offline.py"]
    assert calls[0][-1] == "--stale-only"
    assert messages == ["comparison gallery already current"]
    assert (comparisons / "scores.json").stat().st_mtime > old_mtime
    assert (comparisons / "index.html").stat().st_mtime > old_mtime

    calls.clear()

    def _run_composite_refresh(cmd: list[str], _tag: str) -> list[str]:
        calls.append(cmd)
        if Path(cmd[2]).name == "render_offline.py":
            return ["  REFRESHED  sample"]
        return []

    monkeypatch.setattr(export_models, "_run_tool", _run_composite_refresh)
    assert export_models.refresh_comparison_gallery()
    assert [Path(cmd[2]).name for cmd in calls] == [
        "render_offline.py", "gallery.py",
    ]

    export_models.GALLERY_STAMP.unlink()
    calls.clear()
    monkeypatch.setattr(export_models, "_run_tool", _run)
    assert export_models.refresh_comparison_gallery()
    assert [Path(cmd[2]).name for cmd in calls] == [
        "render_offline.py", "composite.py", "gallery.py",
    ]
    assert calls[0] == ["uv", "run", str(render_tool)]


def test_gallery_missing_blender_fails_export_loudly(tmp_path: Path, monkeypatch) -> None:
    comparisons = tmp_path / "comparisons"
    tools = comparisons / "tools"
    tools.mkdir(parents=True)
    manifest = {"pairs": []}
    (comparisons / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name in ("render_offline.py", "blender_worker.py", "composite.py", "gallery.py"):
        (tools / name).write_text(name, encoding="utf-8")

    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "COMPARISONS_DIR", comparisons)
    monkeypatch.setattr(export_models, "RENDER_OFFLINE", tools / "render_offline.py")
    monkeypatch.setattr(export_models, "BLENDER_WORKER", tools / "blender_worker.py")
    monkeypatch.setattr(export_models, "COMPOSITE_PY", tools / "composite.py")
    monkeypatch.setattr(export_models, "GALLERY_PY", tools / "gallery.py")
    monkeypatch.setattr(export_models, "GALLERY_STAMP", tmp_path / "gallery.json")
    monkeypatch.setattr(export_models, "_prune_stale_gallery", lambda: None)

    def _missing_blender(_cmd: list[str], _tag: str) -> list[str]:
        raise RuntimeError("cmp exited non-zero: BLENDER_UNAVAILABLE: no Blender found")

    monkeypatch.setattr(export_models, "_run_tool", _missing_blender)

    with pytest.raises(RuntimeError, match="comparison gallery requires Blender"):
        export_models.refresh_comparison_gallery()


def test_gallery_digest_includes_blender_worker(tmp_path: Path, monkeypatch) -> None:
    comparisons = tmp_path / "comparisons"
    tools = comparisons / "tools"
    tools.mkdir(parents=True)
    manifest = {"pairs": []}
    inputs = {
        "manifest.json": json.dumps(manifest),
        "tools/render_offline.py": "render",
        "tools/blender_worker.py": "worker-v1",
        "tools/composite.py": "composite",
        "tools/gallery.py": "gallery",
    }
    for relative, content in inputs.items():
        path = comparisons / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "COMPARISONS_DIR", comparisons)
    monkeypatch.setattr(export_models, "RENDER_OFFLINE", tools / "render_offline.py")
    monkeypatch.setattr(export_models, "BLENDER_WORKER", tools / "blender_worker.py")
    monkeypatch.setattr(export_models, "COMPOSITE_PY", tools / "composite.py")
    monkeypatch.setattr(export_models, "GALLERY_PY", tools / "gallery.py")

    before = export_models._gallery_input_digest(manifest)
    (tools / "blender_worker.py").write_text("worker-v2", encoding="utf-8")

    assert export_models._gallery_input_digest(manifest) != before


def test_render_diff_local_source_uses_top_scene(tmp_path: Path) -> None:
    module_path = Path(__file__).parents[1] / "comparisons" / "tools" / "render_diff.py"
    spec = importlib.util.spec_from_file_location("render_diff_under_test", module_path)
    assert spec is not None and spec.loader is not None
    render_diff = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render_diff)
    boxes = tmp_path / "boxes"
    boxes.mkdir()
    (boxes / "channel.json").write_text('{"scene": "channel"}', encoding="utf-8")
    (boxes / "harmonic-analyzer.json").write_text(
        '{"scene": "top"}', encoding="utf-8",
    )

    assert render_diff.LocalSource(tmp_path).scene() == {"scene": "top"}


def test_gallery_with_missing_score_is_incomplete(tmp_path: Path, monkeypatch) -> None:
    comparisons = tmp_path / "comparisons"
    comparisons.mkdir()
    (comparisons / "scores.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(export_models, "COMPARISONS_DIR", comparisons)

    assert not export_models._gallery_outputs_complete({"pairs": [{"id": "sample"}]})


def test_rendered_pair_parser_ignores_composite_progress() -> None:
    assert export_models._rendered_pair_ids([
        "  OK  pair-a",
        "  OK  [1/2] pair-a: score 88.2 (1s)",
        "  REFRESHED  pair-c",
        "  OK  pair-b",
        "composites done",
    ]) == {"pair-a", "pair-b", "pair-c"}


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


def _glb_bytes(gltf: dict) -> bytes:
    payload = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    body = b"\0" * 64
    return (
        struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(payload) + 8 + len(body))
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
        + struct.pack("<II", len(body), 0x004E4942)
        + body
    )


def _read_glb_json(path: Path) -> dict:
    raw = path.read_bytes()
    json_len = struct.unpack("<I", raw[12:16])[0]
    return json.loads(raw[20 : 20 + json_len])


def test_sanitize_glb_drops_mismatched_texcoord_and_untextures_the_material(
    tmp_path: Path,
) -> None:
    gltf = {
        "asset": {"version": "2.0", "generator": "SOLIDWORKSGLTF"},
        "accessors": [
            {"count": 580, "type": "VEC3", "componentType": 5126},  # POSITION
            {"count": 576, "type": "VEC2", "componentType": 5126},  # TEXCOORD_0 (short)
            {"count": 580, "type": "VEC3", "componentType": 5126},  # NORMAL
            {"count": 450, "type": "VEC3", "componentType": 5126},  # clean POSITION
            {"count": 450, "type": "VEC2", "componentType": 5126},  # clean TEXCOORD_0
        ],
        "materials": [
            {
                "name": "cast-iron",
                "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}},
            }
        ],
        "meshes": [
            {
                "primitives": [
                    {"attributes": {"POSITION": 0, "TEXCOORD_0": 1, "NORMAL": 2}, "material": 0},
                    {"attributes": {"POSITION": 3, "TEXCOORD_0": 4}, "material": 0},
                ]
            }
        ],
    }
    glb = tmp_path / "top-frame.glb"
    glb.write_bytes(_glb_bytes(gltf))
    dropped = export_models.sanitize_glb(glb)
    assert dropped == [
        {"mesh": 0, "primitive": 0, "attribute": "TEXCOORD_0", "count": 576, "positions": 580}
    ]
    fixed = _read_glb_json(glb)
    prims = fixed["meshes"][0]["primitives"]
    assert prims[0]["attributes"] == {"POSITION": 0, "NORMAL": 2}
    assert prims[0]["material"] == 1
    assert "baseColorTexture" not in fixed["materials"][1]["pbrMetallicRoughness"]
    assert fixed["materials"][1]["name"] == "cast-iron-untextured"
    # the clean primitive keeps its UVs and its textured material
    assert prims[1]["attributes"] == {"POSITION": 3, "TEXCOORD_0": 4}
    assert prims[1]["material"] == 0
    # binary chunk untouched
    assert glb.read_bytes().endswith(b"\0" * 64)
    # idempotent: a clean file is left alone
    before = glb.read_bytes()
    assert export_models.sanitize_glb(glb) == []
    assert glb.read_bytes() == before


def test_save_as_sanitizes_glb_outputs(tmp_path: Path) -> None:
    gltf = {
        "asset": {"version": "2.0"},
        "accessors": [
            {"count": 10, "type": "VEC3", "componentType": 5126},
            {"count": 12, "type": "VEC2", "componentType": 5126},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}}]}],
    }

    class _Doc:
        def SaveAs3(self, path: str, version: int, options: int) -> int:
            Path(path).write_bytes(_glb_bytes(gltf))
            return 1

    output = tmp_path / "machine.glb"
    assert export_models._save_as(_Doc(), output) == 1
    fixed = _read_glb_json(output)
    assert fixed["meshes"][0]["primitives"][0]["attributes"] == {"POSITION": 0}


def test_sanitize_glb_keeps_textures_on_surviving_uv_sets(tmp_path: Path) -> None:
    gltf = {
        "asset": {"version": "2.0"},
        "accessors": [
            {"count": 100, "type": "VEC3", "componentType": 5126},  # POSITION
            {"count": 96, "type": "VEC2", "componentType": 5126},  # TEXCOORD_0 (bad)
            {"count": 100, "type": "VEC2", "componentType": 5126},  # TEXCOORD_1 (good)
        ],
        "materials": [
            {
                "name": "decal",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0, "texCoord": 1},
                    "metallicRoughnessTexture": {"index": 1},  # texCoord 0 (default)
                },
                "normalTexture": {"index": 2, "texCoord": 1},
            }
        ],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "TEXCOORD_0": 1, "TEXCOORD_1": 2},
                        "material": 0,
                    }
                ]
            }
        ],
    }
    glb = tmp_path / "decal.glb"
    glb.write_bytes(_glb_bytes(gltf))
    dropped = export_models.sanitize_glb(glb)
    assert [d["attribute"] for d in dropped] == ["TEXCOORD_0"]
    fixed = _read_glb_json(glb)
    prim = fixed["meshes"][0]["primitives"][0]
    assert prim["attributes"] == {"POSITION": 0, "TEXCOORD_1": 2}
    clone = fixed["materials"][prim["material"]]
    assert clone["name"] == "decal-untextured"
    # the slot on the dropped set is gone; the slots on TEXCOORD_1 survive
    assert "metallicRoughnessTexture" not in clone["pbrMetallicRoughness"]
    assert clone["pbrMetallicRoughness"]["baseColorTexture"] == {"index": 0, "texCoord": 1}
    assert clone["normalTexture"] == {"index": 2, "texCoord": 1}
    # the source material is untouched
    assert "metallicRoughnessTexture" in fixed["materials"][0]["pbrMetallicRoughness"]
