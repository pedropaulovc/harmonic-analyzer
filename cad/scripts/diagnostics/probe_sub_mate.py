r"""Throwaway: prove the FIX -- add the rod<->rocker pin coincident INSIDE the
channel sub doc (where rod and rocker are sibling top-level components), not at
the top assembly (where they are both nested in the same flexible sub, which
AddMate5 rejects -- proven by probe_axis_isolate: rod.Axis2<->gear.Axis3 CROSS
OK, rod.Axis2<->rocker.Axis2 SAME FAIL).

Attaches to the doc the prior probes left open (channel-1 flexible, rod freed,
drive-train rigid, ch00 cam Axis1@rod<->Axis3@gear present, model tab).

  1. delete the ch00 cam mate -> rod fully free.
  2. retarget currentModel to the channel sub doc; add coincident(
     connecting-rod-1.Axis2 <-> rocker-arm-1.Axis2) INSIDE the sub -> expect OK.
  3. restore currentModel to the top asm; re-add the cam coincident at top
     (cross-sub) -> the closed four-bar. expect OK (loop closes; circle
     intersection holds).

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_sub_mate.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import (
    _flag,
    _read_member,
    log,
)
from _assembly import component_named_ref
from build_motion_study import _find_one, _iter_mates


async def _raw(adapter, kind, ref_a, ref_b, alignment="closest"):
    from solidworks_mcp.adapters.base import AddMateParameters
    res = await adapter.add_mate(AddMateParameters(
        mate_type=kind, entities=[ref_a, ref_b], alignment=alignment))
    if res.is_success:
        return True, res.data.get("name"), None
    return False, None, res.error


async def _del(adapter, name):
    if not name:
        return
    from solidworks_mcp.adapters.base import MateRefParameters
    await adapter.delete_mate(MateRefParameters(name=name))


def ref(comp, name):
    return component_named_ref(comp, name, "AXIS")


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()
    top = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if top is None:
        log("no ActiveDoc")
        return
    _flag(top, "IModelDoc2")
    adapter.currentModel = top
    log(f"ActiveDoc = {str(_read_member(top, 'GetTitle'))!r}")

    # delete ch00 cam mate (top-level coincident referencing rod + gear)
    cam_name = None
    for _f, _m, name, mtype, parts, _v in _iter_mates(adapter, top, read_values=False):
        joined = " ".join(parts)
        if mtype == 0 and "connecting-rod-1" in joined and "cylinder-gear-1" in joined:
            cam_name = name
            break
    log(f"  ch00 cam mate = {cam_name!r}")
    await _del(adapter, cam_name)
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)
    log("  deleted cam -> rod fully free")

    # resolve the channel sub doc and retarget
    ch_comp, _ = _find_one(adapter, "channel-1", toplevel=True)
    ch_doc = adapter._attempt(lambda: ch_comp.GetModelDoc2(), default=None)
    if ch_doc is None:
        log("  channel-1 GetModelDoc2 -> None; abort")
        return
    _flag(ch_doc, "IModelDoc2")
    log(f"  channel sub doc = {str(_read_member(ch_doc, 'GetTitle'))!r}")

    # ---- THE FIX: add pin<->bore INSIDE the sub (siblings, not nested) ----
    adapter.currentModel = ch_doc
    sub_ok = False
    sub_nm = None
    for kind in ("coincident",):
        ok, nm, err = await _raw(adapter, kind, ref("connecting-rod-1", "Axis2"),
                                 ref("rocker-arm-1", "Axis2"))
        log(f"  SUB {kind:11s} rod-1.Axis2 <-> rocker-1.Axis2 (in channel.SLDASM) "
            f"-> {'OK' if ok else 'FAIL ' + str(err)}")
        sub_ok, sub_nm = ok, nm

    adapter.currentModel = top
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)

    # ---- re-add the cam at TOP (cross-sub) -> the closed four-bar ----
    ok, nm, err = await _raw(adapter, "coincident",
                             ref("channel-1/connecting-rod-1", "Axis1"),
                             ref("drive-train-1/cylinder-gear-1", "Axis3"))
    log(f"  TOP cam ring<->lobe (cross-sub, closes 4-bar) -> "
        f"{'OK' if ok else 'FAIL ' + str(err)}")
    log(f"  RESULT: sub pin<->bore {'OK' if sub_ok else 'FAIL'}, "
        f"cam-after {'OK' if ok else 'FAIL'}")

    await adapter.disconnect()
    _telemetry.info("Disconnected (doc left open).")


if __name__ == "__main__":
    asyncio.run(main())
