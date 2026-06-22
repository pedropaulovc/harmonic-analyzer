r"""Reproduction script: pivot shaft (book ch. 14 / ch. 17; 1 used).

Plain Ø6.35 (1/4") x 228.6 (9") steel shaft carrying the 20 rocker arms
at machine (x, y) = (-72.9, 253.8). Each end seats in a pivot-ball-mount's
Ø6.5 cross-bore (north mount on the rocker-support apex at z +101.6,
south mount on the A-frame clevis at z -111, M6.5); pivot-bushing spacers
set the 7.0565 channel pitch along it. The top levers' fulcrum is the
shorter build_fulcrum_shaft.py (182), which clears the west columns.

Dimensions: cad/DIMENSIONS.md "Channel & top-frame layout" (med; dia low).

Layout: shaft axis along Z, centred (z -114.3..+114.3) - the channel bank
is symmetric about the part origin.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pivot_shaft.py
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

PART_NAME = "pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.25 * IN  # 6.35  DIMENSIONS.md channel layout (low)
SHAFT_LENGTH = 9.0 * IN  # 228.6  spans the 20-channel bank + ball mounts (med)


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
