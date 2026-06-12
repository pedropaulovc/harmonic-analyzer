r"""Reproduction script: pinion swing bracket (book ch. 25; 2 used).

The polished-steel strap that carries one end of the alignment-pinion
drum (p. 68 close-ups, shot from the BACK side): a short rounded-end
flat bar with TWO Ø6.35 bores -- the bottom one pivots on the torque
shaft (build_pinion_pivot_shaft.py), the top one journals the drum's
arbor stub (build_alignment_pinion.py). The lift rod's cam pin
(build_pinion_lift_rod.py) bears on the strap flank to swing it.

Layout: pivot bore at the origin, arbor bore at (0, C2C), strap up +Y,
thickness z 0..5.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    apply_color,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-bracket"
MATERIAL = "Plain Carbon Steel"  # p.68: bright steel strap

WIDTH = 22.0  # DIMENSIONS.md ch25: strap width, photo-scaled vs the drum (low)
C2C = 31.0  # pivot bore to arbor bore -- long enough that the engaged
# pose (c2c 68.58 to the cylinder train) stays reachable from a pivot
# shaft parked west of the cone-knob post; the rest pose leans the strap
# 75.6 deg onto the arbor (build_drive_train_assembly geometry, derived)
THICKNESS = 5.0  # photo-scaled (low)
BORE = 6.35  # both bores: torque shaft below, drum arbor stub above (derived)

R_END = WIDTH / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Outer rounded-bar loop + both bores in ONE sketch -> single extrude.
    # Inference OFF: the bottom cap arc endpoints sit near the origin.
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "add bottom cap arc",
            await adapter.add_arc(0.0, 0.0, -R_END, 0.0, R_END, 0.0),
        ),
        check("add right edge", await adapter.add_line(R_END, 0.0, R_END, C2C)),
        check(
            "add top cap arc",
            await adapter.add_arc(0.0, C2C, R_END, C2C, -R_END, C2C),
        ),
        check("add left edge", await adapter.add_line(-R_END, C2C, -R_END, 0.0)),
    ]
    await define_circle(adapter, 0.0, 0.0, BORE / 2.0, "pivot bore")
    await define_circle(adapter, 0.0, C2C, BORE / 2.0, "arbor bore")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "strap sketch", fix_entities=entities)
    check("exit_sketch strap", await adapter.exit_sketch())
    check(
        "extrude strap",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    area = (
        WIDTH * C2C
        + math.pi * R_END**2
        - 2.0 * math.pi * (BORE / 2.0) ** 2
    )
    await volume_check(adapter, "strap", area * THICKNESS, 0.005 * area * THICKNESS)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
