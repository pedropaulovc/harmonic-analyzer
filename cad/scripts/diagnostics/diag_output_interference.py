r"""Diagnose the output-assembly interference clashes (issue #8).

Attaches to the ALREADY-OPEN output assembly (the from-empty build leaves it
open-but-unsaved when the interference gate raises -- fail-loud) and, for every
interfering pair, prints the component names, the overlap volume, and the
bounding box of the *interference body* in machine millimetres. The overlap
box localises exactly which feature of summing-lever the knife-mount /
magnifying-bracket actually touch -- the datum the static analysis was missing.

Read-only: never closes/saves any document.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\diag_output_interference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from _common import _flag, _read_member  # noqa: E402


def _box_mm(body) -> str:
    _flag(body, "IBody2")
    box = _read_member(body, "GetBodyBox")
    if callable(box):
        box = body.GetBodyBox()
    vals = [float(v) * 1000.0 for v in box]
    x1, y1, z1, x2, y2, z2 = vals
    return (
        f"x[{x1:8.2f},{x2:8.2f}] y[{y1:8.2f},{y2:8.2f}] z[{z1:8.2f},{z2:8.2f}]"
        f"  size=({x2 - x1:.2f},{y2 - y1:.2f},{z2 - z1:.2f})"
    )


async def main() -> int:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    await adapter.connect()
    sw = adapter.swApp
    asm = sw.ActiveDoc
    if asm is None:
        print("No ActiveDoc -- the output assembly is not open.")
        return 1
    title = str(_read_member(asm, "GetTitle") if not callable(getattr(asm, "GetTitle", None)) else asm.GetTitle())
    dtype = int(asm.GetType())
    print(f"ActiveDoc: title={title!r} type={dtype} (2=assembly)")
    if dtype != 2:
        print("ActiveDoc is not an assembly -- aborting.")
        return 1

    adapter.currentModel = asm
    _flag(asm, "IAssemblyDoc")
    asm.ForceRebuild3(False)
    mgr = _read_member(asm, "InterferenceDetectionManager")
    if mgr is None:
        print("InterferenceDetectionManager unavailable")
        return 1
    _flag(mgr, "IInterferenceDetectionMgr")
    mgr.TreatCoincidenceAsInterference = False
    mgr.TreatSubAssembliesAsComponents = True
    mgr.IncludeMultibodyPartInterferences = True
    mgr.MakeInterferingPartsTransparent = False
    mgr.CreateFastenersFolder = False
    mgr.UseTransform = False
    print("computing interferences ...")
    interferences = list(mgr.GetInterferences() or [])
    print(f"{len(interferences)} interference(s):\n")
    for itf in interferences:
        _flag(itf, "IInterference")
        names = []
        for comp in list(_read_member(itf, "Components") or []):
            _flag(comp, "IComponent2")
            names.append(str(_read_member(comp, "Name2")))
        vol = float(_read_member(itf, "Volume") or 0.0) * 1e9
        body = itf.GetInterferenceBody()
        box = _box_mm(body) if body is not None else "(no body)"
        print(f"  {' & '.join(names):42s} {vol:10.2f} mm^3")
        print(f"      overlap bbox (machine mm): {box}")
    mgr.Done()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
