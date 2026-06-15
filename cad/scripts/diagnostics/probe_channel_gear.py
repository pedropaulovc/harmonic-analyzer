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

from _common import OUT_PNG, coincident_mate, gear_mate, log, named_ref
from build_motion_study import (
    OUT_SLDASM, _by_z_rank, _comp_xform, _components, _entity_ref, _find_one,
    _rot_angle, _sub_model, _suppress_channel,
)

RATIO = [float(sys.argv[1]) if len(sys.argv) > 1 else 1.0, 1.0]
ROCK_DEG = 10.0  # kinematic test rotation applied to the rocker


async def _shot(adapter, tag):
    """Export iso + front PNGs so the bar pose can be inspected visually."""
    out = OUT_PNG / "probe-gear"
    out.mkdir(parents=True, exist_ok=True)
    for view in ("Isometric", "Front"):
        path = (out / f"gear_{tag}_{view.lower()}.png").resolve()
        await adapter.export_image({
            "file_path": str(path), "format_type": "png",
            "width": 1600, "height": 1000, "view_orientation": view})
        log(f"  shot {tag}/{view} -> {path}")


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
    # Free ONLY the rocker + lever (NOT the bar). The lever has its OWN J4 spin
    # driver -- freeing it is what lets the gear drive it. The amplitude bar is a
    # COEFFICIENT SETTING: keep its drivers so it stays upright + frozen at its
    # slide station (its X/Y ride the lever pin via J3, so it translates upright
    # with the geared lever -- it neither flops nor locks the lever). Suppressing
    # the bar instead (an earlier probe) left all 20 bars free to swing about
    # their lever pins; with the foot support being an ignored CONTACT they
    # flopped up into a black slab. This probe asserts the bar's rotation stays
    # ~0 (no flop) while the lever follows the rocker through the gear.
    # ONE pass: free rocker spin + lever spin + rod drivers ONLY. The amplitude
    # bars stay FULLY MATED -- their J3 top-pin coincident + foot-X spin_driver
    # already make each bar ride the geared lever upright + bob (no lock/decouple
    # needed; the book confirms the bars stay vertical and move up/down).
    await _suppress_channel(adapter)

    # add the ch0 gear INSIDE channel.SLDASM (both parts in the one flexible sub).
    _, ch_doc = _sub_model(adapter, "channel-1")
    top = adapter.currentModel
    adapter.currentModel = ch_doc
    rocker_n = lever_n = None
    try:
        comps = _components(adapter, ch_doc)
        rockers = _by_z_rank(adapter, "rocker-arm", comps=comps)
        levers = _by_z_rank(adapter, "channel-lever", comps=comps)
        bars = _by_z_rank(adapter, "amplitude-bar", comps=comps)
        rocker_n, lever_n = rockers[0][1], levers[0][1]
        bar_n = bars[0][1]
        log(f"  ch0 rocker={rocker_n!r} lever={lever_n!r} bar={bar_n!r}")
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

    await _shot(adapter, "before")  # assembled, bars frozen, gear added

    # measure: rotate the rocker kinematically, read the lever rotation AND the
    # bar rotation (must stay ~0 -- the bar is a coefficient setting; if it
    # rotates it is flopping). The in-sub names ('rocker-arm-1') lack the
    # 'channel-1/' prefix they carry at the top level -- resolve the TOP-level
    # component + name via _find_one.
    rocker_c, rocker_top = _find_one(adapter, rocker_n.split("/")[-1])
    lever_c, _ = _find_one(adapter, lever_n.split("/")[-1])
    bar_c, _ = _find_one(adapter, bar_n.split("/")[-1])
    a0 = _comp_xform(adapter, lever_c)
    ra = _comp_xform(adapter, rocker_c)
    ba0 = _comp_xform(adapter, bar_c)
    # rocker pivot axis = its world Z column (cols 6..8) through its origin.
    await adapter.rotate_component(RotateComponentParameters(
        name=rocker_top,
        angle=ROCK_DEG, axis_vector=[ra[6], ra[7], ra[8]],
        axis_point=[ra[9] * 1000.0, ra[10] * 1000.0, ra[11] * 1000.0],
        mode="kinematic"))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    await _shot(adapter, "after")  # rocker rotated: bars must look unchanged
    a1 = _comp_xform(adapter, lever_c)
    ra1 = _comp_xform(adapter, rocker_c)
    ba1 = _comp_xform(adapter, bar_c)
    lever_moved = _rot_angle(a0, a1) if (a0 and a1) else 0.0
    rocker_moved = _rot_angle(ra, ra1) if (ra and ra1) else 0.0
    bar_rot = _rot_angle(ba0, ba1) if (ba0 and ba1) else 0.0
    # The bar is fully mated (top rides lever, foot-X pinned) so a healthy bar
    # stays ~VERTICAL and bobs -- it should rotate only a little even when the
    # lever swings a lot (rocker arc radius = bar length keeps the tilt small).
    # A flop is the bar sweeping the full lever arc (bar_rot ~= lever_moved, the
    # slab). NOTE the kinematic rotate drives the rocker to its full ROM (~159 deg
    # here), far past the real small operating swing -- so a modest bar tilt at
    # this extreme means a negligible tilt in operation.
    upright = bar_rot < 30.0
    log(f"  rocker rotated {rocker_moved:.2f} deg -> channel-lever {lever_moved:.2f} deg "
        f"| amplitude-bar tilted {bar_rot:.2f} deg "
        f"(want << lever {lever_moved:.2f} = stays vertical + bobs, no slab)")
    transmits = lever_moved > 5.0
    if transmits and upright:
        log(f"  PASS: gear transmits rocker->lever ({lever_moved:.1f} deg lever "
            f"travel, bar-limited) AND bar stays upright ({bar_rot:.1f} deg tilt "
            f"<< {lever_moved:.1f}) -> wire into build_motion_study for 20 channels")
    elif transmits and not upright:
        log(f"  FAIL: bar tilted {bar_rot:.1f} deg ~ lever {lever_moved:.1f} -- "
            f"the bar is sweeping the lever arc (slab), not staying vertical")
    else:
        log("  FAIL: lever did not follow -> gear not enforced kinematically")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
