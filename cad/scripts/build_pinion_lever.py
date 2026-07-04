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

    uv run python cad\scripts\build_pinion_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-lever"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

ROD_DIA = 6.0  # p.68 "6 mm" annotation (high)
ROD_LEN = 98.0  # ball centre to tip (PR6): both ch25 close-ups scaled
# against the annotated 6 mm rod read ~99 (p.68 disengaged, 855 px @
# 8.67 px/mm) and ~84 foreshortened (p.69 engaged) -- the old p002
# photogrammetry 72 undershot by a third (med)
BALL_DIA = 16.0  # root clamp ball (PR6): 150 px / 8.67 (p.68) and
# 145 px / 9.17 (p.69) both read ~16-17 vs the old 14 (med)
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

    # Editable knobs (Tools > Equations): the ball + bore + rod primitives. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 14 = 14 in). RodLen and
    # RodY0 feed the feature-parameter rod extrude (built with the literals);
    # declared so a GUI edit sees the knobs.
    await set_global(adapter, "BallDia", f"{BALL_DIA}mm")
    await set_global(adapter, "Bore", f"{BORE}mm")
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "RodY0", f"{ROD_Y0}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annular clamp ball: Top-plane profile (sketch (u, v) -> (X, -Z)),
    # centerline = the Z axis, profile off-axis (bore wall + ball arc).
    ball = SketchDims()
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
    # Arc (5 DOF): centre on the origin + radius + one constraint per
    # endpoint angle -- the wall's vertical ties the far end, a single
    # horizontal distance sets the near end at the bore wall. The
    # centerline floats apart from the profile (its ends sit on the axis,
    # not on profile points), so it gets pinned through the arc ends.
    check(
        "anchor ball centre",
        await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"),
    )
    check(
        "ball radius",
        await adapter.add_sketch_dimension(arc, None, "radial", BALL_R),
    )
    ball.record("BallRadius", '"BallDia" / 2')
    check(
        "bore wall vertical",
        await adapter.add_sketch_constraint(bore_wall, None, "vertical"),
    )
    check(
        "bore wall offset",
        await adapter.add_sketch_dimension(
            f"{arc}.start", "origin", "horizontal_distance", BORE_R
        ),
    )
    ball.record("BoreWallOffset", '"Bore" / 2')
    check(
        "axis vertical",
        await adapter.add_sketch_constraint(centerline, None, "vertical"),
    )
    check(
        "axis on origin",
        await adapter.add_sketch_constraint(
            f"{centerline}.start", "origin", "vertical_points"
        ),
    )
    check(
        "axis start level",
        await adapter.add_sketch_constraint(
            f"{centerline}.start", f"{arc}.start", "horizontal_points"
        ),
    )
    check(
        "axis end level",
        await adapter.add_sketch_constraint(
            f"{centerline}.end", f"{arc}.end", "horizontal_points"
        ),
    )
    await ensure_fully_defined(adapter, "ball profile")
    check("exit_sketch ball", await adapter.exit_sketch())
    name_last_feature(adapter, "BallProfile")
    drive_jobs += ball.apply(adapter, "BallProfile")
    check(
        "revolve ball",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Ball")
    await volume_check(
        adapter, "annular ball", V_ANNULAR_BALL, 0.005 * V_ANNULAR_BALL
    )

    # Grip rod along +Y from just above the bore, merging into the ball. On-axis
    # circle (origin centre): only the diameter dim is recorded.
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, ROD_R, "rod", dims=rod,
        names=("RodCx", "RodCz", "RodDia"),
        drives=(None, None, '"RodDia"'),
    )
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += rod.apply(adapter, "RodProfile")
    extrude_at_offset(adapter, ROD_LEN - ROD_Y0, ROD_Y0)
    name_last_feature(adapter, "Rod")
    await volume_check(adapter, "lever", V_TOTAL, 0.005 * V_TOTAL)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven lever (equations neutral)", V_TOTAL, 0.005 * V_TOTAL)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
