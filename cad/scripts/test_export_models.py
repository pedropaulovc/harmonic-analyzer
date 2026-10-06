"""Offline regression tests for export staleness and render cleanup."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
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
    src = tmp_path / "sldasm" / "fr-frame.SLDASM"
    boxes = tmp_path / "boxes"
    gltf = tmp_path / "gltf"
    step = tmp_path / "step"
    now = time.time()
    _write(src, now - 10)
    _write(boxes / "fr-frame.json", now)
    _write(gltf / "fr-frame.glb", now)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
    monkeypatch.setattr(export_models, "OUT_STEP", step)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed("fr-frame", src, {})


@pytest.mark.parametrize("output", ["scene", "glb"])
@pytest.mark.parametrize("fault", ["missing", "empty", "older"])
def test_assembly_fallback_still_requires_current_scene_and_glb(
    tmp_path: Path, monkeypatch, output: str, fault: str,
) -> None:
    src = tmp_path / "sldasm" / "fr-frame.SLDASM"
    boxes = tmp_path / "boxes"
    gltf = tmp_path / "gltf"
    now = time.time()
    _write(src, now)
    outputs = {
        "scene": boxes / "fr-frame.json",
        "glb": gltf / "fr-frame.glb",
    }
    for path in outputs.values():
        _write(path, now + 10)
    monkeypatch.setattr(export_models, "OUT_BOXES", boxes)
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed("fr-frame", src, {})
    if fault == "missing":
        outputs[output].unlink()
    elif fault == "empty":
        outputs[output].write_bytes(b"")
    else:
        _write(outputs[output], now - 10)
    # A fresh retired basename must never stand in for the canonical scene.
    _write(boxes / "frame.json", now + 10)

    assert export_models.asm_source_changed("fr-frame", src, {})


def test_subassembly_fallback_does_not_require_a_scene(
    tmp_path: Path, monkeypatch,
) -> None:
    src = tmp_path / "sldasm" / "fr-frame.SLDASM"
    gltf = tmp_path / "gltf"
    now = time.time()
    _write(src, now - 10)
    _write(gltf / "fr-frame.glb", now)
    monkeypatch.setattr(export_models, "OUT_GLTF", gltf)
    monkeypatch.setattr(export_models, "src_digest", lambda _src: None)

    assert not export_models.asm_source_changed(
        "fr-frame", src, {}, require_scene=False,
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


def test_saved_active_and_configuration_exports_preserve_geometry_and_native_state(
    tmp_path: Path, monkeypatch,
) -> None:
    sldprt = tmp_path / "sldprt"
    sldasm = tmp_path / "sldasm"
    stl = tmp_path / "stl"
    gltf = tmp_path / "gltf"
    step = tmp_path / "step"
    boxes = tmp_path / "boxes"
    png = tmp_path / "png"
    native = sldprt / "sample-part.SLDPRT"
    for path in (native, sldasm / "ha-harmonic-analyzer.SLDASM",
                 stl / "sample-part.STL",
                 gltf / "ha-harmonic-analyzer.glb"):
        _write(path, time.time())
    native.write_text('{"configuration":"T24"}', encoding="utf-8")
    native_before = native.read_bytes()
    (gltf / "ha-harmonic-analyzer.glb").write_bytes(
        _glb_bytes({"asset": {"version": "2.0"}}),
    )
    boxes.mkdir(parents=True)
    _write(png / "ha-harmonic-analyzer/ha-harmonic-analyzer_isometric.png", time.time())
    (boxes / "ha-harmonic-analyzer.json").write_text(
        '{"unit":"mm","components":['
        '{"part":"sample-part","cfg":"C1","mesh":"sample-part--c1"},'
        '{"part":"sample-part","cfg":"C2","mesh":"sample-part--c2"}]}',
        encoding="utf-8",
    )

    class _Doc:
        """A saved-active part whose tessellation changes only on rebuild."""

        def __init__(self, path: Path) -> None:
            self.native = path
            cfg = json.loads(path.read_text(encoding="utf-8"))["configuration"]
            self.ConfigurationManager = SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name=cfg),
            )
            self.ForceRebuild3(False)

        def ShowConfiguration2(self, cfg: str) -> bool:
            if cfg not in self.GetConfigurationNames():
                return False
            self.ConfigurationManager.ActiveConfiguration.Name = cfg
            return True

        def ForceRebuild3(self, _top_only: bool) -> bool:
            extent = {"T24": 24.0, "C1": 12.0, "C2": 18.0}[
                self.ConfigurationManager.ActiveConfiguration.Name
            ]
            self.vertices = ((0.0, 0.0, 0.0), (extent, 0.0, 0.0), (0.0, 1.0, 0.0))
            return True

        def EditRebuild3(self) -> bool:
            return self.ForceRebuild3(False)

        def GetConfigurationNames(self) -> list[str]:
            return ["T24", "C1", "C2"]

        def SaveAs3(self, path: str, _version: int, _options: int) -> int:
            out = Path(path)
            if out.suffix == ".STL":
                coordinates = [value for vertex in self.vertices for value in vertex]
                out.write_bytes(
                    b"\0" * 80 + struct.pack("<I", 1)
                    + struct.pack("<12fH", 0.0, 0.0, 1.0, *coordinates, 0),
                )
            elif out.suffix == ".STEP":
                points = [
                    f"#{index} = CARTESIAN_POINT('',({x},{y},{z}));"
                    for index, (x, y, z) in enumerate(self.vertices, 1)
                ]
                out.write_text(
                    "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n"
                    + "\n".join(points) + "\nENDSEC;\nEND-ISO-10303-21;\n",
                    encoding="ascii",
                )
            else:
                raise AssertionError(f"unexpected part export format: {out}")
            return 1

        def Save3(self, *_args) -> int:
            self.native.write_bytes(b"native incorrectly saved during export")
            return 1

    class _Sw:
        def CloseAllDocuments(self, _include_unsaved: bool) -> None:
            return None

    class _Adapter:
        swApp = _Sw()
        currentModel = None

        async def open_model(self, path: str):
            self.currentModel = _Doc(Path(path))
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
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ("ha_harmonic_analyzer",))
    monkeypatch.setattr(export_models, "exporter_untrusted", lambda: False)
    monkeypatch.setattr(export_models, "_certified_outputs", lambda: {})
    monkeypatch.setattr(
        export_models, "_certified_output_changed", lambda *_args: False,
    )
    monkeypatch.setattr(export_models, "load_colors", lambda: {"sample-part": (1, 1, 1)})
    monkeypatch.setattr(
        export_models, "load_src_digests",
        lambda: {"sample-part": "part-v1", "ha-harmonic-analyzer": "asm-v1"},
    )
    monkeypatch.setattr(
        export_models, "src_digest",
        lambda path: "asm-v1" if path.suffix == ".SLDASM" else "part-v1",
    )
    # The export preferences are enforced on the seat; this offline run has none.
    monkeypatch.setattr(export_models, "enforce_preferences", lambda *_args: {})
    monkeypatch.setattr(export_models, "doc_rgb", lambda _doc: (1, 1, 1))
    monkeypatch.setattr(export_models, "stamp_render_cache_current", lambda _paths: None)

    def _no_gallery() -> None:
        raise AssertionError(
            "export must not touch the comparison gallery -- it is the "
            "SolidWorks-free `gallery` task, so export can run on a farm worker"
        )

    monkeypatch.setattr(export_models, "refresh_comparison_gallery", _no_gallery)
    rendered_extent = None

    async def _repair_png(seat, _stem: str) -> None:
        nonlocal rendered_extent
        rendered_extent = max(vertex[0] for vertex in seat.currentModel.vertices)

    monkeypatch.setattr(export_models, "export_build_png", _repair_png)
    monkeypatch.setattr(
        export_models, "run_build",
        lambda build: (asyncio.run(build(adapter)), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py"])

    def stl_extent(path: Path) -> float:
        raw = path.read_bytes()
        assert struct.unpack("<I", raw[80:84])[0] == 1
        triangle = struct.unpack("<12fH", raw[84:])
        return max(triangle[3], triangle[6], triangle[9])

    assert export_models.main() == 0
    assert stl_extent(stl / "sample-part.STL") == 24.0
    assert stl_extent(stl / "sample-part--c1.STL") == 12.0
    assert stl_extent(stl / "sample-part--c2.STL") == 18.0
    points = re.findall(
        r"CARTESIAN_POINT\s*\(\s*''\s*,\s*\(([^)]*)\)\s*\)",
        (step / "sample-part.STEP").read_text(encoding="ascii"),
    )
    assert max(float(point.split(",")[0]) for point in points) == 24.0
    assert rendered_extent == 24.0
    assert native.read_bytes() == native_before


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
    export_models.refresh_comparison_gallery()
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
    export_models.refresh_comparison_gallery()
    assert [Path(cmd[2]).name for cmd in calls] == [
        "render_offline.py", "gallery.py",
    ]

    export_models.GALLERY_STAMP.unlink()
    calls.clear()
    monkeypatch.setattr(export_models, "_run_tool", _run)
    export_models.refresh_comparison_gallery()
    assert [Path(cmd[2]).name for cmd in calls] == [
        "render_offline.py", "composite.py", "gallery.py",
    ]
    assert calls[0] == ["uv", "run", str(render_tool)]


def _stub_gallery_tree(tmp_path: Path, monkeypatch, manifest: dict[str, object]) -> None:
    """Point every gallery path at a tmp tree holding just the manifest + tools."""
    comparisons = tmp_path / "comparisons"
    tools = comparisons / "tools"
    tools.mkdir(parents=True)
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


def test_gallery_missing_blender_fails_loudly(tmp_path: Path, monkeypatch) -> None:
    _stub_gallery_tree(tmp_path, monkeypatch, {"pairs": []})

    def _missing_blender(_cmd: list[str], _tag: str) -> list[str]:
        raise RuntimeError("cmp exited non-zero: BLENDER_UNAVAILABLE: no Blender found")

    monkeypatch.setattr(export_models, "_run_tool", _missing_blender)

    with pytest.raises(RuntimeError, match="comparison gallery requires Blender"):
        export_models.refresh_comparison_gallery()


def test_gallery_render_fault_is_fatal(tmp_path: Path, monkeypatch) -> None:
    """The gallery task owns the whole release showcase, so a renderer/scoring
    fault must fail it: a warn-and-succeed would ship a stale gallery, and the
    stamp must NOT claim the outputs match the current inputs."""
    _stub_gallery_tree(tmp_path, monkeypatch, {"pairs": []})
    warnings: list[str] = []
    monkeypatch.setattr(export_models._telemetry, "warn", warnings.append)

    def _render_fault(_cmd: list[str], _tag: str) -> list[str]:
        raise RuntimeError("cmp exited non-zero: blender crashed on pair sample")

    monkeypatch.setattr(export_models, "_run_tool", _render_fault)

    with pytest.raises(RuntimeError, match="blender crashed on pair sample"):
        export_models.refresh_comparison_gallery()
    assert warnings == []
    assert not (tmp_path / "gallery.json").exists()


def test_comparisons_flag_refreshes_only_the_gallery(monkeypatch) -> None:
    """``--comparisons`` is the SolidWorks-free ``gallery`` doit task: it runs the
    refresh, never attaches to COM, and refuses the export selection flags."""
    calls: list[str] = []
    monkeypatch.setattr(
        export_models, "refresh_comparison_gallery", lambda: calls.append("gallery"),
    )

    def _no_com(_build) -> int:
        raise AssertionError("--comparisons must never attach to SolidWorks")

    monkeypatch.setattr(export_models, "run_build", _no_com)
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--comparisons"])

    assert export_models.main() == 0
    assert calls == ["gallery"]

    monkeypatch.setattr(sys, "argv", ["export_models.py", "--comparisons", "--force"])
    with pytest.raises(SystemExit) as rejected:
        export_models.main()
    assert rejected.value.code == 2
    assert calls == ["gallery"]


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


def test_render_diff_local_source_uses_top_scene(
    tmp_path: Path, monkeypatch,
) -> None:
    module_path = Path(__file__).parents[1] / "comparisons" / "tools" / "render_diff.py"
    spec = importlib.util.spec_from_file_location("render_diff_under_test", module_path)
    assert spec is not None and spec.loader is not None
    monkeypatch.setitem(
        sys.modules,
        "osmesa_win",
        SimpleNamespace(enable_offscreen_gl=lambda: None),
    )
    render_diff = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render_diff)
    boxes = tmp_path / "boxes"
    boxes.mkdir()
    (boxes / "ch-channel.json").write_text('{"scene": "channel"}', encoding="utf-8")
    (boxes / "ha-harmonic-analyzer.json").write_text(
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
    part = "dt-cone-gear"
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
    glb = tmp_path / "fr-top-frame.glb"
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


def test_sanitize_glb_honours_khr_texture_transform_tex_coord(tmp_path: Path) -> None:
    """The extension's ``texCoord`` is the effective UV set, in both directions:
    a slot whose top-level texCoord names the dropped set but whose transform
    override names a surviving set keeps its texture; a slot whose top-level
    texCoord names a surviving set but whose override names the dropped set
    loses it."""
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
                    # top-level says 0 (dropped), override says 1 (survives) -> keep
                    "baseColorTexture": {
                        "index": 0,
                        "texCoord": 0,
                        "extensions": {"KHR_texture_transform": {"texCoord": 1}},
                    },
                },
                # top-level says 1 (survives), override says 0 (dropped) -> remove
                "normalTexture": {
                    "index": 1,
                    "texCoord": 1,
                    "extensions": {"KHR_texture_transform": {"texCoord": 0, "scale": [2, 2]}},
                },
                # extension present WITHOUT texCoord -> top-level 1 rules -> keep
                "occlusionTexture": {
                    "index": 2,
                    "texCoord": 1,
                    "extensions": {"KHR_texture_transform": {"scale": [2, 2]}},
                },
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
    glb = tmp_path / "transform.glb"
    glb.write_bytes(_glb_bytes(gltf))
    assert [d["attribute"] for d in export_models.sanitize_glb(glb)] == ["TEXCOORD_0"]
    fixed = _read_glb_json(glb)
    prim = fixed["meshes"][0]["primitives"][0]
    clone = fixed["materials"][prim["material"]]
    assert clone["name"] == "decal-untextured"
    assert clone["pbrMetallicRoughness"]["baseColorTexture"]["index"] == 0
    assert "normalTexture" not in clone
    assert clone["occlusionTexture"]["index"] == 2


@pytest.mark.parametrize(
    ("change", "reusable"),
    [
        ("line-endings", True),
        ("yaml-comment", True),
        ("yaml-value", False),
        ("face-name", False),
    ],
)
def test_exporter_ledger_reuses_only_equivalent_naming_inputs(
    tmp_path: Path, monkeypatch, change: str, reusable: bool,
) -> None:
    dodo = export_models._import_dodo()
    exporter = tmp_path / "export_models.py"
    naming = tmp_path / "_export_feature_faces.py"
    config = tmp_path / "requirements.yaml"
    exporter.write_bytes(b"EXPORT_REVISION = 1\n")
    naming.write_bytes(b"FACE_NAME_PREFIX = 'HAF_'\n")
    config.write_bytes(b"bore_diameter_mm: 6.5\n")
    deps = [str(path) for path in (exporter, naming, config)]
    monkeypatch.setattr(export_models, "__file__", str(exporter))
    monkeypatch.setattr(export_models, "_import_dodo", lambda: dodo)
    monkeypatch.setattr(dodo, "_export_requirement_deps", lambda: deps)
    monkeypatch.setattr(export_models, "SRC_DIGESTS", tmp_path / "export-src.json")
    ledger = {"ch-rocker-arm": "model-recipe"}
    export_models.save_src_digests(ledger)

    if change == "line-endings":
        for path in (exporter, naming, config):
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    elif change == "yaml-comment":
        config.write_bytes(b"# Same naming dimensions.\nbore_diameter_mm: 6.500\n")
    elif change == "yaml-value":
        config.write_bytes(b"bore_diameter_mm: 6.6\n")
    else:
        naming.write_bytes(b"FACE_NAME_PREFIX = 'HAG_'\n")

    assert export_models.load_src_digests() == (ledger if reusable else {})


def test_canonical_file_bytes_cleans_text_but_never_binary(tmp_path: Path) -> None:
    """The ONE canonicalisation rule: CRLF -> LF for text, untouched for binary.

    A NUL in the first 8 KiB marks binary (Git's own heuristic), and a .SLDPRT whose
    bytes happened to contain CRLF must keep its exact digest.
    """
    dodo = export_models._import_dodo()
    text = tmp_path / "recipe.py"
    text.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert dodo._canonical_file_bytes(str(text)) == b"a = 1\nb = 2\n"

    binary = tmp_path / "model.sldprt"
    payload = b"\x00SLDPRT\r\npayload\r\n"
    binary.write_bytes(payload)
    assert dodo._canonical_file_bytes(str(binary)) == payload


_FIXTURE_DIGEST = "a" * 32


class _Ledger(dict):
    """An exporter ledger that answers ``_FIXTURE_DIGEST`` for every unlisted key.

    The gate SKIPS a key it cannot decide, so a ledger that answers `None` makes
    both directions of the test vacuous: nothing compares, nothing raises. This
    answers every key, and the entries passed in are the ones that MOVED.
    """

    def get(self, key, default=None):  # type: ignore[override]
        return dict.get(self, key, _FIXTURE_DIGEST)


def _gallery_fixture(tmp_path: Path, monkeypatch) -> dict:
    """Build a two-model gallery tree (one assembly scene, one bare part).

    The gate walks `cad/out` and the comparisons manifest, so a test that reads
    the real ones asserts on THIS checkout's build state: it passes or fails with
    whatever the last build/restore left behind, and any recipe-input change (a
    `_artifact_cache.py` edit moved 130 source digests on 2026-09-18) turns the
    suite red without a defect. Construct the tree instead.
    """
    for name in ("sldasm", "sldprt", "boxes"):
        (tmp_path / name).mkdir()
    (tmp_path / "sldasm" / "demo-asm.SLDASM").write_bytes(b"asm")
    (tmp_path / "sldprt" / "demo-part.SLDPRT").write_bytes(b"part")
    (tmp_path / "sldprt" / "dt-cone-gear.SLDPRT").write_bytes(b"cone")
    (tmp_path / "boxes" / "demo-asm.json").write_text(
        json.dumps(
            {
                "unit": "mm",
                "components": [
                    {"part": "dt-cone-gear", "cfg": "t102", "mesh": "dt-cone-gear--t102"},
                    {"part": "demo-part", "cfg": "", "mesh": "demo-part"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(export_models, "OUT_SLDASM", tmp_path / "sldasm")
    monkeypatch.setattr(export_models, "OUT_SLDPRT", tmp_path / "sldprt")
    monkeypatch.setattr(export_models, "OUT_BOXES", tmp_path / "boxes")
    monkeypatch.setattr(export_models, "src_digest", lambda src: _FIXTURE_DIGEST)
    monkeypatch.setattr(export_models, "load_src_digests", _Ledger)
    return {"pairs": [{"model": "demo_asm"}, {"model": "demo_part"}]}


def test_gallery_gate_rejects_inputs_exported_from_another_model(
    monkeypatch, tmp_path: Path
) -> None:
    """The gallery must refuse an STL whose recorded source digest moved.

    This is the check the renderer cannot make (pillow-only ephemeral env), so it
    lives here, in the project env, and is what stops a release bundling a gallery
    rendered from a previous build's meshes.
    """
    manifest = _gallery_fixture(tmp_path, monkeypatch)
    export_models.assert_gallery_inputs_current(manifest)  # positive control

    monkeypatch.setattr(
        export_models,
        "load_src_digests",
        lambda: _Ledger({"dt-cone-gear--t102": "0" * 32}),
    )
    with pytest.raises(RuntimeError, match="dt-cone-gear--t102: exported from"):
        export_models.assert_gallery_inputs_current(manifest)


def test_gallery_gate_skips_keys_the_exporter_never_recorded(
    monkeypatch, tmp_path: Path
) -> None:
    """An unrecorded key cannot decide staleness and must not fail the gallery.

    A foreign ledger (`__exporter__` sentinel mismatch) yields {} and already
    forces a full re-export; turning "unknown" into a failure here would make every
    exporter-source change fail the release instead of re-rendering it.
    """
    manifest = _gallery_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(export_models, "load_src_digests", dict)

    export_models.assert_gallery_inputs_current(manifest)


def test_gallery_gate_rejects_a_mesh_whose_source_is_gone(
    monkeypatch, tmp_path: Path
) -> None:
    """A recipe digest matches even when the .SLDPRT is gone — reject the orphan.

    `_stable_artefact_digest` keys on the producing task's recipe, not the file's
    bytes, so it answers for a declared target that was deleted. The renderer no
    longer stats the source, so nothing else would stop the release rendering and
    certifying an STL with no model behind it.
    """
    manifest = _gallery_fixture(tmp_path, monkeypatch)
    (tmp_path / "sldprt" / "dt-cone-gear.SLDPRT").unlink()

    with pytest.raises(FileNotFoundError, match="is missing but dt-cone-gear--t102"):
        export_models.assert_gallery_inputs_current(manifest)
