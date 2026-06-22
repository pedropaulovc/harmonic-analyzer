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

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
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


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Block outline: rectangle with a corner vertex on the origin.
    check("create_sketch outline", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_WIDTH / 2.0, 0.0),
        (BLOCK_WIDTH / 2.0, 0.0),
        (BLOCK_WIDTH / 2.0, BLOCK_HEIGHT),
        (-BLOCK_WIDTH / 2.0, BLOCK_HEIGHT),
    ]
    lines = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(adapter, lines, block_rect, label="block")
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    # Lever bore along Z.
    check("create_sketch lever bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, LEVER_BORE_Y, LEVER_BORE_DIA / 2.0, "lever bore")
    await ensure_fully_defined(adapter, "lever bore sketch")
    check("exit_sketch lever bore", await adapter.exit_sketch())
    check(
        "cut lever bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after lever bore: {vol:.1f} mm^3")

    # Vertical-rod bore + thumb-screw hole, both along Y from the Top plane
    # (sketch y maps to global -Z; the block spans Z 0..BLOCK_DEPTH).
    check("create_sketch y-bores", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, ROD_BORE_X, -BLOCK_DEPTH / 2.0, ROD_BORE_DIA / 2.0, "rod bore"
    )
    await define_circle(
        adapter, 0.0, -BLOCK_DEPTH / 2.0, SCREW_HOLE_DIA / 2.0, "screw hole"
    )
    await ensure_fully_defined(adapter, "y-bores sketch")
    check("exit_sketch y-bores", await adapter.exit_sketch())
    check(
        "cut y-bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after y-bores: {vol:.1f} mm^3")

    # Named lever-bore axis (local Z through (0, LEVER_BORE_Y)) so the clamp
    # rides the magnifying rod as a concentric slider in the M6 assembly.
    await name_bore_axis(
        adapter, "Top Plane", LEVER_BORE_Y, "Right Plane", 0.0, "lever bore axis"
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
