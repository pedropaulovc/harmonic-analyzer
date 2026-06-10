r"""Reproduction script: translational-gearing rack pinion (book ch. 23).

The large thin brass gear that drives the platen rack: 120 teeth DP 30
(keyframe measurement, DIMENSIONS.md ch. 23 -- OD matches the cylinder
gears' 103.3 mm), ~3 mm disc, plain 3/8" shaft bore (hub hardware deferred
to the M6 drive-train work, Appendix C #8).

Layout: gear axis = Z through the origin, disc z = 0..3 mm.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_rack_pinion.py
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

PART_NAME = "rack-pinion"
MATERIAL = "Brass"  # ch. 23 photos: brass

TEETH = 120  # DIMENSIONS.md ch23: OD + quadrant counts, v4_transgear_028/030 (med)
FACE_WIDTH = 3.0  # mm, edge-on view v4_transgear_002 (low)
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
