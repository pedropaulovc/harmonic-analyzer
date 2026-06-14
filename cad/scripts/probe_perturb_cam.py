r"""Throwaway: does PERTURBING the gear off the design pose let the point-on-axis
cam ADD without "over-defines"?

Two rival diagnoses for the build's 0/20 cam failure:
  (A) the in-sub rod<->rocker revolute makes the cam redundant (order problem);
  (B) at the EXACT design pose the rod ring point lies ON the eccentric lobe
      Axis3 -> degenerate zero-distance mate -> AddMate5 rejects. refpoint_fix
      added 20/20 only because its doc was in a DISPLACED post-motion pose.

The open doc HAS the 20 in-sub revolutes and rods at design pose. If spinning a
gear about its own axis (orbiting the eccentric lobe off the stationary rod ring)
lets the cam ADD -- WITH the revolute still present -- diagnosis (B) is confirmed
and the build fix is: perturb the gears, add cams, rebuild (snaps back), reset,
calc. A CONTROL channel (not perturbed) should still FAIL.

NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_perturb_cam.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, check, coincident_mate, log
from build_motion_study import (
    _add_ring_centre_point, _by_z_rank, _comp_xform, _components, _entity_ref,
    _iter_mates,
)


async def _try_cam(adapter, rod_n, gear_n, point_name, tag):
    try:
        res = await coincident_mate(
            adapter, _entity_ref(rod_n, point_name, "POINT"),
            _entity_ref(gear_n, "Axis3", "AXIS"), label=tag)
        ok = bool(res.get("name"))
        log(f"    {tag}: {'OK ' + str(res.get('name')) if ok else 'no-name ' + str(res)}")
        return ok
    except Exception as exc:  # noqa: BLE001
        log(f"    {tag}: FAILED {exc}")
        return False


async def main():
    from solidworks_mcp.adapters.base import (
        MateRefParameters, RotateComponentParameters, SuppressMateParameters,
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

    # clear any leftover cam mates.
    for _s, _m, name, _t, parts, _v in _iter_mates(adapter, doc, read_values=False):
        j = " ".join(parts)
        if "cylinder-gear" in j and "connecting-rod" in j:
            await adapter.suppress_mate(SuppressMateParameters(name=name, suppress=False))
            await adapter.delete_mate(MateRefParameters(name=name))

    point_name = await _add_ring_centre_point(adapter)

    comps = _components(adapter)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
    n = min(len(gears), len(rods))
    log(f"  {len(gears)} gears, {len(rods)} rods -> {n} channels")

    # CONTROL: channel 0, no perturbation (expect FAIL if diagnosis B).
    log("  --- control (no perturbation) ---")
    ctrl = await _try_cam(adapter, rods[0][1], gears[0][1], point_name, "ch00 control")

    # PERTURBED: channels 1..3, spin gear about its own world axis ~20 deg.
    log("  --- perturbed (spin gear about own axis) ---")
    perturbed = 0
    for i in (1, 2, 3):
        gear_comp, gear_n = gears[i]
        a = _comp_xform(adapter, gear_comp)
        axis_vec = [a[6], a[7], a[8]]           # local Z -> world (spin axis)
        axis_pt = [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]
        check(f"spin {gear_n}", await adapter.rotate_component(RotateComponentParameters(
            name=gear_n, angle=20.0, axis_vector=axis_vec, axis_point=axis_pt, mode="exact")))
        ok = await _try_cam(adapter, rods[i][1], gear_n, point_name, f"ch{i:02d} perturbed")
        perturbed += 1 if ok else 0

    log(f"  control={'OK' if ctrl else 'FAIL'}  perturbed={perturbed}/3")
    log("  control FAIL + perturbed 3/3 => diagnosis B (degeneracy); perturb in build.")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
