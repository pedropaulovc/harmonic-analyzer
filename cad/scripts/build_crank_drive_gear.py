r"""Reproduction script: crank-drive gear (book ch. 12, p. 20).

The dark steel gear at the cone set's large end, annotated "This gear
engages the crank" (p. 20): together with a pinion on the crankshaft
(`build_crank_pinion.py`) it implements the book-stated 4:1 crank-to-cone
reduction (p. 16). Its teeth are visibly ~1.5-2x coarser than the DP 30
train and not countable in the available photos, so the tooth-count/DP
split is the Appendix C #9 working estimate: DP 16, 64T -> PD 4.000"
(OD 104.8 mm, matching the p.20 appearance next to the 120T cone gear),
mating a 16T pinion at PD 1.000". The 4:1 ratio itself is fixed; ratify
the DP split when the drive train is mated in M6.

Dimensions: cad/DIMENSIONS.md "Chapter 12" crank-drive gear row +
Appendix C #9 (low confidence except the ratio).

Layout: gear axis = Z through the origin, disc z = 0..10 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_drive_gear.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    IN,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)
from _gear import build_fixed_gear, volume_check

PART_NAME = "crank-drive-gear"
MATERIAL = "Plain Carbon Steel"  # p.20: dark gear, distinct from the brass train

TEETH = 64  # DIMENSIONS.md ch12 / Appendix C #9 estimate (low)
DP = _config.machine("gear_train", "crank_drive_diametral_pitch")  # cad/config/machine.yaml (low)
FACE_WIDTH = 10.0  # mm, p.20 -- wider than the 7 mm cone faces (low)
# M6.7: seated perpendicular on the cone shaft's 3/8" pivot journal
# like the cone gears (true cone, p.20); the oblique crank-pinion mesh
# is handled in the assembly (contact tooth 50.8*sin(21.1) north of the
# gear centre, crank backed off for the oblique dive).
BORE_DIAMETER = 0.375 * IN  # snug on the 3/8" journal


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

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
