r"""Throwaway: attach to the live failed Assem19 and dump the transforms of
crank-pedestal / cone-pivot-post / cone-gear-shaft, plus the interference
bodies' bounding boxes, to locate the nested-fit clash.

    uv run python cad\scripts\diagnostics\probe_pedestal_clash.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, log


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()

    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    comps = adapter._attempt(lambda: doc.GetComponents(True), default=None) or []
    for c in comps:
        _flag(c, "IComponent2")
        n = str(_read_member(c, "Name2"))
        if not any(k in n for k in ("crank-pedestal", "cone-pivot-post", "cone-gear-shaft")):
            continue
        xf = adapter._attempt(lambda cc=c: cc.Transform2, default=None)
        if xf is None:
            log(f"{n}: no Transform2")
            continue
        a = list(_read_member(xf, "ArrayData"))
        rot = [round(v, 6) for v in a[0:9]]
        trans = [round(v * 1000.0, 4) for v in a[9:12]]
        log(f"{n}: trans_mm={trans}")
        log(f"    rot rows: {rot[0:3]} | {rot[3:6]} | {rot[6:9]}")


if __name__ == "__main__":
    asyncio.run(main())
