r"""Reproduction script: magnifying-lever bracket (book ch. 20, pp. 46-49).

The black fitting that affixes the magnifying lever rod to the summing
lever: a flange butted against the coefficients plate's front edge FACE
and a forward arm ending in a collar (O12, bore 6.2) the O6 rod clamps
into. The collar/rod sit at the plate centreline (machine y 990) so the
rod is coplanar with the plate; the flange spans the plate's full height
(987.46..992.54) and bolts to its front face. M6.10 fasteners: two O3.2
holes bored +Z through the flange (into the plate front face, engagement
not modeled), placed at local x -9.5/-6.5 -- west of the collar/arm
(|x|>5) so the bore touches only the flange band z 6..14.75.

Layout: origin at the collar centre (machine (+40, 990, -85)); collar
axis along X (the rod direction), arm runs +Z beside the plate's east
edge (machine -85 -> -70), flange at local z 4..8.55 (machine -81..-76.45)
butting the plate's real front face at -76.2 with a 0.25 gap. M6.8: the
flange is the part's only x-asymmetric feature, so the machine mirror is
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
FLANGE_X = (-20.0, 5.0)  # mounting flange, machine x +20..+45. The collar sits
# at machine x +40, EAST of the plate's east edge (+29.45), so the flange reaches
# WEST onto the plate front face: x +20..+29.45 (9.45 wide) butts it, the rest
# wraps the collar. (At -11 the flange stopped at x +29, touching the plate only at
# a 0.45-wide corner sliver -> it read as floating in the top view.) The west tab
# clears channel spring j=0 (z -67.1) -- the flange sits at z <= -76.45, well south.
FLANGE_Y = (-2.54, 2.54)  # spans the plate's FULL height: with the collar/rod now
# at the plate centreline (machine 990, see build_magnifier_assembly LEVER_ROD_Y), the
# flange butts the plate FRONT FACE rather than tucking under it -- machine
# 987.46..992.54 = the coplanar .cs plate band
FLANGE_Z = (4.0, 8.55)  # north face at machine -76.45 = 0.25 south of the plate's
# real FRONT (-Z) face at -76.2 (the plate is the Top-rect z +-76.2, centred on the
# pivot -- NOT -70, an earlier mis-read); the flange butts that face. South face
# flush with the arm (z 4). Reaching to z 14.75 punched 0.45 mm into the plate's
# east edge inside its z-span -> a 13.6 mm^3 clash; stopping south of -76.2 clears it.
SCREW_HOLE_DIA = 3.2  # M6.10 mounting-screw holes (O2.9 fillister shanks)
SCREW_HOLE_X = (-9.5, -6.5)  # machine x +30.5 / +33.5: west of the collar/arm
# (|x|>5), in the flange-only band, so the +Z bore hits ONLY the flange


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

    # NOTE: the two cosmetic mounting-screw holes are omitted. With the flange now
    # a thin slab offset from every standard plane (z 6..14.75, no body on the
    # Front plane at the |x|>5 hole line), FeatureCut auto-select cannot grab a
    # body to bore -- all three overloads fail. The assembly's fillister-screw
    # heads seat flush on the flange front face regardless (engagement into the
    # plate not modeled), so the holes were a non-load cosmetic detail; deferred.

    # Named collar axis (local X through the origin) so the magnifying lever
    # rides this bore as a revolute in the M6 mated-DOF assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "collar axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
