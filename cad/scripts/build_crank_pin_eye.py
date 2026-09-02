r"""Reproduction script: crank keeper-ring anchor eyelet (book ch. 11, p. 14).

The small brass wire eye clamped under the slotted anchor screw on the crank
arm's front face (page001_img02): a closed loop of LOOP_R mean radius in
WIRE_DIA wire with a straight TAIL_LEN tail whose end is trapped under the
screw head (the chain that once ran from this eye to the tapered pin's ring
is lost). Modelled as a torus about local Z (loop in the XY plane) plus a
tail cylinder along +Y from the loop's top -- the loop hangs from the tail.

Layout: loop centred on the origin in the XY plane, tail +Y from y = LOOP_R
to LOOP_R + TAIL_LEN; placed flat on the arm face (loop normal = the face
normal) with the tail pointing at the screw.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin_eye.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "crank-pin-eye"
MATERIAL = "Brass"

LOOP_R = 2.0  # mean loop radius (O5 eye, photo-scaled, low)
WIRE_DIA = 1.0  # brass wire (low)
TAIL_LEN = 4.0  # straight tail from the loop's top to under the screw head
V_LOOP = 2.0 * math.pi**2 * LOOP_R * (WIRE_DIA / 2.0) ** 2  # 9.87
V_TAIL = math.pi * (WIRE_DIA / 2.0) ** 2 * TAIL_LEN  # 3.14 (its root merges into the loop)
V_EYE = V_LOOP + V_TAIL


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await set_global(adapter, "LoopR", f"{LOOP_R}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "TailLen", f"{TAIL_LEN}mm")
    drive_jobs: list[tuple[str, str]] = []

    # Loop: a Top-plane sketch maps (x, y) -> global (X, -Z), so a vertical
    # centerline through the origin is the global Z axis and the wire circle
    # at (LoopR, 0) revolves into a torus lying in the XY plane.
    prof = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    centerline = check("axis", await adapter.add_centerline(0.0, -LOOP_R, 0.0, LOOP_R))
    set_sketch_direct_db(adapter, False)
    check("axis vertical", await adapter.add_sketch_constraint(centerline, None, "vertical"))
    check("axis on origin", await adapter.add_sketch_constraint(f"{centerline}.start", "origin", "vertical_points"))
    check("axis length", await adapter.add_sketch_dimension(centerline, None, "linear", 2.0 * LOOP_R))
    prof.record("AxisLen", '2 * "LoopR"')
    await define_circle(
        adapter, LOOP_R, 0.0, WIRE_DIA / 2.0, "wire", dims=prof,
        names=("WireCx", "WireCz", "WireDia"),
        drives=('"LoopR"', None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += prof.apply(adapter, "WireProfile")
    from solidworks_mcp.adapters.base import RevolveParameters

    check("revolve loop", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Loop")
    await volume_check(adapter, "loop", V_LOOP, 0.01 * V_LOOP)

    # Tail: a Top-plane circle on the axis, extruded +Y starting at the loop's
    # wire centre (y = LoopR) so its root fuses into the loop.
    tail = SketchDims()
    check("create_sketch tail", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, WIRE_DIA / 2.0, "tail", dims=tail,
        names=("TailCx", "TailCz", "TailDia"), drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "tail sketch")
    check("exit_sketch tail", await adapter.exit_sketch())
    name_last_feature(adapter, "TailProfile")
    drive_jobs += tail.apply(adapter, "TailProfile")
    extrude_at_offset(adapter, TAIL_LEN, LOOP_R)
    name_last_feature(adapter, "Tail")
    got = await volume_check(adapter, "eye", V_EYE, 0.06 * V_EYE)
    if got < V_LOOP + 0.5 * V_TAIL:
        raise RuntimeError("tail extruded the wrong way (into the loop) -- flip the extrude")

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven eye (equations neutral)", got, 0.001 * got)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
