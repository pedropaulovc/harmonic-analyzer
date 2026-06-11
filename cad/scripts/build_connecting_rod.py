r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rough-finished rod converting each cam's rotation into the rocker
arm's see-saw: a full ring (strap) riding the Ø50.8 eccentric cam (cast
integral with each cylinder gear), a thin flat shank, and a flattened tip
strap pinned (Ø2) to the rocker arm's rod-pin hole 1" from the arm pivot.
Centre distance is exactly 5" (127): rocker pivot height 253.8 minus
drive height 126.8 (M6.3 closure). The tip strap matches the arm's
2.5 thickness so the pin joint stacks strap-beside-arm inside the 7.06
channel pitch; the M2 "thick stepped tip blocks" read of p.29 was
amplitude-bar feet, not these rods.

Dimensions: cad/DIMENSIONS.md "Chapter 13 - Connecting rods" - centre
distance derived (high), ring bore derived from the cam OD (med),
everything else photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the tip block;
thicknesses extruded mid-plane in Z. Build order matters: ring disc,
shank and tip block are bossed first, then the bore is cut so the strap
opening also trims the shank sliver that dips into it.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_connecting_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "connecting-rod"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

CENTER_DISTANCE = 127.0  # ch13 rods: 5" cam ring centre -> rocker pin (derived)
RING_BORE_DIA = 51.0  # ch13 rods: cam OD 50.8 + 0.1 clearance per side
RING_WALL = 5.0  # ch13 rods: radial strap wall (scaled)
RING_THICKNESS = 3.0  # ch13 rods: sandwich budget (scaled)
SHANK_WIDTH = 8.0  # ch13 rods: silhouette vs 7 mm gear face (scaled)
SHANK_THICKNESS = 2.5  # ch13 rods: thinner than the ring (scaled)
BLOCK_WIDTH = 10.0  # flattened tip strap (scaled)
BLOCK_LENGTH = 18.0
BLOCK_THICKNESS = 2.5  # = arm thickness: pin joint stacks beside the arm (M6.3)
PIN_HOLE_DIA = 2.0  # ch14: rocker arm rod-end pin
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness

RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 30.5
SHANK_START_Y = RING_BORE_DIA / 2.0 - 0.5  # overlaps the strap annulus
BLOCK_START_Y = CENTER_DISTANCE - BLOCK_LENGTH / 2.0  # pin hole centred


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Ring disc (bore is cut last so it also trims the shank sliver).
    check("create_sketch ring disc", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, RING_OUTER_RADIUS, "ring outer")
    await ensure_fully_defined(adapter, "ring disc sketch")
    check("exit_sketch ring disc", await adapter.exit_sketch())
    check(
        "extrude ring disc",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )

    # Shank: flat bar from the strap up to the tip block.
    check("create_sketch shank", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    shank = await add_line_chain(
        adapter,
        [
            (-SHANK_WIDTH / 2.0, SHANK_START_Y),
            (SHANK_WIDTH / 2.0, SHANK_START_Y),
            (SHANK_WIDTH / 2.0, BLOCK_START_Y),
            (-SHANK_WIDTH / 2.0, BLOCK_START_Y),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "shank sketch", fix_entities=shank)
    check("exit_sketch shank", await adapter.exit_sketch())
    check(
        "extrude shank",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SHANK_THICKNESS, both_directions=True)
        ),
    )

    # Flattened tip strap, pinned beside the rocker arm at assembly.
    check("create_sketch tip block", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    block = await add_line_chain(
        adapter,
        [
            (-BLOCK_WIDTH / 2.0, BLOCK_START_Y),
            (BLOCK_WIDTH / 2.0, BLOCK_START_Y),
            (BLOCK_WIDTH / 2.0, BLOCK_START_Y + BLOCK_LENGTH),
            (-BLOCK_WIDTH / 2.0, BLOCK_START_Y + BLOCK_LENGTH),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "tip block sketch", fix_entities=block)
    check("exit_sketch tip block", await adapter.exit_sketch())
    check(
        "extrude tip block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BLOCK_THICKNESS, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after bosses: {res.data.volume:.1f} mm^3")
    # expected: 8767 disc + 1860 shank - 109 overlap + 450 block = ~10,968

    # Strap bore - rides the eccentric cam.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, RING_BORE_DIA / 2.0, "strap bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut strap bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )

    # Rocker pin hole through the tip block.
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)  # inference near the block edges
    await define_circle(adapter, 0.0, CENTER_DISTANCE, PIN_HOLE_DIA / 2.0, "pin hole")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after cuts: {res.data.volume:.1f} mm^3")
    # expected: -6128 bore -8 sliver -8 pin -> ~4,824 mm^3

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
