r"""Reproduction script: gooseneck set screw (book p.45 spec; 1 used).

The period square-head set screw gripping the O16 gooseneck post through
the new top-frame casting's hub (replaces the retired gooseneck-clamp,
MHA-033, whose screw spec it reuses).  In frame.SLDASM the axis runs +X
at (y 1017.95, z 3.088): it threads through the tapped 1/4-20 hole in the
hub rib from the west outer face (x -214.1), the square head standing
off that face by ~7.05, the flat point at x -204.85 (0.15 clear of the
post).  Black oxide; wrench-driven -- no driver slot.  Thread not modeled.

Layout: axis along Y (the frame assembly rotates it to +X): under-head
face on the Top plane at y = 0, square head 10 x 10 spanning 0..+6,
shank -16..0.  Symmetric about local x = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_gooseneck_set_screw.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _common import (
    PANEL_BLACK,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
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
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from gooseneck_set_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_AF,
    HEAD_H,
    SHANK_DIA,
    SHANK_LEN,
)

PART_NAME = "gooseneck-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # black hardware


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    # HeadH/ShankLen are extrude DEPTHS (feature parameters) -- declared as
    # knobs, but nothing in drive_jobs references them.
    await set_global(adapter, "HeadAF", f"{HEAD_AF}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Square head 0..+6: origin-centred 10 x 10 square on the Top plane,
    # extruded +Y.  Width and depth are the only driving dims; both track
    # the HeadAF global.
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, HEAD_AF / 2.0, HEAD_AF / 2.0, "head", dims=head_dims,
        name_width="HeadWDim", drive_width='"HeadAF"',
        name_depth="HeadDDim", drive_depth='"HeadAF"',
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
    v_head = HEAD_AF * HEAD_AF * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -16..0 (extruded down from the under-head face; flat point).
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

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven set screw (equations neutral)", expected, 0.005 * v_shank
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
    await apply_color(adapter, PANEL_BLACK)
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
