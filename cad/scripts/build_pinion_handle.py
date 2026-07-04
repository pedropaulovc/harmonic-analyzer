r"""Reproduction script: pinion turning handle (book ch. 25).

The bright tee on the alignment pinion's front arbor (p. 67/68): the
operator turns it to rotate all 20 engaged cylinder gears as one. PR7
re-derivation from ``page002_img07`` (its own Ø6 cross rod = 10 px/mm):
the grip is NOT a ball but a short fat CYLINDER (Ø23) with a slightly
domed south cap; the cross-rod arms are near-symmetric 42/43 (the old
+68 long arm was a p002 misread); and the hub is a BLIND TUBULAR CAP
(OD 10.5, ID 8) swallowed over the arbor stub -- the stub is thicker
steel now (Ø8, build_alignment_pinion), and the cap's dome-less north
rim rides it.

Layout: arbor axis Z; the CROSS ROD plane is the part origin (z 0 --
what the assembly's HANDLE_Z positions). Grip cylinder z -7..+7, domed
cap (sagitta 2) proud of z -7; blind wall z +7..+9; tube annulus z
+9..+19 (the Ø8 stub seats inside); cross rod along Y, arms -42..+43,
built LAST so nothing crosses an axis.

Volume gate (mm^3): grip + cap (spherical-cap formula) + wall + annulus
+ rod - rod/grip overlap (Simpson over circular segments).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_handle.py
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

PART_NAME = "pinion-handle"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)

GRIP_DIA = 23.0  # grip cylinder, img07 (was the Ø24 ball) (med)
GRIP_LEN = 14.0  # along the arbor, z -7..+7 (med)
CAP_SAG = 2.0  # domed south face (img07's rounded cap)
ROD_DIA = 6.0  # cross rod, same stock as the lever root (high)
ROD_DOWN = 42.0  # arm, img07 centre-to-tip (was 35) (med)
ROD_UP = 43.0  # arm, img07 (the old p002 68 is retired) (med)
TUBE_OD = 10.5  # blind cap hub over the arbor stub, img07 (med)
TUBE_ID = 8.0  # = the arbor stub Ø8 (build_alignment_pinion STUB_DIA, must match)
TUBE_LEN = 10.0  # stub seat depth (z +9..+19)
WALL_T = 2.0  # blind wall between grip and tube (z +7..+9)

GRIP_R = GRIP_DIA / 2.0
ROD_R = ROD_DIA / 2.0
CAP_R = (GRIP_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 34.06 crown sphere radius

V_GRIP = math.pi * GRIP_R**2 * GRIP_LEN
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 419.6
V_WALL = math.pi * (TUBE_OD / 2.0) ** 2 * WALL_T
V_TUBE = math.pi * ((TUBE_OD / 2.0) ** 2 - (TUBE_ID / 2.0) ** 2) * TUBE_LEN
V_ROD = math.pi * ROD_R**2 * (ROD_DOWN + ROD_UP)


def _grip_overlap() -> float:
    """Rod volume already inside the grip cylinder: Simpson over the rod's
    y-span inside the grip radius of the disc-segment area |x| <= c(y)
    (the rod's z-extent +-3 stays inside the grip's z -7..+7)."""
    n = 2000
    y0, y1 = -GRIP_R, GRIP_R
    h = (y1 - y0) / n

    def area(y: float) -> float:
        c = math.sqrt(max(GRIP_R**2 - y * y, 0.0))
        if c >= ROD_R:
            return math.pi * ROD_R**2
        return 2.0 * (
            c * math.sqrt(ROD_R**2 - c * c) + ROD_R**2 * math.asin(c / ROD_R)
        )

    total = area(y0) + area(y1)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * area(y0 + i * h)
    return total * h / 3.0


V_TOTAL = V_GRIP + V_CAP + V_WALL + V_TUBE + V_ROD - _grip_overlap()


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document). GripLen/WallT/TubeLen feed extrude DEPTHS (feature params).
    await set_global(adapter, "GripDia", f"{GRIP_DIA}mm")
    await set_global(adapter, "GripLen", f"{GRIP_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodDown", f"{ROD_DOWN}mm")
    await set_global(adapter, "RodUp", f"{ROD_UP}mm")
    await set_global(adapter, "TubeOd", f"{TUBE_OD}mm")
    await set_global(adapter, "TubeId", f"{TUBE_ID}mm")
    await set_global(adapter, "TubeLen", f"{TUBE_LEN}mm")
    await set_global(adapter, "WallT", f"{WALL_T}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Grip cylinder z -7..+7 (on-axis circle: only the diameter is a dim).
    grip = SketchDims()
    check("create_sketch grip", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, GRIP_R, "grip", dims=grip,
        names=("GripCx", "GripCz", "GripDia"),
        drives=(None, None, '"GripDia"'),
    )
    await ensure_fully_defined(adapter, "grip sketch")
    check("exit_sketch grip", await adapter.exit_sketch())
    name_last_feature(adapter, "GripProfile")
    drive_jobs += grip.apply(adapter, "GripProfile")
    extrude_at_offset(adapter, GRIP_LEN, -GRIP_LEN / 2.0)
    name_last_feature(adapter, "Grip")
    expected = V_GRIP
    await volume_check(adapter, "grip", expected, 0.005 * V_GRIP)

    # Domed south cap (sagitta CAP_SAG proud of z -7): Top-plane rim->apex arc
    # revolved about Z -- the crowned-cap idiom (apex at more-positive sketch
    # v for a -Z end; rim -> apex is the minor CCW lobe).
    v_base = GRIP_LEN / 2.0
    v_apex = GRIP_LEN / 2.0 + CAP_SAG
    v_centre = GRIP_LEN / 2.0 + CAP_SAG - CAP_R
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check("cap centerline", await adapter.add_centerline(0.0, v_base, 0.0, v_apex))
    base = check("cap base", await adapter.add_line(0.0, v_base, GRIP_R, v_base))
    arc = check(
        "cap arc",
        await adapter.add_arc(0.0, v_centre, GRIP_R, v_base, 0.0, v_apex),
    )
    close = check("cap close", await adapter.add_line(0.0, v_apex, 0.0, v_base))
    set_sketch_direct_db(adapter, False)
    check("cap base horizontal", await adapter.add_sketch_constraint(base, None, "horizontal"))
    check("cap close vertical", await adapter.add_sketch_constraint(close, None, "vertical"))
    check(
        "cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "horizontal_distance", GRIP_R
        ),
    )
    cap.record("CapRim", '"GripDia" / 2')
    check(
        "cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "vertical_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "cap on axis",
        await adapter.add_sketch_constraint(f"{base}.start", "origin", "vertical_points"),
    )
    check(
        "cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "vertical_distance", v_base
        ),
    )
    cap.record("CapZ", '"GripLen" / 2')
    check(
        "cap radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    cap.record(
        "CapR",
        '("GripDia" / 2 * "GripDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "cap sketch")
    check("exit_sketch cap", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += cap.apply(adapter, "CapProfile")
    check("revolve cap", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Cap")
    expected += V_CAP
    await volume_check(adapter, "cap", expected, 0.03 * V_CAP)

    # Blind wall disc (z +7..+9) then the tube annulus (z +9..+19): the cap
    # hub the Ø8 arbor stub seats into.
    wall = SketchDims()
    check("create_sketch wall", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, TUBE_OD / 2.0, "wall", dims=wall,
        names=("WallCx", "WallCz", "WallDia"),
        drives=(None, None, '"TubeOd"'),
    )
    await ensure_fully_defined(adapter, "wall sketch")
    check("exit_sketch wall", await adapter.exit_sketch())
    name_last_feature(adapter, "WallProfile")
    drive_jobs += wall.apply(adapter, "WallProfile")
    extrude_at_offset(adapter, WALL_T, GRIP_LEN / 2.0)
    name_last_feature(adapter, "Wall")
    expected += V_WALL
    await volume_check(adapter, "wall", expected, 0.01 * V_WALL)

    tube = SketchDims()
    check("create_sketch tube", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, TUBE_OD / 2.0, "tube OD", dims=tube,
        names=("TubeOdCx", "TubeOdCz", "TubeOd"),
        drives=(None, None, '"TubeOd"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, TUBE_ID / 2.0, "tube ID", dims=tube,
        names=("TubeIdCx", "TubeIdCz", "TubeId"),
        drives=(None, None, '"TubeId"'),
    )
    await ensure_fully_defined(adapter, "tube sketch")
    check("exit_sketch tube", await adapter.exit_sketch())
    name_last_feature(adapter, "TubeProfile")
    drive_jobs += tube.apply(adapter, "TubeProfile")
    extrude_at_offset(adapter, TUBE_LEN, GRIP_LEN / 2.0 + WALL_T)
    name_last_feature(adapter, "Tube")
    expected += V_TUBE
    await volume_check(adapter, "tube", expected, 0.01 * V_TUBE)

    # Cross rod LAST: Top-plane on-axis circle extruded +Y across both arms.
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
    extrude_at_offset(adapter, ROD_DOWN + ROD_UP, -ROD_DOWN)
    name_last_feature(adapter, "Rod")
    await volume_check(adapter, "handle", V_TOTAL, 0.01 * V_ROD)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven handle (equations neutral)", V_TOTAL, 0.01 * V_ROD)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
