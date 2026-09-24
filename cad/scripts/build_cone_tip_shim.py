r"""Reproduction script: MHA-141 cone tip shim pack (U30 fit-up stack).

The blackened carbon-steel shim pack under the cone tip block (MHA-092): a
15 x 12 pack of leaves cut from shim stock, stacked at fit-up so the block's
adjuster axis lands on the cone axis, then clamped between the swing
platform's top face and the block's foot by the MHA-140 hold-down screw. The
model is ONE solid at the nominal stack (cone_tip_shim_spec.SHIM_T); the
drawing states the stack range and the leaf stock.

Layout: origin at the centre of the bottom face, footprint on the Top plane
(X across the cone shaft, Z along it -- the tip block's own frame), thickness
up +Y. The horseshoe slot (#6 clearance wide) runs from the -X edge to a
full radius centred on the Y axis, coaxial with the block's foot tap when
the pack sits under the block.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_shim.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    define_rectilinear_chain,
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
from cone_tip_shim_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    MANUFACTURING_NOTES,
    SHIM_T,
    SHIM_X,
    SHIM_Z,
    SLOT_OPEN_SIDE,
    SLOT_R,
    SLOT_W,
)

PART_NAME = "cone-tip-shim"
MATERIAL = "Plain Carbon Steel"  # blackened carbon steel shim stock
# The slot's straight run overshoots the open edge so the mouth cuts clean.
SLOT_OVERRUN = 2.0
# Mid-plane cut total from the bottom face: half of it clears the pack.
CUT_DEPTH = 4.0 * SHIM_T


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations); the mm suffix is load-bearing in an
    # inch document.
    await set_global(adapter, "ShimX", f"{SHIM_X}mm")
    await set_global(adapter, "ShimZ", f"{SHIM_Z}mm")
    await set_global(adapter, "ShimT", f"{SHIM_T}mm")
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch shim", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        SHIM_X / 2.0,
        SHIM_Z / 2.0,
        "shim",
        dims=profile,
        name_width="Width",
        drive_width='"ShimX"',
        name_depth="Depth",
        drive_depth='"ShimZ"',
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

    # Horseshoe (Main's ruling, 2026-09-24): the MHA-140 screw passes the
    # pack through an open slot, so leaves slide in and out with the screw
    # backed off.  The platform lock notch's pattern: a straight run from the
    # screw axis out past the open edge, then one full-radius cap cut on the
    # axis.  The width is dimensioned across the run's closed end, on the
    # screw axis, so the print reads it where the radius starts.
    h = SLOT_W / 2.0
    run_end = SLOT_OPEN_SIDE * (SHIM_X / 2.0 + SLOT_OVERRUN)
    slot_pts = [(0.0, -h), (0.0, h), (run_end, h), (run_end, -h)]
    slot = SketchDims()
    check("create_sketch shim slot", await adapter.create_sketch("Top"))
    slot_lines = await add_line_chain(adapter, slot_pts)
    await define_rectilinear_chain(
        adapter,
        slot_lines,
        slot_pts,
        label="shim slot",
        dims=slot,
        names=["SlotWidth", "SlotRun", "SlotEdge"],
        drives=['"SlotW"', None, '"SlotW" / 2'],
    )
    await ensure_fully_defined(adapter, "shim slot sketch")
    check("exit_sketch shim slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    check(
        "cut shim slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Slot")
    v_run = SLOT_W * SHIM_X / 2.0 * SHIM_T
    volume = await volume_check(adapter, "shim slot", volume - v_run, 0.01 * v_run)

    cap = SketchDims()
    check("create_sketch slot end", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SLOT_R,
        "slot end",
        dims=cap,
        names=(None, None, "SlotEndDia"),
        drives=(None, None, '"SlotW"'),
    )
    await ensure_fully_defined(adapter, "slot end sketch")
    check("exit_sketch slot end", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotEndProfile")
    drive_jobs += cap.apply(adapter, "SlotEndProfile")
    check(
        "cut slot end",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SlotEnd")
    # Only the closed half lies in material; the open half is the run's.
    v_cap = math.pi * SLOT_R**2 / 2.0 * SHIM_T
    volume = await volume_check(adapter, "slot end", volume - v_cap, 0.02 * v_cap)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shim (equations neutral)", volume, 0.005 * v_shim
    )

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
