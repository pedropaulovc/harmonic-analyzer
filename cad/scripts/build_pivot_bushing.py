r"""Reproduction script: rocker pivot spacer bushing (book ch. 14 p. 27; 19 used).

Spacer between adjacent rocker arms on the Ø6.35 pivot shaft: Ø10 OD x
4.5565 long x Ø6.5 bore. Length sets the 7.0565 channel pitch against
the 2.5 arm thickness (7.0565 - 2.5 = 4.5565); 19 fill the gaps between
20 arms.

The OD has a hard geometric ceiling the M2 photo read (Ø25.4) violates:
at d = 0 the amplitude-bar foot passes directly over the shaft, its
cheek bottoms 6.45 above the axis (contact 262.63 - notch 2.381 - axis
253.8), so the spacer radius must stay under ~6.4 or the bar can never
reach zero coefficient (ch. 15 says it slides through the pivot to the
opposite side). The p. 27 "large barrels" are therefore not these
spacers; Ø10 keeps 1.45 clearance under the bar.

Dimensions: cad/DIMENSIONS.md ch. 14 layout "Pivot spacer bushings" row
(derived, med; OD bounded by bar clearance, low).

Layout: bushing axis along Z, centred (annulus on the Front plane,
mid-plane extrude).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pivot_bushing.py
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
MATERIAL = "Brass"

OUTER_DIA = 10.0  # DIMENSIONS.md ch14 layout: bar-clearance ceiling ~12.9 (low)
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
