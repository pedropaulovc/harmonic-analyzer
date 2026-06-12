r"""Reproduction script: pinion pivot block (book ch. 25; 2 used).

The black base block that anchors one pinion swing bracket (p. 68
close-ups): a plain rectangular block screwed to the base, cross-bored
for the Ø6.35 torque shaft the straps pivot on. The slotted screw heads
on the plates are simplified away.

Layout: shaft bore at the origin along Z, block x -15..15,
y -12..4 (bore 12 above the base seat), z 0..12.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_pivot_block.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    apply_color,
    apply_material,
    check,
    add_line_chain,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-pivot-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel block (p.68)

WIDTH = 30.0  # photo-scaled vs the strap (low)
HEIGHT = 16.0  # photo-scaled (low); tall enough that the strap's r 11
# bottom cap (PIVOT_Y - 11 = 51.8) swings clear of the base top 50.8
DEPTH = 12.0  # photo-scaled (low)
BORE_UP = 12.0  # bore height above the base seat -- sets PIVOT_Y (derived)
BORE = 6.35  # rides the Ø6.35 torque shaft (derived)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Block outline + shaft bore in ONE sketch -> single extrude.
    # Inference OFF: the bore circle sits at the origin.
    check("create_sketch block", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = await add_line_chain(
        adapter,
        [
            (-WIDTH / 2.0, -BORE_UP),
            (WIDTH / 2.0, -BORE_UP),
            (WIDTH / 2.0, HEIGHT - BORE_UP),
            (-WIDTH / 2.0, HEIGHT - BORE_UP),
        ],
    )
    await define_circle(adapter, 0.0, 0.0, BORE / 2.0, "shaft bore")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "block sketch", fix_entities=entities)
    check("exit_sketch block", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=DEPTH)),
    )
    area = WIDTH * HEIGHT - math.pi * (BORE / 2.0) ** 2
    await volume_check(adapter, "block", area * DEPTH, 0.005 * area * DEPTH)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
