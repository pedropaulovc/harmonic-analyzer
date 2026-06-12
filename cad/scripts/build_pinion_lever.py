r"""Reproduction script: pinion engage lever (book ch. 25).

The Ø6 rod that swings the pinion brackets: it roots on the torque
shaft just behind the front pivot block, with a Ø13 ball grip near the
root (p. 68: standing up = disengaged, folded flat = engaged). The
ch30/M6.8 model carries it in the DISENGAGED rest pose. The threaded
root is simplified: the rod's flat end face sits tangent on the torque
shaft.

Layout: one solid of revolution -- rod along +Y from the origin, axis
= Y, ball centred at (0, 14, 0).

Volume gate (exact union, mm^3): rod 2035.75 + ball 1150.35 -
coaxial full-pass overlap 347.20 = 2838.90.

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
ROD_LEN = 72.0  # photo-scaled (low)
BALL_DIA = 13.0  # grip ball, photo-scaled (low)
BALL_AT = 14.0  # ball centre along the rod, near the root (photo-scaled, low)

ROD_R = ROD_DIA / 2.0
BALL_R = BALL_DIA / 2.0
JUNCTION = math.sqrt(BALL_R**2 - ROD_R**2)  # 5.7663

V_ROD = math.pi * ROD_R**2 * ROD_LEN
V_BALL = (4.0 * math.pi / 3.0) * BALL_R**3
V_OVERLAP = (4.0 * math.pi / 3.0) * (
    BALL_R**3 - (BALL_R**2 - ROD_R**2) ** 1.5
)
V_TOTAL = V_ROD + V_BALL - V_OVERLAP


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Single revolved profile about +Y: rod with the grip-ball bulge.
    check("create_sketch lever", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline rod axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, ROD_LEN),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (ROD_R, 0.0),
            (ROD_R, BALL_AT - JUNCTION),
        ],
        close=False,
    )
    arc = check(
        "add_arc grip ball",
        await adapter.add_arc(
            0.0, BALL_AT, ROD_R, BALL_AT - JUNCTION, ROD_R, BALL_AT + JUNCTION
        ),
    )
    tail = await add_line_chain(
        adapter,
        [
            (ROD_R, BALL_AT + JUNCTION),
            (ROD_R, ROD_LEN),
            (0.0, ROD_LEN),
            (0.0, 0.0),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "lever profile", fix_entities=[centerline, *lines, arc, *tail]
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
