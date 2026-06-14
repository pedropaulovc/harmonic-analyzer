r"""Fast KINEMATIC probe: can a gear mate transmit rocker -> channel-lever?

The F6 springs diagnostic proved the rocker oscillates (cam chain works) but the
channel-lever stays frozen at 0.00 deg every timestep -- the rocker->amplitude-
bar->channel-lever link is the bar-foot-on-rocker-arc CONTACT, which Basic Motion
ignores. The spring summation (proven viable by poc_spring_adder.py) therefore
never gets a moving anchor.

Fix candidate: replace the dead contact with a GEAR mate rocker(Axis1) <->
channel-lever(Axis1) (parallel Z axes), authored INSIDE channel.SLDASM (both
parts share the one flexible sub, so a top-level mate is rejected -- same as the
rod<->rocker revolute). The bar's foot spin driver (a foot-bore->plane DISTANCE,
i.e. pinned to ground) is suppressed so the lever is free for the gear to drive;
the bar stays attached to the lever via J3 and is dragged along (no force on it
=> it cannot flop).

This probe avoids the ~38 min motion solve: flex ONLY channel-1, suppress the
ch0 rocker spin + ch0 bar foot drivers, add the ch0 gear, then ROTATE the rocker
kinematically (rotate_component mode=kinematic, which propagates through mates)
and measure the channel-lever's rotation. Lever span > 0 => the gear transmits
=> wire it into build_motion_study for all 20 channels. NEVER saves.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_channel_gear.py [ratio_num]
"""

from __future__ import annotations

import asyncio
import math
import sys

from _common import coincident_mate, gear_mate, log, named_ref
from build_motion_study import (
    OUT_SLDASM, _by_z_rank, _comp_xform, _components, _entity_ref, _find_one,
    _rot_angle, _sub_model, _suppress_recurring,
)

RATIO = [float(sys.argv[1]) if len(sys.argv) > 1 else 1.0, 1.0]
ROCK_DEG = 10.0  # kinematic test rotation applied to the rocker


async def _flex_channel(adapter):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    asm = adapter.currentModel
    sub = "channel-1"
    await adapter.float_component(ComponentRefParameters(name=sub))
    for plane in ("Front Plane", "Top Plane", "Right Plane"):
        await coincident_mate(
            adapter, named_ref(f"{plane}@{sub}", "PLANE"),
            named_ref(plane, "PLANE"), label=f"ground {sub} {plane}")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    log(f"  set {sub} FLEXIBLE (blocking solve) ...")
    await adapter.set_component_solving(
        SetComponentSolvingParameters(name=sub, solving="flexible"))
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)


async def main():
    from solidworks_mcp.adapters.base import RotateComponentParameters
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print(f"Connecting ... (ratio={RATIO})", flush=True)
    await adapter.connect()
    # Close any docs left open in the session: a prior run's motion study lingers
    # in the in-memory doc and triggers the blocking "Update Initial Animation
    # State" modal on suppress/rotate (and no-ops the rotate). CloseAllDocuments
    # (True = discard unsaved) gives a fresh disk load -- artifact A is never
    # saved, so nothing is lost.
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    asm_path = str((OUT_SLDASM / "harmonic-analyzer.SLDASM").resolve())
    await adapter.open_model(asm_path)
    log(f"opened {asm_path}")

    await _flex_channel(adapter)
    # Free the WHOLE rocker->bar->lever chain: suppress the recurring pose/spin
    # drivers of all three families (the lever has its OWN J4 bar-pin spin driver
    # -- missing that is why the first gear test left the lever locked). Recurring
    # = the uniform default pose/spin; per-channel axial-Z holds are KEPT so the
    # parts stay at their stations.
    await _suppress_recurring(
        adapter, "channel-1", ("rocker-arm", "amplitude-bar", "channel-lever"),
        "free rocker/bar/lever chain")

    # add the ch0 gear INSIDE channel.SLDASM (both parts in the one flexible sub).
    _, ch_doc = _sub_model(adapter, "channel-1")
    top = adapter.currentModel
    adapter.currentModel = ch_doc
    rocker_n = lever_n = None
    try:
        comps = _components(adapter, ch_doc)
        rockers = _by_z_rank(adapter, "rocker-arm", comps=comps)
        levers = _by_z_rank(adapter, "channel-lever", comps=comps)
        rocker_n, lever_n = rockers[0][1], levers[0][1]
        log(f"  ch0 rocker={rocker_n!r} lever={lever_n!r}")
        for alignment in ("aligned", "anti_aligned"):
            try:
                g = await gear_mate(
                    adapter, _entity_ref(rocker_n, "Axis1", "AXIS"),
                    _entity_ref(lever_n, "Axis1", "AXIS"),
                    RATIO, alignment=alignment, label="ch0 rocker->lever gear")
                if g.get("name"):
                    log(f"  gear OK: {g['name']} (alignment={alignment})")
                    break
            except Exception as exc:  # noqa: BLE001
                log(f"    gear alignment={alignment} rejected: {exc}")
        adapter._attempt(lambda: ch_doc.ForceRebuild3(False), default=None)
    finally:
        adapter.currentModel = top

    # measure: rotate the rocker kinematically, read the lever rotation. The
    # in-sub names ('rocker-arm-1') lack the 'channel-1/' prefix they carry at
    # the top level -- resolve the TOP-level component + name via _find_one.
    rocker_c, rocker_top = _find_one(adapter, rocker_n.split("/")[-1])
    lever_c, _ = _find_one(adapter, lever_n.split("/")[-1])
    a0 = _comp_xform(adapter, lever_c)
    ra = _comp_xform(adapter, rocker_c)
    # rocker pivot axis = its world Z column (cols 6..8) through its origin.
    await adapter.rotate_component(RotateComponentParameters(
        name=rocker_top,
        angle=ROCK_DEG, axis_vector=[ra[6], ra[7], ra[8]],
        axis_point=[ra[9] * 1000.0, ra[10] * 1000.0, ra[11] * 1000.0],
        mode="kinematic"))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    a1 = _comp_xform(adapter, lever_c)
    ra1 = _comp_xform(adapter, rocker_c)
    lever_moved = _rot_angle(a0, a1) if (a0 and a1) else 0.0
    rocker_moved = _rot_angle(ra, ra1) if (ra and ra1) else 0.0
    log(f"  rocker rotated {rocker_moved:.2f} deg -> channel-lever {lever_moved:.2f} deg")
    if lever_moved > 0.3:
        log(f"  PASS: gear transmits rocker->lever (ratio {lever_moved/rocker_moved:.3f} "
            f"effective) -> wire into build_motion_study for all 20 channels")
    else:
        log("  FAIL: lever did not follow -> gear not enforced kinematically; "
            "try four-bar foot-pin instead")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
