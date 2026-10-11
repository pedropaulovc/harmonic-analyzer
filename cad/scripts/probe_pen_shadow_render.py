"""Throwaway native pen render with cast shadows and floor reflections off."""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

from _common import (
    CAD_ROOT,
    OUT_PNG,
    OUT_SLDASM,
    OUT_SLDPRT,
    _early_bound,
    check,
    run_build,
)


async def probe(adapter: Any) -> dict[str, str]:
    sw = _early_bound(adapter.swApp, "ISldWorks")
    import pythoncom
    from solidworks_mcp.adapters.sw_type_info import _find_aux_tlb

    typelib_path = _find_aux_tlb("swconst.tlb")
    if typelib_path is None:
        raise RuntimeError("Installed SolidWorks swconst.tlb not found")
    typelib = pythoncom.LoadTypeLib(str(typelib_path))
    named_constants = {}
    for index in range(typelib.GetTypeInfoCount()):
        if typelib.GetTypeInfoType(index) != pythoncom.TKIND_ENUM:
            continue
        info = typelib.GetTypeInfo(index)
        for variable in range(info.GetTypeAttr().cVars):
            descriptor = info.GetVarDesc(variable)
            named_constants[info.GetNames(descriptor[0])[0]] = int(descriptor[1])

    def enum(name: str) -> int:
        value = named_constants.get(name)
        if value is None:
            raise RuntimeError(f"SolidWorks named constant unavailable: {name}")
        return value

    prefs = {
        name: enum(name)
        for name in (
            "swDisplayShadowsInShadedMode",
            "swDisplayAmbientOcclusionShadows",
        )
    }
    initial = {name: bool(sw.GetUserPreferenceToggle(value)) for name, value in prefs.items()}
    assembly = OUT_SLDASM / "pn-pen.SLDASM"
    output_dir = OUT_PNG / "pn-pen-shadow-probe"
    report = CAD_ROOT / "out" / "reports" / "pn-pen-shadow-render.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    native_paths = [
        *OUT_SLDASM.glob("*.SLDASM"),
        *OUT_SLDPRT.glob("*.SLDPRT"),
    ]

    def native_hashes() -> dict[str, str]:
        hashes = {}
        for path in native_paths:
            with path.open("rb") as stream:
                hashes[path.relative_to(CAD_ROOT.parent).as_posix()] = (
                    hashlib.file_digest(stream, "sha256").hexdigest()
                )
        return hashes

    before_hashes = native_hashes()
    metadata: dict[str, Any] = {
        "infrastructure_base": "5035dbaa3278b82bc7428b68a192f328605846b7",
        "geometry_equivalent_to": "6a85c3e5cfc97f3d78ce854f6d56e050a5a49d3b",
        "base_reason": "Deployed farm protocol 4; CAD scripts/config/templates and adapter gitlink identical to task-start main (only _farm.py differs).",
        "exported_graph_membership": "verify:pn_pen_shadow_render registered in build/release verification closure",
        "assembly": assembly.relative_to(CAD_ROOT.parent).as_posix(),
        "read_only": True,
        "saved_model": False,
        "revision": str(sw.RevisionNumber()),
        "enum_source": str(typelib_path),
        "enum_typelib_identity": [str(item) for item in typelib.GetLibAttr()],
        "preference_ids": prefs,
        "initial_preferences": initial,
        "camera": "isometric, zoom-to-fit once; current view for capture",
        "captures": [],
    }
    artefacts: dict[str, str] = {}
    scene = None
    initial_reflections = None
    try:
        opened = sw.OpenDoc6(
            str(assembly.resolve()),
            enum("swDocASSEMBLY"),
            enum("swOpenDocOptions_Silent") | enum("swOpenDocOptions_ReadOnly"),
            "Default",
            0,
            0,
        )
        model, errors, warnings = opened
        metadata["open_errors"] = int(errors)
        metadata["open_warnings"] = int(warnings)
        if model is None or errors:
            raise RuntimeError(f"Read-only assembly open failed: errors={errors}, warnings={warnings}")
        adapter.currentModel = model
        configuration = _early_bound(model.GetActiveConfiguration(), "IConfiguration")
        if configuration is None:
            raise RuntimeError("Assembly has no active configuration")
        scene = _early_bound(configuration.GetScene(), "ISwScene")
        if scene is None:
            raise RuntimeError("Assembly configuration has no scene")
        initial_reflections = bool(scene.FloorReflections)
        metadata["initial_scene"] = {
            "FloorReflections": initial_reflections,
            "FloorShadows": bool(scene.FloorShadows),
        }
        # FloorReflections is valid only while FloorShadows is true. Establish
        # that prerequisite briefly, then disable both in the open model only.
        # Never call scene.Modify(): it saves the scene, unlike this probe.
        scene.FloorShadows = True
        if not bool(scene.FloorShadows):
            raise RuntimeError("Could not establish reflection setter prerequisite")
        scene.FloorReflections = False
        if bool(scene.FloorReflections):
            raise RuntimeError("Scene floor reflection readback remained enabled")
        scene.FloorShadows = False
        if bool(scene.FloorShadows):
            raise RuntimeError("Scene floor shadow readback remained enabled")
        model.ShowNamedView2("", enum("swIsometricView"))
        adapter._zoom_to_fit(model)
        for shadows, filename in ((False, "both-off.png"),):
            sw.SetUserPreferenceToggle(prefs["swDisplayAmbientOcclusionShadows"], False)
            sw.SetUserPreferenceToggle(prefs["swDisplayShadowsInShadedMode"], shadows)
            observed = {name: bool(sw.GetUserPreferenceToggle(value)) for name, value in prefs.items()}
            if observed != {
                "swDisplayShadowsInShadedMode": shadows,
                "swDisplayAmbientOcclusionShadows": False,
            }:
                raise RuntimeError(f"Render preference readback mismatch: {observed}")
            scene_before = {
                "FloorReflections": bool(scene.FloorReflections),
                "FloorShadows": bool(scene.FloorShadows),
            }
            if scene_before["FloorShadows"]:
                raise RuntimeError(f"Floor shadows enabled before capture: {scene_before}")
            model.GraphicsRedraw2()
            image = output_dir / filename
            image.unlink(missing_ok=True)
            result = await adapter.export_image({
                "file_path": str(image.resolve()),
                "format_type": "png",
                "width": 1600,
                "height": 1000,
                "view_orientation": "current",
            })
            check(f"native capture {filename}", result)
            if not image.is_file() or image.stat().st_size == 0:
                raise RuntimeError(f"Native image capture produced no file: {image}")
            after = {name: bool(sw.GetUserPreferenceToggle(value)) for name, value in prefs.items()}
            if after != observed:
                raise RuntimeError(f"Capture changed preferences: before={observed}, after={after}")
            scene_after = {
                "FloorReflections": bool(scene.FloorReflections),
                "FloorShadows": bool(scene.FloorShadows),
            }
            if scene_after != scene_before:
                raise RuntimeError(f"Capture changed scene: before={scene_before}, after={scene_after}")
            metadata["captures"].append({
                "path": image.relative_to(CAD_ROOT.parent).as_posix(),
                "preferences_before_capture": observed,
                "scene_before_capture": scene_before,
                "scene_after_capture": scene_after,
                "floor_reflections_effectively_enabled": False,
                "reflection_readback_valid": False,
                "observed_preferences": after,
                "bytes": image.stat().st_size,
            })
            artefacts[filename] = str(image)
    finally:
        restoration_errors = []
        if scene is not None and initial_reflections is not None:
            try:
                scene.FloorShadows = True
                scene.FloorReflections = initial_reflections
                if bool(scene.FloorReflections) != initial_reflections:
                    raise RuntimeError("Failed to restore scene FloorReflections")
            except Exception as exc:
                restoration_errors.append(f"scene.FloorReflections: {exc}")
            finally:
                try:
                    scene.FloorShadows = metadata["initial_scene"]["FloorShadows"]
                    metadata["restored_scene"] = {
                        "FloorReflections": bool(scene.FloorReflections),
                        "FloorShadows": bool(scene.FloorShadows),
                    }
                    if metadata["restored_scene"] != metadata["initial_scene"]:
                        raise RuntimeError("Failed to restore original scene properties")
                except Exception as exc:
                    restoration_errors.append(f"scene.FloorShadows: {exc}")
        for name, value in prefs.items():
            try:
                sw.SetUserPreferenceToggle(value, initial[name])
                if bool(sw.GetUserPreferenceToggle(value)) != initial[name]:
                    raise RuntimeError(f"Failed to restore {name}")
            except Exception as exc:
                restoration_errors.append(f"{name}: {exc}")
        metadata["restored_preferences"] = {
            name: bool(sw.GetUserPreferenceToggle(value)) for name, value in prefs.items()
        }
        metadata["restoration_errors"] = restoration_errors
        after_hashes = native_hashes()
        metadata["native_sha256_before"] = before_hashes
        metadata["native_sha256_after"] = after_hashes
        metadata["native_files_unchanged"] = before_hashes == after_hashes
        report.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if restoration_errors:
            raise RuntimeError("; ".join(restoration_errors))
        if before_hashes != after_hashes:
            raise RuntimeError("Read-only render probe changed native model bytes")
    artefacts["metadata"] = str(report)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(probe))
