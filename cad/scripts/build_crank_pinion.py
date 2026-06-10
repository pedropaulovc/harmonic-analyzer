r"""Reproduction script: crank pinion (book ch. 11/12, pp. 16, 20).

The pinion on the crankshaft that meshes the dark steel crank-drive gear
at the cone set's large end (`build_crank_drive_gear.py`), implementing
the book-stated 4:1 crank-to-cone reduction (p. 16). Tooth count/DP per
the Appendix C #9 working estimate: DP 16, 16T -> PD 1.000", mating the
64T drive gear at PD 4.000". The 4:1 ratio is fixed; ratify the DP split
when the drive train is mated in M6.

Dimensions: cad/DIMENSIONS.md "Chapter 12" crank-drive gear row +
Appendix C #9 (low confidence except the ratio). Face slightly wider
than the drive gear's (meshing-pair practice, axial alignment slack).

Layout: gear axis = Z through the origin, disc z = 0..12 mm.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_crank_pinion.py
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

PART_NAME = "crank-pinion"
MATERIAL = "Plain Carbon Steel"  # steel like its mate (p.19/20)

TEETH = 16  # DIMENSIONS.md ch12 / Appendix C #9 estimate (low)
DP = 16.0  # matches the crank-drive gear (low)
FACE_WIDTH = 12.0  # mm, slightly wider than the drive gear's 10 (low)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- crankshaft dia (med)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)

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
