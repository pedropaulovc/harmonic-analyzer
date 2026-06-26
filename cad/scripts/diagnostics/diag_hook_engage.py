r"""Visualize whether the channel spring bottom eye actually engages the spring-hook arm.

Inserts channel.SLDASM + summing.SLDASM at identity (so the plate, springs and
hooks share the world frame), hides everything except the summing-lever plate,
the channel springs and the spring-hooks, and renders tight views. The RIGHT
view (looking along world X) shows each spring bottom eye as a ring and the hook
arm (which runs along X) as a short stub at the ring centre -- if the stub is
inside the ring, they thread; if offset, they don't.

Run (SolidWorks already open)::
    uv run python cad\scripts\diagnostics\diag_hook_engage.py
"""
from __future__ import annotations

import sys

from _common import OUT_PNG, OUT_SLDASM, check, log, run_build
from _assembly import _flag, _read_member


KEEP = ("summing-lever", "spring-hook", "channel-spring-installed")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    check("create_assembly", await adapter.create_assembly())
    for name in ("channel", "summing"):
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
    model = adapter.currentModel
    _flag(asm, "IAssemblyDoc")

    def _leaves(comp):
        kids = list(adapter._attempt(lambda: comp.GetChildren(), default=None) or [])
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
        if any(k in nm for k in KEEP):
            continue
        ok = adapter._attempt(lambda: c.SetVisibility(0, 1, None), default=None)
        if ok is None:
            adapter._attempt(lambda: setattr(c, "Visible", 0), default=None)
        hidden += 1
    adapter._attempt(lambda: model.GraphicsRedraw2(), default=None)
    log(f"leaves={len(leaves)} hid {hidden}; rendering isolated plate+springs+hooks")

    png_dir = (OUT_PNG / "diag_hook_engage")
    png_dir.mkdir(parents=True, exist_ok=True)
    for view in ("right", "front", "isometric", "top"):
        p = (png_dir / f"engage_{view}.png").resolve()
        adapter._attempt(lambda: model.ShowNamedView2("", -1), default=None)
        await adapter.export_image({
            "file_path": str(p), "format_type": "png",
            "width": 2000, "height": 1400, "view_orientation": view,
        })
        log(f"  wrote {p}")
    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
