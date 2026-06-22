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
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
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

    # Block footprint on the Top plane (sketch y = global -Z).
    half_w = BLOCK_WIDTH / 2.0
    half_d = BLOCK_DEPTH / 2.0
    check("create_sketch block", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    footprint = [
        (-half_w, -half_d),
        (half_w, -half_d),
        (half_w, half_d),
        (-half_w, half_d),
    ]
    lines = await add_line_chain(adapter, footprint)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(adapter, lines, footprint, label="block")
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    v_block = BLOCK_WIDTH * BLOCK_DEPTH * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Arbor clamp bore along Z at the drive height.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_DEPTH + 4.0, both_directions=True)
        ),
    )
    v_bore = math.pi * BORE_RADIUS**2 * BLOCK_DEPTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
