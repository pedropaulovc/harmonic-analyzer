r"""Reproduction script: tube frame column (legacy part; book ch. 5-6).

Hollow brass column carrying the upper frame rails: Ø1.375 in tube with a
0.12 in wall (legacy SLDPRT, interrogated live - no source survives).
Length corrected to the book: ch. 6 states the frame columns are 107 cm
tall, while the legacy file was 1016 mm (40 in); the book annotation wins
per the M1 source hierarchy, so this re-author uses 1070 mm.

Deferred: the photogrammetry (PHOTOS.md 195108425/195123524) shows the
real columns are fluted/reeded, not plain round - cosmetic, M4 pass.

Dimensions: cad/DIMENSIONS.md "Legacy part audit" - legacy diameters
(med), book length (stated, high).

Layout: tube axis along +Y (column standing upright), annulus sketched on
the Top plane at the origin, extruded upward.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_tube_frame.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "tube-frame"

OUTER_DIA = 1.375 * IN  # legacy: Ø34.925 (no book numerics)
WALL_THICKNESS = 0.12 * IN  # legacy: 3.048 wall -> Ø28.829 bore
COLUMN_LENGTH = 1070.0  # ch.6: 107 cm column height (supersedes legacy 1016)

INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch annulus", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, 0.0, 0.0, OUTER_DIA / 2.0, "outer circle")
    await define_circle(adapter, 0.0, 0.0, INNER_DIA / 2.0, "bore circle")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "annulus sketch")
    check("exit_sketch annulus", await adapter.exit_sketch())
    check(
        "extrude column",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLUMN_LENGTH)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after extrude: {res.data.volume:.1f} mm^3")
    # expected: pi * (17.4625^2 - 14.4145^2) * 1070 = ~326,620 mm^3

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
