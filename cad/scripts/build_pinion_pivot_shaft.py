r"""Reproduction script: pinion strap torque shaft (book ch. 25).

The plain Ø6.35 rod the two pinion swing brackets pivot on, running
parallel under the alignment-pinion drum through both pivot blocks'
east bores (p. 68 close-ups; the engage lever and its cam pins live on
the SEPARATE lift rod in the west bores -- build_pinion_lift_rod.py).

Layout: shaft axis Z, z 0..196.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_pivot_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "pinion-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)

SHAFT_DIA = 6.35  # rides the strap and block bores (derived)
SHAFT_LEN = 196.0  # machine z -106..+90: through both straps and blocks
# with 2 proud past each block face (the front block sits forward at
# z -104..-92, dodging the cone-pivot-post column) (derived)

SHAFT_R = SHAFT_DIA / 2.0
V_SHAFT = math.pi * SHAFT_R**2 * SHAFT_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 6.35 = 6.35 in). The
    # extrude length is a feature parameter (built with the literal below);
    # ShaftLen is declared so a GUI edit sees the knob.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLen", f"{SHAFT_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis rod (origin centre): define_circle emits only the diameter dim, so
    # only the "Dia" slot is recorded -- the X/Z names are ignored.
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_R, "shaft", dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDia"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LEN)),
    )
    name_last_feature(adapter, "Shaft")
    await volume_check(adapter, "shaft", V_SHAFT, 0.005 * V_SHAFT)

    # Named central axis (Axis1) for the assembly swing revolute: the pinion
    # swing group pivots on this shaft (p2 engage DOF, build_drive_train).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "shaft axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven shaft (equations neutral)", V_SHAFT, 0.005 * V_SHAFT)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
