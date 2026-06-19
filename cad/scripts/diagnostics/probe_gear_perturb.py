r"""Fast diagnostic (NO calc): why do the LINK/WIRE1 gear mates over-define at the
exact assembled pose but added fine on the displaced (post-physics) doc?

Hypothesis: pose-dependent degeneracy, like the cam point-on-axis case -- perturb
the driven part off the design pose, add the gear, snap back. Tests, in ONE open:
  1. add LINK summing->mag at design pose            (expect over-define)
  2. perturb mag-lever ~15 deg in the sub doc, retry (expect success?)
  3. if still failing, try alignment aligned/anti

Also confirms each part has free rotational DOF by rotating it and reading the
transform delta. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_gear_perturb.py
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
    ANGLE, ASM, FLEXIBLE, _comp_xform, _entity_ref, _find_one, _rot_angle,
    _sub_model, _suppress_named,
)

RATIO = [1.0, 1.0]


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


async def _try_link(adapter, tag, alignment="closest"):
    try:
        res = await gear_mate(adapter, _entity_ref("summing-lever-1", "Axis1", "AXIS"),
                              _entity_ref("magnifying-lever-1", "Axis1", "AXIS"),
                              RATIO, alignment=alignment, label=f"LINK {tag}")
        log(f"  [{tag}] LINK OK: {res.get('name')}")
        return res.get("name")
    except Exception as exc:  # noqa: BLE001
        log(f"  [{tag}] LINK FAILED: {exc}")
        return None


async def _rotate_in_sub(adapter, sub_doc, comp_name, axis_vec, deg):
    """Rotate a part within the sub doc about its own origin; return rot delta."""
    from solidworks_mcp.adapters.base import RotateComponentParameters
    comp, _ = _find_one(adapter, comp_name)
    a0 = _comp_xform(adapter, comp)
    await adapter.rotate_component(RotateComponentParameters(
        name=comp_name, angle=deg, axis_vector=axis_vec,
        axis_point=[a0[9] * 1000.0, a0[10] * 1000.0, a0[11] * 1000.0], mode="exact"))
    adapter._attempt(lambda: sub_doc.ForceRebuild3(False), default=None)
    comp2, _ = _find_one(adapter, comp_name)
    a1 = _comp_xform(adapter, comp2)
    delta = _rot_angle(a0, a1)
    log(f"    rotated {comp_name} req={deg} -> actual rot delta={delta:.2f} deg")
    return delta


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
        # A) design pose
        if await _try_link(adapter, "design-closest"):
            log("  design pose succeeded -- pose theory WRONG; investigate elsewhere")
            return
        await _try_link(adapter, "design-aligned", alignment="aligned")
        await _try_link(adapter, "design-anti", alignment="anti_aligned")

        # B) confirm free DOF: rotate mag-lever (about world X) and summing (Z)
        log("  --- DOF check (rotate parts in sub doc) ---")
        await _rotate_in_sub(adapter, out_doc, "magnifying-lever-1", [1.0, 0.0, 0.0], 15.0)
        await _rotate_in_sub(adapter, out_doc, "summing-lever-1", [0.0, 0.0, 1.0], 10.0)

        # C) perturbed pose
        await _try_link(adapter, "perturbed-closest")
        await _try_link(adapter, "perturbed-aligned", alignment="aligned")
    finally:
        adapter.currentModel = top
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
