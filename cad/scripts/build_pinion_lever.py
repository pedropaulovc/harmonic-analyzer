r"""Reproduction script: pinion engage lever (book ch. 25).

The Ø6 rod that turns the lift rod (build_pinion_lift_rod.py) to swing
the pinion into mesh: a ball clamp at the ROOT grips the lift rod's
front end, the rod reaches up-and-out (p. 68 + p002 base-front cluster,
left rod: standing up = disengaged, folded flat = engaged). The
ch30/M6.8 model carries it in the DISENGAGED rest pose.

Layout: ball clamp centred at the origin, BORED Ø6.35 along Z (it
rides the lift rod -- a solid ball would swallow it), rod along +Y
from just clear of the bore to ROD_LEN. Built bore-first as an ANNULAR
revolve about Z (profile excludes the axis, so no degenerate axis edge
-- see solidworks pitfalls), then the rod extruded +Y into it.

Volume gate (exact, mm^3): annular ball (4pi/3)(R^2-r^2)^1.5 + rod
above y0 - rod/ball polar-integral overlap.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    apply_color,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
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
BALL_DIA = 14.0  # root clamp ball, p002 photogrammetry vs the rod (low)
BORE = 6.35  # grips the Ø6.35 lift rod (derived)
ROD_Y0 = 3.5  # rod base above the ball centre: 0.32 radial clearance to
# the bore surface, buried 2.8 under the ball surface (derived)

ROD_R = ROD_DIA / 2.0
BALL_R = BALL_DIA / 2.0
BORE_R = BORE / 2.0
JUNCTION = math.sqrt(BALL_R**2 - BORE_R**2)  # 6.2386: bore meets ball

V_ANNULAR_BALL = (4.0 * math.pi / 3.0) * (BALL_R**2 - BORE_R**2) ** 1.5
V_ROD = math.pi * ROD_R**2 * (ROD_LEN - ROD_Y0)
# Rod portion already inside the ball: polar integral over the rod disc
# of (sqrt(R^2 - rho^2) - ROD_Y0); the rod never reaches the bore region.
V_ROD_BALL = (2.0 * math.pi / 3.0) * (
    BALL_R**3 - (BALL_R**2 - ROD_R**2) ** 1.5
) - ROD_Y0 * math.pi * ROD_R**2
V_TOTAL = V_ANNULAR_BALL + V_ROD - V_ROD_BALL


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Annular clamp ball: Top-plane profile (sketch (u, v) -> (X, -Z)),
    # centerline = the Z axis, profile off-axis (bore wall + ball arc).
    check("create_sketch ball", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline bore axis",
        await adapter.add_centerline(0.0, -JUNCTION, 0.0, JUNCTION),
    )
    bore_wall = check(
        "add bore wall",
        await adapter.add_line(BORE_R, JUNCTION, BORE_R, -JUNCTION),
    )
    arc = check(
        "add_arc ball",
        await adapter.add_arc(
            0.0, 0.0, BORE_R, -JUNCTION, BORE_R, JUNCTION
        ),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "ball profile", fix_entities=[centerline, bore_wall, arc]
    )
    check("exit_sketch ball", await adapter.exit_sketch())
    check(
        "revolve ball",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    volume = await volume_check(
        adapter, "annular ball", V_ANNULAR_BALL, 0.005 * V_ANNULAR_BALL
    )

    # Grip rod along +Y from just above the bore, merging into the ball.
    check("create_sketch rod", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, ROD_R, "rod")
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    extrude_at_offset(adapter, ROD_LEN - ROD_Y0, ROD_Y0)
    await volume_check(adapter, "lever", V_TOTAL, 0.005 * V_TOTAL)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
