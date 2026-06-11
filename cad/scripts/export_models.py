"""Export render-cache geometry from SolidWorks: STL + STEP + component boxes.

For every model referenced by comparisons/manifest.json (or --all build
outputs): fine-tessellation binary STL (the offline-render feed), AP214 STEP
(exact archival geometry), and for assemblies a JSON of per-component
bounding boxes (consumed by offline component framing, replacing the live
GetBox scan).

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
from render_compare import component_boxes, model_path  # noqa: E402

OUT_STL = CAD_ROOT / "out" / "stl"
OUT_STEP = CAD_ROOT / "out" / "step"
OUT_BOXES = CAD_ROOT / "out" / "boxes"

# swconst ids (extracted from the installed swconst.tlb, R2026x)
PREF_STL_QUALITY = 78      # int: swSTLQuality -> 2 = fine
PREF_STEP_AP = 75          # int: swStepAP -> 214 (carries colours)
TOGGLE_STL_BINARY = 69     # swSTLBinaryFormat
TOGGLE_STL_ONE_FILE = 72   # swSTLComponentsIntoOneFile


def manifest_models() -> list[str]:
    manifest = json.loads(
        (CAD_ROOT.parent / "comparisons" / "manifest.json").read_text(encoding="utf-8")
    )
    return sorted({p["model"] for p in manifest["pairs"]})


def set_export_prefs(adapter: Any) -> dict:
    sw = adapter.swApp
    old = {
        "quality": int(sw.GetUserPreferenceIntegerValue(PREF_STL_QUALITY)),
        "ap": int(sw.GetUserPreferenceIntegerValue(PREF_STEP_AP)),
        "binary": bool(sw.GetUserPreferenceToggle(TOGGLE_STL_BINARY)),
        "onefile": bool(sw.GetUserPreferenceToggle(TOGGLE_STL_ONE_FILE)),
    }
    sw.SetUserPreferenceIntegerValue(PREF_STL_QUALITY, 2)  # fine
    sw.SetUserPreferenceIntegerValue(PREF_STEP_AP, 214)
    sw.SetUserPreferenceToggle(TOGGLE_STL_BINARY, True)
    sw.SetUserPreferenceToggle(TOGGLE_STL_ONE_FILE, True)
    log(f"export prefs set (were {old})")
    return old


def restore_export_prefs(adapter: Any, old: dict) -> None:
    sw = adapter.swApp
    sw.SetUserPreferenceIntegerValue(PREF_STL_QUALITY, old["quality"])
    sw.SetUserPreferenceIntegerValue(PREF_STEP_AP, old["ap"])
    sw.SetUserPreferenceToggle(TOGGLE_STL_BINARY, old["binary"])
    sw.SetUserPreferenceToggle(TOGGLE_STL_ONE_FILE, old["onefile"])


def main() -> int:
    models = manifest_models()
    stale = []
    for m in models:
        src = model_path(m)
        stl = OUT_STL / f"{m.replace('_', '-')}.STL"
        if "--force" in sys.argv[1:] or not stl.exists() or stl.stat().st_mtime < src.stat().st_mtime:
            stale.append(m)
    if not stale:
        print("all exports fresh")
        return 0
    print(f"exporting {len(stale)}/{len(models)} models: {', '.join(stale)}")
    for d in (OUT_STL, OUT_STEP, OUT_BOXES):
        d.mkdir(parents=True, exist_ok=True)

    async def build(adapter: Any) -> dict[str, str]:
        old = set_export_prefs(adapter)
        done: dict[str, str] = {}
        try:
            for m in stale:
                src = model_path(m)
                dashed = m.replace("_", "-")
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                for out in (OUT_STL / f"{dashed}.STL", OUT_STEP / f"{dashed}.STEP"):
                    ok = doc.SaveAs3(str(out), 0, 0)
                    if not out.exists():
                        raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={ok})")
                    log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
                if src.suffix.lower() == ".sldasm":
                    boxes = component_boxes(adapter)
                    (OUT_BOXES / f"{dashed}.json").write_text(
                        json.dumps({"unit": "m", "boxes": [
                            {"name": n, "box": list(b)} for n, b in boxes
                        ]}), encoding="utf-8")
                    log(f"saved boxes {dashed}.json ({len(boxes)} components)")
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
                done[m] = "exported"
            return done
        finally:
            restore_export_prefs(adapter, old)

    return run_build(build)


if __name__ == "__main__":
    raise SystemExit(main())
