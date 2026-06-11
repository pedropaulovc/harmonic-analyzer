r"""Reproduction script: rocker pivot spacer bushing (book ch. 14 p. 27; 19 used).

The large barrel spacers visible between the rocker arms in the p. 27
macro: Ø25.4 OD x 4.5565 long x Ø6.5 bore, sliding on the Ø6.35 pivot
shaft. Their length sets the 7.0565 channel pitch against the 2.5 arm
thickness (7.0565 - 2.5 = 4.5565); 19 fill the gaps between 20 arms.

Dimensions: cad/DIMENSIONS.md ch. 14 layout "Pivot spacer bushings" row
(derived/scaled, med).

Layout: bushing axis along Z, centred (annulus on the Front plane,
mid-plane extrude).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pivot_bushing.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)

PART_NAME = "pivot-bushing"
MATERIAL = "Brass"  # p.27 macro: polished barrel spacers

OUTER_DIA = 25.4  # DIMENSIONS.md ch14 layout (scaled, med)
BORE_DIA = 6.5  # rides the 6.35 pivot shaft (derived)
LENGTH = 4.5565  # channel pitch 7.0565 - arm 2.5 (derived)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch annulus", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, OUTER_DIA / 2.0, "outer")
    await define_circle(adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore")
    await ensure_fully_defined(adapter, "annulus sketch")
    check("exit_sketch annulus", await adapter.exit_sketch())
    check(
        "extrude bushing",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LENGTH, both_directions=True)
        ),
    )
    v = math.pi * ((OUTER_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * LENGTH
    await volume_check(adapter, "bushing annulus", v, 0.001 * v)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
