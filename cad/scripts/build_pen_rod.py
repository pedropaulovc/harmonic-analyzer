r"""Reproduction script: pen square rod (book ch. 24, pp. 64-65).

The square brass rod that carries the v-block; the wire from the
magnifying wheel ties into the cross hole near its top, so the rod (and
pen) mirror the summed motion vertically.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — ~5 mm square photo-scaled
(low); length ~120 from the p.64 inset (low).

Layout: length along +Y from the origin (assembly orientation), section
centred on the origin in X, extruded +Z; wire hole along Z near the top.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pen_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "pen-rod"

ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
ROD_LENGTH = 120.0  # DIMENSIONS.md ch24: p.64 inset (low)
WIRE_HOLE_DIA = 2.0  # wire tie-off near the top
WIRE_HOLE_Y = 115.0
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > section


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch section", await adapter.create_sketch("Front"))
    lines = await add_line_chain(
        adapter,
        [
            (-ROD_SECTION / 2.0, 0.0),
            (ROD_SECTION / 2.0, 0.0),
            (ROD_SECTION / 2.0, ROD_LENGTH),
            (-ROD_SECTION / 2.0, ROD_LENGTH),
        ],
    )
    await ensure_fully_defined(adapter, "rod outline", fix_entities=lines)
    check("exit_sketch section", await adapter.exit_sketch())
    check(
        "extrude rod",
        await adapter.create_extrusion(ExtrusionParameters(depth=ROD_SECTION)),
    )

    check("create_sketch wire hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, WIRE_HOLE_Y, WIRE_HOLE_DIA / 2.0, "wire hole")
    await ensure_fully_defined(adapter, "wire hole sketch")
    check("exit_sketch wire hole", await adapter.exit_sketch())
    check(
        "cut wire hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
