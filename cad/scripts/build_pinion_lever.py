r"""Reproduction script: pinion engage lever (book ch. 25).

The Ø6 rod that turns the lift rod (build_pinion_lift_rod.py) to swing
the pinion into mesh: a ball-ended grip at the ROOT where it clamps the
lift rod's front end, rod reaching up-and-out (p. 68 + p002 base-front
cluster, left rod: standing up = disengaged, folded flat = engaged).
The ch30/M6.8 model carries it in the DISENGAGED rest pose. The root
clamp bore is simplified: the ball sits centred on the lift rod axis.

Layout: one solid of revolution -- ball centred at the origin, rod
along +Y to ROD_LEN.

Volume gate (exact union, mm^3): ball 1436.76 + rod above the junction
plane 1856.85 - ball cap above that plane 9.71 = 3283.90.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-lever"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

ROD_DIA = 6.0  # p.68 "6 mm" annotation (high)
ROD_LEN = 72.0  # ball centre to tip, p002 photogrammetry (med)
BALL_DIA = 14.0  # root grip ball, p002 photogrammetry vs the rod (low)

ROD_R = ROD_DIA / 2.0
BALL_R = BALL_DIA / 2.0
JUNCTION = math.sqrt(BALL_R**2 - ROD_R**2)  # 6.3246

V_BALL = (4.0 * math.pi / 3.0) * BALL_R**3
V_ROD_ABOVE = math.pi * ROD_R**2 * (ROD_LEN - JUNCTION)
CAP_H = BALL_R - JUNCTION
V_CAP = math.pi * CAP_H**2 * (3.0 * BALL_R - CAP_H) / 3.0
V_TOTAL = V_BALL + V_ROD_ABOVE - V_CAP


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Single revolved profile about +Y: root ball with the grip rod.
    check("create_sketch lever", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline rod axis",
        await adapter.add_centerline(0.0, -BALL_R, 0.0, ROD_LEN),
    )
    arc = check(
        "add_arc root ball",
        await adapter.add_arc(0.0, 0.0, 0.0, -BALL_R, ROD_R, JUNCTION),
    )
    tail = await add_line_chain(
        adapter,
        [
            (ROD_R, JUNCTION),
            (ROD_R, ROD_LEN),
            (0.0, ROD_LEN),
            (0.0, -BALL_R),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "lever profile", fix_entities=[centerline, arc, *tail]
    )
    check("exit_sketch lever", await adapter.exit_sketch())
    check(
        "revolve lever",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    await volume_check(adapter, "lever", V_TOTAL, 0.005 * V_TOTAL)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
