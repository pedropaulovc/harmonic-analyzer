r"""Fast KINEMATIC probe: does the foot-arc four-bar transmit rocker -> lever?

The F6 model is the REAL linkage (no gear): the amplitude bar is a swinging
coupler whose foot is pinned to the rocker's R800 arc (two in-sub DISTANCE mates
from bar Axis2 -- to the arc-centre RefPoint = R, and to the pivot axis =
r_foot) and whose top swings on the channel-lever pin (the artifact-A J3
coincident, kept). As the rocker seesaws, the foot orbits with it, the rigid bar
pushes the lever pin, the lever rotates -- a clean 1-DOF four-bar. The bar SWINGS
as a coupler (user-confirmed from book ch.17: the bars are not rigid with the
lever).

This probe avoids the heavy motion solve: flex ONLY channel-1, run the single-
pass suppress (frees rocker spin + lever spin + bar foot-X + rod), add the ch0
arc-centre point + the ch0 foot-arc pair, then ROTATE the rocker kinematically
(rotate_component mode=kinematic propagates through mates) and measure the lever
rotation (must follow -> transmits) and the bar rotation (must be bounded ->
swings as a coupler, does not flop into a slab). NEVER saves.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_foot_arc.py
"""

from __future__ import annotations

import asyncio

from _common import OUT_PNG, coincident_mate, distance_driver, log, named_ref
from build_motion_study import (
    BAR_FOOT_LOCAL, OUT_SLDASM, ROCKER_ARC_CENTER_LOCAL, ROCKER_PIVOT_LOCAL,
    _add_rocker_arc_point, _by_z_rank, _comp_xform, _components, _entity_ref,
    _find_one, _rot_angle, _suppress_channel, _sub_model, _world, _xy_dist,
)

ROCK_DEG = 10.0  # kinematic test rotation applied to the rocker


async def _shot(adapter, tag):
    out = OUT_PNG / "probe-foot-arc"
    out.mkdir(parents=True, exist_ok=True)
    for view in ("Isometric", "Front"):
        path = (out / f"foot_{tag}_{view.lower()}.png").resolve()
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


async def _add_ch0_foot_arc(adapter, point_name):
    """Add ONLY ch0's foot-arc pair (fast probe; the full build does all 20)."""
    _, ch_doc = _sub_model(adapter, "channel-1")
    top = adapter.currentModel
    adapter.currentModel = ch_doc
    rk_n = bar_n = None
    try:
        comps = _components(adapter, ch_doc)
        rk_c, rk_n = _by_z_rank(adapter, "rocker-arm", comps=comps)[0]
        bar_c, bar_n = _by_z_rank(adapter, "amplitude-bar", comps=comps)[0]
        ra, ba = _comp_xform(adapter, rk_c), _comp_xform(adapter, bar_c)
        arc_c = _world(ra, ROCKER_ARC_CENTER_LOCAL)
        pivot = _world(ra, ROCKER_PIVOT_LOCAL)
        foot = _world(ba, BAR_FOOT_LOCAL)
        d_arc, d_pivot = _xy_dist(foot, arc_c), _xy_dist(foot, pivot)
        log(f"  ch0 rocker={rk_n!r} bar={bar_n!r} R={d_arc:.2f} r_foot={d_pivot:.2f}")
        a = await distance_driver(
            adapter, _entity_ref(rk_n, point_name, "POINT"),
            _entity_ref(bar_n, "Axis2", "AXIS"), d_arc, label="ch0 foot on R800 arc")
        log(f"    arc dist mate: {a.get('name')!r}")
        p = await distance_driver(
            adapter, _entity_ref(rk_n, "Axis1", "AXIS"),
            _entity_ref(bar_n, "Axis2", "AXIS"), d_pivot, label="ch0 foot radius")
        log(f"    pivot dist mate: {p.get('name')!r}")
        adapter._attempt(lambda: ch_doc.ForceRebuild3(False), default=None)
    finally:
        adapter.currentModel = top
    return rk_n, bar_n


async def main():
    from solidworks_mcp.adapters.base import RotateComponentParameters
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    asm_path = str((OUT_SLDASM / "harmonic-analyzer.SLDASM").resolve())
    await adapter.open_model(asm_path)
    log(f"opened {asm_path}")

    await _flex_channel(adapter)
    await _suppress_channel(adapter)
    point_name = await _add_rocker_arc_point(adapter)
    rocker_n, bar_n = await _add_ch0_foot_arc(adapter, point_name)

    levers = _by_z_rank(adapter, "channel-lever")
    lever_n = levers[0][1]
    await _shot(adapter, "before")

    rocker_c, rocker_top = _find_one(adapter, rocker_n.split("/")[-1])
    lever_c, _ = _find_one(adapter, lever_n.split("/")[-1])
    bar_c, _ = _find_one(adapter, bar_n.split("/")[-1])
    a0 = _comp_xform(adapter, lever_c)
    ra = _comp_xform(adapter, rocker_c)
    ba0 = _comp_xform(adapter, bar_c)
    await adapter.rotate_component(RotateComponentParameters(
        name=rocker_top, angle=ROCK_DEG, axis_vector=[ra[6], ra[7], ra[8]],
        axis_point=[ra[9] * 1000.0, ra[10] * 1000.0, ra[11] * 1000.0],
        mode="kinematic"))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    await _shot(adapter, "after")
    a1 = _comp_xform(adapter, lever_c)
    ra1 = _comp_xform(adapter, rocker_c)
    ba1 = _comp_xform(adapter, bar_c)
    lever_moved = _rot_angle(a0, a1) if (a0 and a1) else 0.0
    rocker_moved = _rot_angle(ra, ra1) if (ra and ra1) else 0.0
    bar_rot = _rot_angle(ba0, ba1) if (ba0 and ba1) else 0.0
    log(f"  rocker rotated {rocker_moved:.2f} deg -> lever {lever_moved:.2f} deg "
        f"| bar swung {bar_rot:.2f} deg")
    transmits = lever_moved > 2.0
    swings_ok = 0.0 < bar_rot < 45.0
    if transmits and swings_ok:
        log(f"  PASS: four-bar transmits (lever {lever_moved:.1f} deg) AND bar "
            f"swings as a coupler ({bar_rot:.1f} deg, bounded) -> wire all 20")
    elif transmits and not swings_ok:
        log(f"  CHECK: lever follows ({lever_moved:.1f}) but bar swing {bar_rot:.1f} "
            f"deg is out of band (0,45) -- inspect the shots")
    else:
        log(f"  FAIL: lever did not follow (lever {lever_moved:.1f} deg) -> the "
            f"foot-arc pair is not coupling the rocker to the lever")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
