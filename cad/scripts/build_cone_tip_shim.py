r"""Reproduction script: MHA-141 cone tip shim pack (U30 fit-up stack).

The blackened carbon-steel shim pack under the cone tip block (MHA-092): a
15 x 12 pack of leaves cut from shim stock, stacked at fit-up so the block's
adjuster axis lands on the cone axis, then clamped between the swing
platform's top face and the block's foot by the MHA-140 hold-down screw. The
model is ONE solid at the nominal stack (cone_tip_shim_spec.SHIM_T); the
drawing states the stack range and the leaf stock.

Layout: origin at the centre of the bottom face, footprint on the Top plane
(X across the cone shaft, Z along it -- the tip block's own frame), thickness
up +Y. The #6 clearance hole is on the Y axis, coaxial with the block's
foot tap when the pack sits under the block.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_shim.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    drive_dimension,
    ensure_fully_defined,
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
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import DIAMETER_TOLERANCE_MM, wizard_holes
from cone_tip_shim_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HOLE_DIA,
    HOLE_SPEC,
    MANUFACTURING_NOTES,
    SHIM_T,
    SHIM_X,
    SHIM_Z,
)

PART_NAME = "cone-tip-shim"
MATERIAL = "Plain Carbon Steel"  # blackened carbon steel shim stock


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations); the mm suffix is load-bearing in an
    # inch document.
    await set_global(adapter, "ShimX", f"{SHIM_X}mm")
    await set_global(adapter, "ShimZ", f"{SHIM_Z}mm")
    await set_global(adapter, "ShimT", f"{SHIM_T}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch shim", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, SHIM_X / 2.0, SHIM_Z / 2.0, "shim", dims=profile,
        name_width="Width", drive_width='"ShimX"',
        name_depth="Depth", drive_depth='"ShimZ"',
    )
    await ensure_fully_defined(adapter, "shim sketch")
    check("exit_sketch shim", await adapter.exit_sketch())
    name_last_feature(adapter, "ShimProfile")
    drive_jobs += profile.apply(adapter, "ShimProfile")
    check(
        "extrude shim",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHIM_T)),
    )
    name_last_feature(adapter, "Shim")
    thickness_dim = name_dimensions(adapter, "Shim", ["Thickness"])
    drive_jobs += [(thickness_dim[0], '"ShimT"')]
    v_shim = SHIM_X * SHIM_Z * SHIM_T
    volume = await volume_check(adapter, "shim", v_shim, 0.005 * v_shim)

    # The MHA-140 screw passes through every leaf on the block's foot-tap
    # axis: one native #6 clearance hole through the pack at the origin.
    hole = wizard_holes(
        adapter,
        HOLE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"hold-down screw clearance ({HOLE_SPEC.size} {HOLE_SPEC.fit} through)",
        name="ScrewHole",
    )
    if abs(hole.hole_dia_mm - HOLE_DIA) > DIAMETER_TOLERANCE_MM:
        raise RuntimeError(
            f"shim screw hole cut Ø{hole.hole_dia_mm:.4f} != spec Ø{HOLE_DIA}"
        )
    v_hole = math.pi * (HOLE_DIA / 2.0) ** 2 * SHIM_T
    volume = await volume_check(adapter, "screw hole", volume - v_hole, 0.02 * v_hole)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven shim (equations neutral)", volume, 0.005 * v_shim)

    apply_drawing_precision(adapter, DRAWING_PRECISION)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, extra={"Manufacturing Notes": MANUFACTURING_NOTES}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
