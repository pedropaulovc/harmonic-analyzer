r"""Throwaway: does a SINGLE four-bar move? All 20 cam couplings are currently
suppressed (probe_suppress_cam left them so) and the gear train spins freely.
Unsuppress exactly ONE cam coupling, recalc, and see whether that one channel's
rocker rocks.

  * one rocker rocks  => a single four-bar is mobile; the 20-loop case jams from
    redundancy / one inconsistent channel (fix: per-channel, or de-redundant).
  * no rocker rocks   => the four-bar mate SCHEME itself locks (coincident-axes
    cam pin is wrong / dead-centre geometry); rethink the joint.

Samples the crank + cylinder-gear + ALL 20 rockers (the full walk is already paid
for, so sampling every rocker is free) and reports the max rocker span. NEVER
saves. Leaves 1 cam unsuppressed, 19 suppressed.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_one_cam.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, check, log
from build_motion_study import (
    _by_z_rank, _comp_xform, _components, _find_one, _iter_mates, _rot_angle,
)

TIMES = [0.0, 0.375, 0.75, 1.125, 1.5]
STUDY = "Motion Study 2"


async def main():
    from solidworks_mcp.adapters.base import (
        MotionStudyRefParameters, MotionTimeParameters, SuppressMateParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting (ATTACH) ...", flush=True)
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    # find the cam couplings + the parts each connects.
    log("  walking top-level mates to find cam couplings ...")
    cams = []  # (name, parts)
    for _sub, _mate, name, _mtype, parts, _val in _iter_mates(
            adapter, doc, read_values=False):
        joined = " ".join(parts)
        if "cylinder-gear" in joined and "connecting-rod" in joined:
            cams.append((name, parts))
    log(f"  found {len(cams)} cam couplings")
    if not cams:
        return
    one_name, one_parts = cams[0]
    log(f"  unsuppressing ONE cam: {one_name} connecting {one_parts}")
    res = await adapter.suppress_mate(SuppressMateParameters(
        name=one_name, suppress=False))
    log(f"  unsuppress ok={res.is_success}")
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name=STUDY)))

    log("  one-time walk to cache crank + cylinder-gear + all rockers ...")
    comps = _components(adapter)
    crank = _find_one(adapter, "crankshaft-1", comps=comps)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rocks = _by_z_rank(adapter, "rocker-arm", comps=comps)
    targets = [("crank", crank[0]), ("cylgear0", gears[0][0] if gears else None)]
    targets += [(f"rock{i:02d}", c) for i, (c, _n) in enumerate(rocks)]

    base, spans = {}, {}
    for t in TIMES:
        check(f"set_time {t:.3f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=STUDY)))
        for key, comp in targets:
            if comp is None:
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            spans[key] = max(spans.get(key, 0.0), _rot_angle(base[key], a))

    log(f"    crank    span = {spans.get('crank', 0.0):6.1f}")
    log(f"    cylgear0 span = {spans.get('cylgear0', 0.0):6.1f}")
    rock_spans = {k: v for k, v in spans.items() if k.startswith("rock")}
    mx = max(rock_spans.items(), key=lambda kv: kv[1]) if rock_spans else ("-", 0)
    log(f"    max rocker span = {mx[1]:6.1f} ({mx[0]})")
    movers = sorted((k for k, v in rock_spans.items() if v > 0.5))
    log(f"    rockers that moved (>0.5deg): {movers}")
    log("  >0 => a single four-bar IS mobile (20-loop redundancy jams); "
        "0 => the four-bar mate scheme itself locks.")

    await adapter.disconnect()
    print("Disconnected (1 cam unsuppressed, doc not saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
