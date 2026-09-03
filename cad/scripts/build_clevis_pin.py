r"""Reproduction script: connecting-rod/rocker clevis pin (20 used).

The ch. 14 close-ups ``ch14_images/page002_img02.png`` and
``page002_img01.jpeg`` show one bright round pin head on every dark
connecting-rod clevis cheek.  The polished-steel pin traverses both #47 cheek
holes and the reduced rocker tongue without changing the J2 revolute geometry.

Layout: axis local Z, origin on the visible front-cheek outer face.  The Ø1.8
shank spans z = 0..4.9 and the flat Ø3.0 head spans z = -0.6..0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_clevis_pin.py
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
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties
from clevis_pin_notes import DRAWING_DIMENSIONS, DRAWING_NOTES, END_VIEW_NOTE
from clevis_pin_spec import (
    GRIP_LENGTH,
    HEAD_DIA,
    HEAD_THICKNESS,
    SHANK_DIA,
    SHANK_DIA_BAND,
)

PART_NAME = "clevis-pin"
MATERIAL = "Plain Carbon Steel"

V_SHANK = math.pi * (SHANK_DIA / 2.0) ** 2 * GRIP_LENGTH
V_HEAD = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_THICKNESS
V_TOTAL = V_SHANK + V_HEAD


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing in the
    # inch document template; every named feature dimension is driven below.
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "GripLength", f"{GRIP_LENGTH}mm")
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadThickness", f"{HEAD_THICKNESS}mm")
    drive_jobs: list[tuple[str, str]] = []

    # Shank: origin/front-cheek seat -> local +Z across the complete clevis.
    shank = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SHANK_DIA / 2.0,
        "shank",
        dims=shank,
        names=("ShankCx", "ShankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    check(
        "extrude shank",
        await adapter.create_extrusion(ExtrusionParameters(depth=GRIP_LENGTH)),
    )
    name_last_feature(adapter, "Shank")
    grip_dim = name_dimensions(adapter, "Shank", ["GripLength"])
    drive_jobs.append((grip_dim[0], '"GripLength"'))
    volume = await volume_check(adapter, "shank", V_SHANK, 0.005 * V_SHANK)

    # Flat circular head: the same z=0 seat, extruded toward machine-front in
    # local -Z.  Its shared circular face merges it into the shank as one solid.
    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        HEAD_DIA / 2.0,
        "head",
        dims=head,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check(
        "extrude head toward -Z",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HEAD_THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Head")
    head_depth = name_dimensions(adapter, "Head", ["HeadThickness"])
    drive_jobs.append((head_depth[0], '"HeadThickness"'))
    volume = await volume_check(adapter, "head", V_TOTAL, 0.01 * V_HEAD)

    # Axis1 is the local-Z centreline consumed by assembly inspection/mates.
    axis_name = await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", 0.0, "clevis-pin axis"
    )
    if axis_name != "Axis1":
        raise RuntimeError(f"clevis-pin centreline must be Axis1, got {axis_name!r}")

    # Apply neutral equations only after all geometry exists, then prove that
    # the equation-driven rebuild preserves the as-authored solid volume.
    await force_rebuild(adapter)
    for dim_name, expression in drive_jobs:
        await drive_dimension(adapter, dim_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven clevis pin (equations neutral)", volume, 0.005 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter,
        "ShankProfile",
        "ShankDia",
        *deviations(SHANK_DIA_BAND),
    )
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
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
