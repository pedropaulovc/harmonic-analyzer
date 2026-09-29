r"""Reproduction script: crank-pin keeper ring (book ch. 11, p. 14).

The round brass wire ring hanging from the crank taper pin's head
(page002_img01), threaded through the pin's cross-hole. A torus of MEAN_R on
the wire centreline; the cross-hole is sized for its arc (see
``crank_pin_ring_spec``), and the keeper chain (MHA-149) loops its bottom.

Layout: the origin is on the cross-hole axis (local Z) and the ring lies in
the local XZ plane, its centre RING_CENTRE_X along local +X. The drive train
maps local +X to machine -Y, so the ring hangs below the pin.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin_ring.py
"""

from __future__ import annotations

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
from crank_pin_ring_spec import ARC_SAGITTA, MEAN_R, RING_CENTRE_X, V_RING, WIRE_DIA

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "MeanR", f"{MEAN_R}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    drive_jobs: list[tuple[str, str]] = []

    # Front-plane sketch (x, y) -> global (X, Y): a vertical centerline at
    # x = RING_CENTRE_X is the torus axis (parallel to Y, through the ring
    # centre), and the wire circle at the ring's crown, x = -ARC_SAGITTA / 2 on
    # the hole's Z = 0 section, revolves about it into the ring in the XZ plane.
    prof = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "axis", await adapter.add_centerline(RING_CENTRE_X, 0.0, RING_CENTRE_X, MEAN_R)
    )
    set_sketch_direct_db(adapter, False)
    check("axis vertical", await adapter.add_sketch_constraint(centerline, None, "vertical"))
    await anchor_point_to_origin(
        adapter, f"{centerline}.start", RING_CENTRE_X, 0.0, "ring centre"
    )
    check("axis length", await adapter.add_sketch_dimension(centerline, None, "linear", MEAN_R))
    prof.record("AxisLen", '"MeanR"')
    crown = -ARC_SAGITTA / 2.0
    await define_circle(
        adapter, crown, 0.0, WIRE_DIA / 2.0, "wire", dims=prof,
        names=("WireCx", "WireCy", "WireDia"), drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += prof.apply(adapter, "WireProfile")
    check("revolve ring", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Ring")
    await volume_check(adapter, "keeper ring", V_RING, 0.005 * V_RING)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keeper ring (equations neutral)", V_RING, 0.005 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
