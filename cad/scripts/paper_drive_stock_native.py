"""Narrow native carriers for the paper drive's finite stock gear forms.

The pure profile owns form equations. These functions only place its public
curves, author genuine flank/root inspection carriers and a physical cutter
end envelope. Callers own manufacturing bands, datum/runout grades, stock
bodies, cutting-path coverage, volume oracles and indexing patterns.
"""

from __future__ import annotations

import math
from typing import Any, NamedTuple

import _telemetry
from _common import (
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    check,
    dimension_between,
    ensure_fully_defined,
    equation_curve,
    name_last_feature,
    set_sketch_direct_db,
)
from _drawing_marks import _named_dimension, set_dimension_prefix
from _visibility import blank_reference_geometry
from paper_drive_stock_inspection import span_contact_points_mm
from stock_form_cutter import StockFormProfile


class CutterEndFeatures(NamedTuple):
    plane: str
    profile: str
    cut: str


def measure_one_solid_body_volume(adapter: Any) -> float:
    """Read one genuine solid body's geometric volume, without adapter fallback."""
    model = adapter.currentModel
    if model is None:
        raise RuntimeError("volume: no native part document")
    part = _early_bound(model, "IPartDoc")
    raw_bodies = part.GetBodies2(0, False)
    if raw_bodies is None:
        raise RuntimeError("volume: expected one native solid, got no body array")
    bodies = tuple(raw_bodies)
    if len(bodies) != 1 or bodies[0] is None:
        raise RuntimeError(f"volume: expected one native solid, got {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    if int(body.GetType()) != 0:
        raise RuntimeError("volume: native body is not solid")
    properties = body.GetMassProperties(1.0)
    if properties is None:
        raise RuntimeError("volume: native solid returned no mass-properties array")
    values = tuple(properties)
    if len(values) != 12 or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in values
    ):
        raise RuntimeError("volume: incomplete or nonfinite native solid mass properties")
    volume = float(values[3]) * 1e9
    if volume <= 0.0:
        raise RuntimeError("volume: native solid volume is not positive")
    return volume


async def check_one_solid_body_volume(
    adapter: Any, label: str, expected_mm3: float, tolerance_mm3: float
) -> float:
    """Gate the strict native measurement against a caller-owned error budget."""
    if (
        not math.isfinite(expected_mm3) or expected_mm3 <= 0.0
        or not math.isfinite(tolerance_mm3) or tolerance_mm3 < 0.0
    ):
        raise ValueError("invalid physical solid volume or error budget")
    volume = measure_one_solid_body_volume(adapter)
    if abs(volume - expected_mm3) > tolerance_mm3:
        raise RuntimeError(
            f"{label}: native solid volume {volume:.6f} mm^3, expected "
            f"{expected_mm3:.6f} +/- {tolerance_mm3:.6f}"
        )
    _telemetry.success(f"{label}: native solid volume {volume:.6f} mm^3")
    return volume


def rotate_mm(
    point: tuple[float, float], angle: float, translation_mm: float = 0.0
) -> tuple[float, float]:
    x, y = point
    x += translation_mm
    c, s = math.cos(angle), math.sin(angle)
    return c * x - s * y, s * x + c * y


async def placed_ground_curve(
    adapter: Any, segment: Any, angle: float, translation_mm: float = 0.0
) -> str:
    """Rigid placement, not a second form-equation or upper-tip generator."""
    c, s = f"{math.cos(angle):.17g}", f"{math.sin(angle):.17g}"
    x = f"(({segment.x})+({translation_mm / 25.4:.17g}))"
    y = f"({segment.y})"
    return await equation_curve(
        adapter, segment.name, f"({x})*({c})-({y})*({s})", f"({x})*({s})+({y})*({c})"
    )


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError(f"{entity}: construction geometry did not persist")


def suppress_dimension_input(adapter: Any) -> None:
    # Entering a new sketch can reset connect-time suppression. Setters are
    # VT_VOID; only the authoritative boolean getter is a success channel.
    app = _early_bound(adapter.swApp, "ISldWorks")
    for preference in (10, 372, 520):
        app.SetUserPreferenceToggle(preference, False)
        if app.GetUserPreferenceToggle(preference) is not False:
            raise RuntimeError(f"dimension input preference {preference} stayed enabled")


def _select_segment(adapter: Any, entity: str, mark: int) -> None:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    raw_manager = model.SelectionManager
    if raw_manager is None:
        raise RuntimeError("physical carrier has no native selection manager")
    manager = _early_bound(raw_manager, "ISelectionMgr")
    raw_data = manager.CreateSelectData()
    if raw_data is None:
        raise RuntimeError("physical carrier has no native selection data")
    data = _early_bound(raw_data, "ISelectData")
    data.Mark = mark
    if int(data.Mark) != mark:
        raise RuntimeError("physical carrier selection mark did not persist")
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    if segment.Select4(True, data) is not True:
        raise RuntimeError(f"physical carrier segment {entity} was not selected")


def _driven_carrier(
    display: Any, name: str, expected_mm: float, geometry_error_bound_mm: float, *, reference: bool
) -> float:
    if display is None:
        raise RuntimeError(f"{name}: no native display dimension was created")
    display = _early_bound(display, "IDisplayDimension")
    native_dimension = display.GetDimension2(0)
    if native_dimension is None:
        raise RuntimeError(f"{name}: display has no native model dimension")
    dimension = _early_bound(native_dimension, "IDimension")
    dimension.DrivenState = 1
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{name}: actual-contact measurement did not remain driven")
    dimension.Name = name
    actual_name = dimension.Name
    if type(actual_name) is not str or actual_name != name:
        raise RuntimeError(f"{name}: native dimension name did not persist")
    # The core native descriptors are exact equations, not a sampled chord
    # approximation. Preserve the repository's native 1e-9 m readback budget;
    # an unobserved seat discrepancy is not permission to widen a grade.
    actual_m = float(dimension.SystemValue)
    if not math.isclose(
        actual_m, expected_mm / 1000.0, rel_tol=0.0,
        abs_tol=1e-9 + geometry_error_bound_mm / 1000.0,
    ):
        raise RuntimeError(f"{name}: native geometry disagrees with the exact finite carrier")
    display.ShowParenthesis = reference
    if display.ShowParenthesis is not reference:
        raise RuntimeError(f"{name}: reference/control ink state did not persist")
    return actual_m * 1000.0


async def author_span(
    adapter: Any,
    profile: StockFormProfile,
    teeth_spanned: int,
    *,
    feature: str = "SpanProfile",
    name: str = "ToothSpan",
) -> float:
    """A real symmetric tangent span, with the anvil rocking DOF removed."""
    expected = profile.tangent_span_mm(teeth_spanned)
    check("create_sketch physical span", await adapter.create_sketch("Front"))
    suppress_dimension_input(adapter)
    segments = profile.gap_segments(unit_scale=1.0 / 25.4)
    upper = next((s for s in segments if s.kind == "flank" and s.name.startswith("Upper")), None)
    lower = next((s for s in segments if s.kind == "flank" and s.name.startswith("Lower")), None)
    if upper is None or lower is None:
        raise ValueError("physical span lacks both supported finite flank descriptors")
    seed = math.pi / profile.teeth
    half = math.pi * teeth_spanned / profile.teeth
    first = await placed_ground_curve(adapter, upper, seed)
    second = await placed_ground_curve(adapter, lower, seed + 2.0 * half)
    for curve in (first, second):
        _construction(adapter, curve)
    await ensure_fully_defined(
        adapter, "span exact finite flank copies", fix_entities=[first, second], allow_fix_escalation=True
    )
    direction = (math.cos(seed + half), math.sin(seed + half))
    (bisector,) = await add_line_chain(
        adapter,
        [(0.0, 0.0), (direction[0] * 2 * profile.blank_radius_mm, direction[1] * 2 * profile.blank_radius_mm)],
        close=False,
    )
    _construction(adapter, bisector)
    await anchor_point_to_origin(adapter, f"{bisector}.start", 0.0, 0.0, "span bisector origin")
    await anchor_point_to_origin(
        adapter, f"{bisector}.end", direction[0] * 2 * profile.blank_radius_mm,
        direction[1] * 2 * profile.blank_radius_mm, "physical pair bisector"
    )
    a, b = span_contact_points_mm(profile, teeth_spanned)
    tangent_length = profile.template.module_mm
    (tangent,) = await add_line_chain(
        adapter, [a, (a[0] + tangent_length * direction[0], a[1] + tangent_length * direction[1])], close=False
    )
    # AddToDB merges the two exactly equal native contact points. A second
    # point-pair coincident relation would be redundant.
    (bridge,) = await add_line_chain(adapter, [a, b], close=False)
    for line in (tangent, bridge):
        _construction(adapter, line)
    for label, entity1, entity2, relation in (
        ("first contact on finite flank", f"{tangent}.start", first, "coincident"),
        ("anvil tangent to first flank", tangent, first, "tangent"),
        ("second contact on finite flank", f"{bridge}.end", second, "coincident"),
        ("span normal to actual tangent", bridge, tangent, "perpendicular"),
        ("span normal to pair bisector", bridge, bisector, "perpendicular"),
    ):
        check(label, await adapter.add_sketch_constraint(entity1, entity2, relation))
    await dimension_between(
        adapter, f"{tangent}.start", f"{tangent}.end", "distance", tangent_length, "construction tangent length"
    )
    await ensure_fully_defined(adapter, "physical span contacts and fixed inspection direction")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    suppress_dimension_input(adapter)
    model.ClearSelection2(True)
    _select_segment(adapter, bridge, 0)
    text = ((a[0] + b[0]) / 2 + direction[0] * 5.0, (a[1] + b[1]) / 2 + direction[1] * 5.0)
    display = model.AddDimension2(text[0] / 1000.0, text[1] / 1000.0, 0.0)
    model.ClearSelection2(True)
    actual_mm = _driven_carrier(display, name, expected, 2 * profile.geometry_error_bound_mm, reference=False)
    check("exit_sketch physical span", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    # A standalone sketch saves shown and renders in every assembly; the
    # drawing still imports its dimension from the hidden sketch.
    blank_reference_sketches(adapter, (feature,))
    return actual_mm


def apply_span_limits(
    adapter: Any,
    *,
    nominal_mm: float,
    deviations: tuple[float, float],
    places: int,
    prefix: str,
    feature: str = "SpanProfile",
    name: str = "ToothSpan",
) -> None:
    """The caller's source-owned physical LIMIT band, not REF acceptance ink."""
    display, dimension = _named_dimension(adapter, feature, name)
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{name}: expected the driven actual-contact carrier")
    lower, upper = deviations  # native API order, from _fit_limits.deviations
    actual = float(dimension.SystemValue) * 1000.0
    if not nominal_mm + lower <= actual <= nominal_mm + upper:
        raise RuntimeError(f"{name}: native measured span is outside its printed acceptance limits")
    raw_tolerance = dimension.Tolerance
    if raw_tolerance is None:
        raise RuntimeError(f"{name}: actual-contact dimension has no native tolerance")
    tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
    tolerance.Type = 3  # swTolLIMIT
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{name}: native source inspection limits were rejected")
    if (
        int(tolerance.Type) != 3
        or not math.isclose(float(tolerance.GetMinValue()), lower / 1000.0, rel_tol=0.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), upper / 1000.0, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise RuntimeError(f"{name}: native inspection limits changed")
    for actual_limit, source_limit in (
        (actual + float(tolerance.GetMinValue()) * 1000.0, nominal_mm + lower),
        (actual + float(tolerance.GetMaxValue()) * 1000.0, nominal_mm + upper),
    ):
        if f"{actual_limit:.{places}f}" != f"{source_limit:.{places}f}":
            raise RuntimeError(f"{name}: real native carrier changed the printed physical limits")
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(-1, -1, places, -1)
    if int(display.GetPrimaryTolPrecision2()) != places:
        raise RuntimeError(f"{name}: native limit precision changed")
    set_dimension_prefix(adapter, feature, name, prefix)


async def author_root_envelope(
    adapter: Any,
    profile: StockFormProfile,
    *,
    feature: str = "RootInspectionProfile",
    name: str = "RootEnvelope",
) -> float:
    """Actual axis-centred minimum-root diameter REF, on genuine root geometry.

    For the paper drive's positive translations the minimum norm is at a
    finite root-arc endpoint. The construction circle is constrained through
    that actual fixed core endpoint, not independently dimensioned to a
    computed acceptance floor. An interior-arc minimum needs a different
    native carrier and is refused here rather than guessed.
    """
    if profile.helix_angle_deg != 0.0:
        raise ValueError("axis-root carrier requires a straight finite profile")
    segment = next((s for s in profile.native_segments() if s.kind == "root_arc"), None)
    if segment is None:
        raise ValueError("axis-root carrier lacks its genuine finite root arc")
    radius = math.hypot(*segment.start_mm)
    if abs(radius - profile.root_radius_min_mm) > 2 * profile.geometry_error_bound_mm:
        raise ValueError("axis-root minimum is not a supported finite root-arc endpoint")
    check("create_sketch axis-root inspection", await adapter.create_sketch("Front"))
    suppress_dimension_input(adapter)
    root = await placed_ground_curve(adapter, segment, math.pi / profile.teeth)
    _construction(adapter, root)
    await ensure_fully_defined(adapter, "exact root inspection arc", fix_entities=[root], allow_fix_escalation=True)
    set_sketch_direct_db(adapter, True)
    try:
        circle = check("actual root envelope circle", await adapter.add_circle(0.0, 0.0, radius))
    finally:
        set_sketch_direct_db(adapter, False)
    _construction(adapter, circle)
    await anchor_point_to_origin(adapter, f"{circle}.center", 0.0, 0.0, "root envelope axis")
    check("root circle through physical minimum", await adapter.add_sketch_constraint(f"{root}.start", circle, "coincident"))
    await ensure_fully_defined(adapter, "genuine axis-root minimum envelope")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    suppress_dimension_input(adapter)
    model.ClearSelection2(True)
    _select_segment(adapter, circle, 0)
    display = model.AddDiameterDimension2((radius + 5.0) / 1000.0, (radius + 5.0) / 1000.0, 0.0)
    model.ClearSelection2(True)
    actual_mm = _driven_carrier(display, name, 2 * radius, 2 * profile.geometry_error_bound_mm, reference=True)
    check("exit_sketch axis-root inspection", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    blank_reference_sketches(adapter, (feature,))
    return actual_mm


async def author_cutter_endcut(
    adapter: Any,
    profile: StockFormProfile,
    cutter_diameter_mm: float,
    station_mm: float,
    *,
    prefix: str = "Tool",
    rotate_rad: float | None = None,
) -> CutterEndFeatures:
    """Native finite ground-component revolution, not a caller's cut-path proof.

    The tool section closes at its true finite ground-tip Y ends and tangent
    arbor X. Both sides remain outside the blank: rotation increases X at
    fixed Y. The caller must separately prove this for every printed corner,
    own any larger stock envelope, and gate the extra native removal volume.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters, RevolveParameters

    if profile.helix_angle_deg != 0.0 or not math.isfinite(cutter_diameter_mm) or cutter_diameter_mm <= 0.0:
        raise ValueError("finite cutter end requires a positive straight disc cutter")
    air = math.hypot(*profile.flank_point(profile.template.flank_parameter_max)) - profile.blank_radius_mm
    if air <= profile.geometry_error_bound_mm:
        raise ValueError("finite ground-tip closure reaches the native blank")
    angle = math.pi / profile.teeth if rotate_rad is None else rotate_rad
    translation = profile.radial_translation_mm
    axis_x = cutter_diameter_mm / 2 + profile.root_point(profile.root_half_angle_rad)[0]
    master_profile = StockFormProfile(profile.template.reference_teeth, profile.template, profile.template.tip_radius_mm, 0.0)
    # Retain only authentic ground branches of the full public zero-T
    # reference-count master. Clearance rays/arc never enter the tool body.
    master = master_profile.native_segments(unit_scale=1.0 / 25.4)
    roots = [segment for segment in master if segment.kind == "root_arc"]
    upper_ground = [segment for segment in master if segment.kind in ("radial", "flank") and segment.name.startswith("Upper")]
    lower_ground = [segment for segment in master if segment.kind in ("radial", "flank") and segment.name.startswith("Lower")]
    if len(roots) != 1 or not upper_ground or not lower_ground:
        raise ValueError("finite cutter master lacks its genuine upper/root/lower ground branches")
    ground = upper_ground + roots + lower_ground
    if max(p[0] + translation for s in ground for p in (s.start_mm, s.end_mm)) >= axis_x:
        raise ValueError("finite ground component crosses its tangential cutter arbor")
    upper, lower = ground[0].start_mm, ground[-1].end_mm
    plane, sketch, cut = f"{prefix}EndPlane", f"{prefix}RunoutProfile", f"{prefix}EndCut"
    check("create_plane finite cutter end", await adapter.create_plane(CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=station_mm)))
    name_last_feature(adapter, plane)
    check("create_sketch finite cutter ground", await adapter.create_sketch(plane))
    suppress_dimension_input(adapter)
    curves = [await placed_ground_curve(adapter, segment, angle, translation) for segment in ground]
    # The ground chain (UpperFiniteFlank, UpperBelowBase, RootArc,
    # LowerBelowBase, LowerFiniteFlank) is defined after all but its last two
    # curves are FIXed; those two close it and must not be nearly collinear.
    # In chain order they were LowerBelowBase and the almost radial
    # LowerFiniteFlank, and the solve ended no_solution. FIX the upper
    # branch, then the lower branch from its outer end, so the radial
    # LowerBelowBase and the tangential RootArc close it: a near-perpendicular
    # pair (_gear.stock_gap_fix_order's rule).
    n_upper = len(upper_ground)
    fix_order = curves[:n_upper] + curves[n_upper + 1 :][::-1] + [curves[n_upper]]
    await ensure_fully_defined(adapter, "finite ground curves", fix_entities=fix_order, allow_fix_escalation=True)
    a, b = rotate_mm((axis_x, lower[1]), angle), rotate_mm((axis_x, upper[1]), angle)
    arbor = check("tangential cutter arbor", await adapter.add_centerline(*a, *b))
    await anchor_point_to_origin(adapter, f"{arbor}.start", *a, "cutter arbor lower end")
    await anchor_point_to_origin(adapter, f"{arbor}.end", *b, "cutter arbor upper end")
    await add_line_chain(
        adapter, [rotate_mm(lower, angle, translation), a, b, rotate_mm(upper, angle, translation)], close=False
    )
    await ensure_fully_defined(adapter, "finite cutter ground envelope")
    check("exit_sketch finite cutter ground", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    check(
        "revolve-cut finite cutter end",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, cut)
    blank_reference_geometry(adapter, ((plane, "PLANE"),))
    return CutterEndFeatures(plane, sketch, cut)
