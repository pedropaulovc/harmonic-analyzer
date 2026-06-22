r"""Reproduction script: pen v-block (book ch. 24, pp. 64-65).

The chunky brass block that seats the marker: chamfered top corners, two
vertical bores, a stopped horizontal slit from one end (the flexing clamp
jaw -- it must NOT run the full length or the block would fall apart) and
a small front hole for the clamp/set screw. This is the modern
replacement pen holder (Harland/Wilson) documented by the book photos;
the marker itself is a consumable, not modelled.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — all scaled from the p.65
close-up vs the ~5 mm square rod (low).

Layout: length along +X, height along +Y from the origin corner, depth
extruded +Z. Vertical bores cut from a Top-plane sketch (maps (x, y) ->
global (X, -Z)); slit and front hole from Front-plane sketches.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_v_block.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "pen-v-block"
MATERIAL = "Brass"  # see _common.apply_material docstring

BLOCK_LENGTH = 32.0  # X  DIMENSIONS.md ch24: p.65 vs 5 mm rod (low)
BLOCK_HEIGHT = 18.0  # Y
BLOCK_DEPTH = 16.0  # Z
CHAMFER = 6.0  # 45 deg top corners
BORE_DIA = 8.0  # two vertical bores
BORE_X = (11.0, 21.0)
SLIT_LENGTH = 26.0  # stopped cut from x=0; hinge remains 26..32
SLIT_Y = (4.0, 8.0)  # slit band
SCREW_HOLE_DIA = 2.5  # front-face clamp/set screw hole
SCREW_HOLE_XY = (29.0, 11.0)

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Outline with 45-degree chamfered top corners (sloped lines need
    # direct-to-DB so inference cannot snap them).
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    outline_pts = [
        (0.0, 0.0),
        (BLOCK_LENGTH, 0.0),
        (BLOCK_LENGTH, BLOCK_HEIGHT - CHAMFER),
        (BLOCK_LENGTH - CHAMFER, BLOCK_HEIGHT),
        (CHAMFER, BLOCK_HEIGHT),
        (0.0, BLOCK_HEIGHT - CHAMFER),
    ]
    lines = await add_line_chain(adapter, outline_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, lines, outline_pts, label="block outline")
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    # Two vertical bores along Y.
    check("create_sketch bores", await adapter.create_sketch("Top"))
    for i, bx in enumerate(BORE_X):
        await define_circle(
            adapter, bx, -BLOCK_DEPTH / 2.0, BORE_DIA / 2.0, f"bore {i + 1}"
        )
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after bores: {vol:.1f} mm^3")

    # Stopped clamp slit through Z from the x=0 end.
    check("create_sketch slit", await adapter.create_sketch("Front"))
    slit_rect = [
        (0.0, SLIT_Y[0]),
        (SLIT_LENGTH, SLIT_Y[0]),
        (SLIT_LENGTH, SLIT_Y[1]),
        (0.0, SLIT_Y[1]),
    ]
    slit = await add_line_chain(adapter, slit_rect)
    await define_rectilinear_chain(adapter, slit, slit_rect, label="slit")
    await ensure_fully_defined(adapter, "slit sketch")
    check("exit_sketch slit", await adapter.exit_sketch())
    check(
        "cut slit",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after slit: {vol:.1f} mm^3")

    # Front-face screw hole along Z.
    check("create_sketch screw hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, SCREW_HOLE_XY[0], SCREW_HOLE_XY[1], SCREW_HOLE_DIA / 2.0, "screw hole"
    )
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw hole", await adapter.exit_sketch())
    check(
        "cut screw hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after screw hole: {vol:.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
