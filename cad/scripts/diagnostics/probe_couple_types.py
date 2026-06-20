r"""Fast diagnostic (NO calc): find a coupling-mate TYPE that SolidWorks accepts
for the output chain. The gear mate over-defines between the SKEW summing(Z) and
mag-lever(X) axes (both parts proven free-rotating). Hypothesis: gear mates need
COPLANAR (parallel/intersecting) axes; summing(Z) and wheel(Z) are PARALLEL.

Tests a matrix of candidate couplings in ONE open, DELETING each success before
the next so the DOF stays clean:

  A gear  summing(Z)  <-> wheel(Z)        PARALLEL  -- key test
  B gear  mag(X)      <-> wheel(Z)        skew      -- control (expect fail)
  C rack  vertical-rod <-> wheel (d20)    WIRE1 as rack-pinion
  D rack  output-fixture <-> wheel (d20)  WIRE1 alt
  E rack  pen-rod     <-> wheel (d100)    WIRE2 (known good) -- sanity

NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_couple_types.py
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
    rack_pinion_mate,
)
from build_motion_study import (
    ANGLE, ASM, FLEXIBLE, _entity_ref, _sub_model, _suppress_named,
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


async def _del(adapter, name):
    from solidworks_mcp.adapters.base import MateRefParameters
    if not name:
        return
    try:
        await adapter.delete_mate(MateRefParameters(name=name))
        log(f"    deleted {name} (clean for next test)")
    except Exception as exc:  # noqa: BLE001
        log(f"    delete {name} FAILED: {exc}")


async def _gear(adapter, tag, a_comp, a_axis, b_comp, b_axis, ratio):
    try:
        res = await gear_mate(adapter, _entity_ref(a_comp, a_axis, "AXIS"),
                              _entity_ref(b_comp, b_axis, "AXIS"), ratio, label=tag)
        log(f"  [{tag}] OK: {res.get('name')}")
        return res.get("name")
    except Exception as exc:  # noqa: BLE001
        log(f"  [{tag}] FAILED: {exc}")
        return None


async def _rack(adapter, tag, rack_comp, rack_axis, pin_comp, pin_axis, dia):
    try:
        rr = _entity_ref(rack_comp, rack_axis, "AXIS")
        rr.mark = 64
        pr = _entity_ref(pin_comp, pin_axis, "AXIS")
        pr.mark = 128
        res = await rack_pinion_mate(adapter, rr, pr,
                                     pinion_pitch_diameter=dia, label=tag)
        log(f"  [{tag}] OK: {res.get('name')}")
        return res.get("name")
    except Exception as exc:  # noqa: BLE001
        log(f"  [{tag}] FAILED: {exc}")
        return None


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")

    await _flex_output(adapter)
    await _suppress_named(adapter, "output-1",
                          ("summing-lever", "magnifying-lever", "magnifying-wheel"),
                          (ANGLE,), "summing+mag+wheel rock")

    _, out_doc = _sub_model(adapter, "output-1")
    top = adapter.currentModel
    adapter.currentModel = out_doc
    try:
        log("  === coupling-type matrix ===")
        await _del(adapter, await _gear(
            adapter, "A gear summing(Z)<->wheel(Z) PARALLEL",
            "summing-lever-1", "Axis1", "magnifying-wheel-1", "Axis1", [5.0, 1.0]))
        await _del(adapter, await _gear(
            adapter, "B gear mag(X)<->wheel(Z) skew",
            "magnifying-lever-1", "Axis1", "magnifying-wheel-1", "Axis1", [5.0, 1.0]))
        await _del(adapter, await _rack(
            adapter, "C rack vertical-rod<->wheel d20",
            "magnifying-vertical-rod-1", "Axis1", "magnifying-wheel-1", "Axis1", 20.0))
        await _del(adapter, await _rack(
            adapter, "D rack output-fixture<->wheel d20",
            "output-fixture-1", "Axis1", "magnifying-wheel-1", "Axis1", 20.0))
        await _del(adapter, await _rack(
            adapter, "E rack pen-rod<->wheel d100 (sanity)",
            "pen-rod-1", "Axis1", "magnifying-wheel-1", "Axis1", 100.0))
    finally:
        adapter.currentModel = top
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
