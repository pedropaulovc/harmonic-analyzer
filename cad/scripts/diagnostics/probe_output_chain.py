r"""Pinpoint where the output amplification chain breaks transmission.

The full study shows: crank turns, rockers oscillate, springs rock the summing
-lever 45 deg -- but the PEN barely moves (one 131 mm snap then frozen). So the
summing-lever motion is NOT reaching the pen through WIRE1 (gear summing->wheel)
+ WIRE2 (scotch-yoke wheel->pen). This probe isolates THAT chain: flex the three
value-chain subs (summing-1, magnifier-1, pen-1), author the exact baked wires as
top-level cross-sub mates, then DRIVE THE SUMMING-LEVER with a low-speed motor
(deterministic, no springs/dynamics) and sample per timestep:

    summing angle   wheel angle   pen Y

If the wheel tracks the summing-lever -> the gear transmits; if the pen tracks
the wheel -> the yoke transmits. Whichever stays flat is the broken link.
NEVER saves.

NOTE (output split, June 2026): the amplification chain now spans THREE sibling
subs (summing/magnifier/pen) instead of the old monolithic output-1, so WIRE1 and
WIRE2 are authored at the TOP level (no sub_model). The leaf-name lookups already
traversed one nesting level under output-1, so they are unchanged. This debug-only
tool NEVER saves and is not part of any gate; revalidate under Motion next time the
transmission chain is exercised.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_output_chain.py
"""

from __future__ import annotations

import asyncio

from _common import (
    OUT_SLDASM,
    check,
    log,
)
from _assembly import (
    coincident_mate,
    named_ref,
)
from build_motion_study import (
    ANGLE, ASM, DURATION_S, FLEXIBLE, _comp_xform, _entity_ref, _find_one,
    _rot_angle, _suppress_named, _world,
)
from build_motion_study_springs import _add_wire1_gear, _rim_point, _suppress_pen_travel

SUM_RPM = 1.0  # gentle: 6 deg/s -> 36 deg over 6 s, no acos wrap
TIMES = [DURATION_S * s / 12.0 for s in range(13)]


VALUE_CHAIN_SUBS = ("summing-1", "magnifier-1", "pen-1")


async def _flex_value_chain(adapter):
    """Float + origin-plane-ground + flex each value-chain sub so its internal
    rock/travel DOF is live at the top level (the subs are inserted fixed, and a
    fixed component can't be made flexible)."""
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    asm = adapter.currentModel
    for sub in VALUE_CHAIN_SUBS:
        check(f"float {sub}", await adapter.float_component(
            ComponentRefParameters(name=sub)))
        for plane in ("Front Plane", "Top Plane", "Right Plane"):
            await coincident_mate(
                adapter, named_ref(f"{plane}@{sub}", "PLANE"),
                named_ref(plane, "PLANE"), label=f"ground {sub} {plane}")
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        check(f"flexible {sub}", await adapter.set_component_solving(
            SetComponentSolvingParameters(name=sub, solving=FLEXIBLE)))


async def main():
    from solidworks_mcp.adapters.base import (
        MotionMotorParameters, MotionStudyParameters, MotionStudyRefParameters,
        MotionTimeParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")

    await _flex_value_chain(adapter)
    # free summing rock + wheel rock + pen travel (the chain's 3 driven DOF),
    # each now in its own sub.
    await _suppress_named(adapter, "summing-1", ("summing-lever",),
                          (ANGLE,), "summing rock")
    await _suppress_named(adapter, "magnifier-1", ("magnifying-wheel",),
                          (ANGLE,), "wheel rock")
    await _suppress_pen_travel(adapter)
    rim_pt = await _rim_point(adapter)

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))

    # WIRE1 (gear summing->wheel) + WIRE2 (yoke wheel->pen) are now cross-sub
    # mates -- author them at the TOP level (no sub_model into a single output).
    top = adapter.currentModel
    w1 = await _add_wire1_gear(adapter)
    log(f"  WIRE1 = {w1.get('name')}")
    w2 = await coincident_mate(
        adapter, _entity_ref("magnifying-wheel-1", rim_pt, "POINT"),
        _entity_ref("pen-rod-1", "Top Plane", "PLANE"), label="WIRE2 yoke")
    log(f"  WIRE2 = {w2.get('name')}")
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)

    check("motor summing", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref("summing-lever-1", "Axis1", "AXIS"),
        speed=SUM_RPM, study_name="")))

    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: top.EditRebuild3(), default=None)
    check("calc", await adapter.calculate_motion(MotionStudyRefParameters(name="")))

    sl, _ = _find_one(adapter, "summing-lever-1")
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    marker, _ = _find_one(adapter, "pen-marker")
    base = {}
    for t in TIMES:
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        vals = []
        for key, comp in (("sum", sl), ("wheel", wh)):
            a = _comp_xform(adapter, comp)
            if a is None:
                vals.append("  n/a")
                continue
            base.setdefault(key, a)
            vals.append(f"{_rot_angle(base[key], a):6.2f}")
        a = _comp_xform(adapter, marker)
        pen_y = f"{_world(a, [0, 0, 0])[1]:8.2f}" if a is not None else "    n/a"
        log(f"    t={t:4.2f}s  sum={vals[0]}  wheel={vals[1]}  penY={pen_y}")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
