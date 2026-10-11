r"""Reproduction script: translational-gearing feed-pinion sleeve (book ch. 23).

The "fifth gear" of the 4/4 video narration: "Behind and attached to the
fourth gear is the fifth gear. This gear has twelve teeth and engages the
rack." 12T at DP 30 (it MUST match the rack -- the scale anchor of ch. 23),
PD 10.160, cut on the rear end of one turned steel sleeve (MHA-PD-010) that
runs on the MHA-PD-023 pin's Ø3.9 shank. In front of the teeth the sleeve
steps once to the Ø9 h6 boss the brass hub slides on and drives through by
its D-flat; the hub's spigot seats on the step face and pilots the 120T
disc, and the nose runs on the front bushing (pd_transgear_feed_pinion_spec,
R9-68 rev 5).

Layout: origin on the axis at the sleeve's rear face, +Z toward the machine
front. Teeth z 0..FACE_WIDTH (root at the 1.25/P full-depth floor), boss to
OVERALL_LENGTH, Ø3.9 bore through, the D-flat on -Y from its end wall at
FLAT_END_STATION to the nose, Ø1.2 oil hole on +Y at the hub spec's
OIL_HOLE_SLEEVE_Z (centred on the faced hub body). The model cuts the teeth
full depth over their whole length; the sheet bounds the form cutter's
run-out (R9-67). Datums: ``Front Plane`` is the rear face (``RearFace``);
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
from _simplified_part import save_simplified_part
from _gear import build_fixed_gear, volume_check
from _holes import cross_hole_volume_mm3
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from pd_transgear_feed_pinion_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    BOSS_DIA,
    BOSS_DIA_DEVIATIONS,
    CUTTER_RUNOUT_DEVIATIONS,
    CUTTER_RUNOUT_MAX,
    CUTTER_RUNOUT_PLACES,
    CUTTER_RUNOUT_PREFIX,
    CUTTER_RUNOUT_TOL_TYPE,
    DEDENDUM_FACTOR,
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
    ROOT_DIA,
    ROOT_DIA_DEVIATIONS,
    ROOT_DIA_MIN,
    ROOT_DIA_TOL_TYPE,
    STATION_TOL,
    SURFACE_FINISHES,
    TEETH,
)
from pd_transgear_disc_hub_spec import OIL_HOLE_DIA, OIL_HOLE_SLEEVE_Z

PART_NAME = "pd-transgear-feed-pinion"
MATERIAL = "Plain Carbon Steel"  # contract §2.3: steel, made

# TEETH (12, the 4/4 video narration: "this gear has twelve teeth") comes from
# the spec; DP meshes the DP30 rack (the ch23 scale anchor).
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
    return await volume_check(adapter, "D-flat", volume - V_FLAT, 0.01 * V_FLAT)


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
    # A global-driven dimension reads back to the inch-rounded global (RootDia
    # 8.0433334 mm against the spec's 8.0433333), so a 1e-12 m match never
    # holds; 1e-9 m is the convention every other readback here uses.
    if not math.isclose(float(dimension.SystemValue), nominal / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {float(dimension.SystemValue) * 1000.0:.7f} is not "
            f"the modelled {nominal:.7f}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
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
    # gap and pattern are built by build_fixed_gear with literal numerics.
    for name, value in (
        ("FaceWidth", FACE_WIDTH),
        ("OutsideDia", OUTSIDE_DIA),
        ("RootDia", ROOT_DIA),
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

    # Teeth z 0..FACE_WIDTH off the Front plane (the rear face). Root relief
    # cuts the gap floor at the 1.25/P root the sheet floors (8.04 MIN): the
    # base-chord floor would leave the rack's tips no working depth.  The
    # model cuts full depth over the whole tooth length: behind FULL_DEPTH the
    # cutter's arc leaves the gaps up to 0.51 shallow at the step, clear of
    # the rack's worst reach (build_pd_paper_drive_assembly).
    disc = await build_fixed_gear(
        adapter,
        TEETH,
        FACE_WIDTH,
        dp=DP,
        pa_deg=PRESSURE_ANGLE_DEG,
        root_relief=True,
        dedendum=DEDENDUM_FACTOR,
    )
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
        await adapter.add_line(0.0, ROOT_DIA / 2.0, -FACE_WIDTH, ROOT_DIA / 2.0),
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
        ("RootDia", f"{root_ref}.start", (-FACE_WIDTH / 2.0, -(ROOT_DIA / 2.0 + 5.0))),
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
    check(
        "revolve sleeve", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Sleeve")
    volume = await volume_check(adapter, "boss", volume + V_BOSS, 0.01 * V_BOSS)

    # Bore through (centre 0,0): define_circle emits only the diameter dim.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
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
    volume = await volume_check(adapter, "bore", volume - V_BORE, 0.01 * V_BORE)

    # Oil hole (R9-8): Ø1.2 on +Y through the boss wall at OIL_HOLE_SLEEVE_Z, where
    # the hub's own hole lands; match-drilled through both at assembly. Top
    # plane sketch (u, v) = model (X, -Z); a reversed cut runs +Y, one wall.
    oil = SketchDims()
    check("create_sketch oil hole", await adapter.create_sketch("Top"))
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
    volume = await volume_check(
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
    await volume_check(
        adapter, "driven feed-pinion sleeve (equations neutral)", volume, 0.01 * V_BORE
    )

    # Bands (pd_transgear_feed_pinion_spec): the flat's end wall and the overall
    # length ±0.05 (R9-5), the reamed bore, the boss's h6 under the disc's
    # and hub's H7 bores, the flat's (0, -0.015) under the hub's flat, the
    # tip's +0/-0.10, the root as a MIN floor; the cutter's full-depth station
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
        ROOT_DIA,
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

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_simplified_part(adapter, PART_NAME, disc.tooth_features)


if __name__ == "__main__":
    sys.exit(run_build(build))
