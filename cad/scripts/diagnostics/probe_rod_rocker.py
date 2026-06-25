r"""Throwaway: attach to the LIVE prepped harmonic-analyzer (flexed + suppressed
+ 20 cam mates already added by a stopped build_motion_study kinematic run) and
diagnose why ch00 rod-pin <-> rocker-bore (Axis2@connecting-rod-1 <->
Axis2@rocker-arm-1) coincident returns AddMate5 status 0 (ErrorUknown) while the
cam mate (Axis1@rod <-> Axis3@gear) succeeds.

No 11-min prefix: stopping the python process leaves the SW doc open with all
flex/suppress/cam-mate state intact, so we attach to ActiveDoc.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_rod_rocker.py
"""

from __future__ import annotations

import asyncio
import math

import _telemetry
from _common import _flag, _read_member, log

# part-local bore locals (mm) from build_channel_assembly.py
ROD_PIN_BORE_LOCAL = [0.0, 127.0, 0.0]      # rod Axis2 (rocker pin)
ROD_RING_BORE_LOCAL = [0.0, 0.0, 0.0]       # rod Axis1 (cam ring centre)
ROCKER_ROD_BORE_LOCAL = [25.4, 8.39937, 0.0]  # rocker Axis2 (rod pin)


def _xform(adapter, comp):
    t = _read_member(comp, "Transform2")
    return [float(v) for v in _read_member(t, "ArrayData")]


def _world(a, local_mm):
    r, t = a[0:9], a[9:12]
    return [sum(local_mm[i] * r[i * 3 + k] for i in range(3)) + t[k] * 1000.0
            for k in range(3)]


def _zdir(a):
    """World direction of the part-local +Z (the pin axes are local Z)."""
    r = a[0:9]
    return [r[2 * 3 + k] for k in range(3)]  # third local basis vector


def _find(adapter, doc, needle):
    for c in (adapter._attempt(lambda: doc.GetComponents(False), default=None) or []):
        _flag(c, "IComponent2")
        if needle in str(_read_member(c, "Name2")):
            return c, str(_read_member(c, "Name2"))
    return None, None


def _axis_params(adapter, comp, feat_name):
    """part-local axis endpoints via the mapped IFeature -> IRefAxis."""
    from solidworks_mcp.adapters.solidworks.assembly import _component_named_feature
    nm = str(_read_member(comp, "Name2"))
    # component path is sub/part already (Name2)
    mapped = _component_named_feature(adapter, nm, feat_name)
    if mapped is None:
        return None, "GetCorresponding -> None"
    ok = adapter._attempt(lambda: mapped.Select2(False, 0), default=None)
    return mapped, f"select2={ok}"


async def _try_mate(adapter, kind, ref_a, ref_b, alignment):
    from solidworks_mcp.adapters.base import AddMateParameters
    res = await adapter.add_mate(AddMateParameters(
        mate_type=kind, entities=[ref_a, ref_b], alignment=alignment))
    tag = "OK" if res.is_success else "FAIL"
    log(f"    {kind:11s} align={alignment:12s} -> {tag} "
        f"{'' if res.is_success else res.error}")
    if res.is_success:
        # remove it again so we can keep probing variants
        nm = res.data.get("name")
        if nm:
            from solidworks_mcp.adapters.base import DeleteMateParameters
            await adapter.delete_mate(DeleteMateParameters(name=nm))
    return res.is_success


async def main():
    from solidworks_mcp.adapters.base import MateEntityRef
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc -- the prepped doc must stay open")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    rod, rod_n = _find(adapter, doc, "channel-1/connecting-rod-1")
    rk, rk_n = _find(adapter, doc, "channel-1/rocker-arm-1")
    log(f"rod={rod_n!r} rocker={rk_n!r}")
    if rod is None or rk is None:
        log("missing components -- abort")
        await adapter.disconnect()
        return

    # --- geometry: where are the two bores + axis directions, post cam-solve ---
    ra, ka = _xform(adapter, rod), _xform(adapter, rk)
    rod_pin = _world(ra, ROD_PIN_BORE_LOCAL)
    rod_ring = _world(ra, ROD_RING_BORE_LOCAL)
    rk_bore = _world(ka, ROCKER_ROD_BORE_LOCAL)
    gap = math.dist(rod_pin, rk_bore)
    rzd, kzd = _zdir(ra), _zdir(ka)
    dot = sum(rzd[i] * kzd[i] for i in range(3))
    log(f"  rod ring  world = ({rod_ring[0]:.2f},{rod_ring[1]:.2f},{rod_ring[2]:.2f})")
    log(f"  rod pin   world = ({rod_pin[0]:.2f},{rod_pin[1]:.2f},{rod_pin[2]:.2f})")
    log(f"  rocker bore world = ({rk_bore[0]:.2f},{rk_bore[1]:.2f},{rk_bore[2]:.2f})")
    log(f"  pin<->bore gap = {gap:.3f} mm   axis-dir dot = {dot:+.4f} "
        f"(+1 parallel, -1 anti)")

    # --- selection sanity: do both Axis2 map + select? ---
    log("  --- axis selection ---")
    _, sa = _axis_params(adapter, rod, "Axis2")
    log(f"    Axis2@rod  {sa}")
    _, sb = _axis_params(adapter, rk, "Axis2")
    log(f"    Axis2@rocker {sb}")
    adapter._attempt(lambda: doc.ClearSelection2(True))

    # --- mate variants (each captures the AddMate5 status via result.error) ---
    rod2 = MateEntityRef(entity_type="AXIS", component="channel-1/connecting-rod-1", name="Axis2")
    rk2 = MateEntityRef(entity_type="AXIS", component="channel-1/rocker-arm-1", name="Axis2")
    log("  --- mate variants Axis2@rod <-> Axis2@rocker ---")
    for align in ("closest", "aligned", "anti_aligned"):
        await _try_mate(adapter, "coincident", rod2, rk2, align)
    await _try_mate(adapter, "concentric", rod2, rk2, "closest")
    await _try_mate(adapter, "distance", rod2, rk2, "closest")

    await adapter.disconnect()
    _telemetry.info("Disconnected (doc left open).")


if __name__ == "__main__":
    asyncio.run(main())
