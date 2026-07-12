r"""Reproduction script: rig hold-down slotted screw (book ch. 25; 4 used).

The plain slotted machine screw that bolts the alignment-pinion rig's
pivot blocks down (p. 69 block close-up ``page002_img01``): two bright
heads per block. (The dark screw at frame left -- the spring foot --
is the smaller build_foot_screw: its Ø4 shank cannot fit the 4-wide
spring strip.) Head bears on the block's top face, shank drops through
its Ø4.2 hole into the harmonic base. Slot and thread not modeled (the
M6.10 fillister convention -- below render resolution).

Layout: axis along Y, AUTHORED IN FINAL ORIENTATION (pointing -Y =
down into the base): under-head face on the Top plane at y = 0, head
0..+2.5, shank -18..0. Symmetric about local x = 0.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_slotted_screw.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
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
    volume_check,
)
from _fastener_slot import FastenerAxis, add_slotted_drive

PART_NAME = "slotted-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_DIA = 8.0  # p.69 close-up, scaled vs the 5-thick strap edge (low)
HEAD_H = 2.5
SHANK_DIA = SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
# (rides the Ø4.2 block holes as clearance, threads #8-32 into the base)
SHANK_LEN = SPEC.length_mm  # through the 16-tall block + 2 engagement into the base
# (thread depth unmodeled, the pedestal-bolt precedent)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    # HeadH/ShankLen are extrude DEPTHS (feature parameters) -- declared as
    # knobs, but nothing in drive_jobs references them.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head 0..+2.5: Top-plane sketch, extruded +Y (on-axis circle: only the
    # diameter is a dim).
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head_dims,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_dims.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_H, 0.0)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -18..0 (extruded down from the under-head face).
    shank_dims = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank_dims,
        names=("ShankCx", "ShankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_dims.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, SHANK_LEN, -SHANK_LEN)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    expected, slot_jobs = await add_slotted_drive(
        adapter,
        axis=FastenerAxis.Y,
        head_radius_mm=HEAD_DIA / 2.0,
        head_face_offset_mm=HEAD_H,
        width_mm=1.2,
        depth_mm=1.0,
        expected_volume_mm3=expected,
    )
    drive_jobs += slot_jobs

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven slotted screw (equations neutral)", expected, 0.005 * v_shank
    )

    from solidworks_mcp.adapters.base import CreateAxisParameters

    check(
        "create_axis ScrewAxis (Front ∩ Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Front Plane", "Right Plane"])
        ),
    )
    name_last_feature(adapter, "ScrewAxis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
