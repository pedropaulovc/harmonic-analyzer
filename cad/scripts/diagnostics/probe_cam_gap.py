r"""DIAGNOSTIC: report key part origins from a subassembly SLDASM.

Used to localise the top-level cylinder-gear <-> connecting-rod interference
regression: open a channel/drive-train SLDASM and print the world origin (mm)
of the first connecting-rod and/or cylinder-gear. In the old green build the
connecting-rod ring (Axis1 = origin) was concentric with the cam lobe, so the
old connecting-rod origin IS the lobe centre; comparing old vs new origins of
each part says which one moved.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_cam_gap.py <path-to-SLDASM>
"""

from __future__ import annotations

import sys

from _common import (
    _flag,
    _read_member,
    log,
    run_build,
)
from _assembly import (
    component_transform,
    world_point,
)

# Local bore coords (mm) mirrored from build_channel_assembly.
ROCKER_ROD_BORE_LOCAL = [25.4, 8.39937, 0.0]
ROD_RING_LOCAL = [0.0, 0.0, 0.0]
ROD_PIN_LOCAL = [0.0, 127.0, 0.0]


def _origins(adapter, needles):
    asm = adapter.currentModel
    out = {}
    for c in adapter._attempt(lambda: asm.GetComponents(True), default=None) or []:
        _flag(c, "IComponent2")
        nm = str(_read_member(c, "Name2"))
        base = nm.split("/")[-1]
        for needle in needles:
            if base == needle and needle not in out:
                a = component_transform(adapter, nm)
                out[needle] = (nm, [round(a[9] * 1000, 4), round(a[10] * 1000, 4), round(a[11] * 1000, 4)])
    return out


async def build(adapter):
    path = sys.argv[1]
    res0 = await adapter.open_model(path)
    log(f"opened {path}: {res0.is_success}")
    res = _origins(adapter, ["connecting-rod-1", "cylinder-gear-1", "rocker-arm-1"])
    for k, (nm, org) in sorted(res.items()):
        log(f"  {k}: {nm}  origin={org}")

    def wp(name, local):
        p = world_point(adapter, name, local)
        return [round(p[0], 4), round(p[1], 4), round(p[2], 4)]

    if "rocker-arm-1" in res:
        log(f"  rocker rod-bore (Axis2): {wp('rocker-arm-1', ROCKER_ROD_BORE_LOCAL)}")
    if "connecting-rod-1" in res:
        log(f"  rod pin  (Axis2): {wp('connecting-rod-1', ROD_PIN_LOCAL)}")
        log(f"  rod ring (Axis1): {wp('connecting-rod-1', ROD_RING_LOCAL)}")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
