r"""Reproduction script: transgear thumbnut (MHA-PD-013; ch. 23 pp. 58-59; 1 used).

The custom knurled #8-32 UNC-2B brass nut seats on the collar's front pilot.
The T24 chain wheel floats under it; the collar's rear face reacts on F
(``pd_transgear_thumbnut_spec`` and the linked assembly fit procedure).

Layout (part frame, ``pd_transgear_thumbnut_spec``): axis local +Y (``Axis1``),
seat face on the Top Plane (y = 0), rim at y = OVERALL_LENGTH.

* ``HeadProfile``: the knurled head as a plain Front-plane rectangle revolved
  about +Y.  Its driving dimensions are the knurl diameter, the head length
  and the overall length from the seat face.
* ``Knurl``: one straight flute cut from a Top-plane seed, circular-patterned
  ``KNURL_TEETH`` times about ``Axis1``.  It comes BEFORE the stem: circular
  patterns of cuts fail on stepped revolved bodies but pattern fine on a
  plain revolved cylinder (``_features.add_reeded_head_and_thread``).  The
  seed puts two crests on the Front Plane, so the axial section shows the
  knurl diameter.
* ``StemProfile``: the waist and flange as a stepped profile revolved onto
  the head's rear face.  Its dimensions are both diameters and the waist
  length; the flange length is the remainder of the overall length.
* ``ThreadBore``: one Hole Wizard #8-32 UNC-2B tapped hole, through all
  from the seat face.
* ``DishProfile``: the dished front face, a cone cut from the rim's Ø down
  to a flat floor, dimensioned by both diameters and the depth from the
  rim's edge to the floor's edge (both edges stand on the finished nut).
* ``Countersinks``: both 90° entry countersinks as one revolved cut, each a
  45° break on the tap-drill edge of a flat face: the seat face at the rear,
  the dish floor at the front.

``RimFace`` (y = OVERALL_LENGTH) and ``DishFloor`` (the dish's flat floor)
are named offset planes for the stud's tip and cut-to-fit stations.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_thumbnut.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    bbox_extent_check,
    check,
    define_polygon_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    _named_dimension,
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_angular_tolerance,
)
from _holes import wizard_holes
from _visibility import blank_reference_geometry
from pd_transgear_thumbnut_spec import (
    CSK_DIA,
    CSK_DIA_DEVIATIONS,
    CSK_DIA_TOL_TYPE,
    CSK_HALF_ANGLE_BAND,
    CSK_HALF_ANGLE_DEG,
    DISH_DEPTH,
    DISH_DIA,
    DISH_FLOOR_CORNER,
    DISH_FLOOR_DIA,
    DISH_FLOOR_Y,
    DISH_RIM_CORNER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLANGE_DIA,
    FLANGE_LENGTH,
    HEAD_DIA,
    HEAD_LENGTH,
    HEAD_REAR_Y,
    KNURL_ROOT_DIA,
    KNURL_TEETH,
    OVERALL_LENGTH,
    REAR_CSK_BREAK,
    RIM_Y,
    TAP_DRILL_DIA,
    TAP_SPEC,
    WAIST_DIA,
    WAIST_LENGTH,
)

PART_NAME = "pd-transgear-thumbnut"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

HEAD_R = HEAD_DIA / 2.0
ROOT_R = KNURL_ROOT_DIA / 2.0
FLANGE_R = FLANGE_DIA / 2.0
WAIST_R = WAIST_DIA / 2.0
DRILL_R = TAP_DRILL_DIA / 2.0
CSK_R = CSK_DIA / 2.0
# How far the flute seed's flanks run past the crests, as a multiple of the
# root-to-crest flank, so the cutter closes outside the head.
_FLUTE_FLANK_RUN = 1.6
_FLUTE_HALF_ANGLE = math.pi / KNURL_TEETH


def _countersink_max_limit(adapter, name: str) -> None:
    """The saved native MAX owns the actual cone, never a hole-note override."""
    _display, dimension = _named_dimension(adapter, "CountersinkProfile", name)
    if abs(float(dimension.SystemValue) * 1000.0 - CSK_DIA) > 1e-6:
        raise RuntimeError(f"{name}: native countersink diameter differs from source")
    tolerance = dimension.Tolerance
    if tolerance is None:
        raise RuntimeError(f"{name}: native countersink tolerance is missing")
    tolerance = _early_bound(tolerance, "IDimensionTolerance")
    tolerance.Type = CSK_DIA_TOL_TYPE
    low, high = (value / 1000.0 for value in CSK_DIA_DEVIATIONS)
    if tolerance.SetValues(low, high) is not True:
        raise RuntimeError(f"{name}: countersink MAX envelope was rejected")
    if (
        int(tolerance.Type) != CSK_DIA_TOL_TYPE
        or abs(float(tolerance.GetMinValue()) - low) > 1e-12
        or abs(float(tolerance.GetMaxValue()) - high) > 1e-12
    ):
        raise RuntimeError(f"{name}: countersink MAX envelope did not persist")


def knurl_seed_points() -> list[tuple[float, float]]:
    """The one flute cutter (Top-plane sketch): root, then both flanks run
    out past their crests.  The crests sit at angles 0 and 2π/N, so the
    pattern puts a crest on every multiple of 2π/N -- including the Front
    Plane on both sides of the axis."""
    root = (
        ROOT_R * math.cos(_FLUTE_HALF_ANGLE),
        ROOT_R * math.sin(_FLUTE_HALF_ANGLE),
    )
    points = [root]
    for crest_angle in (0.0, 2.0 * _FLUTE_HALF_ANGLE):
        crest = (HEAD_R * math.cos(crest_angle), HEAD_R * math.sin(crest_angle))
        points.append(
            (
                root[0] + _FLUTE_FLANK_RUN * (crest[0] - root[0]),
                root[1] + _FLUTE_FLANK_RUN * (crest[1] - root[1]),
            )
        )
    (x1, y1), (x2, y2) = points[1], points[2]
    # The cutter's outer edge must clear the head so the flute is the plain
    # V between two crests.
    if math.hypot((x1 + x2) / 2.0, (y1 + y2) / 2.0) <= HEAD_R:
        raise AssertionError("knurl seed's outer edge cuts into the head")
    return points


def _flute_area() -> float:
    """Head cross-section one flute removes: the V from the root to the two
    crests plus the circular segment between the crests."""
    half = _FLUTE_HALF_ANGLE
    triangle = HEAD_R * math.sin(half) * (HEAD_R * math.cos(half) - ROOT_R)
    segment = HEAD_R**2 / 2.0 * (2.0 * half - math.sin(2.0 * half))
    return triangle + segment


def _dish_volume() -> float:
    """Solid the dish removes once the tap drill is through: the frustum from
    the rim's Ø to the floor's, less the drill inside it."""
    r1, r2, h = DISH_RIM_CORNER[0], DISH_FLOOR_CORNER[0], DISH_DEPTH
    return math.pi * h * ((r1**2 + r1 * r2 + r2**2) / 3.0 - DRILL_R**2)


V_HEAD = math.pi * HEAD_R**2 * HEAD_LENGTH
V_FLUTE = _flute_area() * HEAD_LENGTH
V_KNURLED = V_HEAD - KNURL_TEETH * V_FLUTE
V_STEM = math.pi * (FLANGE_R**2 * FLANGE_LENGTH + WAIST_R**2 * WAIST_LENGTH)
V_THREAD = math.pi * DRILL_R**2 * OVERALL_LENGTH
V_DISH = _dish_volume()
V_REAR_CSK = math.pi * REAR_CSK_BREAK**2 * (DRILL_R + REAR_CSK_BREAK / 3.0)
V_FRONT_CSK = V_REAR_CSK  # the same break, on the flat dish floor
V_TOTAL = V_KNURLED + V_STEM - V_THREAD - V_DISH - V_REAR_CSK - V_FRONT_CSK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("OverallLength", OVERALL_LENGTH),
        ("HeadDia", HEAD_DIA),
        ("HeadLength", HEAD_LENGTH),
        ("FlangeDia", FLANGE_DIA),
        ("WaistDia", WAIST_DIA),
        ("WaistLength", WAIST_LENGTH),
        ("DishDia", DISH_DIA),
        ("DishFloorDia", DISH_FLOOR_DIA),
        ("DishDepth", DISH_DEPTH),
        ("CountersinkDia", CSK_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "CountersinkHalfAngle", f"{CSK_HALF_ANGLE_DEG}deg")

    drive_jobs: list[tuple[str, str]] = []

    # --- Head: a plain cylinder, rear face to rim -------------------------
    # The centerline merges into the two axis corners at creation, so the
    # chain's own relations define it.
    head = SketchDims()
    check("create_sketch head profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    head_axis = check(
        "head axis", await adapter.add_centerline(0.0, HEAD_REAR_Y, 0.0, RIM_Y)
    )
    head_points = [
        (0.0, HEAD_REAR_Y),
        (HEAD_R, HEAD_REAR_Y),
        (HEAD_R, RIM_Y),
        (0.0, RIM_Y),
    ]
    head_lines = await add_line_chain(adapter, head_points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(head_lines):
        relation = "horizontal" if index % 2 == 0 else "vertical"
        check(
            f"head profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "head profile on the axis",
        await adapter.add_sketch_constraint(
            f"{head_lines[0]}.start", "origin", "vertical_points"
        ),
    )
    await add_diametric_linear_dimension(
        adapter,
        head_axis,
        head_lines[1],
        (HEAD_R + 4.0, RIM_Y - HEAD_LENGTH / 2.0),
        "HeadDia",
    )
    head.record("HeadDia", '"HeadDia"')
    check(
        "head length",
        await adapter.add_sketch_dimension(head_lines[1], None, "linear", HEAD_LENGTH),
    )
    head.record("HeadLength", '"HeadLength"')
    # Overall length: the rim's outer corner from the seat face (the sketch
    # origin), the one axial dimension the stud's cut-to-fit rides on.
    await dimension_between(
        adapter,
        f"{head_lines[1]}.end",
        "origin",
        "vertical_distance",
        OVERALL_LENGTH,
        "overall length from the seat face",
    )
    head.record("OverallLength", '"OverallLength"')
    await ensure_fully_defined(adapter, "head profile")
    check("exit_sketch head profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check("revolve head", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Head")
    await volume_check(adapter, "plain head", V_HEAD, 0.005 * V_HEAD)
    await bbox_extent_check(adapter, "head length", "y", HEAD_LENGTH)
    await bbox_extent_check(adapter, "head diameter", "x", HEAD_DIA)

    # The mate axis: the first reference axis, so it is Axis1; the knurl
    # patterns about it.
    nut_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "thumbnut axis"
    )
    if nut_axis != "Axis1":
        raise RuntimeError(f"thumbnut axis came back {nut_axis!r}, not Axis1")

    # --- Straight knurl: one flute, patterned ------------------------------
    seed = knurl_seed_points()
    check("create_sketch knurl flute", await adapter.create_sketch("Top"))
    flute_lines = await add_line_chain(adapter, seed)
    await define_polygon_chain(adapter, flute_lines, seed, label="knurl flute")
    await ensure_fully_defined(adapter, "knurl flute seed")
    check("exit_sketch knurl flute", await adapter.exit_sketch())
    name_last_feature(adapter, "KnurlFluteProfile")
    # Top-plane cuts run opposite the sketch normal by default; reversed, the
    # seed runs up through the whole head (it starts in air below it).
    check(
        "cut knurl flute",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=OVERALL_LENGTH + 1.0, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "KnurlFlute")
    await volume_check(adapter, "knurl flute", V_HEAD - V_FLUTE, 0.02 * V_FLUTE + 0.01)
    check(
        f"knurl pattern ×{KNURL_TEETH}",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=nut_axis,
                features=["KnurlFlute"],
                count=KNURL_TEETH,
                geometry_pattern=True,
            )
        ),
    )
    name_last_feature(adapter, "Knurl")
    await volume_check(adapter, "knurled head", V_KNURLED, 0.02 * KNURL_TEETH * V_FLUTE)

    # --- Waist and flange, onto the head's rear face ------------------------
    stem = SketchDims()
    check("create_sketch stem profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    stem_axis = check(
        "stem axis", await adapter.add_centerline(0.0, 0.0, 0.0, HEAD_REAR_Y)
    )
    stem_points = [
        (0.0, 0.0),
        (FLANGE_R, 0.0),
        (FLANGE_R, FLANGE_LENGTH),
        (WAIST_R, FLANGE_LENGTH),
        (WAIST_R, HEAD_REAR_Y),
        (0.0, HEAD_REAR_Y),
    ]
    stem_lines = await add_line_chain(adapter, stem_points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(stem_lines):
        relation = "horizontal" if index % 2 == 0 else "vertical"
        check(
            f"stem profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{stem_lines[0]}.start", 0.0, 0.0, "seat face on the axis"
    )
    await add_diametric_linear_dimension(
        adapter, stem_axis, stem_lines[1], (FLANGE_R, -4.0), "FlangeDia"
    )
    stem.record("FlangeDia", '"FlangeDia"')
    await add_diametric_linear_dimension(
        adapter, stem_axis, stem_lines[3], (WAIST_R, -8.0), "WaistDia"
    )
    stem.record("WaistDia", '"WaistDia"')
    check(
        "waist length",
        await adapter.add_sketch_dimension(stem_lines[3], None, "linear", WAIST_LENGTH),
    )
    stem.record("WaistLength", '"WaistLength"')
    check(
        "flange length",
        await adapter.add_sketch_dimension(
            stem_lines[1], None, "linear", FLANGE_LENGTH
        ),
    )
    stem.record("FlangeLength", '"OverallLength" - "HeadLength" - "WaistLength"')
    await ensure_fully_defined(adapter, "stem profile")
    check("exit_sketch stem profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StemProfile")
    drive_jobs += stem.apply(adapter, "StemProfile")
    check("revolve stem", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stem")
    volume = await volume_check(
        adapter, "head and stem", V_KNURLED + V_STEM, 0.005 * (V_KNURLED + V_STEM)
    )
    await bbox_extent_check(adapter, "overall length", "y", OVERALL_LENGTH)

    # --- 1/4-20 UNC-2B through, from the seat face -------------------------
    # Drilled while both end faces are still planar, so the removed volume is
    # the plain tap-drill cylinder.
    thread = wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"thumbnut thread ({TAP_SPEC.size} through)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += thread.placement_drive_jobs
    volume = await volume_check(
        adapter, "tapped through", volume - V_THREAD, 0.02 * V_THREAD
    )

    # --- Dished front face ---------------------------------------------------
    # Base on the rim, the cone down to the floor's edge, the floor in to the
    # axis, closed up the axis.  The depth runs between the two corners, the
    # edges the finished nut keeps, not to the axis inside the tap drill.
    dish = SketchDims()
    check("create_sketch dish", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    dish_axis = check(
        "dish axis", await adapter.add_centerline(0.0, DISH_FLOOR_Y, 0.0, RIM_Y)
    )
    dish_base = check("dish base", await adapter.add_line(0.0, RIM_Y, *DISH_RIM_CORNER))
    dish_cone = check(
        "dish cone", await adapter.add_line(*DISH_RIM_CORNER, *DISH_FLOOR_CORNER)
    )
    dish_floor = check(
        "dish floor",
        await adapter.add_line(*DISH_FLOOR_CORNER, 0.0, DISH_FLOOR_Y),
    )
    dish_close = check(
        "dish closure", await adapter.add_line(0.0, DISH_FLOOR_Y, 0.0, RIM_Y)
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("base-cone", f"{dish_base}.end", f"{dish_cone}.start"),
        ("cone-floor", f"{dish_cone}.end", f"{dish_floor}.start"),
        ("floor-close", f"{dish_floor}.end", f"{dish_close}.start"),
        ("close-base", f"{dish_close}.end", f"{dish_base}.start"),
        ("axis start", f"{dish_axis}.start", f"{dish_floor}.end"),
        ("axis end", f"{dish_axis}.end", f"{dish_base}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    for label, entity, relation in (
        ("dish base", dish_base, "horizontal"),
        ("dish floor", dish_floor, "horizontal"),
        ("dish closure", dish_close, "vertical"),
        ("dish axis", dish_axis, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    await anchor_point_to_origin(
        adapter, f"{dish_base}.start", 0.0, RIM_Y, "dish rim on the axis"
    )
    dish.record("DishRim", '"OverallLength"')
    await add_diametric_linear_dimension(
        adapter, dish_axis, f"{dish_base}.end", (DISH_DIA / 4.0, RIM_Y + 3.0), "DishDia"
    )
    dish.record("DishDia", '"DishDia"')
    await add_diametric_linear_dimension(
        adapter,
        dish_axis,
        f"{dish_floor}.start",
        (DISH_FLOOR_DIA / 4.0, RIM_Y + 1.5),
        "DishFloorDia",
    )
    dish.record("DishFloorDia", '"DishFloorDia"')
    await dimension_between(
        adapter,
        f"{dish_floor}.start",
        f"{dish_base}.end",
        "vertical_distance",
        DISH_DEPTH,
        "dish depth, rim edge to floor edge",
    )
    dish.record("DishDepth", '"DishDepth"')
    await ensure_fully_defined(adapter, "dish profile")
    check("exit_sketch dish", await adapter.exit_sketch())
    name_last_feature(adapter, "DishProfile")
    drive_jobs += dish.apply(adapter, "DishProfile")
    check(
        "revolve dish",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Dish")
    volume = await volume_check(adapter, "dished face", volume - V_DISH, 0.01 * V_DISH)

    # --- Both actual entry cones, one shared native diameter/half-angle ----
    apex = CSK_R / math.tan(math.radians(CSK_HALF_ANGLE_DEG))
    profiles = (
        ("rear", [(0.0, apex), (CSK_R, 0.0), (0.0, 0.0)], 0.0,
         "CountersinkDia", "CountersinkHalfAngle"),
        ("front", [(0.0, DISH_FLOOR_Y - apex), (CSK_R, DISH_FLOOR_Y),
                   (0.0, DISH_FLOOR_Y)], DISH_FLOOR_Y,
         "FrontCountersinkDia", "FrontCountersinkHalfAngle"),
    )
    countersink = SketchDims()
    check("create_sketch countersinks", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    csk_axis = check(
        "countersink axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, DISH_FLOOR_Y),
    )
    chains = [(profile, await add_line_chain(adapter, profile[1])) for profile in profiles]
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("countersink axis vertical", csk_axis, None, "vertical"),
        ("countersink axis seat", f"{csk_axis}.start", "origin", "coincident"),
        ("countersink axis floor", f"{csk_axis}.end", f"{chains[1][1][1]}.end", "coincident"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    for (label, points, seat_y, dia_name, angle_name), lines in chains:
        cone, base, axis = lines
        for i in range(3):
            check(
                f"{label} countersink junction {i}",
                await adapter.add_sketch_constraint(
                    f"{lines[i]}.end", f"{lines[(i + 1) % 3]}.start", "coincident"
                ),
            )
        check(f"{label} countersink base", await adapter.add_sketch_constraint(base, None, "horizontal"))
        check(f"{label} countersink axis", await adapter.add_sketch_constraint(axis, None, "vertical"))
        if seat_y == 0.0:
            check("rear countersink seat", await adapter.add_sketch_constraint(f"{base}.end", "origin", "coincident"))
        else:
            await anchor_point_to_origin(adapter, f"{base}.end", 0.0, seat_y, f"{label} countersink seat")
            countersink.record(None, '"OverallLength" - "DishDepth"')
        await add_diametric_linear_dimension(
            adapter, csk_axis, f"{base}.start",
            text_xy=(CSK_R + 1.0, seat_y), label=f"{label} countersink diameter",
        )
        countersink.record(dia_name, '"CountersinkDia"')
        check(
            f"{label} countersink half-angle",
            await adapter.add_sketch_dimension(cone, axis, "angular", CSK_HALF_ANGLE_DEG),
        )
        countersink.record(angle_name, '"CountersinkHalfAngle"')
    await ensure_fully_defined(adapter, "countersink profiles")
    check("exit_sketch countersinks", await adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkProfile")
    drive_jobs += countersink.apply(adapter, "CountersinkProfile")
    check(
        "revolve countersinks",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Countersinks")
    v_csk = V_REAR_CSK + V_FRONT_CSK
    await volume_check(adapter, "countersinks", volume - v_csk, 0.03 * v_csk + 0.05)

    # --- Named stations for the stud: the rim and the dish floor ------------
    for plane, offset, drive in (
        ("RimFace", RIM_Y, '"OverallLength"'),
        ("DishFloor", DISH_FLOOR_Y, '"OverallLength" - "DishDepth"'),
    ):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=offset
                )
            ),
        )
        name_last_feature(adapter, plane)
        blank_reference_geometry(adapter, ((plane, "PLANE"),))
        plane_offset = name_dimensions(adapter, plane, [f"{plane}Offset"])
        drive_jobs.append((plane_offset[0], drive))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven thumbnut (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # Model-owned controls on both actual cones; general printed bands govern
    # the remaining turned sizes. The seat is a clamp, not a running face.
    for name in ("CountersinkDia", "FrontCountersinkDia"):
        _countersink_max_limit(adapter, name)
    set_dimension_symmetric_angular_tolerance(
        adapter, "CountersinkProfile", "CountersinkHalfAngle", max(CSK_HALF_ANGLE_BAND)
    )
    set_dimension_symmetric_angular_tolerance(
        adapter, "CountersinkProfile", "FrontCountersinkHalfAngle", max(CSK_HALF_ANGLE_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
