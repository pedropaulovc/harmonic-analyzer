"""Export render-cache geometry from SolidWorks: STL + STEP + scene JSON.

doit task: ``export`` (on the COM spine). Normally invoked via ``doit export``
or as a prerequisite of ``doit release``; runnable standalone too.


For every model referenced by comparisons/manifest.json: AP214 STEP (exact
archival geometry) and the offline-render feed consumed by
comparisons/tools/render_offline.py —

* parts: fine binary STL in MILLIMETRES, untranslated (cad/out/stl/<dashed>.STL)
  plus an appearance colour in cad/out/stl/colors.json;
* assemblies: a monolithic cad/out/stl/<dashed>.STL and cad/out/boxes/
  <dashed>.json with per-component bounding boxes (framing) plus a scene
  graph: one entry per visible leaf component with its part stem,
  assembly-space transform (IMathTransform.ArrayData, row-vector
  convention, translation in millimetres) and RGB. Every referenced part gets
  its own STL, shared across assemblies and instanced by the Blender
  worker (so 20 cone gears cost one mesh). All geometry is in millimetres
  (mesh units == the scene-graph transform units, so they pair directly).

Colours cascade: component-level override -> part doc colour -> the
material-name table below (the build scripts only ever assign database
materials) -> gray.

Run after any --rebuild so the render cache tracks geometry:

    C:\\src\\SolidworksMCP-python\\.venv\\Scripts\\python.exe cad\\scripts\\export_models.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CAD_ROOT,
    PREF_STL_QUALITY,
    PREF_STL_UNITS,
    TOGGLE_STL_BINARY,
    TOGGLE_STL_NO_TRANSLATE,
    TOGGLE_STL_ONE_FILE,
    check,
    log,
    run_build,
)
from render_compare import _flag, _read_member, model_path  # noqa: E402

OUT_STL = CAD_ROOT / "out" / "stl"
OUT_STEP = CAD_ROOT / "out" / "step"
OUT_BOXES = CAD_ROOT / "out" / "boxes"
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
COLORS = OUT_STL / "colors.json"

# swconst ids (extracted from the installed swconst.tlb, R2026x). The STL ids
# live in _common (shared with the part-build STL export); STEP is export-only.
PREF_STEP_AP = 75            # int: swStepAP -> 214 (carries colours)

# Workbench-friendly equivalents of the SolidWorks material appearances
# actually used by the build scripts (see _common.apply_material).
MATERIAL_RGB = {
    "plain carbon steel": (0.55, 0.56, 0.57),
    "brass": (0.72, 0.60, 0.30),
    "gray cast iron": (0.38, 0.39, 0.40),
    "alloy steel": (0.48, 0.50, 0.52),
    "chrome stainless steel": (0.78, 0.79, 0.80),
    "oak": (0.62, 0.44, 0.24),
}
DEFAULT_RGB = (0.55, 0.55, 0.55)

INT_PREFS = {PREF_STL_QUALITY: 2, PREF_STEP_AP: 214, PREF_STL_UNITS: 0}
TOGGLES = {TOGGLE_STL_BINARY: True, TOGGLE_STL_ONE_FILE: True, TOGGLE_STL_NO_TRANSLATE: True}


def manifest_models() -> list[str]:
    manifest = json.loads(
        (CAD_ROOT.parent / "comparisons" / "manifest.json").read_text(encoding="utf-8")
    )
    return sorted({p["model"] for p in manifest["pairs"]})


def set_export_prefs(adapter: Any) -> dict:
    sw = adapter.swApp
    old = {
        "ints": {k: int(sw.GetUserPreferenceIntegerValue(k)) for k in INT_PREFS},
        "toggles": {k: bool(sw.GetUserPreferenceToggle(k)) for k in TOGGLES},
    }
    for k, v in INT_PREFS.items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in TOGGLES.items():
        sw.SetUserPreferenceToggle(k, v)
    log(f"export prefs set (were {old})")
    return old


def restore_export_prefs(adapter: Any, old: dict) -> None:
    sw = adapter.swApp
    for k, v in old["ints"].items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in old["toggles"].items():
        sw.SetUserPreferenceToggle(k, v)


def _valid_rgb(values: Any) -> tuple[float, float, float] | None:
    try:
        rgb = tuple(float(v) for v in values[:3])
    except Exception:
        return None
    if all(0.0 <= v <= 1.0 for v in rgb):
        return rgb
    return None  # SolidWorks reports -1 for "unset"


def doc_rgb(doc: Any) -> tuple[float, float, float]:
    """Part-doc colour: explicit colour override, else material-name table."""
    rgb = _valid_rgb(_read_member(doc, "MaterialPropertyValues") or ())
    if rgb:
        return rgb
    _flag(doc, "IPartDoc")
    name = ""
    try:
        res = doc.GetMaterialPropertyName2("", "")
        names = list(res) if isinstance(res, (tuple, list)) else [res]
        # pywin32 may return (name, [out] database) in either order
        name = next((s for s in names
                     if isinstance(s, str) and s.strip().lower() in MATERIAL_RGB), "")
    except Exception:
        pass
    return MATERIAL_RGB.get(name.strip().lower(), DEFAULT_RGB)


def comp_rgb(comp: Any, part_colors: dict[str, tuple[float, float, float]],
             stem: str) -> tuple[float, float, float]:
    try:
        rgb = _valid_rgb(comp.GetMaterialPropertyValues2(1, None) or ())
        if rgb:
            return rgb
    except Exception:
        pass
    return part_colors.get(stem, DEFAULT_RGB)


def _safe_cfg(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.strip().lower()).strip("-")


def mesh_key(stem: str, cfg: str) -> str:
    """STL cache key: configured components get their own mesh per config
    (e.g. the 20 cone gears are one part with 20 tooth-count configs).
    Separator is a double dash — SolidWorks SaveAs3 rejects '@' in file
    names (swFileSaveError 8, swFileNameContainsAtSign)."""
    if not cfg or cfg.lower() == "default":
        return stem
    return f"{stem}--{_safe_cfg(cfg)}"


def comp_xform(comp: Any) -> list[float] | None:
    try:
        xf = _read_member(comp, "Transform2")
        arr = _read_member(xf, "ArrayData") if xf is not None else None
        if arr and len(arr) >= 13:
            return [float(v) for v in arr[:13]]
    except Exception:
        pass
    try:  # deprecated but math-object-free
        arr = comp.GetXform()
        if arr and len(arr) >= 13:
            return [float(v) for v in arr[:13]]
    except Exception:
        pass
    return None


def scan_assembly(adapter: Any, part_colors: dict) -> tuple[list, list, set[tuple]]:
    """(boxes, scene components, referenced (stem, cfg, mesh) keys).

    The SolidWorks API reports boxes and transforms in metres (system units);
    they are scaled to MILLIMETRES here so the persisted scene graph matches the
    millimetre STL meshes it is rendered against."""
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")
    comps = model.GetComponents(False) or []
    boxes, scene, stems = [], [], set()
    for i, comp in enumerate(comps, 1):
        if i % 50 == 0:
            log(f"component scan {i}/{len(comps)} ...")
        _flag(comp, "IComponent2")
        try:
            name = str(_read_member(comp, "Name2") or "")
            box = comp.GetBox(False, False)
        except Exception:
            continue
        if not box:
            continue  # suppressed / no graphics
        short = name.split("/")[-1].lower()
        boxes.append((short, tuple(float(v) * 1000.0 for v in box)))  # m -> mm
        try:
            path = Path(str(comp.GetPathName()))
        except Exception:
            continue
        if path.suffix.lower() != ".sldprt":
            continue  # subassembly containers: their children scan separately
        if not bool(_read_member(comp, "Visible")):
            continue
        xform = comp_xform(comp)
        if not xform:
            log(f"  !! no transform for {name}, skipped")
            continue
        # translation (xform[9:12]) m -> mm; rotation [0:9] and scale [12] unitless
        xform = [*xform[:9], xform[9] * 1000.0, xform[10] * 1000.0,
                 xform[11] * 1000.0, *xform[12:]]
        stem = path.stem.lower()
        cfg = str(_read_member(comp, "ReferencedConfiguration") or "")
        mesh = mesh_key(stem, cfg)
        if mesh not in part_colors:
            try:
                doc = comp.GetModelDoc2()
                part_colors[mesh] = doc_rgb(doc) if doc else DEFAULT_RGB
            except Exception:
                part_colors[mesh] = DEFAULT_RGB
        stems.add((stem, cfg, mesh))
        scene.append({
            "name": short,
            "part": stem,
            "cfg": cfg,
            "mesh": mesh,
            "xform": xform,
            "rgb": list(comp_rgb(comp, part_colors, mesh)),
        })
    return boxes, scene, stems


def load_colors() -> dict:
    if COLORS.exists():
        return {k: tuple(v) for k, v in
                json.loads(COLORS.read_text(encoding="utf-8")).items()}
    return {}


def save_colors(colors: dict) -> None:
    COLORS.write_text(json.dumps(
        {k: list(v) for k, v in sorted(colors.items())}, indent=1), encoding="utf-8")


def part_stl_stale(stem: str, mesh: str, colors: dict) -> bool:
    src = OUT_SLDPRT / f"{stem}.SLDPRT"
    stl = OUT_STL / f"{mesh}.STL"
    step = OUT_STEP / f"{stem}.STEP"
    # STEP staleness matters even when the STL looks fresh: a part build now writes
    # a build-time STL (newer than the SLDPRT) but does NOT refresh the STEP or the
    # cached colour, so a rebuilt part would otherwise be skipped here with a stale
    # STEP/colour (codex review #11). A missing/older STEP -> re-export, which also
    # re-reads the appearance colour.
    return (not stl.exists() or stl.stat().st_mtime < src.stat().st_mtime
            or not step.exists() or step.stat().st_mtime < src.stat().st_mtime
            or mesh not in colors)


def main() -> int:
    force = "--force" in sys.argv[1:]
    models = manifest_models()
    colors = load_colors()

    parts = [m for m in models if model_path(m).suffix.lower() == ".sldprt"]
    assemblies = [m for m in models if m not in parts]

    stale_parts = [m for m in parts if force
                   or part_stl_stale(m.replace("_", "-"), m.replace("_", "-"), colors)]
    stale_asms = []
    for m in assemblies:
        src, bj = model_path(m), OUT_BOXES / f"{m.replace('_', '-')}.json"
        mono = OUT_STL / f"{m.replace('_', '-')}.STL"
        if (force or not bj.exists() or bj.stat().st_mtime < src.stat().st_mtime
                or not mono.exists() or mono.stat().st_mtime < src.stat().st_mtime):
            stale_asms.append(m)
            continue
        data = json.loads(bj.read_text(encoding="utf-8"))
        comps = data.get("components") or []
        if (not comps or any("mesh" not in c for c in comps) or any(
                part_stl_stale(c["part"], c["mesh"], colors) for c in comps)):
            stale_asms.append(m)

    if not stale_parts and not stale_asms:
        print("all exports fresh")
        return 0
    print(f"exporting parts={stale_parts or '[]'} assemblies={stale_asms or '[]'}")
    for d in (OUT_STL, OUT_STEP, OUT_BOXES):
        d.mkdir(parents=True, exist_ok=True)

    async def build(adapter: Any) -> dict[str, str]:
        old = set_export_prefs(adapter)
        done: dict[str, str] = {}

        def active_cfg(doc: Any) -> str:
            try:
                cm = _read_member(doc, "ConfigurationManager")
                ac = _read_member(cm, "ActiveConfiguration") if cm is not None else None
                return str(_read_member(ac, "Name") or "") if ac is not None else ""
            except Exception:
                return ""

        async def export_part_stls(stem: str, cfg_meshes: list[tuple[str, str]]) -> None:
            """One open per part; one STL per referenced configuration."""
            src = OUT_SLDPRT / f"{stem}.SLDPRT"
            check(f"open {src.name}", await adapter.open_model(str(src)))
            doc = adapter.currentModel
            for cfg, mesh in cfg_meshes:
                if cfg and cfg.lower() != "default" and active_cfg(doc) != cfg:
                    ok_cfg = doc.ShowConfiguration2(cfg)
                    # ShowConfiguration2 returns False when cfg was already
                    # active — only fail if it's genuinely not active now
                    if not ok_cfg and active_cfg(doc) != cfg:
                        try:
                            names = list(doc.GetConfigurationNames() or [])
                        except Exception:
                            names = None
                        raise RuntimeError(
                            f"{stem}: ShowConfiguration2({cfg!r}) failed (has {names})")
                out = OUT_STL / f"{mesh}.STL"
                ok = doc.SaveAs3(str(out), 0, 0)
                if not out.exists():
                    raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={ok})")
                colors[mesh] = doc_rgb(doc)
                log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB) rgb={colors[mesh]}")
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

        try:
            for m in stale_parts:
                dashed = m.replace("_", "-")
                src = model_path(m)
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                for out in (OUT_STL / f"{dashed}.STL", OUT_STEP / f"{dashed}.STEP"):
                    ok = doc.SaveAs3(str(out), 0, 0)
                    if not out.exists():
                        raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={ok})")
                    log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
                colors[dashed] = doc_rgb(doc)
                log(f"colour {dashed}: {colors[dashed]}")
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
                done[m] = "exported"

            for m in stale_asms:
                dashed = m.replace("_", "-")
                src = model_path(m)
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                out = OUT_STEP / f"{dashed}.STEP"
                ok = doc.SaveAs3(str(out), 0, 0)
                if not out.exists():
                    raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={ok})")
                log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
                mono = OUT_STL / f"{dashed}.STL"  # mm, like every other STL
                ok = doc.SaveAs3(str(mono), 0, 0)
                if not mono.exists():
                    raise RuntimeError(f"SaveAs3 produced no file: {mono} (rc={ok})")
                log(f"saved {mono.name} ({mono.stat().st_size / 1e6:.1f} MB, mm)")
                # fresh cache: preloaded colors.json entries would mask
                # colour changes made to part docs since the last export
                scan_colors: dict = {}
                boxes, scene, stems = scan_assembly(adapter, scan_colors)
                colors.update(scan_colors)
                (OUT_BOXES / f"{dashed}.json").write_text(json.dumps({
                    "unit": "mm",
                    "boxes": [{"name": n, "box": list(b)} for n, b in boxes],
                    "components": scene,
                }), encoding="utf-8")
                log(f"saved boxes+scene {dashed}.json "
                    f"({len(boxes)} boxes, {len(scene)} instances, {len(stems)} meshes)")
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

                by_stem: dict[str, list[tuple[str, str]]] = {}
                for stem, cfg, mesh in sorted(stems):
                    if force or part_stl_stale(stem, mesh, colors):
                        by_stem.setdefault(stem, []).append((cfg, mesh))
                for stem, cfg_meshes in sorted(by_stem.items()):
                    await export_part_stls(stem, cfg_meshes)
                done[m] = "exported"
            return done
        finally:
            save_colors(colors)
            restore_export_prefs(adapter, old)

    return run_build(build)


if __name__ == "__main__":
    raise SystemExit(main())
