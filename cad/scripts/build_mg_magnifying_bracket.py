r"""Reproduction script: magnifying-lever bracket (book ch. 20, pp. 46-49).

The black fitting that affixes the magnifying lever rod to the summing
lever: a flange butted against the coefficients plate's front edge FACE
and a forward arm ending in a collar (O12, bore 6.2) the O6 rod clamps
into. The collar/rod sit at the plate centreline (machine y 979.7, after the
2026-08-02 Cascade-A drop). The flange seats flush on the summing lever's
installed front face and carries two native #2 counterbores entering -Z.
The arm and collar remain unchanged. Joint geometry and hole specifications
are owned by magnifying_bracket_joint_layout, independently of assemblies.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_bracket.py
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
    apply_drawing_precision,
    set_dimension_symmetric_tolerance,
    set_dimension_bilateral_tolerance,
    set_dimension_display_precision,
)
from mg_magnifying_bracket_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)
from mg_magnifying_lever_geom import COLLAR_HALF_LEN as LEVER_COLLAR_HALF_LEN
from magnifying_bracket_joint_layout import (
    BRACKET_HOLE_POINTS,
    CLEARANCE_DIA,
    CLEARANCE_SPEC,
    COUNTERBORE_DIA,
    COUNTERBORE_DEPTH,
    COUNTERBORE_DEPTH_BAND,
    PLATE_THICKNESS_BAND,
    POSITION_BAND,
    SIDE_PLATE_X as FLANGE_X,
    SIDE_PLATE_Y as FLANGE_Y,
    SIDE_PLATE_Z as FLANGE_Z,
    SIDE_PLATE_THICKNESS,
)
from _holes import wizard_holes

PART_NAME = "mg-magnifying-bracket"
MATERIAL = "Plain Carbon Steel"  # black hardware

COLLAR_OD = 12.0  # rod collar (low)
COLLAR_BORE = 6.2  # the O6 magnifying rod clamps in (derived)
# along X. CONFIG owns it (output.magnifier_collar_half_len_mm): the error
# budget derives the magnifier's minimum pose from the collar face, so the
# config value must drive the CAD, not merely be asserted equal to it.
COLLAR_HALF_LEN = LEVER_COLLAR_HALF_LEN
ARM_HALF_X = 5.0  # arm 10 wide (x), y -3..+4.5 (low)
ARM_Y = (-3.0, 4.5)
ARM_Z = (4.0, 58.3)

async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


def _name_mounting_dimensions(adapter) -> None:
    """Resolve native Hole Wizard dimensions before assigning stable names."""
    from _common import _early_bound
    model = _early_bound(adapter.currentModel, "IPartDoc")
    flange = _early_bound(model.FeatureByName("Flange"), "IFeature")
    height = flange.Parameter("D1")
    if height is None:
        raise RuntimeError("Flange: missing native extrusion height")
    height = _early_bound(height, "IDimension")
    if abs(float(height.SystemValue) * 1000.0 - (FLANGE_Y[1] - FLANGE_Y[0])) > 1e-5:
        raise RuntimeError("Flange: native extrusion height differs from contract")
    height.Name = "FlangeHeight"
    feature = _early_bound(model.FeatureByName("MountingCounterbores"), "IFeature")
    required = {
        "HoleDiameter": ("dia", CLEARANCE_DIA),
        "CounterBoreDiameter": ("dia", COUNTERBORE_DIA),
        "CounterBoreDepth": ("depth", COUNTERBORE_DEPTH),
    }
    matches = {name: [] for name in required}
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension(), "IDimension")
        native_name = str(dimension.FullName).split("@")[0].lower()
        for name, (kind, nominal) in required.items():
            if kind in native_name and abs(float(dimension.SystemValue) * 1000.0 - nominal) < 1e-5:
                matches[name].append(dimension)
        display = feature.GetNextDisplayDimension(display)
    for name, dimensions in matches.items():
        if len(dimensions) != 1:
            raise RuntimeError(f"MountingCounterbores: expected one native {name}, found {len(dimensions)}")
        dimensions[0].Name = name


async def _mounting_coordinate_dimensions(adapter) -> None:
    """Own mounting coordinates from the real west edge and lower face."""
    from _common import anchor_point_to_point
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    check("mounting coordinate sketch", await adapter.create_sketch("Front"))
    dimensions = SketchDims()
    for index, point in enumerate(BRACKET_HOLE_POINTS):
        start = (FLANGE_X[0], FLANGE_Y[0])
        corner = (point[0], start[1])
        lines = await add_line_chain(adapter, [start, corner, point[:2]], close=False)
        await anchor_point_to_origin(adapter, f"{lines[0]}.start", *start, "mounting west lower corner")
        dimensions.record(f"MountingOriginX{index}", None)
        dimensions.record(f"MountingOriginY{index}", None)
        await anchor_point_to_point(
            adapter, f"{lines[0]}.start", f"{lines[0]}.end",
            corner[0] - start[0], 0.0, "mounting X station",
        )
        dimensions.record(f"MountingX{index}", None)
        await anchor_point_to_point(
            adapter, f"{lines[1]}.start", f"{lines[1]}.end",
            0.0, point[1] - start[1], "mounting row",
        )
        dimensions.record(f"MountingY{index}", None)
    await ensure_fully_defined(adapter, "mounting coordinate sketch")
    check("exit mounting coordinate sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "MountingCoordinates")
    dimensions.apply(adapter, "MountingCoordinates")
    for name in ("MountingX0", "MountingX1", "MountingY0", "MountingY1"):
        set_dimension_symmetric_tolerance(adapter, "MountingCoordinates", name, POSITION_BAND)
        set_dimension_display_precision(adapter, "MountingCoordinates", name, 2)
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "MountingCoordinates", "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot hide mounting coordinate sketch")
    model.BlankSketch()
    model.ClearSelection2(True)


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
    # The signed west corner drives its unsigned origin distance positively.
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
    # Exact rectangular intersection with the unchanged arm.
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

    wizard_holes(
        adapter,
        CLEARANCE_SPEC,
        BRACKET_HOLE_POINTS,
        (0.0, 0.0, -1.0),
        "magnifying bracket counterbores",
        name="MountingCounterbores",
        expect_dia_mm=CLEARANCE_DIA,
    )
    cut_volume = (
        len(BRACKET_HOLE_POINTS) * math.pi / 4.0 * (
            CLEARANCE_DIA ** 2 * SIDE_PLATE_THICKNESS
            + (COUNTERBORE_DIA ** 2 - CLEARANCE_DIA ** 2) * COUNTERBORE_DEPTH
        )
    )
    expected -= cut_volume
    await volume_check(
        adapter, "bracket mounting counterbores", expected, 0.02 * cut_volume
    )

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

    # Native model dimensions own the flange and head-seat bands; the print
    # imports the plan dimensions and exposes the stepped holes by callout.
    _name_mounting_dimensions(adapter)
    await _mounting_coordinate_dimensions(adapter)
    set_dimension_symmetric_tolerance(
        adapter, "FlangeProfile", "FlangeDepth", PLATE_THICKNESS_BAND
    )
    set_dimension_symmetric_tolerance(
        adapter, "MountingCounterbores", "CounterBoreDepth", COUNTERBORE_DEPTH_BAND
    )
    set_dimension_bilateral_tolerance(
        adapter, "MountingCounterbores", "CounterBoreDiameter", 0.0, 0.10
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
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
