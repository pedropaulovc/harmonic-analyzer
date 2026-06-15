r"""Throwaway isolation probe: is the pin<->bore failure because both parts live
inside the SAME flexible sub (channel-1)?

Attaches to the doc probe_loop_close left open (channel-1 flexible, rod fully
freed, drive-train rigid, ch00 cam mate Axis1@rod<->Axis3@gear present, MODEL
tab). No re-flex / re-suppress / tree walk -- ch00 names are known from the prior
run, and component_named_ref resolves them by path string.

Clean diagnostic (delete the cam mate first so the rod is fully free):
  T1  rod Axis2 <-> gear  Axis3   CROSS-sub (channel<->drive-train) -> expect OK
  T2  rod Axis2 <-> rocker Axis2  SAME-sub  (both channel-1)        -> expect FAIL
  T3  rod Axis1 <-> gear  Axis3   CROSS-sub re-add (sanity)         -> expect OK

T1 OK + T2 FAIL == top-level mate between two parts inside one flexible sub is
rejected; the rod<->rocker revolute must be authored INSIDE channel.SLDASM.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_axis_isolate.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, component_named_ref, log
from build_motion_study import _iter_mates

ROD = "channel-1/connecting-rod-1"
ROCKER = "channel-1/rocker-arm-1"
GEAR = "drive-train-1/cylinder-gear-1"


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
    print("Connecting (ATTACH) ...", flush=True)
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc -- the prepped doc must stay open")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    # find + delete the ch00 cam mate (coincident referencing rod + gear)
    cam_name = None
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, doc, read_values=False):
        joined = " ".join(parts)
        if mtype == 0 and "connecting-rod-1" in joined and "cylinder-gear-1" in joined:
            cam_name = name
            break
    log(f"  ch00 cam mate = {cam_name!r}")
    await _del(adapter, cam_name)
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
    log("  deleted cam mate -> rod fully free")

    # T1: cross-sub, rod's Axis2 against the known-good gear Axis3
    for kind in ("coincident", "concentric"):
        ok, nm, err = await _raw(adapter, kind, ref(ROD, "Axis2"), ref(GEAR, "Axis3"))
        log(f"  T1 {kind:11s} rod.Axis2 <-> gear.Axis3 (CROSS) -> "
            f"{'OK' if ok else 'FAIL ' + str(err)}")
        await _del(adapter, nm)
        adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    # T2: same-sub, rod's Axis2 against rocker's Axis2 (reconfirm the failure)
    for kind in ("coincident", "concentric"):
        ok, nm, err = await _raw(adapter, kind, ref(ROD, "Axis2"), ref(ROCKER, "Axis2"))
        log(f"  T2 {kind:11s} rod.Axis2 <-> rocker.Axis2 (SAME) -> "
            f"{'OK' if ok else 'FAIL ' + str(err)}")
        await _del(adapter, nm)
        adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    # T2b: same-sub but using rod's KNOWN-GOOD Axis1 vs rocker Axis2 -- isolates
    # whether it is the same-sub rule or specifically rod.Axis2 that is bad
    ok, nm, err = await _raw(adapter, "coincident", ref(ROD, "Axis1"), ref(ROCKER, "Axis2"))
    log(f"  T2b coincident rod.Axis1 <-> rocker.Axis2 (SAME) -> "
        f"{'OK' if ok else 'FAIL ' + str(err)}")
    await _del(adapter, nm)
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    # T3: re-add the cam mate (cross-sub sanity, leaves doc usable)
    ok, nm, err = await _raw(adapter, "coincident", ref(ROD, "Axis1"), ref(GEAR, "Axis3"))
    log(f"  T3 coincident rod.Axis1 <-> gear.Axis3 (CROSS, re-add cam) -> "
        f"{'OK' if ok else 'FAIL ' + str(err)}")

    await adapter.disconnect()
    print("Disconnected (doc left open).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
