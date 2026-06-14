r"""Throwaway: definitive in-process motion check + harness-speed test.

Two prior probes CONTRADICTED each other on the same left-open doc:
probe_resample saw crank=180deg, probe_geartrain (run after a disconnect) saw
crank=0. Hypothesis: a motion study's CALCULATED results do NOT survive a
disconnect/reconnect -- set_motion_time then interpolates nothing and every part
reads its assembled (t=0) pose. So calculate and sample MUST happen in ONE
process.

This probe:
  1. attaches to the open doc,
  2. RE-CALCULATES "Motion Study 2" in-process (results guaranteed live),
  3. pays the full-tree walk ONCE to cache target dispatches,
  4. samples Transform2 off the CACHED dispatches each frame (cheap).

Two questions answered at once:
  * does the crank (motor target) move after a fresh in-process calculate?  (if
    crank span > 0 the motor + study are fine; the prior all-zeros was the
    stale-results artifact)
  * do CACHED dispatches reflect the motion?  (if yes, the 269s per-frame
    re-walk in _sample_* is unnecessary -- the inner loop becomes fast; if the
    cached crank reads 0 while we believe it moves, staleness is real and a
    re-fetch is required.)

NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_live.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, check, log
from build_motion_study import (
    _by_z_rank, _comp_xform, _components, _find_one, _rot_angle,
)

TIMES = [0.0, 0.75, 1.5, 2.25, 3.0]
STUDY = "Motion Study 2"


async def main():
    from solidworks_mcp.adapters.base import (
        MotionStudyRefParameters, MotionTimeParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting (ATTACH) ...", flush=True)
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc -- the built doc must stay open")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    studies = await adapter.list_motion_studies()
    if studies.is_success:
        log(f"  motion studies: {[s.get('name') for s in studies.data]}")

    # (1) FRESH in-process solve -- the results the prior cross-process probe lost.
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name=STUDY)))

    # (2) ONE walk -> cache target dispatches (pay 269s once, not per frame).
    log("  one-time walk to cache target dispatches ...")
    comps = _components(adapter)
    crank = _find_one(adapter, "crankshaft-1", comps=comps)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rocks = _by_z_rank(adapter, "rocker-arm", comps=comps)
    rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
    targets = {
        "crank": crank,
        "cylgear0": gears[0] if gears else (None, None),
        "rod0": rods[0] if rods else (None, None),
        "rocker0": rocks[0] if rocks else (None, None),
    }
    for k, (c, nm) in targets.items():
        log(f"    {k:9s} = {nm!r}")

    # (3) cheap cached-dispatch sampling each frame.
    base = {}
    spans = {}
    for t in TIMES:
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=STUDY)))
        row = []
        for key, (comp, _nm) in targets.items():
            if comp is None:
                row.append(f"{key}=NA")
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            ang = _rot_angle(base[key], a)
            spans[key] = max(spans.get(key, 0.0), ang)
            row.append(f"{key}={ang:6.2f}")
        log(f"  t={t:4.2f}s  " + "  ".join(row))

    log("  --- cached-dispatch rotation spans (deg) ---")
    for key in targets:
        log(f"    {key:9s} span = {spans.get(key, 0.0):6.2f}")
    log("  crank>0 => motor+study OK in-process (prior 0s were lost results); "
        "crank>0 via CACHED dispatch => no re-walk needed (fast loop).")

    await adapter.disconnect()
    print("Disconnected (doc left open).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
