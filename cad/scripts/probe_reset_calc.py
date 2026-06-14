r"""Throwaway: is calculate_motion DETERMINISTIC if the model is reset to the
assembled pose first? probe_refpoint_fix saw 3 identical recalcs give 11.9/0/0 --
the only difference was the starting pose (run1 from a fresh rebuild, run2/3 from
the prior calc's t=1.5 pose). So calculate_motion depends on the current pose.

The deliverable calcs ONCE -- so the question that matters: does a calc from a
CLEAN assembled pose reliably give FULL motion (crank ~180 over 1.5 s @ 20 RPM,
rockers rocking)? 3 trials, each: set_motion_time(0) -> ForceRebuild3 ->
EditRebuild3 -> calculate -> sample. Consistent + full => bake 'reset before calc'
into the build; still erratic/weak => the flexible-sub closed-loop solve is
fundamentally fragile (escalate).

Uses whatever cams are in the open doc (probe_refpoint_fix left 20 point-on-axis).
NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_reset_calc.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, check, log
from build_motion_study import _by_z_rank, _comp_xform, _components, _find_one, _rot_angle

STUDY = "Motion Study 2"
TIMES = [0.0, 0.375, 0.75, 1.125, 1.5]


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
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    log("  one-time walk to cache targets ...")
    comps = _components(adapter)
    rocks = _by_z_rank(adapter, "rocker-arm", comps=comps)
    cached = {
        "crank": _find_one(adapter, "crankshaft-1", comps=comps)[0],
        "coneshaft": _find_one(adapter, "cone-gear-shaft-1", comps=comps)[0],
        "cylgear0": _find_one(adapter, "cylinder-gear-1", comps=comps)[0],
    }
    for i, (c, _n) in enumerate(rocks[:4]):
        cached[f"rock{i}"] = c

    for trial in range(1, 4):
        # reset to assembled pose.
        await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=STUDY))
        adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
        adapter._attempt(lambda: doc.EditRebuild3(), default=None)
        check(f"calc trial{trial}", await adapter.calculate_motion(
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
        rmax = max((spans.get(f"rock{i}", 0.0) for i in range(4)), default=0.0)
        log(f"  trial{trial}: crank={spans.get('crank', 0.0):6.1f}  "
            f"coneshaft={spans.get('coneshaft', 0.0):6.1f}  "
            f"cylgear0={spans.get('cylgear0', 0.0):6.1f}  maxrock={rmax:5.1f}")

    log("  consistent crank~180 + maxrock>0 => reset-before-calc is reliable.")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
