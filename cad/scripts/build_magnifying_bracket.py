r"""Reproduction script: magnifying-lever bracket (book ch. 20, pp. 46-49).

The black fitting that affixes the magnifying lever rod to the summing
lever: a flange butted against the coefficients plate's front edge FACE
and a forward arm ending in a collar (O12, bore 6.2) the O6 rod clamps
into. The collar/rod sit at the plate centreline (machine y 979.7, after the
2026-08-02 Cascade-A drop) so the rod is coplanar with the plate; the flange
spans the plate's full height
(977.16..982.24). The current source model is an UNDRILLED blank. The older
mounting-screw description predates the butt-flange orientation and conflicts
on the screw axis/stations, so no hole geometry is asserted here.

Layout: origin at the collar centre (machine (+40, 979.7, -128.3) after the
2026-07-04 depth re-anchor); collar axis along X (the rod direction), arm
runs +Z from the collar back beside the plate's east edge (machine
-124.3 -> -70), flange at local z 47.3..51.85 (machine -81..-76.45,
unchanged) butting the plate's real front face at -76.2 with a 0.25 gap. The
part is authored MACHINE-handed and placed IDENTITY, so local axes are
machine axes (the flange, its only x-asymmetric feature, sits at the
machine-east local -x). Dimensions: cad/DIMENSIONS.md ch. 20 (M6.4, low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

import _telemetry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from magnifying_bracket_spec import (
    ARM_HALF_X,
    ARM_Y,
    ARM_Z,
    COLLAR_BORE,
    COLLAR_HALF_LEN,
    COLLAR_OD,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FLANGE_X,
    FLANGE_Y,
    FLANGE_Z,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "magnifying-bracket"
MATERIAL = "Plain Carbon Steel"  # black hardware

# Nominals live in magnifying_bracket_spec (imported above): the drawing
# reads the same constants to aim its sheet picks.


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive the sketch
    # dimensions below. A GUI fine-tune edits THESE (Tools > Equations) -- e.g.
    # CollarOD or FlangeX0 -- never an auto "D3@Sketch2". The mm suffix is
    # load-bearing: this is an INCH document and the equation manager reads BARE
    # numbers in document units, so an unsuffixed "200" would be read as 200 in
    # and blow the part up 25.4x. The arm/flange Y bounds drive only the extrude
    # DEPTH/OFFSET (feature params, not sketch dims), so they are knobs with
    # nothing in the deferred drive batch -- matches the exemplars.
    await set_global(adapter, "CollarOD", f"{COLLAR_OD}mm")
    await set_global(adapter, "CollarBore", f"{COLLAR_BORE}mm")
    await set_global(adapter, "CollarHalfLen", f"{COLLAR_HALF_LEN}mm")
    await set_global(adapter, "ArmHalfX", f"{ARM_HALF_X}mm")
    await set_global(adapter, "ArmZ0", f"{ARM_Z[0]}mm")
    await set_global(adapter, "ArmZ1", f"{ARM_Z[1]}mm")
    await set_global(adapter, "ArmY0", f"{ARM_Y[0]}mm")
    await set_global(adapter, "ArmY1", f"{ARM_Y[1]}mm")
    await set_global(adapter, "FlangeX0", f"{FLANGE_X[0]}mm")
    await set_global(adapter, "FlangeX1", f"{FLANGE_X[1]}mm")
    await set_global(adapter, "FlangeZ0", f"{FLANGE_Z[0]}mm")
    await set_global(adapter, "FlangeZ1", f"{FLANGE_Z[1]}mm")
    await set_global(adapter, "FlangeY0", f"{FLANGE_Y[0]}mm")
    await set_global(adapter, "FlangeY1", f"{FLANGE_Y[1]}mm")

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims as the define_* helper emits each dim; the drive equations are
    # collected here and applied in one deferred batch at the end (every equation
    # target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Collar tube about the X axis (revolved rectangle).
    collar = SketchDims()
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
    # Emission (rectilinear chain): seg0 width (= 2*HalfLen), seg1 wall span
    # (= OD/2 - Bore/2), THEN the (-HalfLen, Bore/2) corner anchor (x then z;
    # both non-zero). Anchor dims are UNSIGNED distances from the origin: the
    # corner sits at x = -HalfLen, so its dim shows +HalfLen and drives positive.
    await define_rectilinear_chain(
        adapter, profile, profile_rect, label="collar", dims=collar,
        names=["WallLen", "WallSpan", "CornerX", "CornerZ"],
        drives=[
            '2 * "CollarHalfLen"',
            '"CollarOD" / 2 - "CollarBore" / 2',
            '"CollarHalfLen"',
            '"CollarBore" / 2',
        ],
    )
    # The centerline shares no vertex with the off-axis profile rectangle,
    # so it carries its own scheme: horizontal on the axis, length dim,
    # start anchored to the origin. Both its dims are recorded after the chain
    # dims, in creation order: length, then the on-axis start anchor distance.
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
    collar.record("CenterlineLen", '2 * "CollarHalfLen"')
    await anchor_point_to_origin(
        adapter, f"{centerline}.start", -COLLAR_HALF_LEN, 0.0, "centerline start"
    )
    collar.record("CenterlineX", '"CollarHalfLen"')  # unsigned: anchor at x = -HalfLen
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "revolve collar", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Collar")
    expected = (
        math.pi
        * ((COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE / 2.0) ** 2)
        * 2.0
        * COLLAR_HALF_LEN
    )
    vol = await _volume(adapter)
    _telemetry.info(f"volume after collar: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"collar volume {vol:.1f} != {expected:.1f}")

    # 2. Arm from the collar shell toward the plate (+Z), Top sketch.
    arm_dims = SketchDims()
    check("create_sketch arm", await adapter.create_sketch("Top"))
    arm_rect = [
        (-ARM_HALF_X, -ARM_Z[1]),
        (ARM_HALF_X, -ARM_Z[1]),
        (ARM_HALF_X, -ARM_Z[0]),
        (-ARM_HALF_X, -ARM_Z[0]),
    ]
    arm = await add_line_chain(adapter, arm_rect)
    # Emission: seg0 width (= 2*HalfX), seg1 depth (= Z1 - Z0), THEN the
    # (-HalfX, -Z1) corner anchor (x then z). Top sketch maps sketch y -> -Z, so
    # the anchor z lands at the magnitude Z1 (unsigned distance).
    await define_rectilinear_chain(
        adapter, arm, arm_rect, label="arm", dims=arm_dims,
        names=["ArmWidth", "ArmDepth", "ArmCornerX", "ArmCornerZ"],
        drives=[
            '2 * "ArmHalfX"',
            '"ArmZ1" - "ArmZ0"',
            '"ArmHalfX"',
            '"ArmZ1"',
        ],
    )
    await ensure_fully_defined(adapter, "arm sketch")
    check("exit_sketch arm", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmProfile")
    drive_jobs += arm_dims.apply(adapter, "ArmProfile")
    extrude_at_offset(adapter, ARM_Y[1] - ARM_Y[0], ARM_Y[0])
    name_last_feature(adapter, "Arm")
    v_arm = 2.0 * ARM_HALF_X * (ARM_Z[1] - ARM_Z[0]) * (ARM_Y[1] - ARM_Y[0])
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    _telemetry.info(f"volume after arm: {vol:.1f} mm^3 (+{added:.1f}, solid {v_arm:.1f})")
    if not (0.85 * v_arm <= added <= 1.01 * v_arm):
        raise RuntimeError(f"arm: added {added:.1f}, expected ~{v_arm:.1f}")
    expected = vol

    # 3. Flange under the plate's front edge.
    flange_dims = SketchDims()
    check("create_sketch flange", await adapter.create_sketch("Top"))
    flange_rect = [
        (FLANGE_X[0], -FLANGE_Z[1]),
        (FLANGE_X[1], -FLANGE_Z[1]),
        (FLANGE_X[1], -FLANGE_Z[0]),
        (FLANGE_X[0], -FLANGE_Z[0]),
    ]
    flange = await add_line_chain(adapter, flange_rect)
    # Emission: seg0 width (= X1 - X0), seg1 depth (= Z1 - Z0), THEN the
    # (X0, -Z1) corner anchor (x then z). The flange is x-asymmetric: its corner
    # sits at x = X0 = -20, so the anchor dim shows the magnitude 20 and must
    # drive POSITIVE -- negate the signed FlangeX0 global ('-"FlangeX0"').
    await define_rectilinear_chain(
        adapter, flange, flange_rect, label="flange", dims=flange_dims,
        names=["FlangeWidth", "FlangeDepth", "FlangeCornerX", "FlangeCornerZ"],
        drives=[
            '"FlangeX1" - "FlangeX0"',
            '"FlangeZ1" - "FlangeZ0"',
            '-"FlangeX0"',
            '"FlangeZ1"',
        ],
    )
    await ensure_fully_defined(adapter, "flange sketch")
    check("exit_sketch flange", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeProfile")
    drive_jobs += flange_dims.apply(adapter, "FlangeProfile")
    extrude_at_offset(adapter, FLANGE_Y[1] - FLANGE_Y[0], FLANGE_Y[0])
    name_last_feature(adapter, "Flange")
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
    _telemetry.info(f"volume after flange: {vol:.1f} mm^3 (+{added:.1f}, net {v_net:.1f})")
    if abs(added - v_net) > 0.02 * v_net:
        raise RuntimeError(f"flange: added {added:.1f}, expected {v_net:.1f}")
    expected = vol

    # Mounting holes are intentionally absent.  The older source description
    # conflicts with this butt-flange revision on both axis and stations; do not
    # turn that unresolved design input into guessed geometry.

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven magnifying-bracket (equations neutral)", expected, 0.005 * expected
    )

    # Named collar axis (local X through the origin) so the magnifying lever
    # rides this bore as a revolute in the M6 mated-DOF assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "collar axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's model dimensions
    # (the collar length, the plan rectangles' widths/depth and their corner
    # stations from the collar axis -- the collar diameters and the Y
    # thicknesses are drawing-added on real edges) and stamp the
    # make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
