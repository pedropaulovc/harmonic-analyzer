r"""BASIC MOTION probe: does the foot-arc four-bar transmit rocker -> lever?

The F6 model is the REAL linkage (no gear): the amplitude bar is a swinging
coupler whose foot is pinned to the rocker's R800 arc (two in-sub DISTANCE mates
from bar Axis2 -- to the arc-centre RefPoint = R, and to the pivot axis =
r_foot/coefficient) and whose top swings on the channel-lever pin (artifact-A J3
coincident, kept). As the rocker seesaws, the foot orbits with it, the rigid bar
pushes the lever pin, the lever rotates -- a 1-DOF four-bar. The bar SWINGS as a
coupler (user-confirmed, book ch.17: bars are not rigid with the lever).

An earlier version drove the rocker with rotate_component(mode=kinematic) and got
rocker == lever == bar == 159.01 deg (rigid co-rotation): kinematic drag cannot
solve a CLOSED loop, it just tumbles the connected clump. The valid solver is
Basic Motion -- the same one the deliverable uses. So this probe: flex channel-1,
the (cached) single-pass suppress, the ch0 foot-arc pair at a REAL coefficient
(neutral r_foot ~6.5 mm is near-singular -> set ~60 mm so the gain is visible),
a rotary MOTOR on the rocker, Calculate(), then sample the lever rotation over
time. Lever span > 0 with a bounded bar swing => the four-bar transmits => wire
all 20. Enumerates the full tree ONCE (each walk is ~170 s). NEVER saves.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_foot_arc.py
"""

from __future__ import annotations

import asyncio

from _common import OUT_PNG, coincident_mate, distance_driver, log, named_ref
from build_motion_study import (
    BAR_FOOT_LOCAL, BAR_TOP_PIN_LOCAL, OUT_SLDASM, ROCKER_ARC_CENTER_LOCAL,
    _add_rocker_arc_point, _by_z_rank, _comp_xform, _components, _entity_ref,
    _find_one, _rot_angle, _suppress_channel, _sub_model, _world, _xy_dist,
)

ROCK_SPEED = 2.0     # motor speed (rad/s in Basic Motion -> ~115 deg/s)
DURATION_S = 0.75    # keep the rocker inside its real ROM
PERTURB_DEG = 5.0    # swing the freed bar off dead centre before pinning the foot


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


async def _perturb_bar(adapter, bar_c, bar_n, deg):
    """Swing the freed bar ``deg`` about its top pin so the foot leaves dead
    centre (foot ~on the pivot -> rocker rotation gives ~zero foot travel = a
    singular four-bar). Rotating about the top-pin Z axis keeps the top-pin
    coincident + axial-Z satisfied (it IS the bar's free swing DOF), so no mate
    errors; the freed bar holds the new pose (no force pulls it back)."""
    from solidworks_mcp.adapters.base import RotateComponentParameters
    ba = _comp_xform(adapter, bar_c)
    foot0 = _world(ba, BAR_FOOT_LOCAL)
    top_pin = _world(ba, BAR_TOP_PIN_LOCAL)
    await adapter.rotate_component(RotateComponentParameters(
        name=bar_n, angle=deg, axis_vector=[0.0, 0.0, 1.0],
        axis_point=[top_pin[0], top_pin[1], top_pin[2]], mode="exact"))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    foot1 = _world(_comp_xform(adapter, bar_c), BAR_FOOT_LOCAL)
    log(f"  perturb bar {deg:+.1f} deg about top-pin: foot "
        f"({foot0[0]:.1f},{foot0[1]:.1f}) -> ({foot1[0]:.1f},{foot1[1]:.1f}) "
        f"moved {_xy_dist(foot0, foot1):.1f} mm")


async def _add_ch0_foot_arc(adapter, point_name):
    """Add ONLY ch0's foot-arc pair at the CURRENT (perturbed) pose -- both
    distances MEASURED so each mate starts already satisfied (no errored far
    target). d_arc = foot<->arc-centre, d_pivot = foot<->pivot (the coefficient)."""
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
        from build_motion_study import ROCKER_PIVOT_LOCAL
        pivot = _world(ra, ROCKER_PIVOT_LOCAL)
        foot = _world(ba, BAR_FOOT_LOCAL)
        d_arc = _xy_dist(foot, arc_c)
        d_pivot = _xy_dist(foot, pivot)
        log(f"  ch0 rocker={rk_n!r} bar={bar_n!r} R={d_arc:.2f} "
            f"d_pivot={d_pivot:.2f} (measured at perturbed pose)")
        a = await distance_driver(
            adapter, _entity_ref(rk_n, point_name, "POINT"),
            _entity_ref(bar_n, "Axis2", "AXIS"), d_arc, label="ch0 foot on R800 arc")
        log(f"    arc dist mate: {a.get('name')!r}")
        p = await distance_driver(
            adapter, _entity_ref(rk_n, "Axis1", "AXIS"),
            _entity_ref(bar_n, "Axis2", "AXIS"), d_pivot,
            label="ch0 foot radius (coeff)")
        log(f"    pivot dist mate: {p.get('name')!r}")
        adapter._attempt(lambda: ch_doc.ForceRebuild3(False), default=None)
    finally:
        adapter.currentModel = top
    return rk_n, bar_n


async def main():
    from solidworks_mcp.adapters.base import (
        MotionMotorParameters, MotionStudyParameters, MotionStudyRefParameters,
        MotionTimeParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    asm_path = str((OUT_SLDASM / "harmonic-analyzer.SLDASM").resolve())
    await adapter.open_model(asm_path)
    log(f"opened {asm_path}")

    await _flex_channel(adapter)
    await _suppress_channel(adapter)            # cached -> fast
    point_name = await _add_rocker_arc_point(adapter)

    # ONE full-tree walk; reuse the comp objects for perturb + motor + sampling.
    comps = _components(adapter)
    rocker_c, rocker_n = _find_one(adapter, "rocker-arm-1", comps=comps)
    lever_c, lever_n = _find_one(adapter, "channel-lever-1", comps=comps)
    bar_c, bar_n = _find_one(adapter, "amplitude-bar-1", comps=comps)

    # Swing the freed bar off dead centre FIRST, then pin the foot at the measured
    # (non-degenerate, already-satisfied) pose -- avoids the singular four-bar and
    # the errored far-target mate that froze the last run.
    await _perturb_bar(adapter, bar_c, bar_n, PERTURB_DEG)
    await _add_ch0_foot_arc(adapter, point_name)

    check = lambda tag, r: log(f"  {tag}: {getattr(r, 'is_success', r)}")
    await adapter.ensure_motion_addin()
    made = await adapter.create_motion_study(MotionStudyParameters(
        name="", study_type="physical_simulation", duration=DURATION_S, activate=True))
    log(f"  study {getattr(made, 'data', made)}")
    # Motor on the ROCKER axis (its spin is freed by the suppress) -- drives the
    # four-bar directly so the test isolates the foot-arc transmission from the
    # cam chain. Component+name AXIS ref maps through the flexible sub.
    res = await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref(rocker_n, "Axis1", "AXIS"),
        speed=ROCK_SPEED, study_name=""))
    check("add_motor rocker", res)

    log("  Calculate() -- Basic Motion solve of the ch0 four-bar ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    base = {}
    spans = {}
    probes = [("rocker", rocker_c), ("lever", lever_c), ("bar", bar_c)]
    steps = 8
    for s in range(steps + 1):
        t = DURATION_S * s / steps
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        row = []
        for name, comp in probes:
            a = _comp_xform(adapter, comp)
            if a is None:
                row.append(f"{name}=n/a")
                continue
            base.setdefault(name, a)
            ang = _rot_angle(base[name], a)
            spans[name] = max(spans.get(name, 0.0), ang)
            row.append(f"{name}={ang:6.2f}")
        log(f"    t={t:4.2f}s  {'  '.join(row)}")
    log(f"  spans(deg): {dict((k, round(v, 2)) for k, v in spans.items())}")

    rocker_sp = spans.get("rocker", 0.0)
    lever_sp = spans.get("lever", 0.0)
    bar_sp = spans.get("bar", 0.0)
    transmits = lever_sp > 0.5 and rocker_sp > 0.5
    swings_ok = 0.0 < bar_sp < 45.0
    if transmits and swings_ok:
        log(f"  PASS: Basic Motion four-bar transmits (rocker {rocker_sp:.1f} -> "
            f"lever {lever_sp:.1f} deg) AND bar swings as a coupler "
            f"({bar_sp:.1f} deg, bounded) -> wire all 20")
    elif rocker_sp <= 0.5:
        log(f"  FAIL: rocker barely moved ({rocker_sp:.2f} deg) -- the motor did "
            f"not drive (over-constraint or motor target wrong)")
    elif not transmits:
        log(f"  FAIL: rocker moved {rocker_sp:.1f} deg but lever only {lever_sp:.2f} "
            f"-- the foot-arc pair is not coupling rocker -> lever")
    else:
        log(f"  CHECK: transmits but bar swing {bar_sp:.1f} deg out of band (0,45)")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
