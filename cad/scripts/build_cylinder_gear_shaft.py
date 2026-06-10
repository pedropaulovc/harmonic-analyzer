r"""Reproduction script: cylinder gear shaft (book ch. 13, pp. 22-25).

Ø3/8 in steel shaft carrying the 20 identical cylinder gears with their
integral eccentric cams (150 mm sandwich at 7.5 mm axial pitch,
alternating with the black connecting rods that ride the cams). The cams
key onto the shaft (legacy cam keyway 3.2 x 1.5), so the shaft gets a
matching keyseat; it is run from the lower end through the stack span as
a documented simplification (a stack-only keyseat needs an offset-start
cut - Phase 3, M3). Bearing journals into the pedestal bearings at both
ends.

Dimensions: cad/DIMENSIONS.md "Chapter 13" - dia/keyway legacy (med),
length derived from the stack + eight-views 8/8 pedestals (low).

Layout: shaft axis along +Y, keyed end at the origin; keyseat on the +Z
side, y 0..175 (journal 175..200 plain).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cylinder_gear_shaft.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    add_line_chain,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "cylinder-gear-shaft"

SHAFT_DIA = 0.375 * IN  # ch13: = cam bore (legacy parameters.kcl)
SHAFT_LENGTH = 200.0  # ch13: 150 stack + ~25 journal each end (derived)
KEYSEAT_WIDTH = 3.2  # ch13: cam keyway 1/8 in (legacy)
KEYSEAT_DEPTH = 1.5  # ch13: cam keyway 0.06 in (legacy)
KEYSEAT_SPAN = 175.0  # lower end through the stack span (see docstring)

SHAFT_RADIUS = SHAFT_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_RADIUS, "shaft circle")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after shaft: {res.data.volume:.1f} mm^3")
    # expected: pi * 4.7625^2 * 200 = ~14,251 mm^3

    # Keyseat: rectangle past the +Z surface on the Top plane (sketch y is
    # global -Z), cut mid-plane along Y; only y 0..KEYSEAT_SPAN has material
    # inside the rectangle, so the symmetric cut clears exactly the seat.
    seat_floor = SHAFT_RADIUS - KEYSEAT_DEPTH
    half_w = KEYSEAT_WIDTH / 2.0
    check("create_sketch keyseat", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(
        adapter,
        [
            (-half_w, -seat_floor),
            (half_w, -seat_floor),
            (half_w, -SHAFT_RADIUS - 2.0),
            (-half_w, -SHAFT_RADIUS - 2.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "keyseat sketch", fix_entities=lines)
    check("exit_sketch keyseat", await adapter.exit_sketch())
    check(
        "cut keyseat",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=KEYSEAT_SPAN * 2.0, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after keyseat: {res.data.volume:.1f} mm^3")
    # expected: -4.51 mm^2 segment x 175 = -789 -> ~13,462 mm^3

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
