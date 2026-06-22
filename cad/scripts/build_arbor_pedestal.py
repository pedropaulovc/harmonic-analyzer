r"""Reproduction script: cylinder-arbor pedestal (book ch. 13 / eight-views).

Rectangular bearing post that clamps one end of the stationary cylinder
arbor (two used, front and back, at z = +/-92). The gears spin freely on
the arbor (DIMENSIONS.md ch. 13 "M6.2 keyway refutation"), so the post
only has to hold the arbor still: a plain block with a clamp bore at the
drive height. The posts are barely visible behind the gate legs in the
eight views (8/8 shows the drum-end hardware) -- proportions are
estimated, function-driven (low confidence).

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive supports" (estimated, low).

Layout: block standing on the Top plane, centred at the origin in plan
(X width x Z depth), bore along Z at y = BORE_HEIGHT.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_arbor_pedestal.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "arbor-pedestal"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

BLOCK_WIDTH = 24.0  # X; estimated, function-driven (low)
BLOCK_DEPTH = 16.0  # Z; estimated, function-driven (low)
BLOCK_HEIGHT = 85.0  # bore at 76 + 9 of material above (low)
BORE_DIA = 0.375 * IN  # 9.525: arbor diameter (ch. 13, legacy, med)
BORE_HEIGHT = 76.0  # ch13 layout: drive height above base top (med)

BORE_RADIUS = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the block's three extents, plus the
    # bore diameter and its drive-height station. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 85 = 85 in). BlockHeight feeds the extrude
    # DEPTH (a feature parameter, not a sketch dim), so it carries no drive job;
    # it stays a declared knob like the exemplars.
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Block footprint on the Top plane (sketch y = global -Z): an origin-centred
    # rectangle, width along X x depth along Z.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BLOCK_WIDTH / 2.0, BLOCK_DEPTH / 2.0, "block", dims=block,
        name_width="Width", drive_width='"BlockWidth"',
        name_depth="Depth", drive_depth='"BlockDepth"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BlockWidth" / 2', '"BlockDepth" / 2'),
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    v_block = BLOCK_WIDTH * BLOCK_DEPTH * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Arbor clamp bore along Z at the drive height. On-axis in X (x 0): only the
    # bore-height centre dim + the diameter are display dims, so the "X" slot is
    # ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreX", "BoreHeight", "BoreDia"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_DEPTH + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * BORE_RADIUS**2 * BLOCK_DEPTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)
    v_final = volume

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pedestal (equations neutral)", v_final, 0.01 * v_bore)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
