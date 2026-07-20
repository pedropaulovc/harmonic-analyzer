r"""Reproduction script: crank-pin brass pull ring (book ch. 11, pp. 14-15).

The open brass C-ring riding the tapered pin's neck cross-hole
(``ch11_images/page002_img01``): round Ø1.5 wire, Ø14 over the wire, with
a 60 deg gap -- the split ring the pin is pulled by. Modelled as a 300 deg
partial revolve of the wire section, so the gap ends are flat radial faces.

Dimensions: crank_pin_spec.py (photo-scaled, low).

Layout: ring axis along local Y through the origin (the plane of the ring
is XZ); the wire-centre circle has radius RING_MEAN_R. The revolve starts
at the sketch's +X station and sweeps 300 deg, leaving the gap CENTRED on
the -X axis of the part -- the assembly aims it by rotation about Y.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin_ring.py
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
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from crank_pin_spec import RING_MEAN_R, RING_SWEEP_DEG, RING_WIRE_DIA

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"  # see _common.apply_material docstring


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "RingMeanR", f"{RING_MEAN_R}mm")
    await set_global(adapter, "RingWireDia", f"{RING_WIRE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Wire section on Front (XY): a circle at (+RING_MEAN_R, 0) revolved about
    # a Y centerline through the origin.
    wire = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Front"))
    centerline = check(
        "add_centerline ring axis",
        await adapter.add_centerline(0.0, -RING_MEAN_R, 0.0, RING_MEAN_R),
    )
    check(
        "axis vertical",
        await adapter.add_sketch_constraint(centerline, None, "vertical"),
    )
    check(
        "axis through origin",
        await adapter.add_sketch_constraint(f"{centerline}.start", "origin", "vertical_points"),
    )
    await define_circle(
        adapter, RING_MEAN_R, 0.0, RING_WIRE_DIA / 2.0, "wire", dims=wire,
        names=("WireCx", "WireCy", "WireDia"),
        drives=('"RingMeanR"', None, '"RingWireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += wire.apply(adapter, "WireProfile")

    check(
        "revolve ring",
        await adapter.create_revolve(RevolveParameters(angle=RING_SWEEP_DEG)),
    )
    name_last_feature(adapter, "Ring")

    # Pappus: V = sweep-fraction * 2*pi*R_mean * wire area.
    wire_r = RING_WIRE_DIA / 2.0
    v_ring = (RING_SWEEP_DEG / 360.0) * 2.0 * math.pi * RING_MEAN_R * math.pi * wire_r**2
    await volume_check(adapter, "ring", v_ring, 0.01 * v_ring)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven ring (equations neutral)", v_ring, 0.01 * v_ring)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
