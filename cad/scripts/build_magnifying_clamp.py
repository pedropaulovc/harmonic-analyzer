r"""Reproduction script: magnifying-lever clamp block (book ch. 20, p. 48).

The square block that slides along the magnifying lever and carries the
vertical rod beside it; the reeded thumb screw clamps it from the top.
The two rod bores are skew (offset across the block) so the rods pass
without touching, as in the p.48 close-up.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — all photo-scaled vs the Ø6
lever rod (low). Bores get 0.2 mm clearance over their rods.

Layout: lever bore along Z (the extrude direction) through the block's
upper portion; vertical-rod bore along Y, offset in X; thumb-screw hole
along Y above the lever bore. Through-holes are mid-plane blind cuts
(MCP issue #38 workaround); the Top-plane sketch maps (x, y) ->
global (X, -Z).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_clamp.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

PART_NAME = "magnifying-clamp"
MATERIAL = "Brass"  # see _common.apply_material docstring

BLOCK_WIDTH = 20.0  # X  DIMENSIONS.md ch20: clamp block, p.48 (low)
BLOCK_HEIGHT = 26.0  # Y
BLOCK_DEPTH = 12.0  # Z
LEVER_BORE_DIA = 6.2  # Ø6 lever + clearance
LEVER_BORE_Y = 19.0  # bore centre height
ROD_BORE_DIA = 5.2  # Ø5 vertical rod + clearance
ROD_BORE_X = 6.5  # skew offset from the lever bore axis plane
SCREW_HOLE_DIA = 3.0  # thumb-screw shank

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): block envelope plus the three bore
    # diameters and their in-plane stations. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 20 = 20 in, blowing the part up 25.4x).
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "LeverBoreDia", f"{LEVER_BORE_DIA}mm")
    await set_global(adapter, "LeverBoreY", f"{LEVER_BORE_Y}mm")
    await set_global(adapter, "RodBoreDia", f"{ROD_BORE_DIA}mm")
    await set_global(adapter, "RodBoreX", f"{ROD_BORE_X}mm")
    await set_global(adapter, "ScrewHoleDia", f"{SCREW_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Block outline: rectangle with its bottom edge on the X axis, centred in X
    # (corner vertex at (-W/2, 0)). NOT origin-centred, so it stays a
    # define_rectilinear_chain. Emission order is width (bottom segment), height
    # (one side segment), then the anchor X (anchor vertex at x=-W/2, y=0 -> only
    # the X dim; y=0 emits no dim): three display dims.
    block = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_WIDTH / 2.0, 0.0),
        (BLOCK_WIDTH / 2.0, 0.0),
        (BLOCK_WIDTH / 2.0, BLOCK_HEIGHT),
        (-BLOCK_WIDTH / 2.0, BLOCK_HEIGHT),
    ]
    lines = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter, lines, block_rect, label="block", dims=block,
        names=["Width", "Height", "AnchorX"],
        drives=['"BlockWidth"', '"BlockHeight"', '"BlockWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    name_last_feature(adapter, "Block")
    v_block = BLOCK_WIDTH * BLOCK_HEIGHT * BLOCK_DEPTH
    await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Lever bore along Z. On-axis in X (centre x=0), off-axis in y (the bore
    # height), so define_circle emits the Z/height dim then the diameter -- the X
    # slot is ignored.
    lever = SketchDims()
    check("create_sketch lever bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, LEVER_BORE_Y, LEVER_BORE_DIA / 2.0, "lever bore",
        dims=lever,
        names=("LeverCx", "LeverBoreYDim", "LeverBoreDiaDim"),
        drives=(None, '"LeverBoreY"', '"LeverBoreDia"'),
    )
    await ensure_fully_defined(adapter, "lever bore sketch")
    check("exit_sketch lever bore", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverBoreProfile")
    drive_jobs += lever.apply(adapter, "LeverBoreProfile")
    check(
        "cut lever bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBore")
    v_lever = math.pi * (LEVER_BORE_DIA / 2.0) ** 2 * BLOCK_DEPTH
    await volume_check(adapter, "lever bore", v_block - v_lever, 0.005 * v_block)

    # Vertical-rod bore + thumb-screw hole, both along Y from the Top plane
    # (sketch y maps to global -Z; the block spans Z 0..BLOCK_DEPTH). The rod
    # bore is off-axis in both x (skew station) and z (depth mid-plane), so it
    # emits X, Z, then diameter; the screw hole is on-axis in x, so it emits only
    # Z then diameter.
    ybores = SketchDims()
    check("create_sketch y-bores", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, ROD_BORE_X, -BLOCK_DEPTH / 2.0, ROD_BORE_DIA / 2.0, "rod bore",
        dims=ybores,
        names=("RodBoreXDim", "RodBoreZ", "RodBoreDiaDim"),
        drives=('"RodBoreX"', '"BlockDepth" / 2', '"RodBoreDia"'),
    )
    await define_circle(
        adapter, 0.0, -BLOCK_DEPTH / 2.0, SCREW_HOLE_DIA / 2.0, "screw hole",
        dims=ybores,
        names=("ScrewCx", "ScrewHoleZ", "ScrewHoleDiaDim"),
        drives=(None, '"BlockDepth" / 2', '"ScrewHoleDia"'),
    )
    await ensure_fully_defined(adapter, "y-bores sketch")
    check("exit_sketch y-bores", await adapter.exit_sketch())
    name_last_feature(adapter, "YBoresProfile")
    drive_jobs += ybores.apply(adapter, "YBoresProfile")
    check(
        "cut y-bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "YBores")
    # The two Y bores run the full block height; their overlaps with the lever
    # bore (the screw hole crosses it on the X axis) have no clean closed form,
    # so a loose tol absorbs the double-counted intersections.
    v_rod = math.pi * (ROD_BORE_DIA / 2.0) ** 2 * BLOCK_HEIGHT
    v_screw = math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * BLOCK_HEIGHT
    v_final = v_block - v_lever - v_rod - v_screw
    # ~42 mm^3 of lever-bore x Y-bore intersection is double-subtracted above
    # (no closed form), so the loose tol must clear it while still catching a
    # gross (unit-blowup) error.
    await volume_check(adapter, "y-bores", v_final, 80.0)

    # Named lever-bore axis (local Z through (0, LEVER_BORE_Y)) so the clamp
    # rides the magnifying rod as a concentric slider in the M6 assembly.
    await name_bore_axis(
        adapter, "Top Plane", LEVER_BORE_Y, "Right Plane", 0.0, "lever bore axis"
    )

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven magnifying clamp (equations neutral)", v_final, 80.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
