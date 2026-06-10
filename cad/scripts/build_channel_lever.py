r"""Reproduction script: channel (top) lever (book ch. 17, pp. 38-41).

One of the 20 cast third-class levers at the top of the machine: fulcrum
pivot at one end, channel-spring pull at the free end, driven in between
by its amplitude bar. Modelled as a flat bar with a rounded, thickened
fulcrum boss (p.40 bottom-left) and a spring-hook hole at the tip (p.39).
The small fork/clip fittings some tips carry (photogrammetry 195527397)
are deferred to the Phase 3 rebuild.

Dimensions: cad/DIMENSIONS.md "Chapter 17" — length scaled from the p.38
inset against the 320 mm lever-bank width (20 x 16 mm ch.14 pitch), all
low confidence except the bank pitch itself.

Layout: lever length along +X from the pivot axis at the origin, bar
height in Y, width extruded +Z. Through-holes use mid-plane blind cuts
(MCP issue #38 workaround).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_channel_lever.py
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

PART_NAME = "channel-lever"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

LEVER_LENGTH = 240.0  # DIMENSIONS.md ch17: pivot-to-spring-hole c2c (low)
TIP_OVERHANG = 8.0  # DIMENSIONS.md ch17: bar past the spring hole (low)
BAR_THICKNESS = 9.5  # DIMENSIONS.md ch17: bar height, p.39 vs spring OD (low)
LEVER_WIDTH = 12.5  # DIMENSIONS.md ch17: matches ch.14 arm-width callout (low)
BOSS_DIA = 19.0  # DIMENSIONS.md ch17: fulcrum boss, p.40 (low)
BOSS_LENGTH = 14.0  # DIMENSIONS.md ch17: boss block past pivot axis (low)
PIVOT_HOLE_DIA = 6.0  # DIMENSIONS.md ch17: clevis pivot pin (low)
SPRING_HOLE_DIA = 3.0  # DIMENSIONS.md ch17: spring hook passes through (low)

BAR_END_X = LEVER_LENGTH + TIP_OVERHANG
HALF_BAR = BAR_THICKNESS / 2.0
HALF_BOSS = BOSS_DIA / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > extrude width


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Side profile: round-nosed boss block (arc + step) then the flat bar.
    check("create_sketch outline", await adapter.create_sketch("Front"))
    # Direct-to-DB: with inferencing on, the step profile picks up
    # redundant auto-relations and the sketch lands over-defined.
    set_sketch_direct_db(adapter, True)
    arc = check(
        "add_arc boss nose",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_BOSS, 0.0, -HALF_BOSS),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_BOSS),
            (BOSS_LENGTH, -HALF_BOSS),
            (BOSS_LENGTH, -HALF_BAR),
            (BAR_END_X, -HALF_BAR),
            (BAR_END_X, HALF_BAR),
            (BOSS_LENGTH, HALF_BAR),
            (BOSS_LENGTH, HALF_BOSS),
            (0.0, HALF_BOSS),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    # Fix-only definition (crank-pin style): a driving dim here would
    # conflict with fixing geometry downstream of it (see _common recipe).
    await ensure_fully_defined(adapter, "lever outline", fix_entities=[arc, *lines])
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude lever",
        await adapter.create_extrusion(ExtrusionParameters(depth=LEVER_WIDTH)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    # Pivot hole + spring-hook hole, one through-cut across the width.
    check("create_sketch holes", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "pivot hole")
    await define_circle(adapter, LEVER_LENGTH, 0.0, SPRING_HOLE_DIA / 2.0, "spring hole")
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after holes: {vol:.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
