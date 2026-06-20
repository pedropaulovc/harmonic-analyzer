r"""Test the FULL output chain with WIRE2 as a SCOTCH-YOKE (not rack-pinion).

Findings so far: gear (rotation<->rotation, parallel Z) transmits in Basic Motion
in-sub (summing -> wheel works); an axis rack-pinion does NOT transmit (Basic
Motion / physical_simulation supports gear but not rack-pinion -- MotionAnalysis,
which would, is unlicensed on this Makers seat). So model WIRE2 the way the cam
coupling works (RefPoint + coincident, proven in Basic Motion):

  WIRE1  gear  summing-lever(Z) <-> magnifying-wheel(Z)   parallel, ratio
  WIRE2  scotch-yoke: a RefPoint on the wheel RIM (radius 50) held COINCIDENT to
         the pen-rod's horizontal Top Plane. As the wheel turns, the rim point's
         vertical (Y) excursion drags the pen-rod in Y (its X excursion slides
         freely along the infinite plane). pen_Y ~= 50*sin(theta_wheel) -- linear
         for the small operational angles, the 5x living in this radius vs the
         WIRE1 gear ratio. Calibrate amplitude in F6.

Drives summing slowly (1 RPM -> 36 deg over 6 s) so rotations don't wrap acos.
NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_wire2_yoke.py
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
    gear_mate,
    named_ref,
)
from build_motion_study import (
    ANGLE, ASM, DURATION_S, FLEXIBLE, _comp_xform, _entity_ref, _find_one,
    _read_member, _rot_angle, _sub_model, _suppress_named, _world,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

RATIO_SUM_WHEEL = [1.0, 1.0]
SUM_RPM = 1.0
# candidate part-local points on the rim OD circular edge (radius 50); the rim is
# extruded both-directions depth 8 about the Front plane so the edge z is +/-4 or
# +/-8 -- try a few until one selects.
RIM_EDGE_CANDIDATES = [[50.0, 0.0, 4.0], [50.0, 0.0, 8.0], [50.0, 0.0, -4.0],
                       [50.0, 0.0, -8.0], [0.0, 50.0, 4.0], [50.0, 0.0, 0.0]]
TIMES = [DURATION_S * s / 12.0 for s in range(13)]


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
    log("  set output-1 FLEXIBLE ...")
    check("flexible output-1", await adapter.set_component_solving(
        SetComponentSolvingParameters(name="output-1", solving=FLEXIBLE)))


async def _suppress_pen_travel(adapter):
    from solidworks_mcp.adapters.base import SuppressMateParameters
    from build_motion_study import _family, _iter_mates, _lone_real, _mate_value, DISTANCE
    _, model = _sub_model(adapter, "output-1")
    best = (None, -1.0)
    for _f, mate, name, mtype, parts, _v in _iter_mates(adapter, model, read_values=False):
        lone = _lone_real(parts, "output")
        if mtype != DISTANCE or lone is None or _family(lone) != "pen-rod":
            continue
        val = _mate_value(adapter, mate, mtype) or 0.0
        if val > best[1]:
            best = (name, val)
    log(f"  suppressing pen-rod Y-travel snapshot {best[0]}")
    check("suppress pen travel", await adapter.suppress_mate(
        SuppressMateParameters(name=best[0], suppress=True, component="output-1")))


async def _rim_point(adapter):
    """RefPoint at radius 50 on the wheel rim, on the SHARED wheel part doc
    (inherited by the instance via GetCorresponding; never saved)."""
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    part = adapter._attempt(lambda: wh.GetModelDoc2(), default=None)
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    name = None
    for ep in RIM_EDGE_CANDIDATES:
        res = await adapter.create_reference_point(CreateReferencePointParameters(
            mode="along_curve", edge_point=ep, along="percentage", percentage=0.0))
        if res.is_success:
            name = getattr(res.data, "name", None) or (
                res.data.get("name") if isinstance(res.data, dict) else None)
            log(f"  rim RefPoint via edge_point={ep} -> {name!r}")
            break
        log(f"    edge_point={ep} failed: {res.error}")
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = top
    if not name:
        raise RuntimeError("could not create rim RefPoint on the wheel")
    return name


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

    await _flex_output(adapter)
    await _suppress_named(adapter, "output-1", ("summing-lever", "magnifying-wheel"),
                          (ANGLE,), "summing+wheel rock")
    await _suppress_pen_travel(adapter)

    rim_pt = await _rim_point(adapter)  # on shared wheel doc, before retarget

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
                             RATIO_SUM_WHEEL, label="WIRE1 summing->wheel")
        log(f"  WIRE1: {w1.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE1 FAILED: {exc}")
    try:
        # both refs are component-based (GetCorresponding) -- in the sub doc a
        # named_ref string is resolved against the ACTIVE doc (the top assembly)
        # and fails; _entity_ref maps the part feature through the component.
        w2 = await coincident_mate(
            adapter, _entity_ref("magnifying-wheel-1", rim_pt, "POINT"),
            _entity_ref("pen-rod-1", "Top Plane", "PLANE"), label="WIRE2 yoke rim->pen")
        log(f"  WIRE2 yoke: {w2.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE2 FAILED: {exc}")
    adapter._attempt(lambda: out_doc.ForceRebuild3(False), default=None)
    adapter.currentModel = top

    check("motor summing", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref("summing-lever-1", "Axis1", "AXIS"),
        speed=SUM_RPM, study_name="")))

    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: top.EditRebuild3(), default=None)
    check("calc", await adapter.calculate_motion(MotionStudyRefParameters(name="")))

    marker, _ = _find_one(adapter, "pen-marker")
    sl, _ = _find_one(adapter, "summing-lever-1")
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    base, spans, ys = {}, {}, []
    for t in TIMES:
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        if marker is not None:
            ys.append(_world(_comp_xform(adapter, marker), [0, 0, 0])[1])
        for key, comp in (("summing", sl), ("wheel", wh)):
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            spans[key] = max(spans.get(key, 0.0), _rot_angle(base[key], a))
    if ys:
        log(f"  pen-marker Y: min={min(ys):.2f} max={max(ys):.2f} span={max(ys) - min(ys):.3f} mm")
    log(f"  ROCK summing={spans.get('summing', 0):.1f}  wheel={spans.get('wheel', 0):.1f}")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
