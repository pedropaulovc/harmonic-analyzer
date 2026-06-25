r"""Throwaway: read each moving sub's SOLVING state (rigid=0 / flexible=1).

The chain breaks at the FIRST link: the crankshaft spins 180deg but the 16T
pinion -- LOCKED to it -- reads 0. A lock mate can only be ignored if the sub's
internal mates are NOT in the active Motion solve, i.e. the sub is RIGID. If
drive-train-1 reads rigid here, _flex_subs did not stick (or a rebuild / the
health gate reverted it). Top-level walk only -> fast. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_flexstate.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, log
from build_motion_study import MOVING_SUBS, _components

SOLVE = {0: "rigid", 1: "flexible", 2: "fixed"}


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

    comps = _components(adapter, toplevel=True)
    by_name = {nm: c for c, nm in comps}
    for sub in MOVING_SUBS:
        comp = by_name.get(sub)
        if comp is None:
            log(f"  {sub:16s} : NOT FOUND")
            continue
        solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
        fixed = adapter._attempt(lambda c=comp: c.IsFixed(), default=None)
        log(f"  {sub:16s} : Solving={solving} ({SOLVE.get(solving, '?')})  IsFixed={fixed}")

    await adapter.disconnect()
    _telemetry.info("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
