r"""Reproduction script: brass pull ring for the crank's tapered pin.

The ch. 11 close-ups show a loose brass keeper ring through the mushroom
head of the removable crank pin.  The tiny tether chain once attached to the
separate arm eyelet is documented as lost; this part is only the pull ring.

Layout: a torus centred at the origin, ring plane YZ, symmetry axis +X.
The drive-train keeps that orientation: its top wire segment runs along the
pin-head hole's machine-Z axis, then the ring hangs below in the vertical YZ plane.
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

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"

MAJOR_RADIUS = 7.0
WIRE_DIA = 1.4


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "RingRadius", f"{MAJOR_RADIUS}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")

    profile = SketchDims()
    check("create_sketch pull ring", await adapter.create_sketch("Front"))
    axis = check(
        "add_centerline ring axis",
        await adapter.add_centerline(0.0, 0.0, 2.0 * MAJOR_RADIUS, 0.0),
    )
    check(
        "ring axis start at origin",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check("ring axis horizontal", await adapter.add_sketch_constraint(axis, None, "horizontal"))
    check(
        "ring axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", 2.0 * MAJOR_RADIUS),
    )
    profile.record(None, None)

    await define_circle(
        adapter,
        0.0,
        MAJOR_RADIUS,
        WIRE_DIA / 2.0,
        "pull-ring wire",
        dims=profile,
        names=("WireCx", "RingRadius", "WireDia"),
        drives=(None, '"RingRadius"', '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "pull-ring sketch")
    check("exit_sketch pull ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs = profile.apply(adapter, "RingProfile")
    check(
        "revolve pull ring",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "PullRing")

    # The axis length is construction-only; the two geometry globals drive the
    # actual torus.  Profile equations are applied after the feature exists.
    await force_rebuild(adapter)
    for dim_name, expression in drive_jobs:
        await drive_dimension(adapter, dim_name, expression)
    await force_rebuild(adapter)

    wire_r = WIRE_DIA / 2.0
    expected = 2.0 * math.pi**2 * MAJOR_RADIUS * wire_r**2
    await volume_check(adapter, "brass pull ring", expected, 0.01 * expected)
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
