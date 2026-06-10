r"""Reproduction script: cone gear shaft (book ch. 12, pp. 16-21).

Plain Ø3/8 in steel shaft carrying the 20-gear cone set (150 mm annotated
stack, all gears fixed to and rotating with the shaft), the small driven
pinion at the thin end, and bearing journals into the green post (thin
end) and the pivot block (large end - the cone set pivots out of
engagement, ch. 25). Gears attach by means the book never shows (no
keyway data), so the shaft is modeled plain; the gears are M4 parts.

Dimensions: cad/DIMENSIONS.md "Chapter 12" - dia legacy (med), length
derived from the annotated 150 mm stack + p.18 top-down end allowances
(low).

Layout: shaft axis along +Y, large (pivot) end at the origin.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cone_gear_shaft.py
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
)

PART_NAME = "cone-gear-shaft"

SHAFT_DIA = 0.375 * IN  # ch12: = ShaftDiameter (legacy), matches cam bore
SHAFT_LENGTH = 225.0  # ch12: 150 stack + pinion seat ~15 + journals ~35/~25


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft circle")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after shaft: {res.data.volume:.1f} mm^3")
    # expected: pi * 4.7625^2 * 225 = ~16,033 mm^3

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
