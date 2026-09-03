r"""Reproduction script: crank-pin keeper ring (book ch. 11, p. 14).

The small brass wire ring hanging from the crank taper pin's head (ch11
page002_img01: a ring through a hole in the pin's big end -- the keeper the
lost chain once ran to). A plain torus: mean radius RING_R, wire WIRE_DIA.

Layout: revolved about the Y axis (the ring's axis) from a Front-plane wire
circle at (RING_R, 0); the drive-train turns +Y to machine Z so the ring
hangs in the crank arm's plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin_ring.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"

RING_R = 4.5  # mean radius (O9 ring, p.14 photo-scaled, low)
WIRE_DIA = 1.2  # brass wire (low)
RING_INNER_R = RING_R - WIRE_DIA / 2.0  # 3.9
V_RING = 2.0 * math.pi**2 * RING_R * (WIRE_DIA / 2.0) ** 2  # 31.98


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "RingR", f"{RING_R}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    drive_jobs: list[tuple[str, str]] = []

    prof = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check("axis", await adapter.add_centerline(0.0, -RING_R, 0.0, RING_R))
    set_sketch_direct_db(adapter, False)
    check("axis vertical", await adapter.add_sketch_constraint(centerline, None, "vertical"))
    await anchor_point_to_origin(
        adapter, f"{centerline}.start", 0.0, -RING_R, "axis start"
    )
    prof.record("AxisStartY", '"RingR"')
    check("axis length", await adapter.add_sketch_dimension(centerline, None, "linear", 2.0 * RING_R))
    prof.record("AxisLen", '2 * "RingR"')
    await define_circle(
        adapter, RING_R, 0.0, WIRE_DIA / 2.0, "wire", dims=prof,
        names=("WireCx", "WireCz", "WireDia"),
        drives=('"RingR"', None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += prof.apply(adapter, "WireProfile")
    check("revolve ring", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Ring")
    await volume_check(adapter, "ring", V_RING, 0.01 * V_RING)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven ring (equations neutral)", V_RING, 0.01 * V_RING)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
