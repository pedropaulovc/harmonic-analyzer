r"""Throwaway: find the EXACT cam-count at which the mechanism locks.

probe_one_cam proved 1 cam = mobile; probe_chain proved 20 cams = locked. Sweep
the count in between to tell gradual redundancy (locks at a low threshold -> must
reduce per-loop constraints, e.g. point-on-axis cam) from a single bad channel
(works to ~19, only 20 locks -> one dead-centre/non-Grashof loop to fix).

Suppresses ALL 20 cams for a clean baseline, caches crankshaft + cone-gear-shaft
+ cylinder-gear-0 ONCE, then for each target count: unsuppress cams up to that
count, ForceRebuild, recalc in-process, sample the CONE-SHAFT span (the single
node every loop shares -- if any loop jams, the cone shaft cannot turn). NEVER
saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_cam_sweep.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, check, log
from build_motion_study import (
    _comp_xform, _components, _find_one, _iter_mates, _rot_angle,
)

TIMES = [0.0, 0.375, 0.75, 1.125, 1.5]
STUDY = "Motion Study 2"
COUNTS = [1, 2, 3, 5, 8, 12, 16, 20]


async def _recalc_and_span(adapter, doc, cached):
    from solidworks_mcp.adapters.base import (
        MotionStudyRefParameters, MotionTimeParameters,
    )
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name=STUDY)))
    base, spans = {}, {}
    for t in TIMES:
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=STUDY))
        for key, comp in cached.items():
            if comp is None:
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            spans[key] = max(spans.get(key, 0.0), _rot_angle(base[key], a))
    return spans


async def main():
    from solidworks_mcp.adapters.base import SuppressMateParameters
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

    log("  walking top-level mates to find cam couplings ...")
    cam_names = []
    for _sub, _mate, name, _mtype, parts, _val in _iter_mates(
            adapter, doc, read_values=False):
        joined = " ".join(parts)
        if "cylinder-gear" in joined and "connecting-rod" in joined:
            cam_names.append(name)
    log(f"  found {len(cam_names)} cam couplings")

    # clean baseline: suppress all.
    for nm in cam_names:
        await adapter.suppress_mate(SuppressMateParameters(name=nm, suppress=True))
    log("  all cams suppressed (baseline)")

    log("  one-time walk to cache crank + cone-shaft + cyl-gear ...")
    comps = _components(adapter)
    cached = {
        "crank": _find_one(adapter, "crankshaft-1", comps=comps)[0],
        "coneshaft": _find_one(adapter, "cone-gear-shaft-1", comps=comps)[0],
        "cylgear0": _find_one(adapter, "cylinder-gear-1", comps=comps)[0],
    }

    n_on = 0
    for target in COUNTS:
        while n_on < target and n_on < len(cam_names):
            await adapter.suppress_mate(SuppressMateParameters(
                name=cam_names[n_on], suppress=False))
            n_on += 1
        spans = await _recalc_and_span(adapter, doc, cached)
        log(f"  cams={n_on:2d}  coneshaft={spans.get('coneshaft', 0.0):6.1f}  "
            f"cylgear0={spans.get('cylgear0', 0.0):6.1f}  "
            f"crank={spans.get('crank', 0.0):6.1f}")

    log("  coneshaft span ~0 at cams=N => the N-th loop jams; gradual fall => "
        "redundancy (need point-on-axis cam); cliff at 20 => one bad channel.")

    await adapter.disconnect()
    _telemetry.info("Disconnected (cams left as-set, doc not saved).")


if __name__ == "__main__":
    asyncio.run(main())
