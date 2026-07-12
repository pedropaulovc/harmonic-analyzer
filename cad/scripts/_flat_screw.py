r"""Shared builder for plain cylindrical-head machine screws.

The fillister/slotted screw family is one shape -- a cylindrical head under
a plain shank, slot and thread not modeled -- so the new paper-drive screws
(clamp-screw, bracket-screw) share this builder instead of cloning the
fillister script again. Layout: axis along Z, under-head face on the Front
plane at z = 0, head -head_h..0, shank 0..+shank_len; symmetric about
local x = 0.
"""

from __future__ import annotations

import math
from typing import Any

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
    save_part_and_images,
    set_global,
    volume_check,
)


async def build_flat_screw(
    adapter: Any,
    *,
    part_name: str,
    material: str,
    head_dia: float,
    head_h: float,
    shank_dia: float,
    shank_len: float,
) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units). HeadH/ShankLen
    # are extrude depths (feature params, not sketch dims) -- exposed as knobs but
    # nothing drives them, matching the fillister exemplar.
    await set_global(adapter, "HeadDia", f"{head_dia}mm")
    await set_global(adapter, "HeadH", f"{head_h}mm")
    await set_global(adapter, "ShankDia", f"{shank_dia}mm")
    await set_global(adapter, "ShankLen", f"{shank_len}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head (Front sketch, offset extrude up to the under-head plane).
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, head_dia / 2.0, "head", dims=head_dims,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_dims.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, head_h, -head_h)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (head_dia / 2.0) ** 2 * head_h
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank 0..+shank_len.
    shank_dims = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, shank_dia / 2.0, "shank", dims=shank_dims,
        names=("ShankCx", "ShankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_dims.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, shank_len, 0.0)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (shank_dia / 2.0) ** 2 * shank_len
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, f"driven {part_name} (equations neutral)", expected, 0.005 * v_shank
    )

    # Stable assembly datum for physical coaxial mates.  The screw is built on
    # the Front plane, so its shank runs along local Z at the intersection of
    # the Top and Right planes.  A named reference axis avoids selecting a
    # cylindrical face (fragile after feature rebuilds) and gives every user of
    # this shared screw family the same mate contract.
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check(
        "create_axis ScrewAxis (Top ∩ Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    name_last_feature(adapter, "ScrewAxis")

    await apply_material(adapter, material)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, part_name)
