r"""Throwaway: the REAL de-redundancy fix. Add a mateable ring-centre reference
POINT to the shared connecting-rod part doc (in memory, NEVER saved -- all 20
instances inherit it via GetCorresponding), then add 20 point-on-axis cam mates
(rod ring point ON gear lobe Axis3) and check the solve is reliably mobile.

The collinear-axes cam over-constrained orientation (the rod<->rocker pin already
fixes it) -> erratic Basic Motion solves. point-on-axis = 2 constraints, no
orientation -> non-redundant. The "Origin" feature is NOT mateable; a real
RefPoint (arc_center on the Ø51 bore edge -> ring centre = origin) is.

NEVER saves (neither the part nor the assembly).

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_refpoint_fix.py
"""

from __future__ import annotations

import asyncio

from _common import (
    _flag, _read_member, check, coincident_mate, component_named_ref, log,
)
from build_motion_study import (
    _by_z_rank, _comp_xform, _components, _find_one, _iter_mates, _rot_angle, _sub_model,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

TIMES = [0.0, 0.375, 0.75, 1.125, 1.5]
STUDY = "Motion Study 2"
BORE_EDGE_MM = [25.5, 0.0, 1.5]  # a point on the Ø51 bore circular edge (ring face +1.5)


async def _recalc_span(adapter, doc, cached, tag):
    from solidworks_mcp.adapters.base import (
        MotionStudyRefParameters, MotionTimeParameters,
    )
    check(f"calc {tag}", await adapter.calculate_motion(
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
    from solidworks_mcp.adapters.base import (
        CreateReferencePointParameters, MateRefParameters, SuppressMateParameters,
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
    top = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    # 1) ring-centre RefPoint on the shared rod part doc (in memory).
    rod_comp, _ = _find_one(adapter, "connecting-rod-1", toplevel=False)
    part = adapter._attempt(lambda: rod_comp.GetModelDoc2(), default=None)
    if part is None:
        log("  could not resolve connecting-rod part doc")
        return
    part_title = str(_read_member(part, "GetTitle"))
    top_title = str(_read_member(top, "GetTitle"))
    log(f"  rod part doc = {part_title!r}")
    # selection in a component's part doc needs that doc ACTIVE.
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    pt = check("create ring-centre RefPoint", await adapter.create_reference_point(
        CreateReferencePointParameters(mode="arc_center", edge_point=BORE_EDGE_MM)))
    point_name = pt.get("name") if isinstance(pt, dict) else getattr(pt, "name", None)
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = top
    log(f"  ring-centre point feature = {point_name!r}")
    if not point_name:
        log("  no point name -> abort")
        return

    # 2) delete any leftover cam mates, then re-pair by z-rank.
    log("  walking top-level mates to clear any leftover cams ...")
    for _s, _m, name, _t, parts, _v in _iter_mates(adapter, doc, read_values=False):
        joined = " ".join(parts)
        if "cylinder-gear" in joined and "connecting-rod" in joined:
            await adapter.suppress_mate(SuppressMateParameters(name=name, suppress=False))
            await adapter.delete_mate(MateRefParameters(name=name))

    log("  one-time walk to pair gears<->rods + cache sample targets ...")
    comps = _components(adapter)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
    n = min(len(gears), len(rods))
    cached = {
        "crank": _find_one(adapter, "crankshaft-1", comps=comps)[0],
        "coneshaft": _find_one(adapter, "cone-gear-shaft-1", comps=comps)[0],
        "cylgear0": gears[0][0] if gears else None,
    }

    added = 0
    for i in range(n):
        gear_n, rod_n = gears[i][1], rods[i][1]
        try:
            res = await coincident_mate(
                adapter,
                component_named_ref(rod_n, point_name, "POINT"),
                component_named_ref(gear_n, "Axis3", "AXIS"),
                label=f"ch{i:02d} cam point-on-axis")
            ok = bool(res.get("name"))
            added += 1 if ok else 0
            if i < 2 or not ok:
                log(f"    ch{i:02d} {rod_n}/{point_name} -> {gear_n}/Axis3 : "
                    f"{'OK' if ok else 'FAIL ' + str(res)}")
        except Exception as exc:  # noqa: BLE001
            log(f"    ch{i:02d} FAILED: {exc}")
    log(f"  added {added}/{n} point-on-axis cams")
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)

    for run in range(1, 4):
        spans = await _recalc_span(adapter, doc, cached, f"run{run}")
        log(f"  run{run}: coneshaft={spans.get('coneshaft', 0.0):6.1f}  "
            f"cylgear0={spans.get('cylgear0', 0.0):6.1f}  "
            f"crank={spans.get('crank', 0.0):6.1f}")

    log("  all 3 runs coneshaft>0 (consistent) => point-on-axis is the fix.")

    await adapter.disconnect()
    print("Disconnected (doc NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
