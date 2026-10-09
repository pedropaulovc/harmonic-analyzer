r"""Author the cutter-native configured cone family, T006 through T120.

``dt_cone_gear_spec.stock_form_profile`` is the geometry authority. Each
configuration has its own finite, literal core equation-curve gap, through cut
and physical-tooth-count pattern. The other configurations suppress those
features: below-base templates have eight real curves, above-base templates
six. No zero-length connector, ideal-N flank or upper continuation is used.

The common extruded blank and D-bore retain configuration-owned native
dimensions. Gap bisectors rotate by pi/N so tooth zero and the bore flat's
outward normal remain +X. Native inspection sketches carry the actual pitch
thickness and functional root-envelope limits; neither sketch claims to drive
the cutter curves or to depict a circular manufactured floor.

Every row checks blank, single-cut and full-pattern volumes against the core's
Green-area property. Saved configurations retain body, face, pattern, volume,
rebuild, root-envelope and bore-web guards. All twenty must be qualified before
the native build starts; a refused design is not published as partial family.
"""

from __future__ import annotations

import math
import sys
import time
from typing import Any

import _config
from _drawing_marks import (
    _named_dimension,
    add_angular_reference_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_angular_tolerance,
)
from _drawing_simplified import assert_simplified_configurations, derive_simplified_on_saved_part
from _fit_limits import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_pmi import author_part_pmi
from dt_cone_gear_notes import custom_cutter_detail, drawing_notes, gear_data
from dt_cone_gear_spec import (
    BLANK_DIA_BAND,
    BORE_AF_BAND,
    FACE_WIDTH_BAND,
    BORE_DIA_BAND,
    CONFIGURATION_TEETH,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FLAT_CLOCK_TOLERANCE_DEG,
    GAP_FLOOR_SKETCH,
    MM_PER_IN,
    MACHINED_WEB_TARGET_MM,
    WEB_EXCEPTIONS_MM,
    REFERENCE_SKETCHES,
    SURFACE_FINISHES,
    TOOTH_REFERENCE_SKETCH,
    TOOTH_THICKNESS_BAND,
    bore_dia_mm,
    bore_flat_af_mm,
    bore_flat_offset_mm,
    bore_flat_segment_area_mm2,
    configuration_number,
    floor_limits_mm,
    floor_radius_min_mm,
    floor_radius_max_mm,
    material_specification,
    stock_form_profile,
)
from _common import (
    OUT_PNG,
    OUT_SLDPRT,
    SketchDims,
    _early_bound,
    _read_member,
    apply_custom_properties,
    apply_material,
    assert_saved_configurations_regenerate,
    blank_sketch,
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
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)
from _visibility import assert_reference_geometry_hidden, blank_reference_geometry

# Equation-parser/unit guards are reused, not their historical ideal profiles.

import _telemetry
from involute_gear import (
    equation_curve,
    pattern_count_dimension,
    read_dimension,
    set_global,
)

PART_NAME = "dt-cone-gear"
MATERIAL = "Brass"  # ch. 13 text: polished brass gear stock; cone set matches
# The four smallest tip gears read "more yellow ... a harder metal" (ch.12 p.21)
# -- a high-zinc yellow metal (Muntz/manganese bronze). That muntz_yellow tint is
# applied at the ASSEMBLY-COMPONENT level on the four tip-gear instances (see
# build_dt_drive_train_assembly.py): a per-config PART colour loses to the brass
# material appearance and a body colour bleeds across all 20 configs, whereas a
# component appearance is per-instance and is what the render pipeline reads
# (export_models comp_rgb -> IComponent2.GetMaterialPropertyValues2). The part
# itself stays uniformly brass. See cad/config/materials.yaml.

# The exact-tracking mesh fixes the shaft pitch at Z_PITCH*cos(INCLINE_DEG).
# The face is that pitch floored to its printed four places
# (dt_cone_gear_spec.FACE_WIDTH), so neighbouring gears bear on each other.

# Native equation curves evaluate document lengths in inches; core scales them.
R_CLEAR_MM = 60.0
CONFIGS = tuple((f"T{n:03d}", n) for n in CONFIGURATION_TEETH)
DEFAULT_TEETH = CONFIGURATION_TEETH[-1]


def tooth_features(teeth: int) -> tuple[str, str, str]:
    """Distinct real topology for one configured finite cutter profile."""
    if teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    suffix = f"T{teeth:03d}"
    return tuple(f"{stem}{suffix}" for stem in (
        "ToothGapProfile", "ToothGapCut", "ToothGapPattern"
    ))


# All cuts/patterns disappear in the derived assembly drawing configurations.
SIMPLIFIED_FEATURES = tuple(
    feature for teeth in CONFIGURATION_TEETH for feature in tooth_features(teeth)[1:]
)
SIMPLIFIED_FEATURES_BY_CONFIGURATION = {
    f"T{teeth:03d}": tooth_features(teeth)[1:] for teeth in CONFIGURATION_TEETH
}
_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT
_SET_IN_SPECIFIC_CONFIGURATIONS = 3  # swSetValueInConfiguration_e
_VISIBILITY_HIDDEN = 1  # swVisibilityState_e

def bore_dia_in(teeth: int) -> float:
    """Configured bore diameter in inches, matching the stepped-shaft seat."""
    return bore_dia_mm(teeth) / MM_PER_IN


def bore_af_in(teeth: int) -> float:
    """Configured bore across-flat in inches, matching its land's flat."""
    return bore_flat_af_mm(teeth) / MM_PER_IN


def bore_area_mm2(teeth: int) -> float:
    """Area of the D-bore: the round bore less the segment the flat keeps."""
    return math.pi * (bore_dia_mm(teeth) / 2.0) ** 2 - bore_flat_segment_area_mm2(
        teeth
    )


def floor_dia_in(teeth: int) -> float:
    """Functional minimum root envelope, not the translated cutter root radius."""
    return 2.0 * floor_radius_min_mm(teeth) / MM_PER_IN


def gap_floor_deviations_mm(teeth: int) -> tuple[float, float]:
    """FloorDia's (lower, upper) LIMIT deviations from the modelled floor.

    The printed limits are ``floor_limits_mm``; the dimension's nominal is the
    modelled floor, so each limit is stored as its offset from it.
    """
    minimum, maximum = floor_limits_mm(teeth)
    nominal = 2.0 * floor_radius_min_mm(teeth)
    return minimum - nominal, maximum - nominal




def _as_construction(adapter, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _author_tooth_thickness_reference(adapter: Any) -> SketchDims:
    """Author the native circular-thickness acceptance scale on the +X tooth.

    Its value is the actual installed cutter's pitch-circle arc thickness.
    The construction length is an inspection witness, not a chord oracle or a
    controlling flank equation. The solid remains the finite core curves.
    """
    tooth_reference = SketchDims()
    thickness_mm = stock_form_profile(DEFAULT_TEETH).pitch_tooth_thickness_mm
    check(
        "create_sketch tooth-thickness reference",
        await adapter.create_sketch("Front"),
    )
    pitch_radius_mm = DEFAULT_TEETH / DIAMETRAL_PITCH * MM_PER_IN / 2.0
    set_sketch_direct_db(adapter, True)
    tooth_line = check(
        "tooth-thickness reference line",
        await adapter.add_line(
            pitch_radius_mm,
            -thickness_mm / 2.0,
            pitch_radius_mm,
            thickness_mm / 2.0,
        ),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, tooth_line)
    check(
        "tooth-thickness reference vertical",
        await adapter.add_sketch_constraint(tooth_line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        "origin",
        "horizontal_distance",
        pitch_radius_mm,
        "tooth-thickness pitch radius",
    )
    tooth_reference.record(
        "ToothPitchRadius",
        '"ToothCount" / "DP" / 2',
    )
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        "origin",
        "vertical_distance",
        thickness_mm / 2.0,
        "tooth-thickness chord centred on the X axis",
    )
    tooth_reference.record("ToothHalfThickness", '"ToothThickness" / 2')
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        f"{tooth_line}.end",
        "vertical_distance",
        thickness_mm,
        "circular tooth thickness",
    )
    tooth_reference.record("ToothThickness", '"ToothThickness"')
    await ensure_fully_defined(adapter, "tooth-thickness reference sketch")
    check(
        "exit_sketch tooth-thickness reference",
        await adapter.exit_sketch(),
    )
    return tooth_reference


async def _author_gap_floor_reference(adapter: Any) -> SketchDims:
    """Author the model-owned gap-floor dimension: a construction circle at the
    modelled floor, its diameter driven by the configuration-scoped FloorDia.

    The translated cutter root is an off-centre arc. This origin-centred
    witness carries its minimum radial envelope and the permitted functional
    MIN/MAX limits; it is not a circular BRep floor or a cutter driving size.
    """
    floor = SketchDims()
    check("create_sketch gap-floor reference", await adapter.create_sketch("Front"))
    circle = await define_circle(
        adapter,
        0.0,
        0.0,
        floor_radius_min_mm(DEFAULT_TEETH),
        "gap-floor reference",
        dims=floor,
        names=(None, None, "FloorDia"),
        drives=(None, None, '"FloorDia"'),
    )
    _as_construction(adapter, circle)
    await ensure_fully_defined(adapter, "gap-floor reference sketch")
    check("exit_sketch gap-floor reference", await adapter.exit_sketch())
    return floor


def _gap_floor_tolerance(adapter: Any) -> Any:
    _display, dimension = _named_dimension(adapter, GAP_FLOOR_SKETCH, "FloorDia")
    return _early_bound(dimension.Tolerance, "IDimensionTolerance")


def _set_gap_floor_limits(adapter: Any) -> None:
    """Store each configuration's printed floor limits on FloorDia (LIMIT).

    One dimension, twenty bands: ``SetValues2`` with
    swSetValue_InSpecificConfigurations and a one-name BSTR array writes a
    single configuration without activating it.  Probe leaf 834-gapfloor-c301
    read this form back per configuration after save and reopen, and on two
    drawing sheets; the configuration sweep reads all twenty back.
    """
    import pythoncom
    from win32com.client import VARIANT

    tolerance = _gap_floor_tolerance(adapter)
    tolerance.Type = _TOL_LIMIT
    if int(tolerance.Type) != _TOL_LIMIT:
        raise RuntimeError("FloorDia: LIMIT tolerance type did not persist")
    for name, teeth in CONFIGS:
        lower, upper = gap_floor_deviations_mm(teeth)
        names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [name])
        accepted = tolerance.SetValues2(
            lower / 1000.0, upper / 1000.0, _SET_IN_SPECIFIC_CONFIGURATIONS, names
        )
        if not bool(accepted):
            raise RuntimeError(
                f"FloorDia@{name}: SetValues2 rejected the limits "
                f"{floor_limits_mm(teeth)} mm"
            )
    _telemetry.success(f"FloorDia: LIMIT set in {len(CONFIGS)} configurations")


def _assert_gap_floor_limits(adapter: Any, configuration: str, teeth: int) -> None:
    """Read FloorDia's LIMIT back in the active configuration."""
    tolerance = _gap_floor_tolerance(adapter)
    kind = int(tolerance.Type)
    observed = (
        float(tolerance.GetMinValue()) * 1000.0,
        float(tolerance.GetMaxValue()) * 1000.0,
    )
    expected = gap_floor_deviations_mm(teeth)
    drifted = any(abs(o - e) > 1e-6 for o, e in zip(observed, expected))
    if kind != _TOL_LIMIT or drifted:
        raise RuntimeError(
            f"{configuration}: FloorDia tolerance reads type {kind} {observed} mm, "
            f"expected LIMIT {expected} mm"
        )
    _telemetry.success(
        f"{configuration}: gap-floor limits {floor_limits_mm(teeth)} mm"
    )


def _blank_reference_sketches(adapter: Any) -> None:
    """Save the two authoring sketches hidden, and prove it.

    Shown, they render in the part's images and in every assembly that places
    a gear; the sheet's front view shows them again for their dimensions
    (``_drawing_hidden_sketches``).
    """
    part = _early_bound(adapter.currentModel, "IPartDoc")
    for sketch in REFERENCE_SKETCHES:
        blank_sketch(adapter, sketch)
        feature = part.FeatureByName(sketch)
        if feature is None:
            raise RuntimeError(f"{sketch}: sketch missing after BlankSketch")
        visible = int(_read_member(_early_bound(feature, "IFeature"), "Visible"))
        if visible != _VISIBILITY_HIDDEN:
            raise RuntimeError(
                f"{sketch}: still visible after BlankSketch (Visible={visible})"
            )


def _active_configuration(model: Any) -> Any:
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    return _early_bound(manager.ActiveConfiguration, "IConfiguration")


def _activate_configuration(model: Any, configuration: str) -> Any:
    """Activate a configuration, accepting SW 2026's already-active False."""
    active = _active_configuration(model)
    if str(active.Name) != configuration and not bool(
        model.ShowConfiguration2(configuration)
    ):
        raise RuntimeError(f"failed to activate configuration {configuration}")
    active = _active_configuration(model)
    if str(active.Name) != configuration:
        raise RuntimeError(
            f"active configuration {str(active.Name)!r} != {configuration!r}"
        )
    return active


def _expected_configuration_volume(teeth: int) -> float:
    profile = stock_form_profile(teeth)
    return (
        math.pi * profile.blank_radius_mm**2
        - teeth * profile.gap_area_mm2
        - bore_area_mm2(teeth)
    ) * FACE_WIDTH


def _native_root_envelope_mm(body: Any, *, teeth: int) -> tuple[float, float, int]:
    """Read each translated root arc from the solid, including its radial extrema.

    Endpoint pairs identify the actual persisted root edges, not a presumed
    circle at T+root. The edge's closest point to the gear axis supplies MIN;
    endpoints and the symmetric arc midpoint supply MAX. Rotated copies use
    the physical N and the explicit pi/N gap clock.
    """
    profile = stock_form_profile(teeth)
    root = next(segment for segment in profile.native_segments(
        unit_scale=1.0, clearance_radius_mm=R_CLEAR_MM
    ) if segment.kind == "root_arc")
    roots: list[tuple[float, float]] = []
    for raw_edge in tuple(_early_bound(body, "IBody2").GetEdges() or ()):
        edge = _early_bound(raw_edge, "IEdge")
        vertices = (edge.GetStartVertex(), edge.GetEndVertex())
        if any(vertex is None for vertex in vertices):
            continue
        points = tuple(tuple(float(v) * 1000.0 for v in
            _early_bound(vertex, "IVertex").GetPoint()) for vertex in vertices)
        start, end = points
        if abs(start[2] - end[2]) > 1e-6:
            continue
        for index in range(teeth):
            angle = (2 * index + 1) * math.pi / teeth
            cosine, sine = math.cos(angle), math.sin(angle)

            def rotated(t: float) -> tuple[float, float]:
                x, y = root.point(t)
                return cosine * x - sine * y, sine * x + cosine * y

            expected = (rotated(0.0), rotated(1.0))
            matches = any(
                max(math.dist(start[:2], pair[0]), math.dist(end[:2], pair[1])) < 0.002
                for pair in (expected, tuple(reversed(expected)))
            )
            if not matches:
                continue
            closest = tuple(float(v) * 1000.0 for v in
                edge.GetClosestPointOn(0.0, 0.0, start[2] / 1000.0))
            midpoint = rotated(0.5)
            native_midpoint = tuple(float(v) * 1000.0 for v in
                edge.GetClosestPointOn(
                    midpoint[0] / 1000.0, midpoint[1] / 1000.0, start[2] / 1000.0
                ))
            if len(closest) < 3 or len(native_midpoint) < 3:
                raise RuntimeError(f"T{teeth:03d}: unreadable native root edge")
            if math.dist(native_midpoint[:2], midpoint) > 0.002:
                raise RuntimeError(f"T{teeth:03d}: root edge differs from finite cutter arc")
            roots.append((
                math.hypot(*closest[:2]),
                max(math.hypot(*point[:2]) for point in (start, end, native_midpoint)),
            ))
            break
    if len(roots) < teeth:
        raise RuntimeError(f"T{teeth:03d}: only {len(roots)} native root arcs for {teeth} teeth")
    return min(value[0] for value in roots), max(value[1] for value in roots), len(roots)


def _configuration_definition_state(
    adapter: Any, configuration: str, *, phase: str
) -> None:
    """Log the equation, seed-feature and pattern-definition persistence state."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    equation_manager = _early_bound(model.GetEquationMgr(), "IEquationMgr")
    wanted = {"ToothCount", "BoreDia", "BoreAF", "Ra", "FloorDia", "ToothThickness"}
    equations: dict[str, tuple[str, float]] = {}
    count = int(_read_member(equation_manager, "GetCount") or 0)
    for index in range(count):
        equation = str(equation_manager.Equation(index) or "")
        left, _, _right = equation.partition("=")
        name = left.strip().strip('"')
        if name in wanted:
            equations[name] = (equation, float(equation_manager.Value(index)))

    feature_states: dict[str, tuple[bool, int, bool]] = {}
    for name in tooth_features(int(configuration[1:])):
        raw = part.FeatureByName(name)
        if raw is None:
            raise RuntimeError(f"{configuration}: diagnostic feature {name} missing")
        feature = _early_bound(raw, "IFeature")
        states = feature.IsSuppressed2(3, [configuration])
        if not isinstance(states, (list, tuple)):
            states = (states,)
        error_result = feature.GetErrorCode2()
        if not isinstance(error_result, (list, tuple)) or len(error_result) < 2:
            raise RuntimeError(
                f"{configuration}: unreadable {name} error state {error_result!r}"
            )
        feature_states[name] = (
            len(states) != 1 or bool(states[0]),
            int(error_result[0] or 0),
            bool(error_result[1]),
        )

    pattern = _early_bound(
        part.FeatureByName(tooth_features(int(configuration[1:]))[2]), "IFeature"
    )
    definition = _early_bound(
        pattern.GetDefinition(), "ICircularPatternFeatureData"
    )
    _telemetry.info(
        f"{phase} cone-gear definition state {configuration}: "
        f"equations={equations!r}, features={feature_states!r}, "
        f"geometry_pattern={bool(definition.GeometryPattern)}, "
        f"instances={int(definition.TotalInstances)}"
    )


async def _configuration_topology(
    adapter: Any,
    configuration: str,
    teeth: int,
    *,
    phase: str,
) -> tuple[float, str, tuple[str, ...]]:
    """Measure one configuration's real pattern and solid-body topology."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    active = _activate_configuration(model, configuration)
    part = _early_bound(model, "IPartDoc")
    pattern_name = tooth_features(teeth)[2]
    raw_pattern = part.FeatureByName(pattern_name)
    if raw_pattern is None:
        raise RuntimeError(f"{configuration}: {pattern_name} is missing")
    pattern = _early_bound(raw_pattern, "IFeature")
    states = pattern.IsSuppressed2(3, [configuration])
    if not isinstance(states, (list, tuple)):
        states = (states,)
    suppressed = len(states) != 1 or bool(states[0])
    definition = _early_bound(
        pattern.GetDefinition(), "ICircularPatternFeatureData"
    )
    instances = int(definition.TotalInstances)
    error_result = pattern.GetErrorCode2()
    if not isinstance(error_result, (list, tuple)) or len(error_result) < 2:
        raise RuntimeError(
            f"{configuration}: unreadable pattern error state {error_result!r}"
        )
    error_code = int(error_result[0] or 0)
    is_warning = bool(error_result[1])
    bodies = tuple(part.GetBodies2(0, False) or ())
    face_count = (
        int(_early_bound(bodies[0], "IBody2").GetFaceCount())
        if len(bodies) == 1
        else 0
    )
    feature_issues: list[str] = []
    for row_teeth in CONFIGURATION_TEETH:
        for feature_name in tooth_features(row_teeth):
            raw_feature = part.FeatureByName(feature_name)
            if raw_feature is None:
                feature_issues.append(f"missing native feature {feature_name}")
                continue
            feature = _early_bound(raw_feature, "IFeature")
            answer = feature.IsSuppressed2(3, [configuration])
            answer = answer if isinstance(answer, (list, tuple)) else (answer,)
            if len(answer) != 1 or bool(answer[0]) != (row_teeth != teeth):
                feature_issues.append(f"{feature_name}: wrong suppression in {configuration}")
            if row_teeth == teeth:
                error = feature.GetErrorCode2()
                if not isinstance(error, (list, tuple)) or len(error) < 2:
                    feature_issues.append(f"{feature_name}: unreadable native error state")
                elif int(error[0] or 0):
                    feature_issues.append(
                        f"{feature_name}: native error {error[0]}, warning={bool(error[1])}"
                    )
    raw_sketch = part.FeatureByName(tooth_features(teeth)[0])
    if raw_sketch is not None:
        raw_specific = _early_bound(raw_sketch, "IFeature").GetSpecificFeature2()
        if raw_specific is None:
            raise RuntimeError(f"{configuration}: native gap sketch has no ISketch")
        sketch = _early_bound(raw_specific, "ISketch")
        entities = tuple(sketch.GetSketchSegments() or ())
        expected_entities = len(stock_form_profile(teeth).native_segments(
            unit_scale=1.0 / MM_PER_IN, clearance_radius_mm=R_CLEAR_MM
        ))
        if len(entities) != expected_entities:
            feature_issues.append(
                f"native gap entities {len(entities)} != real finite topology {expected_entities}"
            )
    root_observation = ""
    root_issues: list[str] = []
    if len(bodies) == 1:
        native_min, native_max, root_edges = _native_root_envelope_mm(bodies[0], teeth=teeth)
        expected_min, expected_max = floor_radius_min_mm(teeth), floor_radius_max_mm(teeth)
        maximum_bore_radius = (bore_dia_mm(teeth) + BORE_DIA_BAND[0]) / 2.0
        minimum_web = native_min - maximum_bore_radius
        root_observation = (
            f", native_root_min={native_min:.6f}, native_root_max={native_max:.6f}, "
            f"expected_root_min={expected_min:.6f}, expected_root_max={expected_max:.6f}, "
            f"minimum_bore_web={minimum_web:.6f}, root_edges={root_edges}"
        )
        if max(abs(native_min - expected_min), abs(native_max - expected_max)) > 0.002:
            root_issues.append("native radial root envelope differs from the finite cutter arc")
        required_web = WEB_EXCEPTIONS_MM.get(teeth, MACHINED_WEB_TARGET_MM)
        if minimum_web < required_web - 1e-9:
            root_issues.append(
                f"native bore web {minimum_web:.6f} < retained {required_web:.6f} mm"
            )
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{configuration}: get_mass_properties failed: {mass.error}")
    volume = float(mass.data.volume)
    expected = _expected_configuration_volume(teeth)
    needs_rebuild = bool(active.NeedsRebuild)
    save_mark = bool(active.AddRebuildSaveMark)
    observation = (
        f"{configuration}: active={str(active.Name)}, "
        f"needs_rebuild={needs_rebuild}, save_mark={save_mark}, "
        f"{pattern_name} instances={instances}, "
        f"suppressed={suppressed}, error={error_code}, warning={is_warning}, "
        f"bodies={len(bodies)}, faces={face_count}, volume={volume:.1f}, "
        f"expected={expected:.1f}{root_observation}"
    )
    _telemetry.info(f"{phase} cone-gear topology: {observation}")
    issues: list[str] = []
    issues.extend(root_issues)
    issues.extend(feature_issues)
    if needs_rebuild:
        issues.append("configuration needs rebuild")
    if instances != teeth:
        issues.append(f"pattern instances {instances} != {teeth}")
    if suppressed:
        issues.append("pattern is suppressed")
    if error_code:
        issues.append(f"pattern error {error_code} warning={is_warning}")
    if len(bodies) != 1:
        issues.append(f"solid body count {len(bodies)} != 1")
    if face_count < 2 * teeth + 4:
        issues.append(
            f"solid face count {face_count} < toothed minimum {2 * teeth + 4}"
        )
    area_error = stock_form_profile(teeth).gap_area_error_bound_mm2 * teeth * FACE_WIDTH
    if abs(volume - expected) + area_error > 0.01 * expected:
        issues.append(
            f"volume {volume:.1f} outside bounded 1% of Green expectation {expected:.1f}"
        )
    if configuration in {CONFIGS[0][0], CONFIGS[-1][0]}:
        _configuration_definition_state(
            adapter, configuration, phase=phase
        )
    return volume, observation, tuple(issues)


async def assert_saved_configuration_topology(
    adapter: Any, *, phase: str = "saved"
) -> dict[str, float]:
    """Fully solve each reopened configuration, then strictly validate its teeth.

    Before any geometry getter, each saved configuration is activated through
    the repository's established ``set_active_configuration`` helper.  That
    helper switches with ``ShowConfiguration2`` and applies its documented
    full-solve strategy for equation-driven geometry: ``ForceRebuild3(False)``
    with the existing ``EditRebuild3`` fallback.  The returned ``rebuilt`` flag
    must be true.

    An earlier b399963e discriminator read T006 before rebuilding and observed
    pattern error 1 / four faces; that read then lazily changed the state before
    the following ``EditRebuild3``.  A production closure subsequently proved
    that ``EditRebuild3`` alone returns False on untouched inactive caches.
    Those runs are preserved at:
    C:/src/dt-logs/farm-runs/20260921T224631Z-cone-b399-capture/
    20260921T225446Z-leaf-part-cone_gear/task.log lines 481-493, and
    C:/src/dt-logs/farm-runs/20260921T230142Z-cone-closure-capture/
    20260921T231022Z-leaf-part-cone_gear/task.log lines 480-505.

    This validates the rebuilt saved model, not its cold caches; the part's
    reopen proves those first (``_common.assert_saved_configurations_regenerate``).
    A failed
    activation/rebuild or any post-rebuild error, body, face, volume, or
    monotonicity mismatch remains fatal.
    """
    failures: list[str] = []
    volumes: dict[str, float] = {}
    ordered = (CONFIGS[-1], *CONFIGS[:-1])
    _telemetry.info(
        f"{phase}: validating all configurations after the established "
        "set_active_configuration rebuild (the part's reopen proves the saved "
        "caches first, assert_saved_configurations_regenerate)"
    )
    for configuration, teeth in ordered:
        try:
            activation_started = time.perf_counter()
            activation = await adapter.set_active_configuration(configuration)
            activation_elapsed = time.perf_counter() - activation_started
            check(f"{phase} activate {configuration}", activation)
            rebuilt = bool(activation.data.get("rebuilt"))
            _telemetry.info(
                f"{phase} {configuration}: "
                f"set_active_configuration rebuilt={rebuilt}, "
                f"elapsed={activation_elapsed:.6f}s"
            )
            if not rebuilt:
                failures.append(
                    f"{configuration}: set_active_configuration returned "
                    f"rebuilt=False after {activation_elapsed:.6f}s"
                )
                continue
            volume, observation, issues = await _configuration_topology(
                adapter,
                configuration,
                teeth,
                phase=f"{phase} post-activation-rebuild",
            )
        except Exception as exc:
            failures.append(f"{configuration}: {exc}")
            continue
        volumes[configuration] = volume
        if issues:
            failures.append(f"{observation}; issues={issues!r}")

    try:
        restore_started = time.perf_counter()
        restore = await adapter.set_active_configuration(CONFIGS[-1][0])
        restore_elapsed = time.perf_counter() - restore_started
        check(f"{phase} restore {CONFIGS[-1][0]}", restore)
        restore_rebuilt = bool(restore.data.get("rebuilt"))
        _telemetry.info(
            f"{phase} restore {CONFIGS[-1][0]}: "
            f"set_active_configuration rebuilt={restore_rebuilt}, "
            f"elapsed={restore_elapsed:.6f}s"
        )
        if not restore_rebuilt:
            failures.append(
                f"restore {CONFIGS[-1][0]}: set_active_configuration "
                "returned rebuilt=False"
            )
    except Exception as exc:
        failures.append(f"restore {CONFIGS[-1][0]}: {exc}")

    if len(volumes) == len(CONFIGS):
        family = [volumes[name] for name, _teeth in CONFIGS]
        if not all(a < b for a, b in zip(family, family[1:], strict=False)):
            failures.append(f"reopened volumes not monotonic: {volumes!r}")
    if failures:
        raise RuntimeError(
            f"{phase} cone-gear configuration topology is invalid: "
            + "; ".join(failures)
        )
    return volumes


def _apply_configuration_properties(
    adapter: Any, configuration: str, properties: dict[str, str]
) -> None:
    """Write and verify configuration-specific title/data-block properties."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _read_member(model, "Extension")
    manager = adapter._attempt(
        lambda: extension.CustomPropertyManager(configuration), default=None
    )
    if manager is None:
        raise RuntimeError(
            f"CustomPropertyManager unavailable for configuration {configuration}"
        )
    manager = _early_bound(manager, "ICustomPropertyManager")
    for name, value in properties.items():
        text = str(value)
        adapter._attempt(
            lambda n=name, v=text: manager.Add3(n, 30, v, 2), default=None
        )
        observed = str(
            adapter._attempt(
                lambda n=name: model.GetCustomInfoValue(configuration, n), default=""
            )
        )
        if observed != text:
            raise RuntimeError(
                f"{configuration} property {name!r} readback "
                f"{observed!r} != {text!r}"
            )


def native_gap_segments(teeth: int) -> tuple[tuple[str, str, str], ...]:
    """Rotate the canonical core gap by pi/N, retaining its exact finite curves."""
    phase = math.pi / teeth
    cosine, sine = f"{math.cos(phase):.17g}", f"{math.sin(phase):.17g}"
    return tuple(
        (
            segment.name,
            f"({cosine})*({segment.x})-({sine})*({segment.y})",
            f"({sine})*({segment.x})+({cosine})*({segment.y})",
        )
        for segment in stock_form_profile(teeth).native_segments(
            unit_scale=1.0 / MM_PER_IN, clearance_radius_mm=R_CLEAR_MM
        )
    )


def _restrict_to_configuration(adapter: Any, teeth: int) -> None:
    """Suppress a row's real sketch/cut/pattern in every other configuration."""
    from solidworks_mcp.adapters.com_variant import bstr_array

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    selected = f"T{teeth:03d}"
    others = [str(name) for name in model.GetConfigurationNames() if str(name) != selected]
    for name in reversed(tooth_features(teeth)):
        raw = part.FeatureByName(name)
        if raw is None:
            raise RuntimeError(f"{selected}: missing configured feature {name}")
        feature = _early_bound(raw, "IFeature")
        if not bool(feature.SetSuppression2(0, 3, bstr_array(others))):
            raise RuntimeError(f"{selected}: cannot suppress {name} in {others}")


def require_complete_stock_family() -> None:
    """Refuse publication of any absent/unqualified configured native member."""
    refused = []
    for name, teeth in CONFIGS:
        try:
            stock_form_profile(teeth)
        except (ValueError, RuntimeError) as exc:
            refused.append(f"{name}: {exc}")
    if refused:
        raise RuntimeError("cutter-native cone family is unqualified: " + "; ".join(refused))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        CreateConfigurationParameters,
        ExtrusionParameters,
    )


    # Deferred drive jobs for the ORDINARY (non-tooth) circle dims: each
    # ``define_*``/``SketchDims.record`` queues a ``(dim@feature, expr)`` here,
    # applied in one batch after the base model + a rebuild exist (every
    # equation target must resolve against the finished part). The tooth-gap
    # profile contributes NOTHING here -- it must mesh with the mating gear, so
    # its flanks are never pinned to a recorded dim.
    drive_jobs: list[tuple[str, str]] = []
    require_complete_stock_family()

    check("create_part", await adapter.create_part())
    # Configuration-scoped equation updates only work for rows created by
    # IEquationMgr.Add3. A one-configuration model makes the adapter fall back
    # to Add2, whose rows later appeared to update transiently but reopened as
    # 120T in every configuration. Seed T120 before the first equation so every
    # global is born through Add3; the remaining configurations are added after
    # the base geometry exists.
    name, teeth = CONFIGS[-1]
    check(
        f"create_configuration {name}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=name, comment=f"{teeth}-tooth cone gear"
            )
        ),
    )

    profile = stock_form_profile(DEFAULT_TEETH)
    await set_global(adapter, "ToothCount", str(DEFAULT_TEETH), DEFAULT_TEETH)
    await set_global(adapter, "DP", f"{DIAMETRAL_PITCH:.17g}", DIAMETRAL_PITCH)
    for global_name, value in (
        ("Ra", profile.blank_radius_mm / MM_PER_IN),
        ("ToothThickness", profile.pitch_tooth_thickness_mm / MM_PER_IN),
    ):
        await set_global(adapter, global_name, f"{value:.17g}", value)

    # ------------------------------------------------------------------
    # Blank: disc at tip radius Ra -- an origin-snapped circle with a
    # DRIVING diameter dimension, extruded. NOT a revolve: a dimension-
    # driven cut through a revolved body freezes at its creation-time
    # profile size on SW 2026 (any later change of the cut's dimension --
    # equation, configured value or plain SystemValue -- makes the cut
    # solve to NOTHING; minimal repro probe_bore11, extrude counterpart
    # passes in probe_bore12). The bore cut below needs an extruded blank.
    # ------------------------------------------------------------------
    ra_default_mm = profile.blank_radius_mm
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Front"))
    blank_circle = check(
        "add_circle blank", await adapter.add_circle(0.0, 0.0, ra_default_mm)
    )
    check(
        "blank diameter dim (driving, D1)",
        await adapter.add_sketch_dimension(
            blank_circle, None, "diameter", 2.0 * ra_default_mm
        ),
    )
    # Record the manual driving dim into the per-sketch SketchDims (crank-pin
    # pattern): one display dim, driven by 2*Ra. This is the SAME link the
    # blank previously got via an inline ``create_equation`` -- now it is named
    # ("BlankDia") and deferred into ``drive_jobs`` instead, so the equation
    # target is the friendly name and resolves after the final rebuild.
    blank.record("BlankDia", '2 * "Ra"')
    status = await adapter.check_sketch_fully_defined()
    state = status.data.get("definition_state") if status.is_success else None
    if state != "fully_defined":
        raise RuntimeError(
            f"blank sketch is {state!r} -- origin snap missing; a fix would "
            "break the Ra configuration link, aborting"
        )
    _telemetry.success("blank sketch fully defined (driving dim, no fix)")
    check("exit_sketch blank", await adapter.exit_sketch())
    blank_sketch = name_last_feature(adapter, "BlankProfile")
    drive_jobs += blank.apply(adapter, blank_sketch)
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=FACE_WIDTH)),
    )
    name_last_feature(adapter, "Blank")
    # The face width is a size the turner sets, so it prints as a NATIVE model
    # dimension (drawing-simplicity-policy.md rules 1-2): name the extrude
    # depth so it can be marked and given its decimal places like the two
    # circle dims. It stays a literal (no drive job): FACE_WIDTH is one value
    # across all 20 configurations.
    name_dimensions(adapter, "Blank", ["FaceWidth"])

    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"blank mass properties failed: {mass.error}")
    com_z = float(mass.data.center_of_mass[2])
    if abs(com_z - FACE_WIDTH / 2.0) > 0.1:
        raise RuntimeError(
            f"blank centre of mass z = {com_z:.2f}, expected {FACE_WIDTH / 2.0:.2f}"
            " -- Front-plane extrusion direction flipped"
        )
    blank_volume = float(mass.data.volume)
    expected_blank = math.pi * ra_default_mm**2 * FACE_WIDTH
    if abs(blank_volume - expected_blank) > 0.02 * expected_blank:
        raise RuntimeError(
            f"blank volume {blank_volume:.1f} mm^3, expected {expected_blank:.1f}"
        )
    _telemetry.success(f"blank volume {blank_volume:.1f} mm^3 (com z {com_z:.2f})")

    # The blank diameter is now the named dim ``BlankDia@BlankProfile`` (its
    # 2*Ra drive is queued in ``drive_jobs``, applied in the deferred batch
    # below). Dimension values evaluate in DOCUMENT units; probe which unit
    # Parameter().Value reports so the per-config read-back asserts compare in
    # the right unit. The probe reads the AS-BUILT value, unchanged by the
    # rename (the drive is geometry-neutral).
    od_dim = f"BlankDia@{blank_sketch}"
    before = read_dimension(adapter, od_dim)
    ra_in = ra_default_mm / MM_PER_IN
    if abs(before - 2.0 * ra_in) < 1e-6 * ra_in:
        dim_unit = 1.0  # Value reads in inches
    elif abs(before - 2.0 * ra_default_mm) < 1e-6 * ra_default_mm:
        dim_unit = 25.4  # Value reads in millimetres
    else:
        raise RuntimeError(
            f"{od_dim} reads {before!r}, matches neither {2 * ra_in:.6g} in "
            f"nor {2 * ra_default_mm:.6g} mm"
        )
    _telemetry.debug(f"{od_dim} reads {before:g} (unit factor {dim_unit:g})")

    # ------------------------------------------------------------------
    # Configured D-bore (user ruling 2026-09-28): one sketch, one cut.  The
    # round part is an origin-centred arc with a DRIVING diameter linked to
    # "BoreDia"; the flat is a vertical line joining the arc's ends on local
    # +X (the phase-0 tooth's side), so its outward normal is +X.  A
    # construction centreline runs from the arc's far (-X) point along the
    # X axis to the flat: its horizontal length is the across-flat, the
    # DRIVING "BoreAF" dimension linked to the configured "BoreAF" global.
    # The flat's squareness to that centreline (the phase-0 tooth's) comes
    # from the vertical relation; the DRIVEN angular BoreFlatClock between
    # the flat and the centreline carries FLAT_CLOCK_TOLERANCE_DEG (the
    # cylinder gear's NotchPhase precedent).  No fix anywhere: a fix drives
    # the dimensions and kills their configuration links.
    #
    # DOF: arc 5 + flat 4 + centreline 4 = 13 = centre on origin 2 +
    # diameter 1 + flat vertical 1 + two end joins 4 + centreline horizontal
    # 1 + its start on the arc 1 + its start level with the origin 1 + its
    # end on the flat 1 + BoreAF 1.
    #
    # The bore MUST precede the circular pattern: cut AFTER the pattern,
    # the same recipe solves to nothing in every configuration whose
    # BoreDia differs from the creation-time value (live SW 2026 finding,
    # probe_bore5/6; the minimal disc+pattern+bore+configs model does NOT
    # reproduce it, so it is specific to this part's downstream-of-pattern
    # chain -- pre-pattern placement regenerates correctly).
    # ------------------------------------------------------------------
    bore_default_in = bore_dia_in(DEFAULT_TEETH)
    await set_global(adapter, "BoreDia", f"{bore_default_in:g}", bore_default_in)
    bore_af_default_in = bore_af_in(DEFAULT_TEETH)
    await set_global(
        adapter, "BoreAF", f"{bore_af_default_in:.12g}", bore_af_default_in
    )
    bore_radius = bore_dia_mm(DEFAULT_TEETH) / 2.0
    flat_x = bore_flat_offset_mm(DEFAULT_TEETH)
    flat_half = math.sqrt(bore_radius * bore_radius - flat_x * flat_x)
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    # CCW from the flat's upper end round through -X to its lower end.
    bore_arc = check(
        "bore arc",
        await adapter.add_arc(0.0, 0.0, flat_x, flat_half, flat_x, -flat_half),
    )
    bore_flat = check(
        "bore flat", await adapter.add_line(flat_x, -flat_half, flat_x, flat_half)
    )
    clock_line = check(
        "bore clock centreline",
        await adapter.add_centerline(-bore_radius, 0.0, flat_x, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("bore arc centre on origin", f"{bore_arc}.center", "origin", "coincident"),
        ("flat lower end joins arc", f"{bore_flat}.start", f"{bore_arc}.end", "coincident"),
        ("flat upper end joins arc", f"{bore_flat}.end", f"{bore_arc}.start", "coincident"),
        ("flat vertical", bore_flat, None, "vertical"),
        ("clock centreline horizontal", clock_line, None, "horizontal"),
        ("clock centreline starts on the arc", f"{clock_line}.start", bore_arc, "coincident"),
        (
            "clock centreline on the bore axis",
            f"{clock_line}.start",
            "origin",
            "horizontal_points",
        ),
        ("clock centreline ends on the flat", f"{clock_line}.end", bore_flat, "coincident"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    check(
        "bore diameter dim (driving)",
        await adapter.add_sketch_dimension(
            bore_arc, None, "diameter", bore_default_in * 25.4
        ),
    )
    # Record the manual driving dim: one display dim, driven by the "BoreDia"
    # global (the same link the inline equation used, now named + deferred).
    bore.record("BoreCutDia", '"BoreDia"')
    await dimension_between(
        adapter,
        f"{clock_line}.start",
        f"{clock_line}.end",
        "horizontal_distance",
        bore_flat_af_mm(DEFAULT_TEETH),
        "bore across-flat",
    )
    bore.record("BoreAF", '"BoreAF"')
    # Text inside the right angle the flat makes above the centreline; the
    # sheet repositions it.  Either reading is 90 deg.
    await add_angular_reference_dimension(
        adapter,
        bore_flat,
        clock_line,
        (flat_x - 0.3 * bore_radius, 0.4 * flat_half),
        "bore flat clock",
        expected_degrees=90.0,
    )
    bore.record("BoreFlatClock")
    await ensure_fully_defined(adapter, "bore D sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    bore_sketch = name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, bore_sketch)
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "BoreCut")
    bore_dim = f"BoreCutDia@{bore_sketch}"
    bore_before = read_dimension(adapter, bore_dim)
    if not (
        abs(bore_before - bore_default_in) < 1e-6
        or abs(bore_before - bore_default_in * 25.4) < 1e-4
    ):
        raise RuntimeError(f"{bore_dim} reads {bore_before!r}, not the bore diameter")
    bore_af_dim = f"BoreAF@{bore_sketch}"
    bore_af_before = read_dimension(adapter, bore_af_dim)
    if not (
        abs(bore_af_before - bore_af_default_in) < 1e-6
        or abs(bore_af_before - bore_af_default_in * 25.4) < 1e-4
    ):
        raise RuntimeError(
            f"{bore_af_dim} reads {bore_af_before!r}, not the bore across-flat"
        )
    mass = await adapter.get_mass_properties()
    bored_volume = float(mass.data.volume)
    expected_bored = expected_blank - bore_area_mm2(DEFAULT_TEETH) * FACE_WIDTH
    if abs(bored_volume - expected_bored) > 0.02 * expected_bored:
        raise RuntimeError(
            f"bored blank volume {bored_volume:.1f} mm^3, expected {expected_bored:.1f}"
        )
    _telemetry.success(f"bored blank volume {bored_volume:.1f} mm^3")

    # Model-owned inspection dimensions derive from the installed cutter profile;
    # their construction geometry is volume-neutral and does not drive the flanks.
    tooth_reference = await _author_tooth_thickness_reference(adapter)
    tooth_sketch = name_last_feature(adapter, TOOTH_REFERENCE_SKETCH)
    thickness_dim = f"ToothThickness@{tooth_sketch}"
    drive_jobs += tooth_reference.apply(adapter, tooth_sketch)

    # Functional MIN/MAX root envelope, not a purported origin-centred BRep floor.
    floor_default_in = floor_dia_in(DEFAULT_TEETH)
    await set_global(adapter, "FloorDia", f"{floor_default_in:.12g}", floor_default_in)
    floor_reference = await _author_gap_floor_reference(adapter)
    floor_sketch = name_last_feature(adapter, GAP_FLOOR_SKETCH)
    floor_dim = f"FloorDia@{floor_sketch}"
    drive_jobs += floor_reference.apply(adapter, floor_sketch)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "inspection sketches are neutral", expected_bored, 0.01 * expected_bored)

    await apply_material(adapter, MATERIAL)

    # ------------------------------------------------------------------
    # Configuration and regeneration determinism: switch through every
    # configuration, asserting instance count, volume bounds and monotonic
    # growth, then return to the first and require its volume to reproduce.
    # ------------------------------------------------------------------
    for name, teeth in CONFIGS[:-1]:
        check(
            f"create_configuration {name}",
            await adapter.create_configuration(
                CreateConfigurationParameters(
                    name=name, comment=f"{teeth}-tooth cone gear"
                )
            ),
        )
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    for name, teeth in CONFIGS:
        check(
            f"ToothCount = {teeth} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="ToothCount", expression=str(teeth), configuration=name
                )
            ),
        )
        check(
            f"BoreDia = {bore_dia_in(teeth):g} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="BoreDia",
                    expression=f"{bore_dia_in(teeth):g}",
                    configuration=name,
                )
            ),
        )
        bore_af_value = f"{bore_af_in(teeth):.12g}"
        check(
            f"BoreAF = {bore_af_value} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="BoreAF", expression=bore_af_value, configuration=name
                )
            ),
        )
        profile = stock_form_profile(teeth)
        for global_name, number in (
            ("Ra", profile.blank_radius_mm / MM_PER_IN),
            ("ToothThickness", profile.pitch_tooth_thickness_mm / MM_PER_IN),
            ("FloorDia", floor_dia_in(teeth)),
        ):
            check(
                f"{global_name} in {name}",
                await adapter.set_global_variable(
                    SetGlobalVariableParameters(
                        name=global_name, expression=f"{number:.17g}", configuration=name
                    )
                ),
            )
    _set_gap_floor_limits(adapter)

    pattern_axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    ).name
    count_dimensions: dict[int, str] = {}
    for configuration, teeth in CONFIGS:
        check(f"activate native row {configuration}", await adapter.set_active_configuration(configuration))
        profile = stock_form_profile(teeth)
        bored = (math.pi * profile.blank_radius_mm**2 - bore_area_mm2(teeth)) * FACE_WIDTH
        await volume_check(adapter, f"{configuration} bored blank", bored, 0.01 * bored)
        check(f"create {configuration} gap sketch", await adapter.create_sketch("Front"))
        curves = [
            await equation_curve(adapter, f"{configuration} {label}", x, y)
            for label, x, y in native_gap_segments(teeth)
        ]
        await ensure_fully_defined(
            adapter, f"{configuration} finite gap", fix_entities=curves,
            allow_fix_escalation=True,
        )
        check(f"exit {configuration} gap sketch", await adapter.exit_sketch())
        sketch_name, cut_name, pattern_name = tooth_features(teeth)
        name_last_feature(adapter, sketch_name)
        check(
            f"cut {configuration} finite gap",
            await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 1.0)),
        )
        name_last_feature(adapter, cut_name)
        single_cut = bored - profile.gap_area_mm2 * FACE_WIDTH
        removed = profile.gap_area_mm2 * FACE_WIDTH
        area_error = profile.gap_area_error_bound_mm2 * FACE_WIDTH
        await volume_check(
            adapter, f"{configuration} single stock gap", single_cut,
            0.01 * removed - area_error,
        )
        adapter._zoom_to_fit(adapter.currentModel)
        candidates = [[0.0, 0.0, FACE_WIDTH / 2.0]]
        for degrees in (-45.0, -90.0, -135.0, 135.0, 45.0):
            angle = math.radians(degrees)
            candidates.append([
                profile.blank_radius_mm * math.cos(angle),
                profile.blank_radius_mm * math.sin(angle), FACE_WIDTH / 2.0,
            ])
        for point in candidates:
            result = await adapter.circular_pattern_feature(CircularPatternParameters(
                axis_point=point, features=[cut_name], count=teeth, geometry_pattern=True,
            ))
            if result.is_success:
                break
        else:
            raise RuntimeError(f"{configuration}: no circular pattern axis selectable")
        name_last_feature(adapter, pattern_name)
        count_dimensions[teeth] = pattern_count_dimension(adapter, pattern_name, teeth)
        expected = _expected_configuration_volume(teeth)
        await volume_check(
            adapter, f"{configuration} complete stock pattern", expected,
            teeth * (0.01 * removed - area_error),
        )
        _restrict_to_configuration(adapter, teeth)
    blank_reference_geometry(adapter, ((pattern_axis, "AXIS"),))
    check("activate T120 for native PMI", await adapter.set_active_configuration("T120"))

    # Author before the existing 20-configuration regeneration sweep.  This is
    # the live regression gate for the model-owned symbol: a face-attached
    # symbol created in the 120T geometry makes every other configuration's
    # component feature rebuild with swFeatureErrorUnknown.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    # Establish the final path once while T120 is active. The per-configuration
    # sweep can then use IModelDoc2.Save3 directly; the adapter's in-place save
    # deliberately adds AvoidRebuildOnSave, which live probes proved does not
    # persist rebuilt inactive-configuration bodies.  The two authoring
    # sketches go hidden first, so no saved image or placing assembly draws
    # them.  This part saves itself rather than through save_part_and_images,
    # so it runs that helper's construction-geometry check here.
    _blank_reference_sketches(adapter)
    assert_reference_geometry_hidden(adapter, PART_NAME)
    OUT_SLDPRT.mkdir(parents=True, exist_ok=True)
    part_path = (OUT_SLDPRT / f"{PART_NAME}.SLDPRT").resolve()
    check(
        f"establish cone-gear part path -> {part_path}",
        await adapter.save_file(str(part_path)),
    )

    png_dir = OUT_PNG / PART_NAME
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {}
    volumes: dict[str, float] = {}
    for name, teeth in CONFIGS:
        activation = await adapter.set_active_configuration(name)
        check(f"activate {name}", activation)
        if not bool(activation.data.get("rebuilt")):
            raise RuntimeError(
                f"{name}: configuration activation did not rebuild cleanly"
            )
        # Config switches regenerate LAZILY: get_mass_properties can otherwise
        # sample a half-regenerated solid. Seen once in a from-empty build_all run
        # (T006 read 182.7 vs 108.3 -- a partially re-patterned state -- while
        # standalone it reads 108.2 deterministically). Force a full rebuild so the
        # gap pattern is fully applied for THIS config before any measurement.
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if not bool(model.ForceRebuild3(False)):
            raise RuntimeError(f"{name}: ForceRebuild3 reported failure")

        count = read_dimension(adapter, count_dimensions[teeth])
        if abs(count - teeth) > 1e-9:
            raise RuntimeError(
                f"{name}: pattern instance count reads {count:g}, expected {teeth}"
            )
        _telemetry.success(f"{name}: pattern count = {count:g}")

        volume, observation, issues = await _configuration_topology(
            adapter,
            name,
            teeth,
            phase="pre-save",
        )
        if issues:
            raise RuntimeError(f"{observation}; issues={issues!r}")
        volumes[name] = volume
        profile = stock_form_profile(teeth)

        # OD check via the equation-driven diameter dimension (selection-free;
        # the measure tool's point selection proved unreliable on the
        # patterned gear -- it kept grabbing gap-wall faces).
        od = read_dimension(adapter, od_dim)
        expected_od = 2.0 * profile.blank_radius_mm / MM_PER_IN * dim_unit
        if abs(od - expected_od) > 1e-4 * expected_od:
            raise RuntimeError(
                f"{name}: {od_dim} reads {od:g}, expected {expected_od:g}"
            )
        _telemetry.success(f"{name}: blank diameter dim = {od:g}")
        # The native inspection value is derived from the actual core profile.
        thickness = read_dimension(adapter, thickness_dim)
        expected_thickness = profile.pitch_tooth_thickness_mm / MM_PER_IN * dim_unit
        if abs(thickness - expected_thickness) > 1e-6 * expected_thickness:
            raise RuntimeError(
                f"{name}: {thickness_dim} reads {thickness:g}, expected "
                f"{expected_thickness:g} -- ToothThickness did not regenerate"
            )
        _telemetry.success(f"{name}: tooth thickness dim = {thickness:g}")
        # The gap-floor dimension: its nominal follows FloorDia and its LIMIT
        # band is this configuration's own.
        floor = read_dimension(adapter, floor_dim)
        expected_floor = floor_dia_in(teeth) * dim_unit
        if abs(floor - expected_floor) > 1e-6 * expected_floor:
            raise RuntimeError(
                f"{name}: {floor_dim} reads {floor:g}, expected "
                f"{expected_floor:g} -- FloorDia did not regenerate"
            )
        _assert_gap_floor_limits(adapter, name, teeth)
        # The D-bore's across-flat follows its land's flat (BoreAF global).
        bore_af = read_dimension(adapter, bore_af_dim)
        expected_af = bore_af_in(teeth) * dim_unit
        if abs(bore_af - expected_af) > 1e-6 * expected_af:
            raise RuntimeError(
                f"{name}: {bore_af_dim} reads {bore_af:g}, expected "
                f"{expected_af:g} -- BoreAF did not regenerate"
            )
        _telemetry.success(f"{name}: bore across-flat dim = {bore_af:g}")

        img = (png_dir / f"{PART_NAME}_{name}_isometric.png").resolve()
        check(
            f"export_image {name}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": "isometric",
                }
            ),
        )
        artefacts[f"iso_{name}"] = str(img)

    ordered = [volumes[name] for name, _ in CONFIGS]
    if not all(a < b for a, b in zip(ordered, ordered[1:], strict=False)):
        raise RuntimeError(f"volumes not monotonically increasing: {volumes}")
    _telemetry.success(f"volumes monotonic: {ordered}")


    # Determinism: revisit the first configuration after the full cycle.
    first_name, _ = CONFIGS[0]
    check(f"re-activate {first_name}", await adapter.set_active_configuration(first_name))
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"re-check {first_name}: {mass.error}")
    revisit = float(mass.data.volume)
    if abs(revisit - volumes[first_name]) > abs(volumes[first_name]) * 1e-6:
        raise RuntimeError(
            f"{first_name} volume drifted on revisit: {revisit} vs "
            f"{volumes[first_name]} -- regeneration is not deterministic"
        )
    _telemetry.success(f"{first_name} volume reproduced on revisit: {revisit:.1f} mm^3")

    check("activate T120 for saved views", await adapter.set_active_configuration("T120"))
    grouped_spec = _config.parts(PART_NAME)
    part_number = str(grouped_spec.get("number", ""))
    description = str(grouped_spec.get("description", "")).strip()
    apply_grouped_bom_properties(
        adapter,
        [name for name, _teeth in CONFIGS],
        part_number=part_number,
        description=description,
    )
    apply_custom_properties(adapter, {"Description": description})
    await report_mass_properties(adapter)

    # Mark the manufacturing model dimensions.  Each carries a band
    # derived above (FloorDia's per-configuration LIMIT was set before the
    # sweep); their decimal places live on the model and each configuration
    # sheet only imports and arranges them.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    set_dimension_bilateral_tolerance(
        adapter, "BlankProfile", "BlankDia", *deviations(BLANK_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "Blank", "FaceWidth", *deviations(FACE_WIDTH_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreCutDia", *deviations(BORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreAF", *deviations(BORE_AF_BAND)
    )
    set_dimension_symmetric_angular_tolerance(
        adapter,
        "BoreProfile",
        "BoreFlatClock",
        FLAT_CLOCK_TOLERANCE_DEG,
        require_driven=True,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        TOOTH_REFERENCE_SKETCH,
        "ToothThickness",
        *deviations(TOOTH_THICKNESS_BAND),
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": gear_data(DEFAULT_TEETH),
            "Manufacturing Notes": drawing_notes(DEFAULT_TEETH),
            "Cutter Profile": custom_cutter_detail(),
        },
    )
    _apply_configuration_properties(
        adapter,
        "Default",
        {
            "Gear Data": "UNPLACED SEED BLANK - NOT A FINISHED FAMILY GEAR",
            "Manufacturing Notes": "REFERENCE BLANK ONLY.",
            "Cutter Profile": "NO CUTTER FEATURES IN UNPLACED DEFAULT.",
        },
    )
    for configuration, teeth in CONFIGS:
        _apply_configuration_properties(
            adapter,
            configuration,
            {
                # The title block's DWG. NO. reads $PRPSHEET:"Number", and a
                # configuration property wins over the file one, so each sheet
                # names its own gear (Fable, 2026-09-23: twenty sheets carried
                # one number).  The grouped BOM keeps MHA-DT-003 (AlternateName).
                "Number": configuration_number(part_number, teeth),
                "Gear Data": gear_data(teeth),
                "Manufacturing Notes": drawing_notes(teeth),
                "Cutter Profile": custom_cutter_detail() if teeth == 6 else gear_data(teeth),
                "Material Specification": material_specification(teeth),
            },
        )
    artefacts.update(await save_part_and_images(adapter, PART_NAME))
    part_path = artefacts["part"]
    # Each T-configuration's derived "<T> Simplified" (teeth suppressed) is
    # what the drive-train drawing's small line views print; it inherits the
    # grouped BOM identity and the per-configuration properties set above.
    # Only the T-configurations are derived: Default is never placed, and on
    # farm build 2 of #1102 it read the teeth suppressed beside its derived
    # child while every T parent kept them (the features were authored with
    # T120 active, Default a bystander). It is derived on the saved part
    # reopened from disk (on this authoring document the derivation raised a
    # modal dialog, c85a21ec4), which is then finalized in place: every
    # configuration activated and force-rebuilt (the no-switch rebuild-all
    # verbs left the T00x tooth gaps faulted, cg-fx1), marked for
    # rebuild-save, and saved in one Save3.
    placed = [name for name, _teeth in CONFIGS]
    await derive_simplified_on_saved_part(
        adapter, PART_NAME, SIMPLIFIED_FEATURES_BY_CONFIGURATION, part_path, placed
    )
    check("reopen saved cone-gear", await adapter.open_model(part_path))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    await assert_saved_configuration_topology(adapter, phase="reopened")
    assert_simplified_configurations(
        adapter, PART_NAME, SIMPLIFIED_FEATURES_BY_CONFIGURATION, placed
    )

    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
