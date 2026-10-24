"""Offline regression tests for export staleness and render cleanup."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import hashlib
import json
import re
import struct
import os
import sys
import tomllib
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import _part_save
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


# Explicit expected paths: deriving the expectation from the production inventory
# would hide a dropped member or an accidental bare-name alias.
_SHARED_MEMBERS = {
    "sh_vn_chain_link": (
        ("InnerLink", "sh-vn-chain-link", "sh-vn-chain-link--innerlink"),
        ("OuterLink", "sh-vn-chain-link--outerlink", "sh-vn-chain-link--outerlink"),
    ),
    "sh_vn_clamping_kit_hardware": (
        ("HoldDownStud", "sh-vn-clamping-kit-hardware",
         "sh-vn-clamping-kit-hardware--holddownstud"),
        ("TNut", "sh-vn-clamping-kit-hardware--tnut", "sh-vn-clamping-kit-hardware--tnut"),
        ("FlangeNut", "sh-vn-clamping-kit-hardware--flangenut",
         "sh-vn-clamping-kit-hardware--flangenut"),
    ),
    "sh_vn_music_wire": (
        ("LeverWire", "sh-vn-music-wire", "sh-vn-music-wire--leverwire"),
        ("PenWire", "sh-vn-music-wire--penwire", "sh-vn-music-wire--penwire"),
    ),
}


def _shared_release_fixture(tmp_path: Path, monkeypatch):
    """Real registry, paths and certificates; only external seat work is faked."""
    import _part_configuration_exports as members
    import export_features
    import features_bound

    root = tmp_path / "cad" / "out"
    for name in ("STEP", "STL", "PNG", "SLDPRT", "SLDASM", "GLTF", "BOXES", "FEATURES"):
        monkeypatch.setattr(export_models, f"OUT_{name}", root / name.lower())
    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "NEUTRAL_MANIFEST", root / "reports/release-neutral.json")
    monkeypatch.setattr(export_models, "COLORS", root / "stl/colors.json")
    monkeypatch.setattr(export_models, "SRC_DIGESTS", root / "stl/export-src.json")
    monkeypatch.setattr(export_models, "part_stems", lambda: list(_SHARED_MEMBERS))
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ())
    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", ())
    monkeypatch.setattr(features_bound, "stage_feature_steps", lambda *_args: [])
    monkeypatch.setattr(export_models, "_exporter_digest", lambda: "fixture-exporter")
    monkeypatch.setattr(export_models, "exporter_untrusted", lambda: False)
    monkeypatch.setattr(export_models, "src_digest", lambda _path: "fixture-recipe")
    monkeypatch.setattr(export_models, "load_src_digests", lambda: {
        stem.replace("_", "-"): "fixture-recipe" for stem in _SHARED_MEMBERS
    })
    monkeypatch.setattr(export_models, "load_colors", lambda: {})
    monkeypatch.setattr(export_models, "enforce_preferences", lambda *_args: {})
    monkeypatch.setattr(export_models, "stamp_render_cache_current", lambda _paths: None)
    monkeypatch.setattr(export_models, "doc_rgb", lambda _doc: (1, 1, 1))
    # Redirect the helper's default root without replacing its path/validation API.
    monkeypatch.setattr(members, "__file__", str(tmp_path / "cad/scripts/_part_configuration_exports.py"))
    expected = {}
    owned = {}
    for stem, configurations in _SHARED_MEMBERS.items():
        dashed = stem.replace("_", "-")
        native = root / "sldprt" / f"{dashed}.SLDPRT"
        native.parent.mkdir(parents=True, exist_ok=True)
        native.write_bytes(f"native:{stem}".encode())
        identity = hashlib.sha256(native.read_bytes()).hexdigest()
        (native.parent / f".{dashed}.execution").write_text(identity, encoding="utf-8")
        records = {}
        for configuration, neutral, mesh in configurations:
            records[configuration] = {}
            for kind, relative in (
                ("step", f"step/{neutral}.STEP"),
                ("png", f"png/{neutral}/{neutral}_isometric.png"),
                ("stl", f"stl/{mesh}.STL"),
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = f"{stem}:{configuration}:{kind}".encode()
                path.write_bytes(payload)
                expected[relative] = path
                if kind != "stl":
                    owned[path] = payload
                    records[configuration][kind] = {
                        "path": relative, "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
        certificate = members.configuration_manifest_path(stem, root)
        certificate.parent.mkdir(parents=True, exist_ok=True)
        certificate.write_text(json.dumps({
            "schema": "harmonic-analyzer/part-member-neutral@1",
            "source": f"sldprt/{dashed}.SLDPRT",
            "execution_identity": identity,
            "default_configuration": configurations[0][0],
            "configurations": records,
        }), encoding="utf-8")
    return root, expected, owned


def test_shared_release_inventory_requires_all_seven_members_without_scenes(
    tmp_path: Path, monkeypatch,
) -> None:
    _root, expected, _owned = _shared_release_fixture(tmp_path, monkeypatch)

    inventory = export_models._release_inventory(list(_SHARED_MEMBERS), [], {}, set())

    assert inventory == expected
    assert len([name for name in inventory if name.startswith("step/")]) == 7
    assert len([name for name in inventory if name.startswith("png/")]) == 7
    assert len([name for name in inventory if name.startswith("stl/")]) == 7
    for stem, configurations in _SHARED_MEMBERS.items():
        dashed = stem.replace("_", "-")
        assert f"stl/{dashed}.STL" not in inventory
        default, neutral, mesh = configurations[0]
        assert default != "Default"
        assert neutral == dashed
        assert mesh != dashed


def _shared_scene_meshes():
    return {
        stem.replace("_", "-"): [(configuration, mesh) for configuration, _neutral, mesh in entries]
        for stem, entries in _SHARED_MEMBERS.items()
    }


def test_shared_neutral_certificate_and_stage_include_unseen_members(
    tmp_path: Path, monkeypatch,
) -> None:
    _root, expected, _owned = _shared_release_fixture(tmp_path, monkeypatch)
    scene_meshes = _shared_scene_meshes()
    monkeypatch.setattr(export_models, "all_scene_part_meshes", lambda _scenes: scene_meshes)
    digests = export_models.load_src_digests()
    digests.update({mesh: "fixture-recipe" for entries in scene_meshes.values()
                    for _configuration, mesh in entries})
    export_models.write_release_neutral_manifest(
        list(_SHARED_MEMBERS), [], scene_meshes, set(), {}, digests,
    )
    manifest = json.loads(export_models.NEUTRAL_MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest["files"]) == set(expected)
    assert manifest["part_configurations"] == {
        stem.replace("_", "-"): {
            configuration: {
                "step": f"step/{neutral}.STEP",
                "stl": f"stl/{mesh}.STL",
                "png": f"png/{neutral}/{neutral}_isometric.png",
            }
            for configuration, neutral, mesh in entries
        }
        for stem, entries in _SHARED_MEMBERS.items()
    }

    stage = tmp_path / "stage"
    facts = export_models.stage_release_neutral(stage)

    assert facts == {
        "documents": 3,
        "parts": 3,
        "assemblies": 0,
        "steps": 7,
        "stls": 7,
        "pngs": 7,
        "views": 1,
        "config_meshes": 7,
    }
    for relative, source in expected.items():
        assert (stage / relative).read_bytes() == source.read_bytes()


@pytest.mark.parametrize("kind", ["step", "png", "stl"])
def test_shared_neutral_certification_refuses_unseen_missing_member(
    tmp_path: Path, monkeypatch, kind: str,
) -> None:
    _root, expected, _owned = _shared_release_fixture(tmp_path, monkeypatch)
    scene_meshes = _shared_scene_meshes()
    digests = export_models.load_src_digests()
    digests.update({mesh: "fixture-recipe" for entries in scene_meshes.values()
                    for _configuration, mesh in entries})
    missing = next(path for relative, path in expected.items()
                   if relative.startswith(f"{kind}/") and "--penwire" in relative)
    missing.unlink()

    with pytest.raises(RuntimeError):
        export_models.write_release_neutral_manifest(
            list(_SHARED_MEMBERS), [], scene_meshes, set(), {}, digests,
        )
    assert not export_models.NEUTRAL_MANIFEST.exists()


def test_shared_neutral_certification_refuses_missing_scene_member_coverage(
    tmp_path: Path, monkeypatch,
) -> None:
    _shared_release_fixture(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError):
        export_models.write_release_neutral_manifest(
            list(_SHARED_MEMBERS), [], {}, set(), {}, export_models.load_src_digests(),
        )
    assert not export_models.NEUTRAL_MANIFEST.exists()


@pytest.mark.parametrize("kind", ["step", "png", "stl"])
@pytest.mark.parametrize("fault", ["missing", "same-size-corruption"])
def test_release_stage_refuses_changed_nondefault_shared_member(
    tmp_path: Path, monkeypatch, kind: str, fault: str,
) -> None:
    _root, expected, _owned = _shared_release_fixture(tmp_path, monkeypatch)
    scene_meshes = _shared_scene_meshes()
    monkeypatch.setattr(export_models, "all_scene_part_meshes", lambda _scenes: scene_meshes)
    digests = export_models.load_src_digests()
    digests.update({mesh: "fixture-recipe" for entries in scene_meshes.values()
                    for _configuration, mesh in entries})
    export_models.write_release_neutral_manifest(
        list(_SHARED_MEMBERS), [], scene_meshes, set(), {}, digests,
    )
    path = next(path for relative, path in expected.items()
                if relative.startswith(f"{kind}/") and "--penwire" in relative)
    if fault == "missing":
        path.unlink()
    else:
        path.write_bytes(b"x" * path.stat().st_size)

    with pytest.raises(RuntimeError):
        export_models.stage_release_neutral(tmp_path / "stage")


class _MemberDoc:
    def __init__(self, native):
        configurations = _SHARED_MEMBERS[native.stem.replace("-", "_")]
        self.names = [entry[0] for entry in configurations]
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=self.names[0]),
        )

    def ShowConfiguration2(self, configuration):
        assert configuration in self.names
        self.ConfigurationManager.ActiveConfiguration.Name = configuration
        return True

    def ForceRebuild3(self, _top_only):
        return True

    def EditRebuild3(self):
        return True

    def SaveAs3(self, filename, _version, _options):
        path = Path(filename)
        assert path.suffix == ".STL", "full exporter must not regenerate member STEP"
        path.write_bytes(self.ConfigurationManager.ActiveConfiguration.Name.encode())
        return 1


class _MemberAdapter:
    swApp = SimpleNamespace(CloseAllDocuments=lambda _unsaved: None)
    currentModel = None

    async def open_model(self, filename):
        self.currentModel = _MemberDoc(Path(filename))
        return SimpleNamespace(is_success=True, data=None)

    def _attempt(self, call, default=None):
        return call()


def test_forced_full_export_preserves_part_owned_member_bytes(
    tmp_path: Path, monkeypatch,
) -> None:
    root, expected, owned = _shared_release_fixture(tmp_path, monkeypatch)
    certificates = {
        path: path.read_bytes() for path in (root / "reports/part-neutral").glob("*.json")
    }

    async def forbid_render(*_args):
        raise AssertionError("full exporter must not regenerate part-owned member PNG")

    monkeypatch.setattr(export_models, "export_build_png", forbid_render)
    monkeypatch.setattr(
        export_models, "run_build", lambda build: (asyncio.run(build(_MemberAdapter())), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--force"])

    assert export_models.main() == 0

    for path, payload in {**owned, **certificates}.items():
        assert path.read_bytes() == payload
    assert all(path.is_file() for path in expected.values())


@pytest.mark.parametrize("fault", [None, "unstaged-member-change"])
def test_feature_staged_default_member_step_is_certified_as_feature_bytes(
    tmp_path: Path, monkeypatch, fault: str | None,
) -> None:
    # sh_vn_clamping_kit_hardware is both a member part and a feature part: its
    # labelled feature STEP replaces the part-certified default (bare) STEP.
    import features_bound

    root, expected, owned = _shared_release_fixture(tmp_path, monkeypatch)
    feature_step = root / "step" / "sh-vn-clamping-kit-hardware.STEP"
    other_member = root / "step" / "sh-vn-clamping-kit-hardware--tnut.STEP"
    labelled = b"labelled feature STEP"

    def stage(_out, _step_directory):
        feature_step.write_bytes(labelled)
        if fault:
            other_member.write_bytes(b"x" * other_member.stat().st_size)
        return (feature_step,)

    scene_meshes = _shared_scene_meshes()
    digests = {stem.replace("_", "-"): "fixture-recipe" for stem in _SHARED_MEMBERS}
    digests.update({mesh: "fixture-recipe" for entries in scene_meshes.values()
                    for _configuration, mesh in entries})
    monkeypatch.setattr(features_bound, "stage_feature_steps", stage)
    monkeypatch.setattr(export_models, "load_src_digests", lambda: dict(digests))
    monkeypatch.setattr(export_models, "all_scene_part_meshes", lambda _scenes: scene_meshes)
    monkeypatch.setattr(export_models, "export_build_png", None)
    monkeypatch.setattr(
        export_models, "run_build", lambda build: (asyncio.run(build(_MemberAdapter())), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--force", "--record-digests"])

    if fault:
        with pytest.raises(RuntimeError, match="changed after certification"):
            export_models.main()
        assert not export_models.NEUTRAL_MANIFEST.exists()
        return
    assert export_models.main() == 0

    files = json.loads(export_models.NEUTRAL_MANIFEST.read_text(encoding="utf-8"))["files"]
    assert set(files) == set(expected)
    assert files["step/sh-vn-clamping-kit-hardware.STEP"]["sha256"] == (
        hashlib.sha256(labelled).hexdigest()
    )
    for path, payload in owned.items():
        if path != feature_step:
            relative = path.relative_to(root).as_posix()
            assert files[relative]["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("stem", list(_SHARED_MEMBERS))
@pytest.mark.parametrize(
    "fault",
    ["missing-certificate", "stale-execution", "corrupt-certificate",
     "missing-step", "corrupt-step", "missing-png", "corrupt-png"],
)
def test_forced_export_refuses_invalid_member_before_any_export_work(
    tmp_path: Path, monkeypatch, stem: str, fault: str,
) -> None:
    import _part_configuration_exports as members
    import features_bound

    root, _expected, owned = _shared_release_fixture(tmp_path, monkeypatch)
    certificate = members.configuration_manifest_path(stem, root)
    if fault == "missing-certificate":
        certificate.unlink()
    elif fault == "stale-execution":
        (root / "sldprt" / f".{stem.replace('_', '-')}.execution").write_text(
            "f" * 64, encoding="utf-8",
        )
    elif fault == "corrupt-certificate":
        certificate.write_text("{", encoding="utf-8")
    else:
        kind = fault.split("-")[1]
        # Non-default member catches implementations validating only bare files.
        path = members.configuration_export_paths(stem, root)[_SHARED_MEMBERS[stem][-1][0]][kind]
        if fault.startswith("missing"):
            path.unlink()
        else:
            path.write_bytes(b"x" * path.stat().st_size)
    remaining = {path: path.read_bytes() for path in owned if path.exists()}

    def forbid_work(*_args):
        raise AssertionError("invalid member certificate must fail before export work")

    monkeypatch.setattr(features_bound, "stage_feature_steps", forbid_work)
    monkeypatch.setattr(export_models, "run_build", forbid_work)
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--force"])

    with pytest.raises(RuntimeError):
        export_models.main()

    assert not export_models.NEUTRAL_MANIFEST.exists()
    for path, payload in remaining.items():
        assert path.read_bytes() == payload


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
    import export_features

    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", ())
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

    _part_save._prune_stale_part_views(tmp_path, part, ["isometric"])

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


@pytest.mark.parametrize("stem", ["ch_pivot_shaft", "ch_rocker_arm_tl_oblique_pivot_pin"])
def test_features_cli_writes_only_one_requested_part_using_public_bundle_paths(
    tmp_path: Path, monkeypatch, stem: str,
) -> None:
    import export_features
    from _export_feature_faces import face_name

    native = tmp_path / "sldprt" / f"{stem.replace('_', '-')}.SLDPRT"
    native.parent.mkdir()
    native.write_bytes(b"unchanged native part")
    unrelated = tmp_path / "features" / "ch_rocker_arm" / "features.toml"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"another leaf's independent manifest")
    ledger = tmp_path / "stl" / "export-src.json"
    ledger.parent.mkdir()
    ledger.write_bytes(b"full export ledger stays untouched")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    opened = []
    closed = []

    class Adapter:
        currentModel = None
        swApp = SimpleNamespace(CloseAllDocuments=lambda unsaved: closed.append(unsaved))

        async def open_model(self, path):
            opened.append(Path(path))
            self.currentModel = Path(path)
            return SimpleNamespace(is_success=True, data=None)

        def _attempt(self, call, default=None):
            return call()

    def save_step(_doc, selected, step):
        assert selected == stem
        rows = [
            f"#{index} = ADVANCED_FACE ( '{face_name(feature, 1)}', ( #100 ), #101, .T. ) ;"
            for index, feature in enumerate(export_features.feature_selectors(selected), 1)
        ]
        step.write_text(
            "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n"
            + "\n".join(rows) + "\nENDSEC;\nEND-ISO-10303-21;\n",
            encoding="ascii",
        )

    monkeypatch.setattr(export_models, "OUT_SLDPRT", native.parent)
    monkeypatch.setattr(export_models, "OUT_FEATURES", tmp_path / "features")
    monkeypatch.setattr(export_models, "enforce_preferences", lambda *_args: None)
    monkeypatch.setattr(export_models, "_save_feature_step", save_step)
    monkeypatch.setattr(export_models._config, "release_revision", lambda: "v38")
    monkeypatch.setattr(
        export_models, "run_build", lambda build: (asyncio.run(build(Adapter())), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--features", stem.replace("_", "-")])

    assert export_models.main() == 0
    manifest, step = export_features.bundle_paths(stem, tmp_path)
    content = tomllib.loads(manifest.read_text(encoding="utf-8"))
    assert content["step"] == step.name
    assert content["step_sha256"] == hashlib.sha256(step.read_bytes()).hexdigest()
    assert content["drawing"]["revision"] == "v38"
    assert set(content["features"]) == set(export_features.feature_selectors(stem))
    assert opened == [native]
    assert closed == [True]
    after = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert {path: after[path] for path in before} == before
    assert set(after) - set(before) == {manifest, step}


def test_features_cli_exports_and_stages_one_step_per_declared_configuration(
    tmp_path: Path, monkeypatch,
) -> None:
    """A test-only multi-configuration bundle carries every declared configuration."""
    import export_features
    import features_bound
    from _export_feature_faces import face_name

    from dt_crank_handle_pivot_screw_spec import INSTALLED_CONFIG

    # Reuse real feature declarations; simulate configurations only in this test.
    stem = "ch_rocker_arm_tl_oblique_pivot_pin"
    original = export_features.step_configurations
    monkeypatch.setattr(
        export_features, "step_configurations",
        lambda selected: ("Default", INSTALLED_CONFIG) if selected == stem else original(selected),
    )
    dashed = stem.replace("_", "-")
    native = tmp_path / "sldprt" / f"{dashed}.SLDPRT"
    native.parent.mkdir()
    native.write_bytes(b"unchanged native part")
    saves = []

    class Doc:
        def __init__(self) -> None:
            self.active = "Default"  # the saved configuration

        @property
        def ConfigurationManager(self):
            return SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name=self.active))

        def ShowConfiguration2(self, cfg):
            self.active = cfg
            return True

        def ForceRebuild3(self, _top_only):
            return True

        def EditRebuild3(self):
            return True

    class Adapter:
        currentModel = None
        swApp = SimpleNamespace(CloseAllDocuments=lambda _unsaved: None)

        async def open_model(self, path):
            self.currentModel = Doc()
            return SimpleNamespace(is_success=True, data=None)

        def _attempt(self, call, default=None):
            return call()

    def save_step(doc, selected, step, *, reuse_names=False):
        assert selected == stem
        saves.append((step.name, doc.active, reuse_names))
        rows = [
            f"#{index} = ADVANCED_FACE ( '{face_name(feature, 1)}', ( #100 ), #101, .T. ) ;"
            for index, feature in enumerate(export_features.feature_selectors(selected), 1)
        ]
        step.write_text(
            f"ISO-10303-21;\nHEADER;\n/* {doc.active} */\nENDSEC;\nDATA;\n"
            + "\n".join(rows) + "\nENDSEC;\nEND-ISO-10303-21;\n",
            encoding="ascii",
        )

    monkeypatch.setattr(export_models, "OUT_SLDPRT", native.parent)
    monkeypatch.setattr(export_models, "OUT_FEATURES", tmp_path / "features")
    monkeypatch.setattr(export_models, "enforce_preferences", lambda *_args: None)
    monkeypatch.setattr(export_models, "_save_feature_step", save_step)
    monkeypatch.setattr(export_models._config, "release_revision", lambda: "v38")
    monkeypatch.setattr(
        export_models, "run_build", lambda build: (asyncio.run(build(Adapter())), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--features", dashed])

    assert export_models.main() == 0
    assert saves == [
        (f"{dashed}.STEP", "Default", False),
        (f"{dashed}-Default.STEP", "Default", True),
        (f"{dashed}-{INSTALLED_CONFIG}.STEP", INSTALLED_CONFIG, True),
    ]
    manifest, step = export_features.bundle_paths(stem, tmp_path)
    configured = export_features.configuration_step_paths(stem, tmp_path)
    assert list(configured) == ["Default", INSTALLED_CONFIG]
    assert {path for path in manifest.parent.iterdir()} == {manifest, step, *configured.values()}

    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", (stem,))
    staged = features_bound.stage_feature_steps(tmp_path, tmp_path / "step")
    assert {path.name for path in staged} == {
        f"{dashed}.STEP", f"{dashed}-Default.STEP", f"{dashed}-{INSTALLED_CONFIG}.STEP",
    }
    for cfg, path in configured.items():
        assert (tmp_path / "step" / path.name).read_bytes() == path.read_bytes()
        assert f"/* {cfg} */" in path.read_text(encoding="ascii")


def test_single_configuration_parts_declare_no_configuration_steps() -> None:
    import export_features

    assert export_features.step_configurations("ch_pivot_shaft") == ()
    assert export_features.configuration_step_paths("ch_pivot_shaft") == {}


def test_configuration_steps_require_explicit_spec_opt_in(monkeypatch) -> None:
    import export_features
    from dt_crank_handle_pivot_screw_spec import INSTALLED_CONFIG

    stem = "ch_rocker_arm_tl_oblique_pivot_pin"
    # Surviving feature owners do not opt into extra configuration STEP exports.
    assert export_features.step_configurations(stem) == ()
    original = export_features.source_tree
    spec_path = Path(export_features.__file__).parent / f"{stem}_spec.py"
    declaration = ast.parse(
        f"FEATURE_STEP_CONFIGURATIONS = {('Default', INSTALLED_CONFIG)!r}"
    )
    monkeypatch.setattr(
        export_features, "source_tree",
        lambda path: declaration if path == spec_path else original(path),
    )
    # Bypass the production cache so the test-only declaration cannot leak.
    assert export_features.step_configurations.__wrapped__(stem) == ("Default", INSTALLED_CONFIG)



@pytest.fixture
def produced_feature_bundles(tmp_path: Path, monkeypatch):
    """Real manifest/STEP bundles with already-current native STL/render outputs."""
    import export_features
    from _export_feature_faces import face_name

    stems = ("ch_pivot_shaft", "ch_rocker_arm_tl_oblique_pivot_pin")
    monkeypatch.setattr(export_features, "SUPPORTED_PARTS", stems)
    colors = {}
    digests = {}
    for stem in stems:
        manifest, step = export_features.bundle_paths(stem, tmp_path)
        step.parent.mkdir(parents=True)
        rows = [
            f"#{index} = ADVANCED_FACE ( '{face_name(feature, 1)}', ( #100 ), #101, .T. ) ;"
            for index, feature in enumerate(export_features.feature_selectors(stem), 1)
        ]
        step.write_bytes(
            ("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n"
             + "\n".join(rows) + "\nENDSEC;\nEND-ISO-10303-21;\n").encode("ascii")
        )
        export_features.write_manifest(stem, step, revision="v38")
        dashed = stem.replace("_", "-")
        for relative in (
            f"sldprt/{dashed}.SLDPRT", f"stl/{dashed}.STL",
            f"png/{dashed}/{dashed}_isometric.png",
        ):
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"current native-owned output")
        colors[dashed] = (1, 1, 1)
        digests[dashed] = "current-native-recipe"
    for name, relative in (
        ("OUT_FEATURES", "features"), ("OUT_STEP", "step"),
        ("OUT_STL", "stl"), ("OUT_PNG", "png"), ("OUT_SLDPRT", "sldprt"),
        ("OUT_SLDASM", "sldasm"), ("OUT_BOXES", "boxes"), ("OUT_GLTF", "gltf"),
    ):
        monkeypatch.setattr(export_models, name, tmp_path / relative)
    monkeypatch.setattr(export_models, "COLORS", tmp_path / "stl/colors.json")
    monkeypatch.setattr(export_models, "SRC_DIGESTS", tmp_path / "stl/export-src.json")
    monkeypatch.setattr(export_models, "part_stems", lambda: list(stems))
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ())
    monkeypatch.setattr(export_models, "exporter_untrusted", lambda: False)
    monkeypatch.setattr(export_models, "load_colors", lambda: dict(colors))
    monkeypatch.setattr(export_models, "load_src_digests", lambda: dict(digests))
    monkeypatch.setattr(export_models, "src_digest", lambda _path: "current-native-recipe")
    monkeypatch.setattr(export_models, "_certified_outputs", lambda: {})
    monkeypatch.setattr(export_models, "_certified_output_changed", lambda *_args: False)
    monkeypatch.setattr(export_models, "stamp_render_cache_current", lambda _paths: None)

    def refuse_generation(*_args, **_kwargs):
        pytest.fail("full export must consume produced bundles, not regenerate them")

    for name in ("feature_selectors", "requirement_manifest", "write_manifest"):
        monkeypatch.setattr(export_features, name, refuse_generation)
    monkeypatch.setattr(export_models, "_save_feature_step", refuse_generation)
    monkeypatch.setattr(export_models, "export_feature_bundles", refuse_generation)
    monkeypatch.setattr(export_models, "run_build", refuse_generation)
    monkeypatch.setattr(sys, "argv", ["export_models.py"])
    return tmp_path, stems


def test_full_export_copies_raw_feature_steps_without_rederiving_or_opening_cad(
    produced_feature_bundles,
) -> None:
    root, stems = produced_feature_bundles
    originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    # An old neutral STEP must be repaired even though the native STL ledger is fresh.
    output = root / "step" / f"{stems[0].replace('_', '-')}.STEP"
    output.parent.mkdir()
    output.write_bytes(b"stale independent STEP")
    assert export_models.main() == 0
    for stem in stems:
        name = f"{stem.replace('_', '-')}.STEP"
        assert (root / "step" / name).read_bytes() == (
            root / "features" / stem / name
        ).read_bytes()
    assert {path: path.read_bytes() for path in originals} == originals


@pytest.mark.parametrize("fault", ["missing-manifest", "missing-step", "unbound-step"])
def test_full_export_refuses_incomplete_bundles_before_copying_any_output(
    produced_feature_bundles, fault: str,
) -> None:
    import export_features
    from features_bound import FeaturesBoundError

    root, stems = produced_feature_bundles
    manifest, step = export_features.bundle_paths(stems[-1], root)
    if fault == "missing-manifest":
        manifest.unlink()
        diagnostic = "cannot read required file"
    elif fault == "missing-step":
        step.unlink()
        diagnostic = "cannot read required file"
    else:
        step.write_bytes(step.read_bytes() + b"unbound producer bytes")
        diagnostic = "does not bind the adjacent STEP"
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    with pytest.raises(FeaturesBoundError, match=diagnostic):
        export_models.main()
    assert not (root / "step").exists()
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


def test_forced_full_export_regenerates_native_outputs_but_keeps_bundle_step_bytes(
    produced_feature_bundles, monkeypatch,
) -> None:
    root, stems = produced_feature_bundles
    native_bytes = {
        path: path.read_bytes() for path in (root / "sldprt").iterdir()
    }
    saved = []

    class Adapter:
        swApp = SimpleNamespace(CloseAllDocuments=lambda _unsaved: None)
        currentModel = None

        async def open_model(self, path):
            self.currentModel = Path(path)
            return SimpleNamespace(is_success=True, data=None)

        def _attempt(self, call, default=None):
            return call()

    def save_as(_doc, path):
        assert path.suffix == ".STL", "enrolled STEP must never be re-exported"
        path.write_bytes(b"forced native STL")
        saved.append(path.name)
        return 1

    async def render(_adapter, stem):
        path = root / "png" / stem / f"{stem}_isometric.png"
        path.write_bytes(b"forced native render")

    monkeypatch.setattr(export_models, "_save_as", save_as)
    monkeypatch.setattr(export_models, "export_build_png", render)
    monkeypatch.setattr(export_models, "enforce_preferences", lambda *_args: None)
    monkeypatch.setattr(export_models, "doc_rgb", lambda _doc: (1, 1, 1))
    monkeypatch.setattr(
        export_models, "run_build",
        lambda build: (asyncio.run(build(Adapter())), 0)[1],
    )
    monkeypatch.setattr(sys, "argv", ["export_models.py", "--force"])
    assert export_models.main() == 0
    assert set(saved) == {f"{stem.replace('_', '-')}.STL" for stem in stems}
    for stem in stems:
        name = f"{stem.replace('_', '-')}.STEP"
        assert (root / "step" / name).read_bytes() == (
            root / "features" / stem / name
        ).read_bytes()
    assert {path: path.read_bytes() for path in native_bytes} == native_bytes
