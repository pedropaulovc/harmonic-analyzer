r"""Diagnostic round 2: bisect the floating bars within channel-1 by part
family. Renders az -90 with each family hidden. Read-only (state not saved).

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_hide2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import _telemetry  # noqa: E402
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

FAMILIES = {
    "springs": ("channel-spring-installed",),
    "ampbars": ("amplitude-bar",),
    "levers": ("channel-lever",),
    "shafts": ("fulcrum-shaft", "pivot-shaft", "pivot-ball-mount"),
    "rockers": ("rocker-arm-", "connecting-rod", "pivot-bushing", "lever-bushing"),
}


async def build(adapter) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    check("open", await adapter.open_model(str(ASM)))
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")

    comps = model.GetComponents(False) or []
    chan = []
    for c in comps:
        _flag(c, "IComponent2")
        if c.Name2.startswith("channel-1/"):
            chan.append(c)
    _telemetry.info(f"channel children: {len(chan)}")

    boxes = component_boxes(adapter)
    cam = dict(CAM)
    cam.update(resolve_framing(CAM, boxes))

    async def shot(tag: str) -> None:
        set_camera(adapter, cam)
        out = OUT / f"diag2-az-90--{tag}.png"
        await capture(adapter, out, 945, 2240)
        _telemetry.success(f"captured {out.name}")

    for tag, prefixes in FAMILIES.items():
        group = [
            c for c in chan
            if any(c.Name2.split("/", 1)[1].startswith(p) for p in prefixes)
        ]
        _telemetry.info(f"{tag}: hiding {len(group)}")
        for c in group:
            c.Visible = False
        await shot(f"hide-{tag}")
        for c in group:
            c.Visible = True

    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
