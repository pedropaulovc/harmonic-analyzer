r"""Reproduction script: top-frame boss side screw (ch30 evidence; 4 used).

One of the four slotted cheese-head screws pinning the new top-frame
casting's corner bosses to the tube-frame columns: axes along Z at
(x +/-197, y 1017.95), the front pair driven from the front (heads at
z -137.6 behind a O9 x 0.5 spot-face on the O52.2 boss), the rear pair
from the rear (+137.6).  Each threads into a tapped #10-24 boss hole;
the tip stops 0.15 short of the column surface.  Thread not modeled.

Layout: axis along Y (the frame assembly rotates it to +/-Z): under-head
face on the Top plane at y = 0, cheese head 0..+3 with the driver slot on
top, shank -12.7..0.  Symmetric about local x = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_frame_side_screw.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _fastener_slot import FastenerAxis, add_slotted_drive
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from frame_side_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_H,
    SHANK_DIA,
    SHANK_LEN,
    SLOT_D,
    SLOT_W,
)

PART_NAME = "frame-side-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright hardware


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

    # Head 0..+3: Top-plane sketch, extruded +Y (on-axis circle: only the
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
    # Name the extrude DEPTH dim so the drawing can insert it as the head-height
    # model dimension (the depth is the first display dim of a blind boss).
    name_dimensions(adapter, "Head", ["HeadHt"])
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -12.7..0 (extruded down from the under-head face).
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
    name_dimensions(adapter, "Shank", ["ShankLg"])
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    expected, slot_jobs = await add_slotted_drive(
        adapter,
        axis=FastenerAxis.Y,
        head_radius_mm=HEAD_DIA / 2.0,
        head_face_offset_mm=HEAD_H,
        width_mm=SLOT_W,
        depth_mm=SLOT_D,
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
        adapter, "driven side screw (equations neutral)", expected, 0.005 * v_shank
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
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
