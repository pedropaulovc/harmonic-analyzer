r"""Reproduction script: magnifying-lever bracket (book ch. 20, pp. 46-49).

The black fitting that affixes the magnifying lever rod to the summing
lever: a flange butted against the coefficients plate's front edge FACE
and a forward arm ending in a collar (O12, bore mg_lever_press_fit_geom
.COLLAR_BORE_DIA) the O6 rod is PRESSED into and retained with Loctite 638
(p.46 "firmly affixed"; user ruling 2026-10-11). The collar/rod sit at the
plate centreline (machine y 979.7, after the 2026-08-02 Cascade-A drop). The
flange seats flush on the summing lever's installed front face and carries
two native plain #2 clearance holes entering -Z, the screw heads bearing on
the flange's front face. Joint geometry and hole specifications are owned by
magnifying_bracket_joint_layout, independently of assemblies; the press fit
(bore nominal, band, engagement, budget, installation notes) by the
config-free mg_lever_press_fit_geom, which the lever print and this one share.
``ArmRootFillet`` breaks the three arm-to-flange inside corners on the
flange's front face at the print's single MAX radius.

``ArmSection`` (blanked, on the Right plane): the arm's section in the
profile the RIGHT view prints -- its lower face from the bore axis, the seat
face from the bore axis and the arm's end past that face -- as native
dimensions (machinist review: nothing located the bore axis). Its three
construction lines lie on the arm's end face and the seat face's visible
edge pieces, so the sketch, shown in that view to import its dimensions,
prints nothing the model does not already draw but the bore axis: a
centerline from the collar's centre to the arm's end station, the axis
extended for dimensioning.  ``ArmFootprint`` (blanked, on the Front plane):
the arm's end face as the BOTTOM view draws it, face-on inside the flange's
outline -- its thickness and its lower face from the flange's hole-datum
face as native dimensions, on the flange's east end the arm's +X face
shares.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_bracket.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _fit_deviations import deviations
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle

import _telemetry
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision, set_dimension_display_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance, set_dimension_bilateral_tolerance
from mg_magnifying_bracket_spec import (
    ARM_ROOT_R_BAND,
    ARM_ROOT_R_MAX,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    RADIUS_TOL_TYPE,
)
from mg_lever_press_fit_geom import COLLAR_BORE_DIA, COLLAR_LENGTH_BAND
from mg_magnifying_lever_geom import COLLAR_HALF_LEN as LEVER_COLLAR_HALF_LEN
from magnifying_bracket_joint_layout import (
    BRACKET_HOLE_POINTS,
    CLEARANCE_DIA,
    CLEARANCE_SPEC,
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
# The bore is the press seat for the O6 lever rod: nominal and band come from
# mg_lever_press_fit_geom (ONE config-free read point for the joint).
# Half the collar length along X. CONFIG owns it
# (output.magnifier_collar_half_len_mm): the error
# budget derives the magnifier's minimum pose from the collar face, so the
# config value must drive the CAD, not merely be asserted equal to it.
COLLAR_HALF_LEN = LEVER_COLLAR_HALF_LEN
ARM_HALF_X = 5.0  # arm 10 wide (x), y -3..+4.5 (low)
ARM_Y = (-3.0, 4.5)
# The arm's end stands this far past the flange's mounting face (ArmPastSeat),
# so its length follows the joint layout's seat station: the A1 pose (#1559)
# moved the collar 45.21 forward of the plate, 58.30 -> 103.51 from the axis.
ARM_PAST_SEAT = 3.11
ARM_Z = (4.0, round(FLANGE_Z[1] + ARM_PAST_SEAT, 2))
# The arm-root fillet leaves the flange's front face a flat beside the arm on
# both sides (above the arm 1.85, below it 3.35), so the print's MAX radius
# never runs the fillet onto the flange's edges.
ARM_ROOT_EDGES = (
    ((-ARM_HALF_X, (ARM_Y[0] + ARM_Y[1]) / 2.0, FLANGE_Z[0]), ARM_Y[1] - ARM_Y[0]),
    ((0.0, ARM_Y[0], FLANGE_Z[0]), 2.0 * ARM_HALF_X),
    ((0.0, ARM_Y[1], FLANGE_Z[0]), 2.0 * ARM_HALF_X),
)
if not ARM_ROOT_R_MAX < min(FLANGE_Y[1] - ARM_Y[1], ARM_Y[0] - FLANGE_Y[0]):
    raise AssertionError("the arm-root fillet would leave no flat on the flange's front face")


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


def _make_construction(adapter, entity: str) -> None:
    """Turn one sketch segment into construction geometry, and prove it."""
    from _com import _early_bound
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: failed to become construction geometry")


def _resolve_native_mounting_dimensions(adapter) -> dict[str, str]:
    """Name the extrusion height; resolve Wizard roles without renaming them."""
    from _com import _early_bound
    model = _early_bound(adapter.currentModel, "IPartDoc")
    flange = _early_bound(model.FeatureByName("Flange"), "IFeature")
    height = flange.Parameter("D1")
    if height is None:
        raise RuntimeError("Flange: missing native extrusion height")
    height = _early_bound(height, "IDimension")
    if abs(float(height.SystemValue) * 1000.0 - (FLANGE_Y[1] - FLANGE_Y[0])) > 1e-5:
        raise RuntimeError("Flange: native extrusion height differs from contract")
    height.Name = "FlangeHeight"
    feature = _early_bound(model.FeatureByName("MountingHoles"), "IFeature")
    required = {
        "HoleDiameter": ("dia", CLEARANCE_DIA),
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
    resolved = {}
    for name, dimensions in matches.items():
        if len(dimensions) != 1:
            raise RuntimeError(f"MountingHoles: expected one native {name}, found {len(dimensions)}")
        resolved[name] = str(dimensions[0].Name)
    return resolved


def _apply_native_mounting_annotations(adapter, native_names: dict[str, str]) -> None:
    """Give the observed Wizard hole diameter its callout precision; the
    drilled hole takes the title block's DRILLED HOLES band, no native one."""
    set_dimension_display_precision(
        adapter, "MountingHoles", native_names["HoleDiameter"], 3
    )


def _arm_root_radius_max_limit(adapter) -> None:
    """ArmRootR as the single limit "R1.0 MAX" carrying the band's deviations
    (build_ch_pivot_bracket._corner_radius_max_limit's recipe)."""
    from _com import _early_bound
    lower, upper = deviations(ARM_ROOT_R_BAND)
    _, dimension = _named_dimension(adapter, "ArmRootFillet", "ArmRootR")
    label = "ArmRootR@ArmRootFillet"
    value = float(dimension.SystemValue)
    if not math.isclose(value, ARM_ROOT_R_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max {ARM_ROOT_R_MAX}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = RADIUS_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != RADIUS_TOL_TYPE
        or not math.isclose(float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12)
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {ARM_ROOT_R_MAX:g} MAX")


async def _mounting_coordinate_dimensions(adapter) -> None:
    """Own mounting coordinates from the real west edge and lower face."""
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
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive the sketch
    # dimensions below. A GUI fine-tune edits THESE (Tools > Equations) -- e.g.
    # CollarOD or FlangeX0 -- never an auto "D3@Sketch2". The mm suffix is
    # load-bearing: this is an INCH document and the equation manager reads BARE
    # numbers in document units, so an unsuffixed "200" would be read as 200 in
    # and blow the part up 25.4x. The arm/flange Y bounds drive the extrude
    # DEPTH/OFFSET (feature params, not sketch dims) and the ArmSection witness
    # dimensions the RIGHT view prints -- matches the exemplars.
    await set_global(adapter, "CollarOD", f"{COLLAR_OD}mm")
    await set_global(adapter, "CollarBore", f"{COLLAR_BORE_DIA}mm")
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
    await set_global(adapter, "ArmRootRMax", f"{ARM_ROOT_R_MAX}mm")

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims as the define_* helper emits each dim; the drive equations are
    # collected here and applied in one deferred batch at the end (every equation
    # target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Collar tube about the X axis: an annulus on the Right plane (normal
    # +X), extruded mid-plane so it spans x -HalfLen..+HalfLen. Two on-axis
    # circles, so each records ONLY its diameter dim -- and those are the
    # print's: the end view (RIGHT) imports the O12 and the press-seat bore
    # (its reference nominal, under the matched-fit callout) natively, where
    # the old revolved half-profile put the bore on a hidden wall line.
    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, COLLAR_OD / 2.0, "collar OD", dims=collar,
        names=(None, None, "CollarOd"),
        drives=(None, None, '"CollarOD"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, COLLAR_BORE_DIA / 2.0, "collar bore", dims=collar,
        names=(None, None, "CollarBore"),
        drives=(None, None, '"CollarBore"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "extrude collar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * COLLAR_HALF_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Collar")
    # The mid-plane extrude's one dimension is the collar's full length; the
    # TOP view prints it.
    drive_jobs += [
        (name_dimensions(adapter, "Collar", ["CollarLen"])[0], '2 * "CollarHalfLen"')
    ]
    expected = (
        math.pi
        * ((COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE_DIA / 2.0) ** 2)
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

    # Arm-to-flange inside corners on the flange's front (-Z) face: the arm's
    # west face and both its Y faces meet the flange there.  Filleted AT the
    # print's MAX radius; each straight edge adds (1 - pi/4) R^2 per length
    # (the two blends at the arm's west corners are within the tolerance).
    check(
        "fillet arm-to-flange inside corners",
        await adapter.add_fillet(
            ARM_ROOT_R_MAX, [list(point) for point, _length in ARM_ROOT_EDGES], propagate=False
        ),
    )
    name_last_feature(adapter, "ArmRootFillet")
    arm_root = name_dimensions(adapter, "ArmRootFillet", ["ArmRootR"])
    drive_jobs.append((arm_root[0], '"ArmRootRMax"'))
    v_arm_root = (1.0 - math.pi / 4.0) * ARM_ROOT_R_MAX ** 2 * sum(
        length for _point, length in ARM_ROOT_EDGES
    )
    expected += v_arm_root
    await volume_check(adapter, "arm-to-flange inside corner fillet", expected, 0.15 * v_arm_root)

    # Plain clearance holes through the flange, entering its front (-Z) face,
    # where the screw heads bear.
    wizard_holes(
        adapter,
        CLEARANCE_SPEC,
        BRACKET_HOLE_POINTS,
        (0.0, 0.0, -1.0),
        "magnifying bracket mounting holes",
        name="MountingHoles",
        expect_dia_mm=CLEARANCE_DIA,
    )
    cut_volume = (
        len(BRACKET_HOLE_POINTS) * math.pi / 4.0 * CLEARANCE_DIA ** 2 * SIDE_PLATE_THICKNESS
    )
    expected -= cut_volume
    await volume_check(
        adapter, "bracket mounting holes", expected, 0.02 * cut_volume
    )

    # 4. Arm section witness (ArmSection, blanked; Right plane, sketch (u, v)
    # -> model (-Z, Y)): the RIGHT view shows the arm in profile between the
    # flange's seat face and the collar, and drawing-simplicity-policy.md `How the repository implements the guidelines` wants the arm's
    # station along Z and its lower face from the bore axis as native
    # dimensions (machinist review: nothing located the bore axis). Three
    # construction lines, each on an edge the view already draws: the arm's
    # end face (its full thickness, past the seat face) and the seat face's
    # two visible pieces -- below the arm, from the flange's lower (hole-datum)
    # face up to the arm; above it, from the arm up to the flange's top -- so
    # the sketch, shown in that view to import its dimensions, prints nothing
    # new but the bore axis: a centerline from the arm's end station to the
    # collar's centre, the axis extended for dimensioning (ASME Y14.5), so the
    # arm's 3.00 from the axis reads off the centerline's end at the arm's end
    # face, its two witnesses 3 mm long, not 60 mm back through the arm to the
    # collar's centre. The dimensions the print keeps all take the arm's END
    # corners, so their extension lines run away from the part instead of
    # along the arm's faces. Six dimensions in creation order: the thickness
    # (ArmThickness, unmarked: the print controls it in the bottom view, from
    # ArmFootprint below), the arm's lower face from the bore axis
    # (ArmBelowAxis), the arm's end past the seat face (ArmPastSeat: the
    # arm's end corner to the seat piece's hole-datum corner, so the bore
    # axis has ONE toleranced chain along Z -- SeatToAxis, then this -- and
    # the sheet prints the arm's end from the axis as its parenthesised sum,
    # mreview10 blocker 2), the arm's lower face from the hole-datum flange
    # face (ArmOffset, unmarked: controlled in the bottom view too), the
    # flange above the arm (unmarked) and the seat face from the bore axis
    # (SeatToAxis, the flange's top corner to the origin).
    section = SketchDims()
    check("create_sketch arm section", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    seat_u = -FLANGE_Z[1]
    end_u = -ARM_Z[1]
    axis = check(
        "arm section bore axis",
        await adapter.add_centerline(end_u, 0.0, 0.0, 0.0),
    )
    end = check(
        "arm section end face",
        await adapter.add_line(end_u, ARM_Y[0], end_u, ARM_Y[1]),
    )
    below = check(
        "arm section seat face below the arm",
        await adapter.add_line(seat_u, FLANGE_Y[0], seat_u, ARM_Y[0]),
    )
    above = check(
        "arm section seat face above the arm",
        await adapter.add_line(seat_u, ARM_Y[1], seat_u, FLANGE_Y[1]),
    )
    set_sketch_direct_db(adapter, False)
    for line in (end, below, above):
        _make_construction(adapter, line)
    check(
        "arm section bore axis horizontal",
        await adapter.add_sketch_constraint(axis, None, "horizontal"),
    )
    await anchor_point_to_origin(adapter, f"{axis}.end", 0.0, 0.0, "arm section bore axis end")
    check(
        "arm section bore axis from the arm's end station",
        await adapter.add_sketch_constraint(
            f"{axis}.start", f"{end}.start", "vertical_points"
        ),
    )
    await anchor_point_to_point(
        adapter, f"{end}.start", f"{end}.end",
        0.0, ARM_Y[1] - ARM_Y[0], "arm section ArmThickness",
    )
    section.record("ArmThickness", '"ArmY1" - "ArmY0"')
    await dimension_between(
        adapter, f"{end}.start", f"{axis}.start", "vertical_distance",
        -ARM_Y[0], "arm section ArmBelowAxis",
    )
    section.record("ArmBelowAxis", '-"ArmY0"')
    await dimension_between(
        adapter, f"{end}.start", f"{below}.start", "horizontal_distance",
        ARM_Z[1] - FLANGE_Z[1], "arm section ArmPastSeat",
    )
    section.record("ArmPastSeat", '"ArmZ1" - "FlangeZ1"')
    # Each seat piece's arm-side corner sits on the arm face it was drawn at:
    # below.end on the arm's LOWER face (end.start), above.start on its upper
    # face (end.end).  Pairing same-named corners (below.end with end.end)
    # dragged the piece below the arm up to the arm's top, and ArmOffset's
    # 3.35 then re-solved its seat-face witness to Y +0.35, above the bore
    # axis (retry08 native layout audit: that extension line printed at sheet
    # y 180.4 mm instead of on the hole-datum face at 173.65 mm).
    for piece, corner, arm_corner in (
        (below, "end", "start"),
        (above, "start", "end"),
    ):
        check(
            f"arm section {piece} vertical",
            await adapter.add_sketch_constraint(piece, None, "vertical"),
        )
        check(
            f"arm section {piece}.{corner} on the arm's face",
            await adapter.add_sketch_constraint(
                f"{piece}.{corner}", f"{end}.{arm_corner}", "horizontal_points"
            ),
        )
    check(
        "arm section seat pieces on one station",
        await adapter.add_sketch_constraint(
            f"{below}.end", f"{above}.start", "vertical_points"
        ),
    )
    await dimension_between(
        adapter, f"{below}.start", f"{end}.start", "vertical_distance",
        ARM_Y[0] - FLANGE_Y[0], "arm section ArmOffset",
    )
    section.record("ArmOffset", '"ArmY0" - "FlangeY0"')
    await dimension_between(
        adapter, f"{above}.start", f"{above}.end", "vertical_distance",
        FLANGE_Y[1] - ARM_Y[1], "arm section FlangeAboveArm",
    )
    section.record("FlangeAboveArm", '"FlangeY1" - "ArmY1"')
    await dimension_between(
        adapter, f"{above}.end", "origin", "horizontal_distance",
        FLANGE_Z[1], "arm section SeatToAxis",
    )
    section.record("SeatToAxis", '"FlangeZ1"')
    await ensure_fully_defined(adapter, "arm section sketch")
    check("exit_sketch arm section", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmSection")
    drive_jobs += section.apply(adapter, "ArmSection")

    # 5. Arm footprint witness (ArmFootprint, blanked; Front plane, sketch
    # (u, v) -> model (X, Y)): the BOTTOM view looks at the mounting face and
    # draws the arm's end face face-on, a rectangle inside the flange's
    # outline, so the arm's thickness across the flange and its lower face
    # from the flange's lower (hole-datum) face are controlled THERE, where
    # the footprint is seen (mreview10 blocker 1 wanted the arm tied to a
    # flange edge by a toleranced dimension; the side view's edge-on stack
    # of the same two values crowded the arm's end, Main's retry11 ruling).
    # Two construction lines on the flange's east end, X = FLANGE_X[1], which
    # the arm's +X face shares (ARM_HALF_X == FLANGE_X[1]), so both lie on
    # the one edge the view draws there: the hole-datum face up to the arm's
    # lower face, and the arm's full thickness.  Their dimensions take the
    # flange's and the arm's east corners, so the extension lines run east,
    # away from the part.  Four dimensions in creation order: the corner's
    # anchor (FootprintCornerX, FootprintCornerY), the arm's lower face from
    # the hole-datum face (FootprintOffset) and the thickness
    # (FootprintThickness), every one driven by the globals so an edited
    # flange or arm moves the witness with the body.
    if ARM_HALF_X != FLANGE_X[1]:
        raise RuntimeError(
            "the arm footprint witness lies on the flange's east end, which the "
            f"arm's +X face must share: ARM_HALF_X {ARM_HALF_X} != FLANGE_X[1] {FLANGE_X[1]}"
        )
    footprint = SketchDims()
    check("create_sketch arm footprint", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    end_x = FLANGE_X[1]
    gap = check(
        "arm footprint hole-datum face to the arm",
        await adapter.add_line(end_x, FLANGE_Y[0], end_x, ARM_Y[0]),
    )
    block = check(
        "arm footprint arm thickness",
        await adapter.add_line(end_x, ARM_Y[0], end_x, ARM_Y[1]),
    )
    set_sketch_direct_db(adapter, False)
    for line in (gap, block):
        _make_construction(adapter, line)
    check(
        "arm footprint pieces meet on the arm's lower face",
        await adapter.add_sketch_constraint(f"{gap}.end", f"{block}.start", "coincident"),
    )
    await anchor_point_to_origin(
        adapter, f"{gap}.start", end_x, FLANGE_Y[0], "arm footprint hole-datum corner"
    )
    footprint.record("FootprintCornerX", '"FlangeX1"')
    footprint.record("FootprintCornerY", '-"FlangeY0"')
    # Each piece's far end is pinned over its start (an alignment relation
    # and one vertical dim, as the section's ArmThickness is).
    await anchor_point_to_point(
        adapter, f"{gap}.start", f"{gap}.end",
        0.0, ARM_Y[0] - FLANGE_Y[0], "arm footprint FootprintOffset",
    )
    footprint.record("FootprintOffset", '"ArmY0" - "FlangeY0"')
    await anchor_point_to_point(
        adapter, f"{block}.start", f"{block}.end",
        0.0, ARM_Y[1] - ARM_Y[0], "arm footprint FootprintThickness",
    )
    footprint.record("FootprintThickness", '"ArmY1" - "ArmY0"')
    await ensure_fully_defined(adapter, "arm footprint sketch")
    check("exit_sketch arm footprint", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmFootprint")
    drive_jobs += footprint.apply(adapter, "ArmFootprint")

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

    # Named collar axis (local X through the origin): the lever rod's press
    # seat. The assembly places the bracket at its joint origin and locks it to
    # the lever (they rock together about the knife edge), so the axis is a
    # reference, not a revolute.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "collar axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Native model dimensions own the coordinate and press-stack bands; the
    # print imports the plan dimensions and exposes the plain holes by
    # callout. The flange's thickness (the screws' grip) takes the title
    # block's .XXX band and the bore is a reference nominal under its
    # matched-fit callout (mg_magnifying_bracket_spec.COLLAR_BORE_CALLOUT), so
    # neither carries a native band. The length band is mg_lever_press_fit_geom's
    # (upper, lower) contract: the press contact is the collar's length less
    # the lever's dome, so the length's band bounds the installation force.
    native_mounting_names = _resolve_native_mounting_dimensions(adapter)
    await _mounting_coordinate_dimensions(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "Collar", "CollarLen", *deviations(COLLAR_LENGTH_BAND)
    )
    _apply_native_mounting_annotations(adapter, native_mounting_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _arm_root_radius_max_limit(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Isometric View Note": ISOMETRIC_VIEW_NOTE},
    )
    blank_reference_sketches(adapter, ("ArmSection", "ArmFootprint"))
    # Annotation changes must preserve the cut holes through the final rebuild,
    # not merely at the earlier, pre-annotation equation check.
    await force_rebuild(adapter)
    await volume_check(
        adapter, "final magnifying-bracket (annotations neutral)", expected, 0.02 * cut_volume
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
