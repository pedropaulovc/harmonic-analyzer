r"""Build the integral finite-stock 12T48DP knob shaft MHA-PD-008.

The pure source owns the actual #8/12T master, printed-span-inverted tool
setting, contact-critical blank, D-core, conventional front neck, #8-32
stud and 6g6 running journal. F and all retained cup/chain stations are
unchanged. Exact finite gaps run straight only to FULL_DEPTH. A genuine
stock-disc cutter revolution removes the partial-depth rear tooth gaps
and journal cavity; no generated-profile shift or flat end-mill slot is
used. The front terminal intersects no material in the paid source family.

Root REF and driven tangent-span carriers use the same physical finite
contact curves. The running-journal datum and source-approved core controls
are saved on the native part. Local D-flat normal is -Y; the assembly owns
clocking of the complete collar/wheel/dowel stack to the phased shaft.

Every physical volume gate reads the actual single native solid. Authored
contracts and static binding audits are not a substitute for the final
source-SHA supervised farm build and drawing receipt.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_knob_shaft.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import report_mass_properties
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
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
from _sketch_circle import define_circle
from _fit_deviations import deviations
from _gear import ToothedDisc
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from paper_drive_stock_native import (
    apply_span_limits,
    author_cutter_endcut,
    author_root_envelope,
    author_span,
    measure_one_solid_body_volume,
    pattern_stock_feature,
    placed_ground_curve,
    suppress_dimension_input,
)
from pd_transgear_knob_shaft_spec import (
    CORE_DIA,
    CORE_DIA_BAND,
    CORE_FLAT_BAND,
    CORE_FLAT_FROM_AXIS,
    CORE_FRONT_FROM_F,
    CORE_ACTIVE_LENGTH,
    CORE_FLAT_CUT_END_Z,
    CORE_FLAT_TOOL_END_RADIUS,
    CORE_FLAT_TOOL_END_RADIUS_BAND,
    CORE_FLAT_TOOL_END_RADIUS_TOL_TYPE,
    CORE_FLAT_CUT_END_BAND,
    CORE_FLAT_CUT_END_TOL_TYPE,
    CORE_FLAT_TOOL_REACH_NOTE,
    CUTTER_DIA,
    CUTTER_RUNOUT_DEVIATIONS,
    CUTTER_RUNOUT_MAX,
    CUTTER_RUNOUT_PLACES,
    CUTTER_RUNOUT_PREFIX,
    CUTTER_RUNOUT_TOL_TYPE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FULL_DEPTH,
    FULL_DEPTH_BAND,
    FRONT_RELIEF_DIA,
    FRONT_RELIEF_WIDTH,
    FRONT_CORNER_RADIUS,
    FRONT_CORNER_RADIUS_BAND,
    FRONT_CORNER_RADIUS_TOL_TYPE,
    FULL_DEPTH_PREFIX,
    GEAR_DATA,
    GEOMETRIC_CONTROLS,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_LENGTH,
    OUTSIDE_DIA_BAND,
    OUTSIDE_DIA,
    PINION_REAR_Z,
    PLAIN_CORE,
    PART_DATUMS,
    REAR_END_Z,
    ROOT_ACCEPTANCE,
    RELIEF_DIA,
    SPAN_DEVIATIONS,
    SPAN_NOMINAL,
    SPAN_PLACES,
    SPAN_PREFIX,
    SPAN_TEETH,
    STOCK_PROFILE,
    SURFACE_FINISHES,
    TEETH,
    THREAD_BLANK_DIA,
    THREAD_BLANK_DIA_BAND,
    THREAD_END_Z,
    TIP_CHAMFER,
    TIP_STATION,
    TIP_Z,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
    endcut_volume_bounds_mm3,
    expected_volume_bounds_mm3,
)

PART_NAME = "pd-transgear-knob-shaft"
MATERIAL = "Plain Carbon Steel"  # contract §1.1: steel, made

_R_CORE = CORE_DIA / 2.0
_R_RELIEF = RELIEF_DIA / 2.0
_R_BLANK = THREAD_BLANK_DIA / 2.0
_R_JOURNAL = JOURNAL_DIA / 2.0
_R_NECK = FRONT_RELIEF_DIA / 2.0

# Actual nominal quarter-tori, not an approximate shoulder-volume allowance.
V_FRONT_CORNERS = 2.0 * math.pi * (
    (2.0 - math.pi / 2.0) * _R_NECK * FRONT_CORNER_RADIUS**2
    + (5.0 / 3.0 - math.pi / 2.0) * FRONT_CORNER_RADIUS**3
)
V_STUD = (
    math.pi * _R_NECK**2 * FRONT_RELIEF_WIDTH
    + math.pi * _R_CORE**2 * CORE_ACTIVE_LENGTH
    + V_FRONT_CORNERS
    + math.pi * _R_RELIEF**2 * (PLAIN_CORE - CORE_FRONT_FROM_F)
    + math.pi * _R_BLANK**2 * (TIP_STATION - PLAIN_CORE)
    - math.pi * TIP_CHAMFER**2 * (_R_BLANK - TIP_CHAMFER / 3.0)
)
V_JOURNAL = math.pi * _R_JOURNAL**2 * JOURNAL_LENGTH




async def _create_sketch(adapter: Any, plane: str, label: str) -> None:
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    suppress_dimension_input(adapter)


async def _native_volume_check(
    adapter: Any, label: str, lower: float, upper: float, allowance: float
) -> float:
    """A paid interval on one true native solid, never an adapter fallback."""
    if not (
        all(math.isfinite(value) for value in (lower, upper, allowance))
        and 0.0 < lower <= upper
        and allowance >= 0.0
    ):
        raise ValueError(f"{label}: invalid native volume bounds")
    expected = (lower + upper) / 2.0
    actual = measure_one_solid_body_volume(adapter)
    tolerance = (upper - lower) / 2.0 + allowance
    if abs(actual - expected) > tolerance:
        raise RuntimeError(
            f"{label}: native solid {actual:.9f} mm^3 outside "
            f"{lower:.9f}..{upper:.9f} with paid allowance {allowance:.9f}"
        )
    return actual


async def _straight_stock_gaps(
    adapter: Any, drive_jobs: list[tuple[str, str]]
) -> ToothedDisc:
    """The actual blank and exact straight finite pass only from F to full depth."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    radius = STOCK_PROFILE.blank_radius_mm
    blank_volume = math.pi * radius**2 * FACE_WIDTH
    await _create_sketch(adapter, "Front", "gear blank")
    await define_circle(adapter, 0.0, 0.0, radius, "knob stock blank")
    await ensure_fully_defined(adapter, "knob stock blank")
    check("exit_sketch gear blank", await adapter.exit_sketch())
    name_last_feature(adapter, "GearBlankProfile")
    drive_jobs.append(
        (name_dimensions(adapter, "GearBlankProfile", ["BlankDia"])[0], '"OutsideDia"')
    )
    check(
        "extrude native stock blank",
        await adapter.create_extrusion(
            ExtrusionParameters(
                depth=FACE_WIDTH,
                end_condition="Blind",
                reverse_direction=False,
                both_directions=False,
            )
        ),
    )
    name_last_feature(adapter, "GearBlank")
    drive_jobs.append(
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    )
    await _native_volume_check(
        adapter, "stock blank", blank_volume, blank_volume, 0.005 * blank_volume
    )

    await _create_sketch(adapter, "Front", "finite straight stock gap")
    # Main's cut_tooth_gap order (flanks first), FIXed as created.
    segments = STOCK_PROFILE.cut_order_native_segments(clearance_radius_mm=radius + 1.0)
    curves = [await placed_ground_curve(adapter, segment, math.pi / TEETH) for segment in segments]
    await ensure_fully_defined(
        adapter,
        "finite straight stock gap",
        fix_entities=curves,
        allow_fix_escalation=True,
    )
    check("exit_sketch straight stock gap", await adapter.exit_sketch())
    name_last_feature(adapter, "StraightToothProfile")
    check(
        "cut actual finite stock gap",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FULL_DEPTH)),
    )
    name_last_feature(adapter, "StraightToothGap")
    drive_jobs.append(
        (name_dimensions(adapter, "StraightToothGap", ["StraightCutDepth"])[0], '"FullDepth"')
    )
    one_gap = STOCK_PROFILE.gap_area_mm2 * FULL_DEPTH
    area_error = STOCK_PROFILE.gap_area_error_bound_mm2 * FULL_DEPTH
    await _native_volume_check(
        adapter, "finite stock gap seed",
        blank_volume - one_gap - area_error,
        blank_volume - one_gap + area_error,
        1.0,
    )
    pattern = await pattern_stock_feature(adapter, "StraightToothGap", TEETH, "StraightToothPattern")
    expected = blank_volume - TEETH * one_gap
    volume = await _native_volume_check(
        adapter, "finite twelve-gap straight pattern",
        expected - TEETH * area_error, expected + TEETH * area_error, 0.01 * expected,
    )
    return ToothedDisc(volume, ("StraightToothGap", pattern))


async def _stock_cutter_endcut(
    adapter: Any, volume: float, drive_jobs: list[tuple[str, str]]
) -> tuple[float, tuple[str, str]]:
    """The real rear disk cavity, including the actual journal stock domain."""
    lower, upper = endcut_volume_bounds_mm3()
    if not 0.0 < lower <= upper:
        raise ValueError("rear finite cutter has no resolved positive removal")
    features = await author_cutter_endcut(adapter, STOCK_PROFILE, CUTTER_DIA, FULL_DEPTH)
    drive_jobs.append(
        (name_dimensions(adapter, features.plane, ["ToolEndStation"])[0], '"FullDepth"')
    )
    removed = (lower + upper) / 2.0
    await _native_volume_check(
        adapter, "rear finite stock-disk terminal seed",
        volume - upper, volume - lower, 0.01 * removed,
    )
    pattern = await pattern_stock_feature(adapter, features.cut, TEETH, "ToolEndPattern")
    actual = await _native_volume_check(
        adapter, "twelve rear finite stock-disk terminals",
        volume - TEETH * upper, volume - TEETH * lower, 0.01 * TEETH * removed,
    )
    return actual, (features.cut, pattern)


def _native_arc(adapter: Any, label: str, *points: float) -> str:
    """Exact CCW circular geometry; dispatch absence is not truthiness."""
    raw_manager = adapter.currentSketchManager
    if raw_manager is None:
        raise RuntimeError(f"{label}: no native sketch manager")
    manager = _early_bound(raw_manager, "ISketchManager")
    cx, cy, sx, sy, ex, ey = (value / 1000.0 for value in points)
    arc = manager.CreateArc(cx, cy, 0.0, sx, sy, 0.0, ex, ey, 0.0, 1)
    if arc is None:
        raise RuntimeError(f"{label}: CreateArc returned no native circular segment")
    return adapter._register_sketch_entity("Arc", arc)




def _as_construction(adapter: Any, line: str) -> None:
    raw = adapter._sketch_entities[line]
    if raw is None:
        raise RuntimeError(f"{line}: no native construction segment")
    segment = _early_bound(raw, "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError(f"{line}: failed to become construction geometry")


async def _stud_profile(adapter: Any) -> list[tuple[str, str]]:
    """The revolve in front of F.  Right sketch (u, v) maps to model (-Z, Y),
    so the stud (model z < 0) lies at positive u."""
    profile = SketchDims()
    await _create_sketch(adapter, "Right", "stud")
    set_sketch_direct_db(adapter, True)
    axis = check(
        "stud axis centerline", await adapter.add_centerline(0.0, 0.0, TIP_STATION, 0.0)
    )
    # Two real tangent quarter-circle neck corners are part of the turned
    # profile. Their exact revolution is the pure source's quarter-tori.
    radius = FRONT_CORNER_RADIUS
    (front_face,) = await add_line_chain(
        adapter, [(0.0, 0.0), (0.0, _R_NECK + radius)], close=False
    )
    front_corner = _native_arc(
        adapter, "front neck corner",
        radius, _R_NECK + radius, 0.0, _R_NECK + radius, radius, _R_NECK,
    )
    (neck_floor,) = await add_line_chain(
        adapter,
        [(radius, _R_NECK), (FRONT_RELIEF_WIDTH - radius, _R_NECK)],
        close=False,
    )
    core_corner = _native_arc(
        adapter, "core neck corner",
        FRONT_RELIEF_WIDTH - radius, _R_NECK + radius,
        FRONT_RELIEF_WIDTH - radius, _R_NECK,
        FRONT_RELIEF_WIDTH, _R_NECK + radius,
    )
    (
        neck_step, core, core_step, relief, thread_end,
        blank, chamfer, tip_face, axis_edge,
    ) = await add_line_chain(
        adapter,
        [
            (FRONT_RELIEF_WIDTH, _R_NECK + radius),
            (FRONT_RELIEF_WIDTH, _R_CORE),
            (CORE_FRONT_FROM_F, _R_CORE),
            (CORE_FRONT_FROM_F, _R_RELIEF),
            (PLAIN_CORE, _R_RELIEF),
            (PLAIN_CORE, _R_BLANK),
            (TIP_STATION - TIP_CHAMFER, _R_BLANK),
            (TIP_STATION, _R_BLANK - TIP_CHAMFER),
            (TIP_STATION, 0.0),
            (0.0, 0.0),
        ],
        close=False,
    )
    outside = check(
        "tooth-tip blank witness",
        await adapter.add_line(0.0, OUTSIDE_DIA / 2.0, -FACE_WIDTH, OUTSIDE_DIA / 2.0),
    )
    # R9-21: the cutter's full-depth station and run-out limit, from F along
    # the tooth tips' lower line, so each baseline dimension below the side
    # view rises from the part's edge.
    tip_v = -OUTSIDE_DIA / 2.0
    runout_ref = check(
        "run-out-limit witness",
        await adapter.add_line(0.0, tip_v, -CUTTER_RUNOUT_MAX, tip_v),
    )
    full_depth_ref = check(
        "full-depth witness", await adapter.add_line(0.0, tip_v, -FULL_DEPTH, tip_v)
    )
    set_sketch_direct_db(adapter, False)
    for line in (outside, runout_ref, full_depth_ref):
        _as_construction(adapter, line)
    for line, relation in (
        (front_face, "vertical"),
        (neck_floor, "horizontal"),
        (neck_step, "vertical"),
        (core, "horizontal"),
        (core_step, "vertical"),
        (relief, "horizontal"),
        (thread_end, "vertical"),
        (blank, "horizontal"),
        (tip_face, "vertical"),
        (axis_edge, "horizontal"),
        (outside, "horizontal"),
        (runout_ref, "horizontal"),
        (full_depth_ref, "horizontal"),
    ):
        check(
            f"stud profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    for first, second in (
        (front_face, front_corner), (front_corner, neck_floor),
        (neck_floor, core_corner), (core_corner, neck_step),
    ):
        check(
            "tangent physical neck corner",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    check(
        "equal physical neck radii",
        await adapter.add_sketch_constraint(front_corner, core_corner, "equal"),
    )
    check(
        "dimension physical front corner",
        await adapter.add_sketch_dimension(front_corner, None, "radial", FRONT_CORNER_RADIUS),
    )
    profile.record("FrontCornerRadius", '"FrontCornerRadius"')
    check(
        "tip witness starts at F",
        await adapter.add_sketch_constraint(
            f"{outside}.start", "origin", "vertical_points"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{front_face}.start", 0.0, 0.0, "stud profile at F"
    )
    await dimension_between(
        adapter,
        f"{tip_face}.end",
        "origin",
        "horizontal_distance",
        TIP_STATION,
        "stud TipStation",
    )
    profile.record("TipStation", '"TipStation"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "horizontal_distance",
        TIP_CHAMFER,
        "stud TipChamfer",
    )
    profile.record("TipChamfer", '"TipChamfer"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "vertical_distance",
        TIP_CHAMFER,
        "stud tip chamfer rise",
    )
    profile.record("TipChamferRise", '"TipChamfer"')
    for name, line, value in (
        ("CoreFront", core_step, CORE_FRONT_FROM_F),
        ("FrontReliefWidth", neck_step, FRONT_RELIEF_WIDTH),
        ("PlainCore", thread_end, PLAIN_CORE),
    ):
        await dimension_between(
            adapter,
            f"{line}.start",
            "origin",
            "horizontal_distance",
            value,
            f"stud {name}",
        )
        profile.record(name, f'"{name}"')
    await dimension_between(
        adapter,
        f"{outside}.start",
        f"{outside}.end",
        "horizontal_distance",
        FACE_WIDTH,
        "tooth-tip witness span",
    )
    profile.record("BlankSpan", '"FaceWidth"')
    for name, target, xy in (
        ("CoreDia", core, ((FRONT_RELIEF_WIDTH + CORE_FRONT_FROM_F) / 2.0, _R_CORE + 5.0)),
        ("FrontReliefDia", neck_floor, (FRONT_RELIEF_WIDTH / 2.0, _R_NECK + 5.0)),
        ("ReliefDia", relief, ((CORE_FRONT_FROM_F + PLAIN_CORE) / 2.0, _R_RELIEF + 5.0)),
        (
            "ThreadBlankDia",
            blank,
            ((PLAIN_CORE + TIP_STATION) / 2.0, _R_BLANK + 5.0),
        ),
        (
            "OutsideDia",
            f"{outside}.start",
            (-FACE_WIDTH / 2.0, OUTSIDE_DIA / 2.0 + 5.0),
        ),
    ):
        await add_diametric_linear_dimension(adapter, axis, target, xy, name)
        profile.record(name, f'"{name}"')
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
    for name, line, value, drive in (
        ("FullDepth", full_depth_ref, FULL_DEPTH, '"FullDepth"'),
        ("CutterRunout", runout_ref, CUTTER_RUNOUT_MAX, '"CutterRunoutMax"'),
    ):
        await dimension_between(
            adapter, f"{line}.end", "origin", "horizontal_distance", value, name
        )
        profile.record(name, drive)
    await ensure_fully_defined(adapter, "stud sketch")
    check("exit_sketch stud", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    jobs = profile.apply(adapter, "StudProfile")
    await _revolve_profile(adapter, "stud", "Stud")
    return jobs


async def _revolve_profile(adapter: Any, label: str, feature: str) -> None:
    """Main's adapter revolve about the just-closed sketch's one centerline."""
    from solidworks_mcp.adapters.base import RevolveParameters

    check(
        f"revolve {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, feature)


def _runout_max_limit(adapter: Any) -> None:
    """CutterRunout as the single limit "10.60 MAX" (swTolMAX): SolidWorks
    prints the nominal then the limit word, so the nominal is the limit; the
    deviations stay on the native tolerance as the model's record of the
    band."""
    lower, upper = CUTTER_RUNOUT_DEVIATIONS
    _, dimension = _named_dimension(adapter, "StudProfile", "CutterRunout")
    label = "CutterRunout@StudProfile"
    if not math.isclose(
        float(dimension.SystemValue), CUTTER_RUNOUT_MAX / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(f"{label}: nominal is not the run-out limit")
    raw_tolerance = dimension.Tolerance
    if raw_tolerance is None:
        raise RuntimeError(f"{label}: native dimension has no tolerance")
    tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
    tolerance.Type = CUTTER_RUNOUT_TOL_TYPE
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != CUTTER_RUNOUT_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(
        f"{label}: single limit {CUTTER_RUNOUT_MAX:.{CUTTER_RUNOUT_PLACES}f} MAX"
    )


async def _cut_core_flat(
    adapter: Any, drive_jobs: list[tuple[str, str]], volume: float
) -> float:
    """Mill the local -Y D face; the signed physical tool end stays before F."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    end = -CORE_FLAT_CUT_END_Z
    radius = CORE_FLAT_TOOL_END_RADIUS
    floor = -CORE_FLAT_FROM_AXIS
    bottom = -CORE_DIA  # closure is wholly outside the turned body
    dims = SketchDims()
    await _create_sketch(adapter, "Right", "D core flat")
    set_sketch_direct_db(adapter, True)
    bottom_edge, core_end, flat = await add_line_chain(
        adapter,
        [(end, bottom), (CORE_FRONT_FROM_F, bottom),
         (CORE_FRONT_FROM_F, floor), (end + radius, floor)],
        close=False,
    )
    corner = _native_arc(
        adapter, "signed physical flat-tool end",
        end + radius, floor - radius, end + radius, floor, end, floor - radius,
    )
    (tool_end,) = await add_line_chain(
        adapter, [(end, floor - radius), (end, bottom)], close=False
    )
    set_sketch_direct_db(adapter, False)
    for segment, relation in (
        (bottom_edge, "horizontal"), (core_end, "vertical"),
        (flat, "horizontal"), (tool_end, "vertical"),
    ):
        check(
            f"flat profile {relation}",
            await adapter.add_sketch_constraint(segment, None, relation),
        )
    for segment in (flat, tool_end):
        check(
            "tangent physical flat-tool corner",
            await adapter.add_sketch_constraint(segment, corner, "tangent"),
        )
    await dimension_between(
        adapter, f"{flat}.start", "origin", "vertical_distance",
        CORE_FLAT_FROM_AXIS, "actual D flat plane",
    )
    dims.record("FlatToAxis", '"CoreFlat"')
    await dimension_between(
        adapter, f"{core_end}.start", "origin", "horizontal_distance",
        CORE_FRONT_FROM_F, "flat front shoulder station",
    )
    dims.record("FlatCoreFront", '"CoreFront"')
    await dimension_between(
        adapter, f"{tool_end}.end", "origin", "horizontal_distance",
        end, "signed physical tool end station",
    )
    dims.record("FlatEnd", '"FlatEnd"')
    await dimension_between(
        adapter, f"{bottom_edge}.start", "origin", "vertical_distance",
        -bottom, "flat closure outside body",
    )
    dims.record("FlatClosure", '"CoreDia"')
    check(
        "actual physical flat-tool corner radius",
        await adapter.add_sketch_dimension(corner, None, "radial", radius),
    )
    dims.record("FlatToolRadius")
    await ensure_fully_defined(adapter, "physical D-flat tool profile")
    check("exit_sketch D core flat", await adapter.exit_sketch())
    name_last_feature(adapter, "CoreFlatProfile")
    drive_jobs.extend(dims.apply(adapter, "CoreFlatProfile"))
    check(
        "cut actual solid D core",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CORE_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CoreFlat")
    r = CORE_DIA / 2.0
    h = CORE_FLAT_FROM_AXIS
    removed = (r**2 * math.acos(h / r) - h * math.sqrt(r**2 - h**2)) * CORE_ACTIVE_LENGTH
    return await _native_volume_check(
        adapter, "actual D circular-segment removal", volume - removed, volume - removed,
        0.005 * removed,
    )


def _apply_native_limits(
    adapter: Any, feature: str, name: str, nominal: float,
    band: tuple[float, float], tolerance_type: int,
) -> None:
    """Print an actual driving feature dimension as lower/upper LIMITS."""
    lower, upper = deviations(band)
    set_dimension_bilateral_tolerance(adapter, feature, name, lower, upper)
    _, dimension = _named_dimension(adapter, feature, name)
    if not math.isclose(float(dimension.SystemValue) * 1000.0, nominal, abs_tol=1e-6):
        raise RuntimeError(f"{name}: actual controlled feature nominal changed")
    raw_tolerance = dimension.Tolerance
    if raw_tolerance is None:
        raise RuntimeError(f"{name}: no native tolerance")
    tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
    tolerance.Type = tolerance_type
    if int(tolerance.Type) != tolerance_type or not (
        math.isclose(float(tolerance.GetMinValue()) * 1000.0, lower, abs_tol=1e-9)
        and math.isclose(float(tolerance.GetMaxValue()) * 1000.0, upper, abs_tol=1e-9)
    ):
        raise RuntimeError(f"{name}: native LIMITS readback changed")


def _apply_neck_and_flat_limits(adapter: Any) -> None:
    _apply_native_limits(
        adapter, "StudProfile", "FrontCornerRadius", FRONT_CORNER_RADIUS,
        FRONT_CORNER_RADIUS_BAND, FRONT_CORNER_RADIUS_TOL_TYPE,
    )
    _apply_native_limits(
        adapter, "CoreFlatProfile", "FlatEnd", -CORE_FLAT_CUT_END_Z,
        CORE_FLAT_CUT_END_BAND, CORE_FLAT_CUT_END_TOL_TYPE,
    )
    _apply_native_limits(
        adapter, "CoreFlatProfile", "FlatToolRadius", CORE_FLAT_TOOL_END_RADIUS,
        CORE_FLAT_TOOL_END_RADIUS_BAND, CORE_FLAT_TOOL_END_RADIUS_TOL_TYPE,
    )
    set_dimension_prefix(adapter, "CoreFlatProfile", "FlatEnd", "TOOL END FROM F ")


async def _journal_profile(adapter: Any) -> list[tuple[str, str]]:
    """The source-owned 6g6 journal behind the actual rear tooth ends."""
    profile = SketchDims()
    await _create_sketch(adapter, "Right", "journal")
    set_sketch_direct_db(adapter, True)
    axis = check(
        "journal axis centerline",
        await adapter.add_centerline(-PINION_REAR_Z, 0.0, -REAR_END_Z, 0.0),
    )
    points = [
        (-PINION_REAR_Z, 0.0),
        (-PINION_REAR_Z, _R_JOURNAL),
        (-REAR_END_Z, _R_JOURNAL),
        (-REAR_END_Z, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for i, line in enumerate(lines):
        (_, y1), (_, y2) = points[i], points[(i + 1) % len(lines)]
        relation = "horizontal" if y1 == y2 else "vertical"
        check(
            f"journal {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", -PINION_REAR_Z, 0.0, "journal at the rear teeth"
    )
    profile.record("ProfileStart", '"FaceWidth"')
    await dimension_between(
        adapter,
        f"{lines[1]}.start",
        f"{lines[1]}.end",
        "horizontal_distance",
        JOURNAL_LENGTH,
        "journal JournalLength",
    )
    profile.record("JournalLength", '"JournalLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        lines[1],
        (-(PINION_REAR_Z + REAR_END_Z) / 2.0, _R_JOURNAL + 5.0),
        "JournalDia",
    )
    profile.record("JournalDia", '"JournalDia"')
    await ensure_fully_defined(adapter, "journal sketch")
    check("exit_sketch journal", await adapter.exit_sketch())
    name_last_feature(adapter, "JournalProfile")
    jobs = profile.apply(adapter, "JournalProfile")
    await _revolve_profile(adapter, "journal", "Journal")
    return jobs




async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check("create_part", await adapter.create_part())
    # Linear globals retain an explicit mm suffix in the inch source model.
    # The finite tooth master is literal source geometry, not an editable x.
    for name, value in (
        ("FaceWidth", FACE_WIDTH),
        ("OutsideDia", OUTSIDE_DIA),
        ("CoreDia", CORE_DIA),
        ("CoreFront", CORE_FRONT_FROM_F),
        ("FrontReliefDia", FRONT_RELIEF_DIA),
        ("FrontReliefWidth", FRONT_RELIEF_WIDTH),
        ("FrontCornerRadius", FRONT_CORNER_RADIUS),
        ("CoreFlat", CORE_FLAT_FROM_AXIS),
        ("FlatEnd", -CORE_FLAT_CUT_END_Z),
        ("ReliefDia", RELIEF_DIA),
        ("PlainCore", PLAIN_CORE),
        ("ThreadBlankDia", THREAD_BLANK_DIA),
        ("TipStation", TIP_STATION),
        ("TipChamfer", TIP_CHAMFER),
        ("JournalDia", JOURNAL_DIA),
        ("JournalLength", JOURNAL_LENGTH),
        ("FullDepth", FULL_DEPTH),
        ("CutterRunoutMax", CUTTER_RUNOUT_MAX),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []
    disc = await _straight_stock_gaps(adapter, drive_jobs)
    volume = disc.volume
    _feature_by_name(adapter, "Axis1")  # retained assembly mate axis

    drive_jobs += await _stud_profile(adapter)
    volume = await _native_volume_check(
        adapter, "actual neck core relief and stud", volume + V_STUD, volume + V_STUD,
        0.005 * V_STUD,
    )
    volume = await _cut_core_flat(adapter, drive_jobs, volume)

    drive_jobs += await _journal_profile(adapter)
    volume = await _native_volume_check(
        adapter, "actual running journal", volume + V_JOURNAL, volume + V_JOURNAL,
        0.005 * V_JOURNAL,
    )

    # The F terminal is genuinely empty by the pure front-envelope proof.
    # The rear terminal must cut both partial-depth teeth and real journal.
    volume, end_features = await _stock_cutter_endcut(adapter, volume, drive_jobs)
    await author_root_envelope(adapter, STOCK_PROFILE)
    await author_span(adapter, STOCK_PROFILE, SPAN_TEETH, places=SPAN_PLACES)

    stations = (
        ("PinionRear", PINION_REAR_Z, '"FaceWidth"'),
        ("RearFace", REAR_END_Z, '"FaceWidth" + "JournalLength"'),
        ("ThreadEnd", THREAD_END_Z, '"PlainCore"'),
        ("StudTip", TIP_Z, '"TipStation"'),
    )
    for plane, offset, expr in stations:
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
            ),
        )
        name_last_feature(adapter, plane)
        drive_jobs.append((name_dimensions(adapter, plane, [f"{plane}Offset"])[0], expr))
    blank_reference_geometry(adapter, tuple((plane, "PLANE") for plane, _, _ in stations))

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await _native_volume_check(
        adapter, "neutral source equations", volume, volume, 0.005 * V_JOURNAL
    )
    lower_volume, upper_volume = expected_volume_bounds_mm3()
    await _native_volume_check(
        adapter, "complete finite-stock shaft source oracle",
        lower_volume, upper_volume, 0.005 * V_JOURNAL,
    )

    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "CoreDia", *deviations(CORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "ThreadBlankDia", *deviations(THREAD_BLANK_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "JournalProfile", "JournalDia", *deviations(JOURNAL_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "OutsideDia", *deviations(OUTSIDE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "CoreFlatProfile", "FlatToAxis", *deviations(CORE_FLAT_BAND)
    )
    set_dimension_symmetric_tolerance(adapter, "StudProfile", "FullDepth", FULL_DEPTH_BAND)
    _runout_max_limit(adapter)
    _apply_neck_and_flat_limits(adapter)
    set_dimension_prefix(adapter, "StudProfile", "FullDepth", FULL_DEPTH_PREFIX)
    set_dimension_prefix(adapter, "StudProfile", "CutterRunout", CUTTER_RUNOUT_PREFIX)
    set_dimension_prefix(adapter, "RootInspectionProfile", "RootEnvelope", "REFERENCE ROOT ")
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
    author_part_pmi(
        adapter, datums=PART_DATUMS, controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": GEAR_DATA,
            "Manufacturing Notes": "\n".join((DRAWING_NOTES, CORE_FLAT_TOOL_REACH_NOTE)),
            "Root Acceptance": ROOT_ACCEPTANCE,
            TOOTH_SPACE_CALLOUT_PROPERTY: TOOTH_SPACE_CALLOUT,
        },
    )
    return await save_simplified_part(adapter, PART_NAME, disc.tooth_features + end_features)


if __name__ == "__main__":
    sys.exit(run_build(build))
