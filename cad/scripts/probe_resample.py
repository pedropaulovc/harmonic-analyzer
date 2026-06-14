r"""Throwaway: re-sample the calculated motion study with the PROVEN re-fetch
pattern. The kinematic build reported rocker rock spans of EXACTLY 0.0 -- the
signature of stale IComponent2 pointers (build_motion_study._sample_rockers
captures comp dispatches ONCE; a pre-fetched pointer for a part in a flexible sub
reports a stale pose after SetTime -- see motion-study-pipeline memory). This
re-walks the tree EACH frame so every dispatch is fresh, and samples the crank
(motor target -> must rotate) + a cylinder-gear (cam) + two rockers, to tell a
SAMPLING bug (gears/rockers DO move) from a genuinely LOCKED mechanism (nothing
moves even with fresh pointers).

Attaches to the doc the build left open (harmonic-analyzer with Motion Study 2
calculated + active). NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_resample.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, check, log
from build_motion_study import _by_z_rank, _comp_xform, _components, _find_one, _rot_angle

TIMES = [0.0, 0.75, 1.5, 2.25, 3.0]
STUDY = "Motion Study 2"  # the calculated study (must be named to re-activate
#                           in a fresh attach -- no study is active on connect)


async def main():
    from solidworks_mcp.adapters.base import MotionTimeParameters
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting (ATTACH) ...", flush=True)
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc -- the calculated doc must stay open")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    studies = await adapter.list_motion_studies()
    if studies.is_success:
        log(f"  motion studies: {[s.get('name') for s in studies.data]}")

    base = {}
    spans = {}
    for t in TIMES:
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=STUDY)))
        comps = _components(adapter)  # FRESH walk -> fresh dispatches each frame
        crank = _find_one(adapter, "crankshaft-1", comps=comps)
        gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
        rocks = _by_z_rank(adapter, "rocker-arm", comps=comps)
        rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
        targets = {
            "crank": crank,
            "gear0": gears[0] if gears else (None, None),
            "rod0": rods[0] if rods else (None, None),
            "rock0": rocks[0] if rocks else (None, None),
            "rock1": rocks[1] if len(rocks) > 1 else (None, None),
        }
        row = []
        for key, (comp, name) in targets.items():
            if comp is None:
                row.append(f"{key}=NA")
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            ang = _rot_angle(base[key], a)
            spans[key] = max(spans.get(key, 0.0), ang)
            row.append(f"{key}={ang:6.2f}")
        log(f"  t={t:4.2f}s  " + "  ".join(row))

    log("  --- rotation spans (deg) over the run ---")
    for key, v in spans.items():
        log(f"    {key:6s} span = {v:.2f} deg")
    log("  crank/gear span >0 + rocker span 0 => cam coupling not transmitting; "
        "all >0 => the sampling in _sample_rockers was stale (fix it).")

    await adapter.disconnect()
    print("Disconnected (doc left open).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
