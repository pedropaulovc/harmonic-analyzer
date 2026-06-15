r"""Diagnostic: bisect which top-level component produces the floating
hatched bars above the top frame in the az -90 view.

Renders the harmonic-analyzer az -90 el 0 view once per hidden top-level
component (plus a baseline) to cad/out/png/diag/. Read-only on the model
(hide state is not saved).

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_hide.py
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
    "az_deg": -90.0,
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

    top = [c for c in (model.GetComponents(True) or [])]
    for c in top:
        _flag(c, "IComponent2")
    names = [c.Name2 for c in top]
    print("top-level:", names)

    boxes = component_boxes(adapter)
    cam = dict(CAM)
    cam.update(resolve_framing(CAM, boxes))

    async def shot(tag: str) -> None:
        set_camera(adapter, cam)
        out = OUT / f"diag-az-90--{tag}.png"
        await capture(adapter, out, 945, 2240)
        print(f"captured {out.name}")

    await shot("baseline")
    for c in top:
        name = c.Name2
        tag = name.replace("/", "_")
        c.Visible = False
        model.EditRebuild3
        await shot(f"hide-{tag}")
        c.Visible = True
    model.EditRebuild3

    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
