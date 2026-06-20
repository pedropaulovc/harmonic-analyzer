r"""Localize the summing-lever <-> neutral-spring top-level clash.

Inserts ONLY channel.SLDASM + output.SLDASM (the clashing pair) at identity,
runs interference detection, and for every interference dumps the two
components' assembly-space bounding boxes (mm) plus their AABB overlap region
-- the overlap box is where the 3.99 mm^3 sits, so it names the offending
summing-lever feature by location.

Run (SolidWorks already open)::
    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\diag_sl_clash.py
"""
from __future__ import annotations

import sys

from _common import OUT_SLDASM, check, log, run_build
from _assembly import _flag, _read_member  # raw-COM helpers


def _box_mm(adapter, comp):
    """Assembly-space AABB [xmin,ymin,zmin,xmax,ymax,zmax] in mm, or None."""
    box = adapter._attempt(lambda: comp.GetBox(False, False), default=None)
    if box is None:
        return None
    return [v * 1000.0 for v in list(box)]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    check("create_assembly", await adapter.create_assembly())
    for name in ("channel", "output"):
        path = str((OUT_SLDASM / f"{name}.SLDASM").resolve())
        data = check(
            f"insert {name}",
            await adapter.insert_component(
                InsertComponentParameters(file_path=path, position=[0, 0, 0], rotation=[0, 0, 0])
            ),
        )
        comp = data["name"]
        if not data.get("fixed"):
            check(f"fix {name}", await adapter.fix_component(ComponentRefParameters(name=comp)))

    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    mgr = _read_member(asm, "InterferenceDetectionManager")
    _flag(mgr, "IInterferenceDetectionMgr")
    mgr.TreatCoincidenceAsInterference = False
    mgr.TreatSubAssembliesAsComponents = True
    mgr.IncludeMultibodyPartInterferences = True
    interferences = adapter._attempt(lambda: mgr.GetInterferences(), default=None)
    for itf in list(interferences or []):
        _flag(itf, "IInterference")
        vol = float(_read_member(itf, "Volume") or 0.0) * 1e9
        comps = list(_read_member(itf, "Components") or [])
        names, boxes = [], []
        for c in comps:
            _flag(c, "IComponent2")
            names.append(str(_read_member(c, "Name2")))
            boxes.append(_box_mm(adapter, c))
        log(f"--- interference {vol:.2f} mm^3 : {' & '.join(names)}")
        ibody = adapter._attempt(lambda: itf.GetInterferenceBody(), default=None)
        if ibody is not None:
            bb = adapter._attempt(lambda: ibody.GetBodyBox(), default=None)
            if bb:
                m = [v * 1000.0 for v in list(bb)]
                log(f"    CLASH BODY box(mm): x[{m[0]:.2f},{m[3]:.2f}] "
                    f"y[{m[1]:.2f},{m[4]:.2f}] z[{m[2]:.2f},{m[5]:.2f}]")
        for n, b in zip(names, boxes):
            if b:
                log(f"    {n}: x[{b[0]:.1f},{b[3]:.1f}] y[{b[1]:.1f},{b[4]:.1f}] z[{b[2]:.1f},{b[5]:.1f}]")
        if len(boxes) == 2 and all(boxes):
            a, b = boxes
            ox = (max(a[0], b[0]), min(a[3], b[3]))
            oy = (max(a[1], b[1]), min(a[4], b[4]))
            oz = (max(a[2], b[2]), min(a[5], b[5]))
            log(f"    OVERLAP AABB: x[{ox[0]:.2f},{ox[1]:.2f}] y[{oy[0]:.2f},{oy[1]:.2f}] z[{oz[0]:.2f},{oz[1]:.2f}]")
    adapter._attempt(lambda: mgr.Done(), default=None)

    # --- isolate summing-lever + the stretch00 springs, render the clash -----
    keep = ("summing-lever", "channel-spring-installed-stretch00")
    model = adapter.currentModel

    def _leaves(comp):
        kids = adapter._attempt(lambda: comp.GetChildren(), default=None)
        kids = list(kids or [])
        if not kids:
            return [comp]
        out = []
        for k in kids:
            _flag(k, "IComponent2")
            out.extend(_leaves(k))
        return out

    top = list(adapter._attempt(lambda: asm.GetComponents(True), default=None) or [])
    leaves = []
    for t in top:
        _flag(t, "IComponent2")
        leaves.extend(_leaves(t))
    hidden = 0
    for c in leaves:
        nm = str(_read_member(c, "Name2"))
        if any(k in nm for k in keep):
            continue
        ok = adapter._attempt(lambda: c.SetVisibility(0, 1, None), default=None)
        if ok is None:
            adapter._attempt(lambda: setattr(c, "Visible", 0), default=None)
        hidden += 1
    adapter._attempt(lambda: model.GraphicsRedraw2(), default=None)
    log(f"leaves={len(leaves)} hid {hidden}; rendering isolated clash")

    from _common import OUT_PNG
    png_dir = (OUT_PNG / "diag_sl_clash")
    png_dir.mkdir(parents=True, exist_ok=True)
    for view in ("right", "top", "isometric", "front"):
        p = (png_dir / f"clash_{view}.png").resolve()
        adapter._attempt(lambda: model.ShowNamedView2("", -1), default=None)
        await adapter.export_image({
            "file_path": str(p), "format_type": "png",
            "width": 1800, "height": 1200, "view_orientation": view,
        })
        log(f"  wrote {p}")
    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
