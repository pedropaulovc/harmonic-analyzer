r"""Throwaway, MODEL-TAB experiment: does the per-channel four-bar loop actually
close, and which mate formulation closes it?

Earlier diagnosis ("rigid 127 mm rod can't span the 127.4 mm cam->rocker gap, so
the loop is geometrically impossible") is WRONG -- the circle-intersection test
holds (|127-120.92|=6.08 <= centre-dist 178.6 <= 127+120.92=247.9), so an
assembled config exists 0.19 deg of rocker rotation away from the snapshot pose.
So AddMate5 status 0 must be a solver / mate-formulation / active-tab artefact,
not an impossibility. The prior probe ran with the MOTION STUDY tab active, which
can block mate edits; this one NEVER creates a motion study, so the model tab
stays active.

Cheapest isolation: flex ONLY channel-1 (one ~180 s solve) and leave drive-train
RIGID, so the cam lobe is a FIXED point -- the pure "can the rod pin reach the
rocker bore" question, no gear-train DOF in the loop. Decision tree:

  * pin<->bore (cam absent)  must succeed (rod+rocker both free) -- sanity.
  * cam ring<->lobe          must succeed (rod free, first constraint) -- sanity.
  * pin<->bore (cam present) is the real failing case. Try coincident (all 3
    alignments), concentric, then dump GetWhatsWrong. Whichever returns status 1
    is the fix to fold back into _add_cam_couplings.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_loop_close.py
"""

from __future__ import annotations

import asyncio
import math

from _common import OUT_SLDASM, _flag, _read_member, check, log
from build_motion_study import (
    ASM, _by_z_rank, _comp_xform, _components, _entity_ref, _find_one,
    _suppress_named, _suppress_recurring, _world,
)

ROD_RING_LOCAL = [0.0, 0.0, 0.0]        # rod Axis1 (cam ring centre)
ROD_PIN_LOCAL = [0.0, 127.0, 0.0]       # rod Axis2 (rocker pin)
ROCKER_BORE_LOCAL = [25.4, 8.39937, 0.0]  # rocker Axis2 (rod pin)

ANGLE, DISTANCE = 6, 5


async def _flex_channel(adapter):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    from _common import coincident_mate, named_ref
    asm = adapter.currentModel
    sub = "channel-1"
    check(f"float {sub}", await adapter.float_component(ComponentRefParameters(name=sub)))
    for plane in ("Front Plane", "Top Plane", "Right Plane"):
        await coincident_mate(
            adapter, named_ref(f"{plane}@{sub}", "PLANE"),
            named_ref(plane, "PLANE"), label=f"ground {sub} {plane}")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    log(f"  set {sub} FLEXIBLE -- blocking solve, expect ~180 s ...")
    check(f"flexible {sub}", await adapter.set_component_solving(
        SetComponentSolvingParameters(name=sub, solving="flexible")))
    comp, _ = _find_one(adapter, sub, toplevel=True)
    solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
    log(f"  {sub} Solving={solving} (1=flexible)")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)


def _positions(adapter, rod, rk, tag):
    ra, ka = _comp_xform(adapter, rod), _comp_xform(adapter, rk)
    ring = _world(ra, ROD_RING_LOCAL)
    pin = _world(ra, ROD_PIN_LOCAL)
    bore = _world(ka, ROCKER_BORE_LOCAL)
    gap = math.dist(pin, bore)
    log(f"  [{tag}] ring=({ring[0]:.2f},{ring[1]:.2f},{ring[2]:.2f}) "
        f"pin=({pin[0]:.2f},{pin[1]:.2f},{pin[2]:.2f}) "
        f"bore=({bore[0]:.2f},{bore[1]:.2f},{bore[2]:.2f}) gap={gap:.3f}mm")


async def _raw_mate(adapter, kind, ref_a, ref_b, alignment="closest"):
    """Add a mate directly (no verify/flip); return (ok, name, err)."""
    from solidworks_mcp.adapters.base import AddMateParameters
    res = await adapter.add_mate(AddMateParameters(
        mate_type=kind, entities=[ref_a, ref_b], alignment=alignment))
    if res.is_success:
        return True, res.data.get("name"), None
    return False, None, res.error


async def _del(adapter, name):
    if not name:
        return
    from solidworks_mcp.adapters.base import MateRefParameters
    await adapter.delete_mate(MateRefParameters(name=name))


def _whats_wrong(adapter):
    model = adapter.currentModel
    errs = adapter._attempt(lambda: model.GetWhatsWrong(), default=None)
    if not errs:
        log("  GetWhatsWrong: (none)")
        return
    try:
        for e in errs:
            log(f"  GetWhatsWrong: {e}")
    except TypeError:
        log(f"  GetWhatsWrong: {errs}")


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    log("CloseAllDocuments (clean session)")

    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open", await adapter.open_model(asm_path))
    log(f"opened {asm_path}  (drive-train left RIGID -> cam lobe is a fixed point)")

    await _flex_channel(adapter)

    # free the rod + rocker inside channel-1 (same suppress the build does)
    await _suppress_recurring(
        adapter, "channel-1", ("rocker-arm",), "rocker spin drivers")
    await _suppress_named(
        adapter, "channel-1", ("connecting-rod",), (DISTANCE, ANGLE),
        "rod drivers (free the rod fully)")

    # ch00 trio by Z-rank (same station)
    comps = _components(adapter)
    gear, gear_n = _by_z_rank(adapter, "cylinder-gear", comps=comps)[0]
    rod, rod_n = _by_z_rank(adapter, "connecting-rod", comps=comps)[0]
    rk, rk_n = _by_z_rank(adapter, "rocker-arm", comps=comps)[0]
    log(f"  ch00: gear={gear_n!r} rod={rod_n!r} rocker={rk_n!r}")
    _positions(adapter, rod, rk, "start")

    ring_ref = _entity_ref(rod_n, "Axis1", "AXIS")
    pin_ref = _entity_ref(rod_n, "Axis2", "AXIS")
    lobe_ref = _entity_ref(gear_n, "Axis3", "AXIS")
    bore_ref = _entity_ref(rk_n, "Axis2", "AXIS")

    # --- Test A: pin<->bore STANDALONE (no cam) -- must succeed -------------
    log("=== Test A: coincident pin<->bore, NO cam (rod+rocker free) ===")
    ok, nm, err = await _raw_mate(adapter, "coincident", pin_ref, bore_ref)
    log(f"  A coincident pin<->bore -> {'OK' if ok else 'FAIL ' + str(err)}")
    if ok:
        _positions(adapter, rod, rk, "after A")
    await _del(adapter, nm)
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)

    # --- Test B: cam first, then pin<->bore (the real loop) ----------------
    log("=== Test B: cam ring<->lobe, THEN pin<->bore ===")
    ok, cam_nm, err = await _raw_mate(adapter, "coincident", ring_ref, lobe_ref)
    log(f"  B cam ring<->lobe -> {'OK' if ok else 'FAIL ' + str(err)}")
    if ok:
        _positions(adapter, rod, rk, "after cam")

    for align in ("closest", "aligned", "anti_aligned"):
        ok, nm, err = await _raw_mate(adapter, "coincident", pin_ref, bore_ref, align)
        log(f"  B coincident pin<->bore align={align:12s} -> "
            f"{'OK' if ok else 'FAIL ' + str(err)}")
        if ok:
            _positions(adapter, rod, rk, f"after pin coincident/{align}")
            await _del(adapter, nm)
            adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
        else:
            _whats_wrong(adapter)

    for align in ("closest", "aligned", "anti_aligned"):
        ok, nm, err = await _raw_mate(adapter, "concentric", pin_ref, bore_ref, align)
        log(f"  B concentric pin<->bore align={align:12s} -> "
            f"{'OK' if ok else 'FAIL ' + str(err)}")
        if ok:
            _positions(adapter, rod, rk, f"after pin concentric/{align}")
            await _del(adapter, nm)
            adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)

    await adapter.disconnect()
    print("Disconnected (doc left open).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
