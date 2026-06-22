r"""Reproduction script: top-lever fulcrum spacer bushing (book ch. 17; 19 used).

Small spacer between adjacent top levers on the common Ø6.35 fulcrum
shaft: Ø12 OD x 4.0565 long x Ø6.5 bore. Length sets the 7.0565 channel
pitch against the 3.0 lever thickness (7.0565 - 3.0 = 4.0565); 19 fill
the gaps between 20 levers - the lever-bank twin of the rocker bank's
pivot-bushing.

Dimensions: cad/DIMENSIONS.md "Chapter 17" lever rows (derived, med;
OD scaled, low).

Layout: bushing axis along Z, centred (annulus on the Front plane,
mid-plane extrude).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_lever_bushing.py
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

PART_NAME = "lever-bushing"
MATERIAL = "Brass"  # lever-bank twin of the brass pivot-bushing

OUTER_DIA = 12.0  # DIMENSIONS.md ch17 (scaled, low)
BORE_DIA = 6.5  # rides the 6.35 fulcrum shaft (derived)
LENGTH = 4.0565  # channel pitch 7.0565 - lever 3.0 (derived)


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
