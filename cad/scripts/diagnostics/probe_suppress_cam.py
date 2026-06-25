r"""Throwaway: is the CAM coupling the jam? Suppress the 20 top-level cam mates
(cylinder-gear lobe <-> connecting-rod ring), recalc, and check whether the gear
train then spins.

The chain is frozen from the very first link (crankshaft spins, locked 16T pinion
does not) -- the signature of a JAMMED downstream the motor is overpowering.
probe_flex_motion proved the gear train transmits as a flexible sub WITHOUT the
channel load, so the cam four-bar is the prime suspect. Suppressing only the
top-level cam couplings isolates the drive train from the channel: if the
cylinder gear then spins, the cam coupling is the jam (the in-sub rod<->rocker
revolutes don't touch the drive train, so they cannot lock the gears).

NEVER saves. Leaves the cam mates SUPPRESSED in the open doc (re-run the build to
restore, or unsuppress).

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_suppress_cam.py
"""

from __future__ import annotations

import asyncio

import _telemetry
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
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    # find the cam couplings: top-level mates referencing a cylinder-gear AND a
    # connecting-rod.
    log("  walking top-level mate group to find cam couplings ...")
    cam_names = []
    for _sub, _mate, name, _mtype, parts, _val in _iter_mates(
            adapter, doc, read_values=False):
        joined = " ".join(parts)
        if "cylinder-gear" in joined and "connecting-rod" in joined:
            cam_names.append(name)
    log(f"  found {len(cam_names)} cam couplings: {cam_names[:3]}...")

    ok = 0
    for nm in cam_names:
        res = await adapter.suppress_mate(SuppressMateParameters(name=nm, suppress=True))
        ok += 1 if res.is_success else 0
    log(f"  suppressed {ok}/{len(cam_names)} cam couplings")
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name=STUDY)))

    log("  one-time walk to cache crankshaft + cylinder-gear ...")
    comps = _components(adapter)
    crank = _find_one(adapter, "crankshaft-1", comps=comps)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    targets = {"crank": crank, "cylgear0": gears[0] if gears else (None, None)}

    base, spans = {}, {}
    for t in TIMES:
        check(f"set_time {t:.3f}", await adapter.set_motion_time(
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
            row.append(f"{key}={ang:6.1f}")
        log(f"  t={t:5.3f}s  " + "  ".join(row))

    log("  --- spans with cam couplings SUPPRESSED (deg) ---")
    for key in targets:
        log(f"    {key:9s} span = {spans.get(key, 0.0):6.1f}")
    log("  cylgear>0 now => the CAM coupling was the jam; cylgear still 0 => the "
        "gear/lock mates are not transmitting (deeper).")

    await adapter.disconnect()
    _telemetry.info("Disconnected (cam mates left SUPPRESSED, doc not saved).")


if __name__ == "__main__":
    asyncio.run(main())
