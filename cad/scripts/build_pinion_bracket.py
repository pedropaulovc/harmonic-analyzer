r"""Reproduction script: pinion swing bracket (book ch. 25; 2 used).

The polished-steel strap that carries one end of the alignment-pinion
drum (p. 68 close-ups): a rounded-end flat bar, pivot bore at the
bottom riding the Ø6.35 torque shaft (build_pinion_pivot_shaft.py),
rounded top capping the drum end face. The top journal hardware (big
countersunk screw on the plates) is simplified away -- the strap's
inner face simply butts against the drum end.

Layout: pivot bore at the origin, strap up +Y (drum axis at (0, 47)),
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
C2C = 47.0  # pivot bore to drum axis -- build_drive_train_assembly PINION_Y
THICKNESS = 5.0  # photo-scaled (low)
PIVOT_BORE = 6.35  # rides the Ø6.35 torque shaft (derived)

R_END = WIDTH / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Outer rounded-bar loop + pivot bore in ONE sketch -> single extrude.
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
    await define_circle(adapter, 0.0, 0.0, PIVOT_BORE / 2.0, "pivot bore")
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
        - math.pi * (PIVOT_BORE / 2.0) ** 2
    )
    await volume_check(adapter, "strap", area * THICKNESS, 0.005 * area * THICKNESS)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
