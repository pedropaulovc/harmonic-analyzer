r"""Diagnostic: hide tube-frame instances in the top assembly and render
az 0 — do the black columns survive? Also dumps every component whose name
contains 'tube' or whose box is column-like (full height, small xz).

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_hide_tubeframe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import check, run_build  # noqa: E402
from render_compare import _flag, capture, component_boxes, resolve_framing, set_camera  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "out" / "sldasm" / "harmonic-analyzer.SLDASM"
OUT = ROOT / "out" / "png" / "diag"

CAM = {
    "mode": "euler",
    "az_deg": 0.0,
    "el_deg": 0.0,
    "roll_deg": 0.0,
    "zoom": 1.0,
    "target_mm": None,
    "perspective": None,
}


async def build(adapter) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    check("open", await adapter.open_model(str(ASM)))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")

    comps = model.GetComponents(False) or []
    tubes = []
    for c in comps:
        _flag(c, "IComponent2")
        name = c.Name2
        leaf = name.rsplit("/", 1)[-1]
        if leaf.startswith("tube-frame"):
            tubes.append(c)
        box = None
        try:
            box = c.GetBox(False, False)
        except Exception:
            pass
        if box:
            x0, y0, z0, x1, y1, z1 = [v * 1000.0 for v in box]
            if (y1 - y0) > 800 and (x1 - x0) < 80 and (z1 - z0) < 80:
                print(f"column-like: {name} x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}] z[{z0:.0f},{z1:.0f}]")

    print(f"hiding {len(tubes)} tube-frame instances")
    boxes = component_boxes(adapter)
    cam = dict(CAM)
    cam.update(resolve_framing(CAM, boxes))
    for c in tubes:
        c.Visible = False
    set_camera(adapter, cam)
    await capture(adapter, OUT / "diag-az0-no-tubeframe.png", 945, 2240)
    for c in tubes:
        c.Visible = True
    print("captured diag-az0-no-tubeframe.png")
    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
