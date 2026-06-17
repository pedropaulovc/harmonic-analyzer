r"""Reproduction script: magnifying-lever bracket (book ch. 20, pp. 46-49).

The black fitting that affixes the magnifying lever rod to the summing
lever: a flange screwed under the coefficients plate's front edge and a
forward arm ending in a collar (O12, bore 6.2) the O6 rod clamps into.
M6.10 fasteners pass: two O3.2 holes through the flange on its local
z 18.0 line -- the strip actually under the plate (the plate front edge
is at local z 15 = machine -70) and clear of the arm (z 4..15): the O5.5
fillister heads (r 2.75) reach down to z 15.25, 0.25 off the arm face,
with free air below; the screws thread up flush with
the plate bottom (987.46 -- the corrected coplanar .cs plate, engagement
into the summing lever's plate not modeled). Their heads clear channel
spring j=0 (east edge x +28.35) by 1.9.

Layout: origin at the collar centre (machine (+40, 985, -85)); collar
axis along X (the rod direction), arm runs +Z (toward the plate, machine
-85 -> -70), flange under the plate at local z 9..20. M6.8: the flange
is the part's only x-asymmetric feature, so the machine mirror is
authored here (FLANGE_X negated) and the assembly places the part with
MIRROR_PLANE 'x0'. Dimensions: cad/DIMENSIONS.md ch. 20 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_magnifying_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    name_bore_axis,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "magnifying-bracket"
MATERIAL = "Plain Carbon Steel"  # black hardware

COLLAR_OD = 12.0  # rod collar (low)
COLLAR_BORE = 6.2  # the O6 magnifying rod clamps in (derived)
COLLAR_HALF_LEN = 5.0  # along X
ARM_HALF_X = 5.0  # arm 10 wide (x), y -3..+4.5, z 4..15 (low)
ARM_Y = (-3.0, 4.5)
ARM_Z = (4.0, 15.0)
FLANGE_X = (-11.0, 5.0)  # under-plate flange, machine x +29..+45: stops 0.65
# east of channel spring j=0's helix (east edge x +28.35; M6.5 top-level fit,
# M6.8-mirrored)
FLANGE_Y = (-1.54, 2.46)  # flange top (machine 987.46) touches the corrected
# .cs plate bottom (987.46); dropped 5.44 from the old (3.9, 7.9)/992.9 when the
# coplanar plate fell to 987.46..992.54 (see build_summing_lever)
FLANGE_Z = (9.0, 20.0)  # under the plate's front edge band (derived)
SCREW_HOLE_DIA = 3.2  # M6.10 mounting-screw holes (O2.9 fillister shanks)
SCREW_HOLE_X = (-7.0, 1.0)  # machine x +33 / +41: inset 4 from the flange ends
SCREW_HOLE_Z = 18.0  # machine z -67.0: under the plate; head edge 0.25 off
# the arm's z 15 face, hole edge 0.4 off the flange end (z 20)


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # 1. Collar tube about the X axis (revolved rectangle).
    check("create_sketch collar", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "collar centerline",
        await adapter.add_centerline(-COLLAR_HALF_LEN, 0.0, COLLAR_HALF_LEN, 0.0),
    )
    profile_rect = [
        (-COLLAR_HALF_LEN, COLLAR_BORE / 2.0),
        (COLLAR_HALF_LEN, COLLAR_BORE / 2.0),
        (COLLAR_HALF_LEN, COLLAR_OD / 2.0),
        (-COLLAR_HALF_LEN, COLLAR_OD / 2.0),
    ]
    profile = await add_line_chain(adapter, profile_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(adapter, profile, profile_rect, label="collar")
    # The centerline shares no vertex with the off-axis profile rectangle,
    # so it carries its own scheme: horizontal on the axis, length dim,
    # start anchored to the origin.
    check(
        "centerline horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    check(
        "centerline length",
        await adapter.add_sketch_dimension(
            centerline, None, "linear", 2.0 * COLLAR_HALF_LEN
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{centerline}.start", -COLLAR_HALF_LEN, 0.0, "centerline start"
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    check(
        "revolve collar", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    expected = (
        math.pi
        * ((COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE / 2.0) ** 2)
        * 2.0
        * COLLAR_HALF_LEN
    )
    vol = await _volume(adapter)
    print(f"  volume after collar: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"collar volume {vol:.1f} != {expected:.1f}")

    # 2. Arm from the collar shell toward the plate (+Z), Top sketch.
    check("create_sketch arm", await adapter.create_sketch("Top"))
    arm_rect = [
        (-ARM_HALF_X, -ARM_Z[1]),
        (ARM_HALF_X, -ARM_Z[1]),
        (ARM_HALF_X, -ARM_Z[0]),
        (-ARM_HALF_X, -ARM_Z[0]),
    ]
    arm = await add_line_chain(adapter, arm_rect)
    await define_rectilinear_chain(adapter, arm, arm_rect, label="arm")
    await ensure_fully_defined(adapter, "arm sketch")
    check("exit_sketch arm", await adapter.exit_sketch())
    extrude_at_offset(adapter, ARM_Y[1] - ARM_Y[0], ARM_Y[0])
    v_arm = 2.0 * ARM_HALF_X * (ARM_Z[1] - ARM_Z[0]) * (ARM_Y[1] - ARM_Y[0])
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after arm: {vol:.1f} mm^3 (+{added:.1f}, solid {v_arm:.1f})")
    if not (0.85 * v_arm <= added <= 1.01 * v_arm):
        raise RuntimeError(f"arm: added {added:.1f}, expected ~{v_arm:.1f}")
    expected = vol

    # 3. Flange under the plate's front edge.
    check("create_sketch flange", await adapter.create_sketch("Top"))
    flange_rect = [
        (FLANGE_X[0], -FLANGE_Z[1]),
        (FLANGE_X[1], -FLANGE_Z[1]),
        (FLANGE_X[1], -FLANGE_Z[0]),
        (FLANGE_X[0], -FLANGE_Z[0]),
    ]
    flange = await add_line_chain(adapter, flange_rect)
    await define_rectilinear_chain(adapter, flange, flange_rect, label="flange")
    await ensure_fully_defined(adapter, "flange sketch")
    check("exit_sketch flange", await adapter.exit_sketch())
    extrude_at_offset(adapter, FLANGE_Y[1] - FLANGE_Y[0], FLANGE_Y[0])
    v_flange = (
        (FLANGE_X[1] - FLANGE_X[0])
        * (FLANGE_Z[1] - FLANGE_Z[0])
        * (FLANGE_Y[1] - FLANGE_Y[0])
    )
    # Overlap with the arm: x +-5 cap, z 9..15, y 3.9..4.5.
    v_overlap = (
        (min(ARM_HALF_X, FLANGE_X[1]) - max(-ARM_HALF_X, FLANGE_X[0]))
        * (min(ARM_Z[1], FLANGE_Z[1]) - max(ARM_Z[0], FLANGE_Z[0]))
        * (min(ARM_Y[1], FLANGE_Y[1]) - max(ARM_Y[0], FLANGE_Y[0]))
    )
    v_net = v_flange - v_overlap
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after flange: {vol:.1f} mm^3 (+{added:.1f}, net {v_net:.1f})")
    if abs(added - v_net) > 0.02 * v_net:
        raise RuntimeError(f"flange: added {added:.1f}, expected {v_net:.1f}")
    expected = vol

    # 4. Mounting-screw holes through the flange (Top sketch (x, y) ->
    # global (X, -Z), mid-plane cut: only the flange band 3.9..7.9 is
    # material at that footprint -- the arm stops at z 15).
    check("create_sketch screw holes", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    for x in SCREW_HOLE_X:
        await define_circle(
            adapter, x, -SCREW_HOLE_Z, SCREW_HOLE_DIA / 2.0, f"screw hole x{x:+.0f}"
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screw holes sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * FLANGE_Y[1], both_directions=True)
        ),
    )
    expected -= (
        2.0 * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * (FLANGE_Y[1] - FLANGE_Y[0])
    )
    vol = await _volume(adapter)
    print(f"  volume after screw holes: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 2.0:
        raise RuntimeError(f"screw holes volume {vol:.1f} != {expected:.1f}")

    # Named collar axis (local X through the origin) so the magnifying lever
    # rides this bore as a revolute in the M6 mated-DOF assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "collar axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
