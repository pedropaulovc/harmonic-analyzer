r"""Reproduction script: channel (top) lever (book ch. 17, pp. 38-41).

One of the 20 cast third-class levers at the top of the machine: fulcrum
pivot at one end (Ø6.5 hole riding the common Ø6.35 fulcrum shaft - the
p.40 ball clevis is the shaft's END mount, mirroring the rocker-pivot
design), channel-spring pull at the free end (Ø3 hook hole at 254 = 10"),
driven in between by its amplitude bar pinned Ø2 at 127 (5") - an exact
2:1 motion ratio. Section 9.5 tall x 3.0 thick: 20 levers at the 7.0565
channel pitch cap the thickness (the M2 12.5 "width" violated the pitch),
and 3.0 lets the bar's 3.2 top slot straddle the lever at the pin. The
small fork/clip fittings some tips carry (photogrammetry 195527397)
remain deferred.

Dimensions: cad/DIMENSIONS.md "Chapter 17" - lengths/section derived in
M6.3 (med), hole diameters low.

Layout: lever length along +X from the pivot axis at the origin, bar
height in Y, thickness extruded mid-plane in Z. Through-holes use
mid-plane blind cuts (MCP issue #38 workaround).

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

LEVER_LENGTH = 254.0  # DIMENSIONS.md ch17: fulcrum-to-spring-hole c2c, 10" (derived)
TIP_OVERHANG = 8.0  # DIMENSIONS.md ch17: bar past the spring hole (low)
BAR_TALL = 9.5  # DIMENSIONS.md ch17: bar height, p.39 vs spring OD (low)
LEVER_THICKNESS = 3.0  # DIMENSIONS.md ch17: fits 7.06 pitch + 3.2 bar slot (derived)
PIVOT_HOLE_DIA = 6.5  # DIMENSIONS.md ch17: rides the 6.35 fulcrum shaft (derived)
BAR_PIN_HOLE_DIA = 2.0  # DIMENSIONS.md ch17: amplitude-bar top pin (derived)
BAR_PIN_X = 127.0  # 5" from the fulcrum = half the spring c2c (derived)
SPRING_HOLE_DIA = 3.0  # DIMENSIONS.md ch17: spring hook passes through (low)

BAR_END_X = LEVER_LENGTH + TIP_OVERHANG
HALF_BAR = BAR_TALL / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > extrude width


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Side profile: round-nosed flat bar (arc about the fulcrum + 3 lines).
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    arc = check(
        "add_arc fulcrum nose",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_BAR, 0.0, -HALF_BAR),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_BAR),
            (BAR_END_X, -HALF_BAR),
            (BAR_END_X, HALF_BAR),
            (0.0, HALF_BAR),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "lever outline", fix_entities=[arc, *lines])
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude lever",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LEVER_THICKNESS, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")
    # expected: (262 * 9.5 + pi/2 * 4.75^2) * 3.0 = ~7,573 mm^3

    # Fulcrum hole + bar-pin hole + spring-hook hole, one mid-plane cut.
    check("create_sketch holes", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "fulcrum hole")
    await define_circle(adapter, BAR_PIN_X, 0.0, BAR_PIN_HOLE_DIA / 2.0, "bar pin hole")
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
    # expected: -3.0 * pi * (3.25^2 + 1^2 + 1.5^2) = ~7,442 mm^3

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
