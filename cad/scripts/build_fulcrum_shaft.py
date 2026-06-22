r"""Reproduction script: lever fulcrum shaft (book ch. 17; 1 used).

Plain Ø6.35 (1/4") x 182 steel shaft: the top levers' common fulcrum at
machine (x, y) = (-199.9, 1065.9). M6.5 split this off the 228.6
pivot-shaft: the fulcrum line sits on the west column line, and a 228.6
shaft's tips (z +-114.3) still clip the Ø25.4 columns (tip 3.7 from the
column axis vs the 12.7 surface; OD rederived from the 8-views, M6.11).
182 ends the shaft at z +-91, ~5.3 clear of the column surface (was 0.6
at the old Ø34.925), still 6 past each lever ball-mount's cross-bore
centre at z +-85.

Dimensions: cad/DIMENSIONS.md "Channel & top-frame layout" (med; dia low).

Layout: shaft axis along Z, centred (z -91..+91).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fulcrum_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)

PART_NAME = "fulcrum-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.25 * IN  # 6.35  DIMENSIONS.md channel layout (low)
SHAFT_LENGTH = 182.0  # ends z +-91: clear of the west columns (derived, M6.5)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch section", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft section")
    await ensure_fully_defined(adapter, "section sketch")
    check("exit_sketch section", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SHAFT_LENGTH, both_directions=True)
        ),
    )
    v = math.pi * (SHAFT_DIA / 2.0) ** 2 * SHAFT_LENGTH
    await volume_check(adapter, "shaft", v, 0.001 * v)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
