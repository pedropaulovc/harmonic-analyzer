r"""Reproduction script: translational-gearing feed-pinion sleeve (book ch. 23).

The independent feed stage has 12 teeth and a finite standard 32DP PA20
stock #8 master translated rigidly, not a generated profile shift. The
teeth mesh the matching platen rack and are integral with the rear end of
one turned steel sleeve (MHA-PD-010), running on the MHA-PD-023 pin's Ø3.9
shank. Ahead of the teeth, the Ø8.2 h6 boss carries the brass hub and drives
it through its unchanged D-flat; the hub's spigot seats on the step.

Layout: origin at the sleeve's rear face, +Z toward the machine front.
The actual finite gap is cut straight only to FULL_DEPTH. Behind that
station, a revolved finite ground-form cutter envelope leaves partial-depth
gaps to the step; neither an ideal full-face tooth nor a flat run-out slot
stands in for the physical cutting envelope. The bore, flat and oil hole
retain their station owners. A driven span between genuine finite-flank
contacts carries the tooth-thickness inspection limits. Datums: ``Front Plane``
is the rear face (``RearFace``);
``GearFace`` (the step face the hub seats on) and ``FlatEndFace`` are offset
planes; ``Axis1`` is the tooth pattern's Top x Right axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_feed_pinion.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    _feature_by_name,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    set_global,
    set_sketch_direct_db,
)
from _drawing_marks import (
    _named_dimension,
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_prefix,
    set_dimension_symmetric_tolerance,
)
from _drawing_simplified import save_simplified_part
from _gear import ToothedDisc, pattern_about_z
from _holes import cross_hole_volume_mm3
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from paper_drive_stock_native import (
    apply_span_limits,
    author_cutter_endcut,
    author_span,
    measure_one_solid_body_volume,
    check_one_solid_body_volume,
    placed_ground_curve,
    suppress_dimension_input,
)
from pd_transgear_feed_pinion_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    BOSS_DIA,
    BOSS_DIA_DEVIATIONS,
    CUTTER_DIA_MAX,
    CUTTER_RUNOUT_DEVIATIONS,
    CUTTER_RUNOUT_MAX,
    CUTTER_RUNOUT_PLACES,
    CUTTER_RUNOUT_PREFIX,
    CUTTER_RUNOUT_TOL_TYPE,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FLAT_END_STATION,
    FLAT_TO_AXIS,
    FLAT_TO_AXIS_DEVIATIONS,
    FULL_DEPTH,
    FULL_DEPTH_BAND,
    FULL_DEPTH_PREFIX,
    GEAR_DATA,
    OUTSIDE_DIA,
    OUTSIDE_DIA_DEVIATIONS,
    OVERALL_LENGTH,
    PRESSURE_ANGLE_DEG,
    SPAN_DEVIATIONS,
    SPAN_NOMINAL,
    SPAN_PLACES,
    SPAN_PREFIX,
    SPAN_TEETH,
    STOCK_PROFILE,
    ROOT_DIA_DEVIATIONS,
    ROOT_DIA_MIN,
    ROOT_DIA_TOL_TYPE,
    STATION_TOL,
    SURFACE_FINISHES,
    TEETH,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
    TOOTH_SPACE_INSPECTION_PHASE_RAD,
    endcut_volume_bounds_mm3,
)
from pd_transgear_disc_hub_spec import OIL_HOLE_DIA, OIL_HOLE_SLEEVE_Z

PART_NAME = "pd-transgear-feed-pinion"
MATERIAL = "Plain Carbon Steel"  # contract §2.3: steel, made

# TEETH (12, the 4/4 video narration: "this gear has twelve teeth") comes from
# the spec; DP and PA match the catalog-sized rack.
DP = DIAMETRAL_PITCH

# Solid volumes the gates expect (mm^3).
V_BOSS = math.pi * (BOSS_DIA / 2.0) ** 2 * (OVERALL_LENGTH - FACE_WIDTH)
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * OVERALL_LENGTH
# One wall only (+Y): half the through cross-drill of the boss less the bore's.
V_OIL_HOLE = (
    cross_hole_volume_mm3(OIL_HOLE_DIA, BOSS_DIA)
    - cross_hole_volume_mm3(OIL_HOLE_DIA, BORE_DIA)
) / 2.0
_R_BOSS = BOSS_DIA / 2.0
# The D-flat: the boss's circular segment beyond the flat plane, nose to its
# end wall (the bore, 1.95 off the axis, stays under the 3.5 flat).
V_FLAT = (
    _R_BOSS**2 * math.acos(FLAT_TO_AXIS / _R_BOSS)
    - FLAT_TO_AXIS * math.sqrt(_R_BOSS**2 - FLAT_TO_AXIS**2)
) * (OVERALL_LENGTH - FLAT_END_STATION)

# These later cuts do not overlap the end-envelope oracle's stock bodies.
if OIL_HOLE_SLEEVE_Z - OIL_HOLE_DIA / 2.0 <= CUTTER_RUNOUT_MAX:
    raise AssertionError("oil hole overlaps the finite cutter end envelope")
if FLAT_END_STATION <= CUTTER_RUNOUT_MAX:
    raise AssertionError("D-flat overlaps the finite cutter end envelope")
if BORE_DIA / 2.0 >= STOCK_PROFILE.root_radius_min_mm:
    raise AssertionError("bore overlaps the finite cutter end envelope")


async def _straight_stock_gaps(
    adapter: Any, drive_jobs: list[tuple[str, str]]
) -> ToothedDisc:
    """Full native blank, exact finite straight pass only to FULL_DEPTH."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    radius = STOCK_PROFILE.blank_radius_mm
    blank_volume = math.pi * radius * radius * FACE_WIDTH
    check("create_sketch gear blank", await adapter.create_sketch("Front"))
    suppress_dimension_input(adapter)
    await define_circle(adapter, 0.0, 0.0, radius, "feed gear blank")
    await ensure_fully_defined(adapter, "feed gear blank")
    check("exit_sketch gear blank", await adapter.exit_sketch())
    check(
        "extrude full gear blank",
        await adapter.create_extrusion(
            ExtrusionParameters(
                depth=FACE_WIDTH,
                end_condition="Blind",
                reverse_direction=False,
                both_directions=False,
            )
        ),
    )
    await check_one_solid_body_volume(adapter, "feed gear blank", blank_volume, 0.005 * blank_volume)

    check("create_sketch finite straight gap", await adapter.create_sketch("Front"))
    suppress_dimension_input(adapter)
    curves = [
        await placed_ground_curve(adapter, segment, TOOTH_SPACE_INSPECTION_PHASE_RAD)
        for segment in STOCK_PROFILE.native_segments(clearance_radius_mm=radius + 1.0)
    ]
    await ensure_fully_defined(
        adapter, "finite straight gap", fix_entities=curves, allow_fix_escalation=True
    )
    check("exit_sketch finite straight gap", await adapter.exit_sketch())
    check("cut finite straight gap", await adapter.create_cut_extrude(ExtrusionParameters(depth=FULL_DEPTH)))
    name_last_feature(adapter, "StraightToothGap")
    drive_jobs.append(
        (name_dimensions(adapter, "StraightToothGap", ["StraightCutDepth"])[0], '"FullDepth"')
    )
    one_gap = STOCK_PROFILE.gap_area_mm2 * FULL_DEPTH
    await check_one_solid_body_volume(adapter, "finite straight gap", blank_volume - one_gap, 1.0)
    await pattern_about_z(adapter, "StraightToothGap", TEETH, radius, FULL_DEPTH / 2.0)
    name_last_feature(adapter, "StraightToothPattern")
    expected = blank_volume - TEETH * one_gap
    volume = await check_one_solid_body_volume(adapter, "finite straight tooth pattern", expected, 0.01 * expected)
    return ToothedDisc(volume, ("StraightToothGap", "StraightToothPattern"))


async def _stock_cutter_endcut(
    adapter: Any, drive_jobs: list[tuple[str, str]]
) -> tuple[float, tuple[str, str]]:
    """Gate the common authentic cutter end against the owned partial-cut oracle."""
    volume = measure_one_solid_body_volume(adapter)
    features = await author_cutter_endcut(
        adapter, STOCK_PROFILE, CUTTER_DIA_MAX, FULL_DEPTH,
        rotate_rad=TOOTH_SPACE_INSPECTION_PHASE_RAD,
    )
    drive_jobs.append(
        (name_dimensions(adapter, features.plane, ["ToolEndStation"])[0], '"FullDepth"')
    )
    lower_volume, upper_volume = endcut_volume_bounds_mm3()
    removed = (lower_volume + upper_volume) / 2.0
    uncertainty = (upper_volume - lower_volume) / 2.0
    if lower_volume <= uncertainty:
        raise AssertionError("finite cutter endcut is unresolved above its volume error")
    await check_one_solid_body_volume(
        adapter, "finite cutter endcut", volume - removed, uncertainty + 0.01 * removed
    )
    await pattern_about_z(adapter, features.cut, TEETH, OUTSIDE_DIA / 2.0, FULL_DEPTH)
    name_last_feature(adapter, "ToolEndPattern")
    expected = volume - TEETH * removed
    volume = await check_one_solid_body_volume(
        adapter, "finite cutter end pattern", expected, TEETH * (uncertainty + 0.01 * removed)
    )
    return volume, (features.cut, "ToolEndPattern")


async def _cut_flat(
    adapter: Any, drive_jobs: list[tuple[str, str]], volume: float
) -> float:
    """Cut the D-flat on -Y and return the gated volume.

    Sketched on the Right plane (local x -> model -Z, local y -> model Y), the
    section's plane, where the flat shows edge-on: a rectangle whose upper
    edge is the flat, from its end wall to 1 mm past the nose, and whose
    lower edge stands 1 mm clear of the boss.  The end wall is placed from
    the origin (the rear face) and the flat from a construction axis line
    that ends with it past the nose, so the section prints that distance
    just right of the nose, its extension lines short.  The cut is mid-plane
    across the sketch plane, 1 mm clear of the boss either side (a
    through-all cut here ran one way only), so the wall is square across the
    boss.  The wall stops nothing (the hub's flat starts clear ahead of it),
    so the end mill's corner radius is not modelled."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    reach = BOSS_DIA / 2.0 + 1.0
    overrun = OVERALL_LENGTH + 1.0
    check("create_sketch flat", await adapter.create_sketch("Right"))
    suppress_dimension_input(adapter)
    set_sketch_direct_db(adapter, True)
    corners = [
        (-FLAT_END_STATION, -FLAT_TO_AXIS),
        (-overrun, -FLAT_TO_AXIS),
        (-overrun, -reach),
        (-FLAT_END_STATION, -reach),
    ]
    flat, front, floor, rear = await add_line_chain(adapter, corners)
    (axis,) = await add_line_chain(adapter, [(0.0, 0.0), (-overrun, 0.0)], close=False)
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, axis)
    for edge, direction in (
        (flat, "horizontal"),
        (front, "vertical"),
        (floor, "horizontal"),
        (rear, "vertical"),
        (axis, "horizontal"),
    ):
        check(
            f"flat {direction} {edge}",
            await adapter.add_sketch_constraint(edge, None, direction),
        )
    check(
        "flat axis line starts at the origin",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "flat axis line ends under the flat's front end",
        await adapter.add_sketch_constraint(
            f"{axis}.end", f"{flat}.end", "vertical_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{flat}.start",
        "origin",
        "horizontal_distance",
        FLAT_END_STATION,
        "flat's end wall",
    )
    dims.record("FlatEnd", '"FlatEnd"')
    await dimension_between(
        adapter,
        f"{flat}.end",
        f"{axis}.end",
        "vertical_distance",
        FLAT_TO_AXIS,
        "flat from the axis",
    )
    dims.record("FlatToAxis", '"FlatToAxis"')
    await dimension_between(
        adapter,
        f"{flat}.start",
        f"{flat}.end",
        "horizontal_distance",
        overrun - FLAT_END_STATION,
        "flat runs past the nose",
    )
    dims.record("FlatOverrun", '"OverallLength" - "FlatEnd" + 1mm')
    await dimension_between(
        adapter,
        f"{rear}.start",
        f"{rear}.end",
        "vertical_distance",
        reach - FLAT_TO_AXIS,
        "flat cut clears the boss",
    )
    dims.record("FlatReach", '"BossDia" / 2 - "FlatToAxis" + 1mm')
    await ensure_fully_defined(adapter, "flat sketch")
    check("exit_sketch flat", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatProfile")
    drive_jobs += dims.apply(adapter, "FlatProfile")
    check(
        "cut flat",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * reach, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Flat")
    drive_jobs.append(
        (name_dimensions(adapter, "Flat", ["FlatCutWidth"])[0], '"BossDia" + 2mm')
    )
    return await check_one_solid_body_volume(adapter, "D-flat", volume - V_FLAT, 0.01 * V_FLAT)


def _as_construction(adapter, line: str) -> None:
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{line}: failed to become construction geometry")


def _single_limit(
    adapter,
    name: str,
    nominal: float,
    limit_deviations: tuple[float, float],
    tol_type: int,
    printed: str,
) -> None:
    """A SleeveProfile dimension as a single MIN or MAX limit: SolidWorks
    prints its nominal then the limit word, so the nominal is the limit's
    value at the sheet's places; the deviations stay on the native tolerance
    as the model's record of the band."""
    lower, upper = limit_deviations
    _, dimension = _named_dimension(adapter, "SleeveProfile", name)
    label = f"{name}@SleeveProfile"
    # Source globals use the repository's 1e-9 m neutral-readback convention;
    # an inch-document round-trip must not be tested at exact bit equality.
    if not math.isclose(float(dimension.SystemValue), nominal / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {float(dimension.SystemValue) * 1000.0:.7f} is not "
            f"the modelled {nominal:.7f}"
        )
    raw_tolerance = dimension.Tolerance
    if raw_tolerance is None:
        raise RuntimeError(f"{label}: native dimension has no tolerance")
    tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != tol_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: single-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {printed}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): every length carries the load-bearing
    # mm suffix (INCH document). TEETH/DP stay module constants -- the tooth
    # finite stock profile and integer pattern are authored from the spec.
    for name, value in (
        ("FaceWidth", FACE_WIDTH),
        ("OutsideDia", OUTSIDE_DIA),
        ("RootDia", ROOT_DIA_MIN),
        ("BoreDia", BORE_DIA),
        ("BossDia", BOSS_DIA),
        ("FlatToAxis", FLAT_TO_AXIS),
        ("FlatEnd", FLAT_END_STATION),
        ("OverallLength", OVERALL_LENGTH),
        ("OilHoleDia", OIL_HOLE_DIA),
        ("OilHoleZ", OIL_HOLE_SLEEVE_Z),
        ("FullDepth", FULL_DEPTH),
        ("CutterRunoutMax", CUTTER_RUNOUT_MAX),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Preserve the full gear blank's face-width owner, but cut the finite
    # stock gaps straight only over the rack's actual full-depth window.
    disc = await _straight_stock_gaps(adapter, drive_jobs)
    volume = disc.volume
    # The tooth pattern's Top x Right axis is the part's first reference axis:
    # the sleeve axis every mate uses.
    _feature_by_name(adapter, "Axis1")

    _feature_by_name(adapter, "Boss-Extrude1").Name = "GearBlank"
    _telemetry.success("feature 'Boss-Extrude1' -> 'GearBlank'")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]
    _feature_by_name(adapter, "Sketch1").Name = "GearBlankProfile"
    _telemetry.success("feature 'Sketch1' -> 'GearBlankProfile'")
    drive_jobs += [
        (
            name_dimensions(adapter, "GearBlankProfile", ["OutsideDia"])[0],
            '"OutsideDia"',
        )
    ]

    # The boss: a revolve of a half-profile on the Right plane (local x ->
    # model -Z, local y -> model Y), so its diameter prints beside its length
    # on the section (rule 7). The profile starts AT the tooth face, clear of
    # the relieved gap floors (crank pinion #906): the one step.
    # Construction witnesses carry the tip, root and bore diameters.
    profile = SketchDims()
    check("create_sketch sleeve", await adapter.create_sketch("Right"))
    suppress_dimension_input(adapter)
    set_sketch_direct_db(adapter, True)
    axis = check(
        "sleeve axis centerline",
        await adapter.add_centerline(-FACE_WIDTH, 0.0, -OVERALL_LENGTH, 0.0),
    )
    points = [
        (-FACE_WIDTH, 0.0),
        (-FACE_WIDTH, BOSS_DIA / 2.0),
        (-OVERALL_LENGTH, BOSS_DIA / 2.0),
        (-OVERALL_LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    outside_ref = check(
        "outside-diameter witness",
        await adapter.add_line(0.0, OUTSIDE_DIA / 2.0, -FACE_WIDTH, OUTSIDE_DIA / 2.0),
    )
    root_ref = check(
        "root-diameter witness",
        await adapter.add_line(0.0, ROOT_DIA_MIN / 2.0, -FACE_WIDTH, ROOT_DIA_MIN / 2.0),
    )
    bore_ref = check(
        "bore-diameter witness",
        await adapter.add_line(0.0, BORE_DIA / 2.0, -OVERALL_LENGTH, BORE_DIA / 2.0),
    )
    # R9-67: the cutter's full-depth station and run-out limit, from the rear
    # face along the tooth tips' lower line, so each baseline dimension below
    # the section rises from the part's edge.
    tip_v = -OUTSIDE_DIA / 2.0
    runout_ref = check(
        "run-out-limit witness",
        await adapter.add_line(0.0, tip_v, -CUTTER_RUNOUT_MAX, tip_v),
    )
    full_depth_ref = check(
        "full-depth witness", await adapter.add_line(0.0, tip_v, -FULL_DEPTH, tip_v)
    )
    set_sketch_direct_db(adapter, False)
    for line in (outside_ref, root_ref, bore_ref, runout_ref, full_depth_ref):
        _as_construction(adapter, line)
    for i, line in enumerate(lines):
        (_, y1), (_, y2) = points[i], points[(i + 1) % len(lines)]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"sleeve {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    for label, line, end_point in (
        ("outside-diameter witness", outside_ref, f"{lines[0]}.start"),
        ("root-diameter witness", root_ref, f"{lines[0]}.start"),
        ("bore-diameter witness", bore_ref, f"{lines[2]}.end"),
    ):
        check(
            f"{label} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
        check(
            f"{label} starts at the rear face",
            await adapter.add_sketch_constraint(
                f"{line}.start", "origin", "vertical_points"
            ),
        )
        check(
            f"{label} ends at its feature's end",
            await adapter.add_sketch_constraint(
                f"{line}.end", end_point, "vertical_points"
            ),
        )
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", -FACE_WIDTH, 0.0, "sleeve profile anchor"
    )
    profile.record("ProfileStart", '"FaceWidth"')
    await dimension_between(
        adapter,
        f"{lines[1]}.end",
        "origin",
        "horizontal_distance",
        OVERALL_LENGTH,
        "OverallLength",
    )
    profile.record("OverallLength", '"OverallLength"')
    for name, target, xy in (
        (
            "BossDia",
            lines[1],
            (-(FACE_WIDTH + OVERALL_LENGTH) / 2.0, BOSS_DIA / 2.0 + 5.0),
        ),
        (
            "OutsideDia",
            f"{outside_ref}.start",
            (-FACE_WIDTH / 2.0, OUTSIDE_DIA / 2.0 + 5.0),
        ),
        ("RootDia", f"{root_ref}.start", (-FACE_WIDTH / 2.0, -(ROOT_DIA_MIN / 2.0 + 5.0))),
        ("BoreDia", f"{bore_ref}.start", (-OVERALL_LENGTH / 2.0, BORE_DIA / 2.0 + 3.0)),
    ):
        await add_diametric_linear_dimension(adapter, axis, target, xy, name)
        profile.record(name, f'"{name}"')
    for label, line in (
        ("run-out-limit witness", runout_ref),
        ("full-depth witness", full_depth_ref),
    ):
        check(
            f"{label} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    check(
        "full-depth witness starts on the run-out witness",
        await adapter.add_sketch_constraint(
            f"{full_depth_ref}.start", f"{runout_ref}.start", "coincident"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{runout_ref}.start", 0.0, tip_v, "witnesses on the tip line"
    )
    profile.record("WitnessDrop", '"OutsideDia" / 2')
    await dimension_between(
        adapter,
        f"{full_depth_ref}.end",
        "origin",
        "horizontal_distance",
        FULL_DEPTH,
        "FullDepth",
    )
    profile.record("FullDepth", '"FullDepth"')
    await dimension_between(
        adapter,
        f"{runout_ref}.end",
        "origin",
        "horizontal_distance",
        CUTTER_RUNOUT_MAX,
        "CutterRunout",
    )
    profile.record("CutterRunout", '"CutterRunoutMax"')
    await ensure_fully_defined(adapter, "sleeve sketch")
    check("exit_sketch sleeve", await adapter.exit_sketch())
    name_last_feature(adapter, "SleeveProfile")
    drive_jobs += profile.apply(adapter, "SleeveProfile")
    volume = measure_one_solid_body_volume(adapter)
    check(
        "revolve sleeve", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Sleeve")
    volume = await check_one_solid_body_volume(adapter, "boss", volume + V_BOSS, 0.01 * V_BOSS)

    volume, end_features = await _stock_cutter_endcut(adapter, drive_jobs)
    await author_span(adapter, STOCK_PROFILE, SPAN_TEETH)

    # Bore through (centre 0,0): define_circle emits only the diameter dim.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    suppress_dimension_input(adapter)
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "bore",
        dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=OVERALL_LENGTH + 2.0)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await check_one_solid_body_volume(adapter, "bore", volume - V_BORE, 0.01 * V_BORE)

    # Oil hole (R9-8): Ø1.2 on +Y through the boss wall at OIL_HOLE_SLEEVE_Z, where
    # the hub's own hole lands; match-drilled through both at assembly. Top
    # plane sketch (u, v) = model (X, -Z); a reversed cut runs +Y, one wall.
    oil = SketchDims()
    check("create_sketch oil hole", await adapter.create_sketch("Top"))
    suppress_dimension_input(adapter)
    await define_circle(
        adapter,
        0.0,
        -OIL_HOLE_SLEEVE_Z,
        OIL_HOLE_DIA / 2.0,
        "oil hole",
        dims=oil,
        names=("OilHoleX", "OilHoleZ", "OilHoleDia"),
        drives=(None, '"OilHoleZ"', '"OilHoleDia"'),
    )
    await ensure_fully_defined(adapter, "oil hole sketch")
    check("exit_sketch oil hole", await adapter.exit_sketch())
    name_last_feature(adapter, "OilHoleProfile")
    drive_jobs += oil.apply(adapter, "OilHoleProfile")
    check(
        "cut oil hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BOSS_DIA, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "OilHole")
    drive_jobs.append(
        (name_dimensions(adapter, "OilHole", ["OilHoleDepth"])[0], '"BossDia"')
    )
    volume = await check_one_solid_body_volume(
        adapter, "oil hole", volume - V_OIL_HOLE, 0.05 * V_OIL_HOLE
    )

    # The D-flat on -Y, opposite the oil hole: the hub drives through it.
    volume = await _cut_flat(adapter, drive_jobs, volume)

    # Mate datums: the gear face and the flat's end wall (the hub's rear
    # stop, the disc's front face), each driven by the station it sits at;
    # the rear face is the Front Plane.
    for plane, offset, expr in (
        ("GearFace", FACE_WIDTH, '"FaceWidth"'),
        ("FlatEndFace", FLAT_END_STATION, '"FlatEnd"'),
    ):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Front Plane", offset=offset
                )
            ),
        )
        name_last_feature(adapter, plane)
        drive_jobs.append(
            (name_dimensions(adapter, plane, [f"{plane}Offset"])[0], expr)
        )
    blank_reference_geometry(adapter, (("GearFace", "PLANE"), ("FlatEndFace", "PLANE")))

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await force_rebuild(adapter)
    await check_one_solid_body_volume(
        adapter, "driven feed-pinion sleeve (equations neutral)", volume, 0.01 * V_BORE
    )

    # Bands (pd_transgear_feed_pinion_spec): the flat's end wall and the overall
    # length ±0.05 (R9-5), the reamed bore, the boss's h6 under the disc's
    # and hub's H7 bores, the flat's (0, -0.015) under the hub's flat, the
    # contact-critical tip class, the root as a physical MIN floor; the cutter's full-depth station
    # at its .XXX band and its run-out as a MAX limit (R9-67).  The tooth
    # length, which only places the step, holds the title block's .XXX.
    set_dimension_symmetric_tolerance(adapter, "FlatProfile", "FlatEnd", STATION_TOL)
    set_dimension_symmetric_tolerance(
        adapter, "SleeveProfile", "OverallLength", STATION_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "SleeveProfile", "FullDepth", FULL_DEPTH_BAND
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "BoreDia", *BORE_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "BossDia", *BOSS_DIA_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "FlatProfile", "FlatToAxis", *FLAT_TO_AXIS_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "OutsideDia", *OUTSIDE_DIA_DEVIATIONS
    )
    _single_limit(
        adapter,
        "RootDia",
        ROOT_DIA_MIN,
        ROOT_DIA_DEVIATIONS,
        ROOT_DIA_TOL_TYPE,
        f"{ROOT_DIA_MIN:.2f} MIN",
    )
    _single_limit(
        adapter,
        "CutterRunout",
        CUTTER_RUNOUT_MAX,
        CUTTER_RUNOUT_DEVIATIONS,
        CUTTER_RUNOUT_TOL_TYPE,
        f"{CUTTER_RUNOUT_MAX:.{CUTTER_RUNOUT_PLACES}f} MAX",
    )
    # Each cutter station names itself: neither ends at a drawn edge.
    set_dimension_prefix(adapter, "SleeveProfile", "FullDepth", FULL_DEPTH_PREFIX)
    set_dimension_prefix(adapter, "SleeveProfile", "CutterRunout", CUTTER_RUNOUT_PREFIX)
    apply_span_limits(
        adapter, nominal_mm=SPAN_NOMINAL, deviations=SPAN_DEVIATIONS,
        places=SPAN_PLACES, prefix=SPAN_PREFIX,
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    # Radial toothspace runout and calibrated all-space/wrap index are
    # distinct controls, saved together on the actual source toothpattern.
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": GEAR_DATA,
            "Manufacturing Notes": DRAWING_NOTES,
            TOOTH_SPACE_CALLOUT_PROPERTY: TOOTH_SPACE_CALLOUT,
            "Tooth Cut Features": "\n".join(disc.tooth_features),
        },
    )
    return await save_simplified_part(
        adapter, PART_NAME, disc.tooth_features + end_features
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
