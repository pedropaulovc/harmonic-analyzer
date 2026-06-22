r"""Reproduction script: translational-gearing reduction pinion (book ch. 23).

The small fine-tooth steel pinion that rides coaxially with the 120T rack
pinion (edge-on views `v4_transgear_002/003/008`): estimated 24T DP 30
(measured OD ~ 21 mm; 24T -> 22.0 mm), ~6 mm face, plain 3/8" bore. What it
meshes is unresolved -- Appendix C #8; re-check the tooth count against the
platen-speed law when mating the drive train in M6.

Layout: gear axis = Z through the origin, disc z = 0..6 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_pinion.py
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
)
from _gear import build_fixed_gear, volume_check

PART_NAME = "transgear-pinion"
MATERIAL = "Plain Carbon Steel"  # ch. 23 photos: steel (unlike the brass wheels)

TEETH = 24  # DIMENSIONS.md ch23: est. from measured OD ~21 mm (low)
FACE_WIDTH = 6.0  # mm, edge-on view v4_transgear_002 (low)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- machine-standard shaft stock (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH)

    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
    await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
