r"""Fast isolation of WIRE2 (wheel rack-pinion -> pen): does the rack-pinion mate
actually transmit wheel rotation into pen-rod Y translation?

In probe_wires2 the gear (summing->wheel) drove the wheel 97 deg but the pen did
NOT move, even though the true Y-travel snapshot (Distance12, FACE-FACE) was
suppressed. This probe adds ONLY WIRE2, rotates the wheel in the sub doc, rebuilds
and reads the pen-marker delta -- testing whether the assembly solver enforces the
rack-pinion at all (no slow motion calc). NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_wire2_only.py
"""

from __future__ import annotations

import asyncio

from _common import (
    OUT_SLDASM, check, coincident_mate, log, named_ref, rack_pinion_mate,
)
from build_motion_study import (
    ANGLE, ASM, FLEXIBLE, _comp_xform, _entity_ref, _find_one, _sub_model,
    _suppress_named, _world,
)


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
    """Suppress the pen-rod Y-travel snapshot (largest-value pen-rod DISTANCE =
    the Top<->Top plane Y position; confirmed Distance12 via probe_pen_mates)."""
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
    if best[0] is None:
        log("  pen-rod Y-travel NOT FOUND")
        return
    log(f"  suppressing pen-rod Y-travel snapshot {best[0]} (val={best[1] * 1000:.1f}mm)")
    check("suppress pen travel", await adapter.suppress_mate(
        SuppressMateParameters(name=best[0], suppress=True, component="output-1")))


async def main():
    from solidworks_mcp.adapters.base import RotateComponentParameters
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

    _, out_doc = _sub_model(adapter, "output-1")
    top = adapter.currentModel
    adapter.currentModel = out_doc
    marker, _ = _find_one(adapter, "pen-marker")
    y0 = _world(_comp_xform(adapter, marker), [0, 0, 0])[1] if marker else None
    try:
        rr = _entity_ref("pen-rod-1", "Axis1", "AXIS")
        rr.mark = 64
        pr = _entity_ref("magnifying-wheel-1", "Axis1", "AXIS")
        pr.mark = 128
        w2 = await rack_pinion_mate(adapter, rr, pr, pinion_pitch_diameter=100.0,
                                    label="WIRE2 wheel->pen")
        log(f"  WIRE2: {w2.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE2 FAILED: {exc}")

    # rotate the wheel 30 deg about its own axis (Z) and rebuild; read pen delta.
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    a = _comp_xform(adapter, wh)
    await adapter.rotate_component(RotateComponentParameters(
        name="magnifying-wheel-1", angle=30.0, axis_vector=[a[6], a[7], a[8]],
        axis_point=[a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0], mode="exact"))
    adapter._attempt(lambda: out_doc.ForceRebuild3(False), default=None)
    marker2, _ = _find_one(adapter, "pen-marker")
    y1 = _world(_comp_xform(adapter, marker2), [0, 0, 0])[1] if marker2 else None
    if y0 is not None and y1 is not None:
        log(f"  pen-marker Y: {y0:.3f} -> {y1:.3f}  delta={y1 - y0:.3f} mm "
            f"(expect ~50*30deg*pi/180 = 26 mm if rack-pinion transmits)")
    adapter.currentModel = top
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
