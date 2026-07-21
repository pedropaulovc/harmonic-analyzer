r"""Reproduction script: fillister screw (book ch. 20/22; 6 used).

The small brass machine screw used twice over: 4x holding the platen
paper-clip strips through their existing O3 end holes into O3 platen
sockets (ch. 22 p. 55 -- the platen's "fastener holes deferred to
assembly" promise, resolved in the M6.10 fasteners pass), and 2x
fastening the magnifying-lever bracket's flange up into the summing
lever's coefficients plate (ch. 20 p. 47 "mounting screws omitted").
The cylindrical head carries its native 0.8 mm driver slot; thread geometry
is not modeled.

Dimensions: cad/DIMENSIONS.md ch. 20/22 (M6.10) -- shank matches the
clip holes (O3, scaled low); head photo-plausible fillister (low).

Layout: axis along Z, AUTHORED IN FINAL ORIENTATION (pointing +Z =
machine north for the clips; the flange copies rotate Rx(-90) to point
+Y): under-head face on the Front plane at z = 0, head -2.2..0, shank
0..+4. Symmetric about local x = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fillister_screw.py
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
from fillister_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_H,
    SHANK_DIA,
    SHANK_LEN,
)

PART_NAME = "fillister-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright screws on the brass clips


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units). HeadH/ShankLen
    # are extrude depths (feature params, not sketch dims) -- exposed as knobs but
    # nothing drives them, matching the exemplars.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head -2.2..0 (Front sketch, offset extrude up to the under-head plane).
    # On-axis circle (origin): only the diameter is a dim.
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head_dims,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_dims.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_H, -HEAD_H)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank 0..+4 (on-axis circle: only the diameter is a dim).
    shank_dims = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank_dims,
        names=("ShankCx", "ShankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_dims.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, SHANK_LEN, 0.0)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    expected, slot_jobs = await add_slotted_drive(
        adapter,
        axis=FastenerAxis.Z,
        head_radius_mm=HEAD_DIA / 2.0,
        head_face_offset_mm=-HEAD_H,
        width_mm=0.8,
        depth_mm=0.7,
        expected_volume_mm3=expected,
    )
    drive_jobs += slot_jobs

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven fillister screw (equations neutral)", expected, 0.005 * v_shank)

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
