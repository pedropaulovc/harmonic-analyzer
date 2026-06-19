r"""Throwaway: collinear-axes cams (Axis1@rod <-> Axis3@gear) + reset-before-calc.

point-on-axis cams "over-define" when added from the exact DESIGN pose (the ring
point already lies on the lobe axis -> degenerate / the flexible sub pins the
under-defined rod). Collinear-axes cams add reliably (the 0.39mm slack keeps them
non-degenerate) -- but were only ever tested WITHOUT reset (erratic). Test them
WITH reset-before-calc, which was the actual fix for reliable motion.

The open doc (build left it) has the 20 in-sub rod<->rocker revolutes + motor +
study, but NO cams (point-on-axis all failed). Add 20 collinear cams, then 3
reset+calc trials. Reliable rocker motion => revert build cam to collinear, keep
reset. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_collinear_reset.py
"""

from __future__ import annotations

import asyncio

from _common import (
    _flag,
    _read_member,
    check,
    log,
)
from _assembly import coincident_mate
from build_motion_study import (
    _by_z_rank, _comp_xform, _components, _entity_ref, _find_one, _iter_mates, _rot_angle,
)

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

    # clear any leftover cams, then add collinear-axes cams.
    from solidworks_mcp.adapters.base import MateRefParameters, SuppressMateParameters
    for _s, _m, name, _t, parts, _v in _iter_mates(adapter, doc, read_values=False):
        j = " ".join(parts)
        if "cylinder-gear" in j and "connecting-rod" in j:
            await adapter.suppress_mate(SuppressMateParameters(name=name, suppress=False))
            await adapter.delete_mate(MateRefParameters(name=name))

    log("  one-time walk to pair + cache ...")
    comps = _components(adapter)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
    rocks = _by_z_rank(adapter, "rocker-arm", comps=comps)
    n = min(len(gears), len(rods))
    cached = {
        "crank": _find_one(adapter, "crankshaft-1", comps=comps)[0],
        "coneshaft": _find_one(adapter, "cone-gear-shaft-1", comps=comps)[0],
        "cylgear0": gears[0][0] if gears else None,
    }
    for i, (c, _nm) in enumerate(rocks[:4]):
        cached[f"rock{i}"] = c

    ok = 0
    for i in range(n):
        try:
            res = await coincident_mate(
                adapter, _entity_ref(rods[i][1], "Axis1", "AXIS"),
                _entity_ref(gears[i][1], "Axis3", "AXIS"),
                label=f"ch{i:02d} cam collinear")
            ok += 1 if res.get("name") else 0
        except Exception as exc:  # noqa: BLE001
            log(f"    ch{i:02d} collinear cam FAILED: {exc}")
    log(f"  added {ok}/{n} collinear-axes cams")

    for trial in range(1, 4):
        await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=STUDY))
        adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
        adapter._attempt(lambda: doc.EditRebuild3(), default=None)
        check(f"calc t{trial}", await adapter.calculate_motion(
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
            f"coneshaft={spans.get('coneshaft', 0.0):6.1f}  maxrock={rmax:5.1f}")

    log("  consistent crank~180 + maxrock>0 => collinear+reset works (simplest).")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
