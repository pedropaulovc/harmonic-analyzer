r"""Throwaway: VALIDATE the fix -- replace each collinear-axes cam coupling with a
POINT-ON-AXIS coincident (rod ring-centre point ON the gear lobe axis), which
removes the redundant orientation constraint (the rod<->rocker pin already fixes
orientation). The cam-sweep showed the collinear-axes scheme gives ERRATIC,
non-deterministic solves (coneshaft locked at 1/3/8/16 cams, moved at 2/5/12/20)
-- the signature of an ill-conditioned over-constrained system. A non-redundant
cam should solve RELIABLY with all 20 active.

The rod's ring centre is the rod ORIGIN (ring modelled at the part origin). A
component ref selects ANY named feature via GetCorresponding + Select2 (entity_type
is ignored for component refs), so component_named_ref(rod,"Origin") picks the
origin point; coincident(point, lobe-axis) = point-on-line = 2 constraints.

Deletes the 20 existing cams, re-adds point-on-axis, then recalcs 3x to check the
solve is now DETERMINISTIC + mobile. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_cam_pointaxis.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import (
    _flag,
    _read_member,
    check,
    log,
)
from _assembly import (
    coincident_mate,
    component_named_ref,
)
from build_motion_study import _comp_xform, _components, _find_one, _iter_mates, _rot_angle

TIMES = [0.0, 0.375, 0.75, 1.125, 1.5]
STUDY = "Motion Study 2"


def _gear_rod(parts):
    gear = next((p for p in parts if "cylinder-gear" in p), None)
    rod = next((p for p in parts if "connecting-rod" in p), None)
    return gear, rod


async def _recalc_span(adapter, doc, cached, tag):
    from solidworks_mcp.adapters.base import (
        MotionStudyRefParameters, MotionTimeParameters,
    )
    check(f"calculate_motion {tag}", await adapter.calculate_motion(
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
    from solidworks_mcp.adapters.base import MateRefParameters, SuppressMateParameters
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
    cams = []  # (name, gear, rod)
    for _sub, _mate, name, _mtype, parts, _val in _iter_mates(
            adapter, doc, read_values=False):
        joined = " ".join(parts)
        if "cylinder-gear" in joined and "connecting-rod" in joined:
            gear, rod = _gear_rod(parts)
            cams.append((name, gear, rod))
    log(f"  found {len(cams)} cam couplings")

    # ensure all are unsuppressed first (prior probes left a mix), then delete.
    for name, _g, _r in cams:
        await adapter.suppress_mate(SuppressMateParameters(name=name, suppress=False))
    deleted = 0
    for name, _g, _r in cams:
        res = await adapter.delete_mate(MateRefParameters(name=name))
        deleted += 1 if res.is_success else 0
    log(f"  deleted {deleted}/{len(cams)} collinear-axes cams")

    # re-add as point-on-axis: rod Origin point ON gear Axis3 lobe line.
    added = 0
    for i, (_name, gear, rod) in enumerate(cams):
        try:
            res = await coincident_mate(
                adapter,
                component_named_ref(rod, "Origin", "POINT"),
                component_named_ref(gear, "Axis3", "AXIS"),
                label=f"ch{i:02d} cam point-on-axis")
            ok = bool(res.get("name"))
            added += 1 if ok else 0
            if i < 2 or not ok:
                log(f"    ch{i:02d} {rod} Origin -> {gear} Axis3 : "
                    f"{'OK' if ok else 'FAIL ' + str(res)}")
        except Exception as exc:  # noqa: BLE001
            log(f"    ch{i:02d} point-on-axis FAILED: {exc}")
    log(f"  re-added {added}/{len(cams)} point-on-axis cams")
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    log("  one-time walk to cache crank + cone-shaft + cyl-gear ...")
    comps = _components(adapter)
    cached = {
        "crank": _find_one(adapter, "crankshaft-1", comps=comps)[0],
        "coneshaft": _find_one(adapter, "cone-gear-shaft-1", comps=comps)[0],
        "cylgear0": _find_one(adapter, "cylinder-gear-1", comps=comps)[0],
    }

    for run in range(1, 4):
        spans = await _recalc_span(adapter, doc, cached, f"run{run}")
        log(f"  run{run}: coneshaft={spans.get('coneshaft', 0.0):6.1f}  "
            f"cylgear0={spans.get('cylgear0', 0.0):6.1f}  "
            f"crank={spans.get('crank', 0.0):6.1f}")

    log("  all 3 runs coneshaft>0 => point-on-axis solves RELIABLY (the fix); "
        "still erratic/0 => need a different de-redundancy.")

    await adapter.disconnect()
    _telemetry.info("Disconnected (cams now point-on-axis, doc NOT saved).")


if __name__ == "__main__":
    asyncio.run(main())
