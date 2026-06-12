r"""Reproduction script: pinion strap torque shaft (book ch. 25).

The plain Ø6.35 rod the two pinion swing brackets pivot on, running
parallel under the alignment-pinion drum through both pivot blocks'
east bores (p. 68 close-ups; the engage lever and its cam pins live on
the SEPARATE lift rod in the west bores -- build_pinion_lift_rod.py).

Layout: shaft axis Z, z 0..188.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_pivot_shaft.py
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
    volume_check,
)

PART_NAME = "pinion-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)

SHAFT_DIA = 6.35  # rides the strap and block bores (derived)
SHAFT_LEN = 196.0  # machine z -106..+90: through both straps and blocks
# with 2 proud past each block face (the front block sits forward at
# z -104..-92, dodging the cone-pivot-post column) (derived)

SHAFT_R = SHAFT_DIA / 2.0
V_SHAFT = math.pi * SHAFT_R**2 * SHAFT_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch shaft", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_R, "shaft")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LEN)),
    )
    await volume_check(adapter, "shaft", V_SHAFT, 0.005 * V_SHAFT)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
