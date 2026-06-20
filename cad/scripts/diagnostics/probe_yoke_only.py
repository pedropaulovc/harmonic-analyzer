r"""Clean, unambiguous test of WIRE2 (scotch-yoke) ALONE: motor the WHEEL directly
at LOW speed (0.5 RPM -> 18 deg over 6 s, no acos wrap), yoke the rim point to the
pen-rod Top plane, and verify the pen Y tracks the wheel rotation sinusoidally.

No WIRE1, no summing motor, no springs -- isolates the wheel->pen coupling with a
KNOWN driver. Expect pen_Y span ~ 2*50*sin(18deg) ~ 31 mm if the yoke transmits.
NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_yoke_only.py
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
    _read_member, _rot_angle, _sub_model, _suppress_named, _world,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

WHEEL_RPM = 0.5
RIM_EDGE_CANDIDATES = [[50.0, 0.0, 4.0], [50.0, 0.0, 8.0], [50.0, 0.0, -4.0],
                       [50.0, 0.0, -8.0], [0.0, 50.0, 4.0]]
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
    log(f"  suppress pen-rod Y-travel {best[0]}")
    check("suppress pen travel", await adapter.suppress_mate(
        SuppressMateParameters(name=best[0], suppress=True, component="output-1")))


async def _rim_point(adapter):
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
            log(f"  rim RefPoint edge_point={ep} -> {name!r}")
            break
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = top
    if not name:
        raise RuntimeError("no rim RefPoint")
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
    await _suppress_named(adapter, "output-1", ("magnifying-wheel",), (ANGLE,),
                          "wheel rock")
    await _suppress_pen_travel(adapter)
    rim_pt = await _rim_point(adapter)

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))

    _, out_doc = _sub_model(adapter, "output-1")
    top = adapter.currentModel
    adapter.currentModel = out_doc
    try:
        w2 = await coincident_mate(
            adapter, _entity_ref("magnifying-wheel-1", rim_pt, "POINT"),
            _entity_ref("pen-rod-1", "Top Plane", "PLANE"), label="yoke rim->pen")
        log(f"  WIRE2 yoke: {w2.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE2 FAILED: {exc}")
    adapter._attempt(lambda: out_doc.ForceRebuild3(False), default=None)
    adapter.currentModel = top

    check("motor wheel", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref("magnifying-wheel-1", "Axis1", "AXIS"),
        speed=WHEEL_RPM, study_name="")))

    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: top.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: top.EditRebuild3(), default=None)
    check("calc", await adapter.calculate_motion(MotionStudyRefParameters(name="")))

    marker, _ = _find_one(adapter, "pen-marker")
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    base = None
    rows = []
    for t in TIMES:
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        y = _world(_comp_xform(adapter, marker), [0, 0, 0])[1] if marker else 0.0
        a = _comp_xform(adapter, wh)
        if base is None:
            base = a
        rot = _rot_angle(base, a)
        rows.append((t, rot, y))
    for t, rot, y in rows:
        log(f"    t={t:4.2f}s wheelrot={rot:6.2f}deg  penY={y:8.2f}")
    ys = [y for _t, _r, y in rows]
    log(f"  pen-marker Y span = {max(ys) - min(ys):.3f} mm (yoke transmits if >0 "
        f"and tracks wheelrot)")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
