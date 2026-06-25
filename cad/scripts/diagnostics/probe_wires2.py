r"""Clean, ISOLATED validation of the F5 output-chain wire couplings.

The previous probe (probe_wires.py) attached to a dirty, accumulated doc, so its
results were unreliable (e.g. wheel rock=0 with stale couplings). This probe
opens the SLDASM FRESH and isolates the wire chain from the spring/cam physics:
only output-1 is made flexible, and the summing-lever is driven by a DIRECT
rotary motor (standing in for the spring force balance). If the wheel and pen
move, the three in-sub couplings propagate correctly in Basic Motion.

  LINK  summing-lever(Rz) -> magnifying-lever(Rx)  gear ratio (lever linkage)
  WIRE1 magnifying-lever  -> magnifying-wheel(Rz)  gear ratio (clamp r : hub R)
  WIRE2 magnifying-wheel  -> pen-rod (Y slide)     rack_pinion (rim pitch O100)

All three are authored INSIDE output.SLDASM's doc (the four parts share the one
output-1 flexible sub -> top-level mates between them are rejected). NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_wires2.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import (
    OUT_SLDASM,
    check,
    log,
)
from _assembly import (
    coincident_mate,
    gear_mate,
    named_ref,
    rack_pinion_mate,
)
from build_motion_study import (
    ANGLE, ASM, DISTANCE, DURATION_S, FLEXIBLE, _comp_xform, _entity_ref,
    _family, _find_one, _iter_mates, _lone_real, _mate_value, _rot_angle,
    _sub_model, _suppress_named,
)

STUDY = ""                   # active study
SUM_RPM = 6.0                # gentle drive on the summing-lever stand-in
# WIRE1 (lumped): summing-lever(Z) <-> magnifying-wheel(Z) are PARALLEL axes, so
# a gear mate is accepted (the skew mag-lever(X) gear over-defines -- proven by
# probe_couple_types). This rotary-rotary gear stands in for the faithful
# "summing -> mag-lever -> WIRE1 -> hub O20" transmission (both ends rotary).
# [1,1] here just to maximise the validation signal; the real 5x amplification is
# tuned in F6 via this ratio + the WIRE2 pitch diameter.
RATIO_SUM_WHEEL = [1.0, 1.0]
WIRE2_PITCH_MM = 100.0       # wheel rim pitch diameter -> pen travel = pi*100/rev
TIMES = [DURATION_S * s / 8.0 for s in range(9)]


async def _flex_output(adapter):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    asm = adapter.currentModel
    check("float output-1", await adapter.float_component(
        ComponentRefParameters(name="output-1")))
    for plane in ("Front Plane", "Top Plane", "Right Plane"):
        await coincident_mate(
            adapter, named_ref(f"{plane}@output-1", "PLANE"),
            named_ref(plane, "PLANE"), label=f"ground output-1 {plane}")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    log("  set output-1 FLEXIBLE -- blocking solve ...")
    check("flexible output-1", await adapter.set_component_solving(
        SetComponentSolvingParameters(name="output-1", solving=FLEXIBLE)))
    comp, _ = _find_one(adapter, "output-1", toplevel=True)
    solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
    log(f"  output-1 Solving={solving} (1=flexible)")


async def _suppress_pen_travel(adapter):
    from solidworks_mcp.adapters.base import SuppressMateParameters
    _, model = _sub_model(adapter, "output-1")
    best = (None, -1.0)
    for _f, mate, name, mtype, parts, _v in _iter_mates(adapter, model, read_values=False):
        lone = _lone_real(parts, "output")
        if mtype != DISTANCE or lone is None or _family(lone) != "pen-rod":
            continue
        val = _mate_value(adapter, mate, mtype) or 0.0
        if val > best[1]:
            best = (name, val)
    if best[0] is None:
        log("  pen-rod travel snapshot NOT FOUND")
        return
    log(f"  suppressing pen-rod travel snapshot {best[0]} (val={best[1] * 1000:.1f}mm)")
    check("suppress pen travel", await adapter.suppress_mate(
        SuppressMateParameters(name=best[0], suppress=True, component="output-1")))


async def main():
    from solidworks_mcp.adapters.base import (
        MotionMotorParameters, MotionStudyParameters, MotionStudyRefParameters,
        MotionTimeParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting ...")
    await adapter.connect()
    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open", await adapter.open_model(asm_path))  # sets adapter.currentModel
    log(f"opened {asm_path}")

    # 1) only output-1 flexible; the other subs stay rigid (isolate the chain).
    await _flex_output(adapter)

    # 2) free the driven DOF: summing rock (springs/motor), wheel rock (gear),
    #    pen travel (rack-pinion). The mag-lever rock stays PINNED at its set
    #    position (its skew X-axis can't be geared; its motion is lumped into the
    #    summing<->wheel gear ratio).
    await _suppress_named(adapter, "output-1",
                          ("summing-lever", "magnifying-wheel"),
                          (ANGLE,), "summing+wheel rock")
    await _suppress_pen_travel(adapter)

    # 3) study + the 3 couplings authored INSIDE the output sub doc.
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made['name']!r}")

    _, out_doc = _sub_model(adapter, "output-1")
    top = adapter.currentModel
    adapter.currentModel = out_doc
    try:
        w1 = await gear_mate(adapter, _entity_ref("summing-lever-1", "Axis1", "AXIS"),
                             _entity_ref("magnifying-wheel-1", "Axis1", "AXIS"),
                             RATIO_SUM_WHEEL, label="WIRE1 summing->wheel (parallel Z)")
        log(f"  WIRE1 summing->wheel: {w1.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE1 FAILED: {exc}")
    try:
        rack_ref = _entity_ref("pen-rod-1", "Axis1", "AXIS")
        rack_ref.mark = 64
        pinion_ref = _entity_ref("magnifying-wheel-1", "Axis1", "AXIS")
        pinion_ref.mark = 128
        w2 = await rack_pinion_mate(adapter, rack_ref, pinion_ref,
                                    pinion_pitch_diameter=WIRE2_PITCH_MM,
                                    label="WIRE2 wheel->pen")
        log(f"  WIRE2 wheel->pen: {w2.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE2 FAILED: {exc}")
    adapter._attempt(lambda: out_doc.ForceRebuild3(False), default=None)
    adapter.currentModel = top

    # 4) DIRECT motor on the summing-lever Axis1 (knife rotation axis) -- the
    #    stand-in for the spring force balance, isolating the coupling chain.
    motor = check("motor summing", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref("summing-lever-1", "Axis1", "AXIS"),
        speed=SUM_RPM, study_name=STUDY)))
    log(f"  motor on summing-lever Axis1 ({SUM_RPM} RPM): {motor}")

    # 5) reset + calc + sample mag-lever / wheel / pen.
    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=STUDY))
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: top.EditRebuild3(), default=None)
    check("calc", await adapter.calculate_motion(MotionStudyRefParameters(name=STUDY)))

    marker, _ = _find_one(adapter, "pen-marker")
    sl, _ = _find_one(adapter, "summing-lever-1")
    ml, _ = _find_one(adapter, "magnifying-lever-1")
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    base, spans, ys = {}, {}, []
    for t in TIMES:
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=STUDY))
        if marker is not None:
            from build_motion_study import _world
            ys.append(_world(_comp_xform(adapter, marker), [0, 0, 0])[1])
        for key, comp in (("summing", sl), ("mag-lever", ml), ("wheel", wh)):
            if comp is None:
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            spans[key] = max(spans.get(key, 0.0), _rot_angle(base[key], a))
    if ys:
        log(f"  pen-marker Y span = {max(ys) - min(ys):.3f} mm")
    log(f"  ROCK summing={spans.get('summing', 0):.1f}  "
        f"mag-lever={spans.get('mag-lever', 0):.1f}  wheel={spans.get('wheel', 0):.1f}")
    await adapter.disconnect()
    _telemetry.info("Disconnected (NOT saved).")


if __name__ == "__main__":
    asyncio.run(main())
