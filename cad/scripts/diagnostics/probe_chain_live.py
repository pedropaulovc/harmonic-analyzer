r"""Throwaway: localize WHERE the drive chain breaks, IN-PROCESS + FAST.

probe_live proved (a) the motor+study work in-process (crank spins 180deg), (b)
cached IComponent2 dispatches DO reflect motion across SetTime (no per-frame
re-walk needed -- memory's staleness caveat was overcautious), and (c) the break
is between crankshaft (spins) and cylinder-gear (frozen).

This walks the tree ONCE, caches every stage of the chain, calculates in-process,
and samples the cached dispatches cheaply each frame:

  crankshaft --lock--> crank-pinion(16T) --gear[16:64]--> crank-drive-gear(64T)
    --lock--> cone-gear-shaft --lock--> cone-gear --gear[t:120]--> cylinder-gear
    --cam--> connecting-rod --pin--> rocker-arm

The first stage whose span drops to ~0 is where transmission stops. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_chain_live.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, check, log
from build_motion_study import (
    _by_z_rank, _comp_xform, _components, _find_one, _rot_angle,
)

TIMES = [0.0, 0.375, 0.75, 1.125, 1.5]
STUDY = "Motion Study 2"

# (label, family, single?) -- chain order from motor to rocker
CHAIN = [
    ("crankshaft", "crankshaft", True),
    ("16Tpinion", "crank-pinion", True),
    ("64Tgear", "crank-drive-gear", True),
    ("coneshaft", "cone-gear-shaft", True),
    ("conegear", "cone-gear", False),
    ("cylgear", "cylinder-gear", False),
    ("rod", "connecting-rod", False),
    ("rocker", "rocker-arm", False),
]


async def main():
    from solidworks_mcp.adapters.base import (
        MotionStudyRefParameters, MotionTimeParameters,
    )
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

    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name=STUDY)))

    log("  one-time walk to cache the chain ...")
    comps = _components(adapter)
    cached = []  # (label, comp, name)
    for label, family, single in CHAIN:
        if single:
            comp, name = _find_one(adapter, family + "-", comps=comps)
        else:
            ranked = _by_z_rank(adapter, family, comps=comps)
            comp, name = ranked[0] if ranked else (None, None)
        cached.append((label, comp, name))
        log(f"    {label:11s} = {name!r}")

    base = {}
    spans = {}
    for t in TIMES:
        check(f"set_time {t:.3f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=STUDY)))
        row = []
        for label, comp, _name in cached:
            if comp is None:
                row.append(f"{label}=NA")
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(label, a)
            ang = _rot_angle(base[label], a)
            spans[label] = max(spans.get(label, 0.0), ang)
            row.append(f"{label}={ang:6.1f}")
        log(f"  t={t:5.3f}s  " + "  ".join(row))

    log("  --- rotation spans over the run (deg) ---")
    for label, _f, _s in CHAIN:
        log(f"    {label:11s} span = {spans.get(label, 0.0):6.1f}")
    log("  the chain breaks at the first stage whose span drops to ~0.")

    await adapter.disconnect()
    _telemetry.info("Disconnected (doc left open).")


if __name__ == "__main__":
    asyncio.run(main())
