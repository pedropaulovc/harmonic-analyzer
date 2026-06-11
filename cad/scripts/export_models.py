"""Export render-cache geometry from SolidWorks: STL + STEP + scene JSON.

For every model referenced by comparisons/manifest.json: AP214 STEP (exact
archival geometry) and the offline-render feed consumed by
comparisons/tools/render_offline.py —

* parts: fine binary STL in METERS, untranslated (cad/out/stl/<dashed>.STL)
  plus an appearance colour in cad/out/stl/colors.json;
* assemblies: NO monolithic STL. cad/out/boxes/<dashed>.json gets per-
  component bounding boxes (framing) and a scene graph: one entry per
  visible leaf component with its part stem, assembly-space transform
  (IMathTransform.ArrayData, row-vector convention, translation in metres)
  and RGB. Every referenced part gets its own STL, shared across
  assemblies and instanced by the Blender worker (so 20 cone gears cost
  one mesh).

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
from _common import CAD_ROOT, check, log, run_build  # noqa: E402
from render_compare import _flag, _read_member, model_path  # noqa: E402

OUT_STL = CAD_ROOT / "out" / "stl"
OUT_STEP = CAD_ROOT / "out" / "step"
OUT_BOXES = CAD_ROOT / "out" / "boxes"
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
COLORS = OUT_STL / "colors.json"

# swconst ids (extracted from the installed swconst.tlb, R2026x)
PREF_STL_QUALITY = 78        # int: swSTLQuality -> 2 = fine
PREF_STEP_AP = 75            # int: swStepAP -> 214 (carries colours)
PREF_STL_UNITS = 211         # int: swExportStlUnits -> 2 = swMETER
TOGGLE_STL_BINARY = 69       # swSTLBinaryFormat
TOGGLE_STL_ONE_FILE = 72     # swSTLComponentsIntoOneFile
TOGGLE_STL_NO_TRANSLATE = 71  # swSTLDontTranslateToPositive: keep model origin

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

INT_PREFS = {PREF_STL_QUALITY: 2, PREF_STEP_AP: 214, PREF_STL_UNITS: 2}
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


def scan_assembly(adapter: Any, part_colors: dict) -> tuple[list, list, set[str]]:
    """(boxes, scene components, referenced part stems) for the open assembly."""
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
        boxes.append((short, tuple(float(v) for v in box)))
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
        stem = path.stem.lower()
        if stem not in part_colors:
            try:
                doc = comp.GetModelDoc2()
                part_colors[stem] = doc_rgb(doc) if doc else DEFAULT_RGB
            except Exception:
                part_colors[stem] = DEFAULT_RGB
        stems.add(stem)
        scene.append({
            "name": short,
            "part": stem,
            "xform": xform,
            "rgb": list(comp_rgb(comp, part_colors, stem)),
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


def part_stl_stale(stem: str, colors: dict) -> bool:
    src = OUT_SLDPRT / f"{stem}.SLDPRT"
    stl = OUT_STL / f"{stem}.STL"
    return (not stl.exists() or stl.stat().st_mtime < src.stat().st_mtime
            or stem not in colors)


def main() -> int:
    force = "--force" in sys.argv[1:]
    models = manifest_models()
    colors = load_colors()

    parts = [m for m in models if model_path(m).suffix.lower() == ".sldprt"]
    assemblies = [m for m in models if m not in parts]

    stale_parts = [m for m in parts if force
                   or part_stl_stale(m.replace("_", "-"), colors)
                   or not (OUT_STEP / f"{m.replace('_', '-')}.STEP").exists()]
    stale_asms = []
    for m in assemblies:
        src, bj = model_path(m), OUT_BOXES / f"{m.replace('_', '-')}.json"
        if force or not bj.exists() or bj.stat().st_mtime < src.stat().st_mtime:
            stale_asms.append(m)
            continue
        data = json.loads(bj.read_text(encoding="utf-8"))
        if "components" not in data or any(
                part_stl_stale(c["part"], colors) for c in data["components"]):
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

        async def export_part_stl(stem: str) -> None:
            src = OUT_SLDPRT / f"{stem}.SLDPRT"
            check(f"open {src.name}", await adapter.open_model(str(src)))
            doc = adapter.currentModel
            out = OUT_STL / f"{stem}.STL"
            ok = doc.SaveAs3(str(out), 0, 0)
            if not out.exists():
                raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={ok})")
            colors[stem] = doc_rgb(doc)
            log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB) rgb={colors[stem]}")
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
                # fresh cache: preloaded colors.json entries would mask
                # colour changes made to part docs since the last export
                scan_colors: dict = {}
                boxes, scene, stems = scan_assembly(adapter, scan_colors)
                colors.update(scan_colors)
                (OUT_BOXES / f"{dashed}.json").write_text(json.dumps({
                    "unit": "m",
                    "boxes": [{"name": n, "box": list(b)} for n, b in boxes],
                    "components": scene,
                }), encoding="utf-8")
                log(f"saved boxes+scene {dashed}.json "
                    f"({len(boxes)} boxes, {len(scene)} instances, {len(stems)} parts)")
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

                for stem in sorted(stems):
                    if force or part_stl_stale(stem, colors):
                        await export_part_stl(stem)
                done[m] = "exported"
            return done
        finally:
            save_colors(colors)
            restore_export_prefs(adapter, old)

    return run_build(build)


if __name__ == "__main__":
    raise SystemExit(main())
