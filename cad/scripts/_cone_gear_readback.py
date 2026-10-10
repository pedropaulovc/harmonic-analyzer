"""Saved cone-family configuration topology validation shared with its drawing.

Keeps the established activation/rebuild and native topology checks separate
from part authoring, simplified-configuration derivation and saving so those
operations do not enter drawing cache keys.
"""

from __future__ import annotations

import math
import time
from typing import Any

import _telemetry
from _check import check
from _com import _com_invoke, _early_bound, _read_member
from _cone_gear_geometry import R_CLEAR_MM, bore_area_mm2
from _drawing_marks import _named_dimension
from _fit_deviations import deviations
from dt_cone_gear_spec import (
    BORE_DIA_BAND,
    CONFIGS,
    CONFIGURATION_TEETH,
    FACE_WIDTH,
    GAP_FLOOR_SKETCH,
    MACHINED_WEB_TARGET_MM,
    MM_PER_IN,
    TOOTH_REFERENCE_SKETCH,
    WEB_EXCEPTIONS_MM,
    blank_dia_band,
    bore_dia_mm,
    floor_limits_mm,
    floor_radius_max_mm,
    floor_radius_min_mm,
    gap_floor_deviations_mm,
    stock_form_profile,
    tooth_features,
    tooth_thickness_band,
)

_TOL_BILAT = 2  # swTolType_e.swTolBILAT
_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT


# The two bilateral bands T006 overrides (the named exception); every other
# configuration carries the shared band.
_BANDED_DIMENSIONS = (
    ("BlankProfile", "BlankDia", blank_dia_band),
    (TOOTH_REFERENCE_SKETCH, "ToothThickness", tooth_thickness_band),
)


def _gap_floor_tolerance(adapter: Any) -> Any:
    _display, dimension = _named_dimension(adapter, GAP_FLOOR_SKETCH, "FloorDia")
    return _early_bound(dimension.Tolerance, "IDimensionTolerance")


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


def _assert_configuration_bands(adapter: Any, configuration: str, teeth: int) -> None:
    """Read FloorDia, BlankDia and ToothThickness back in the active configuration."""
    _assert_gap_floor_limits(adapter, configuration, teeth)
    for feature, name, band_for in _BANDED_DIMENSIONS:
        _display, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        kind = int(tolerance.Type)
        observed = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        band = band_for(teeth)
        expected = deviations(band)
        if kind != _TOL_BILAT or any(abs(o - e) > 1e-6 for o, e in zip(observed, expected)):
            raise RuntimeError(
                f"{configuration}: {name} tolerance reads type {kind} {observed} mm, "
                f"expected bilateral {expected} mm"
            )
    _telemetry.success(
        f"{configuration}: blank {blank_dia_band(teeth)} and tooth-thickness "
        f"{tooth_thickness_band(teeth)} bands"
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


def _exit_face(body: Any) -> Any:
    """Return the gear's planar end face farther from the Front sketch plane.

    The gap cuts are sketched on Front and extruded through, so this is the
    face every cut exits: a cut that stopped short leaves it unbroken.
    """
    caps: list[tuple[float, Any]] = []
    for face in _com_invoke(body, "IBody2", "GetFaces") or ():
        box = tuple(float(v) * 1000.0 for v in (_com_invoke(face, "IFace2", "GetBox") or ()))
        if len(box) == 6 and abs(box[5] - box[2]) < 0.01:
            caps.append((box[2], face))
    if len(caps) != 2 or abs(abs(caps[0][0] - caps[1][0]) - FACE_WIDTH) > 0.01:
        raise RuntimeError(
            f"expected two end faces {FACE_WIDTH} apart, found z={[z for z, _ in caps]}"
        )
    return max(caps, key=lambda cap: abs(cap[0]))[1]


def _native_root_envelope_mm(body: Any, *, teeth: int) -> tuple[float, float, int]:
    """Read each root arc on the exit face, including its radial extrema.

    Endpoint pairs identify the actual persisted root edges, not a presumed
    circle at T+root. The edge's closest point to the gear axis supplies MIN;
    endpoints and the symmetric arc midpoint supply MAX. Rotated copies use
    the physical N and the explicit pi/N gap clock. The cuts are straight
    extrusions, so the exit face carries every gap's root once; each edge
    costs two raw round trips (GetCurve, then GetCurveParams2, which reads
    the curve GetCurve generated) and each root two closest-point reads.
    """
    profile = stock_form_profile(teeth)
    root = next(segment for segment in profile.native_segments(
        unit_scale=1.0, clearance_radius_mm=R_CLEAR_MM
    ) if segment.kind == "root_arc")
    canonical = (root.point(0.0), root.point(0.5), root.point(1.0))
    gaps = []
    for index in range(teeth):
        angle = (2 * index + 1) * math.pi / teeth
        cosine, sine = math.cos(angle), math.sin(angle)
        gaps.append(tuple(
            (cosine * x - sine * y, sine * x + cosine * y) for x, y in canonical
        ))
    roots: list[tuple[float, float]] = []
    for edge in _com_invoke(_exit_face(body), "IFace2", "GetEdges") or ():
        if _com_invoke(edge, "IEdge", "GetCurve") is None:
            continue
        params = tuple(float(v) * 1000.0 for v in
            (_com_invoke(edge, "IEdge", "GetCurveParams2") or ())[:6])
        if len(params) < 6:
            raise RuntimeError(f"T{teeth:03d}: unreadable native exit-face edge")
        start, end = params[:3], params[3:6]
        for first, midpoint, last in gaps:
            if not any(
                max(math.dist(start[:2], a), math.dist(end[:2], b)) < 0.002
                for a, b in ((first, last), (last, first))
            ):
                continue
            closest = tuple(float(v) * 1000.0 for v in _com_invoke(
                edge, "IEdge", "GetClosestPointOn", 0.0, 0.0, start[2] / 1000.0
            ))
            native_midpoint = tuple(float(v) * 1000.0 for v in _com_invoke(
                edge, "IEdge", "GetClosestPointOn",
                midpoint[0] / 1000.0, midpoint[1] / 1000.0, start[2] / 1000.0,
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
    if len(roots) != teeth:
        raise RuntimeError(
            f"T{teeth:03d}: {len(roots)} native root arcs on the exit face for {teeth} teeth"
        )
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

    from solidworks_mcp.adapters.com_variant import null_variant

    if str(_active_configuration(model).Name) != configuration:
        raise RuntimeError(f"{configuration}: not active for the definition state")
    feature_states: dict[str, tuple[bool, int, bool]] = {}
    for name in tooth_features(int(configuration[1:])):
        raw = part.FeatureByName(name)
        if raw is None:
            raise RuntimeError(f"{configuration}: diagnostic feature {name} missing")
        feature = _early_bound(raw, "IFeature")
        states = feature.IsSuppressed2(1, null_variant())
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
    measure_roots: bool,
) -> tuple[float, str, tuple[str, ...]]:
    """Measure one configuration's real pattern and solid-body topology.

    ``measure_roots`` adds the native root-arc envelope and bore-web gate,
    which costs a COM round trip per exit-face edge; the build reads it once,
    on the saved part reopened from disk.
    """
    from solidworks_mcp.adapters.com_variant import null_variant

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    active = _activate_configuration(model, configuration)
    part = _early_bound(model, "IPartDoc")
    pattern_name = tooth_features(teeth)[2]
    raw_pattern = part.FeatureByName(pattern_name)
    if raw_pattern is None:
        raise RuntimeError(f"{configuration}: {pattern_name} is missing")
    pattern = _early_bound(raw_pattern, "IFeature")
    # Active-configuration reads only: IsSuppressed2(3, [name]) answers None
    # for every feature (7e88be269 farm log), so it cannot fail a check.
    states = pattern.IsSuppressed2(1, null_variant())
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
    # Every row is read in the ACTIVE configuration (IsSuppressed2(1, null)),
    # the way the suppression sweep set and verified it.
    if str(_active_configuration(model).Name) != configuration:
        raise RuntimeError(f"{configuration}: not active for the suppression audit")
    for row_teeth in CONFIGURATION_TEETH:
        for feature_name in tooth_features(row_teeth):
            raw_feature = part.FeatureByName(feature_name)
            if raw_feature is None:
                feature_issues.append(f"missing native feature {feature_name}")
                continue
            feature = _early_bound(raw_feature, "IFeature")
            answer = feature.IsSuppressed2(1, null_variant())
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
    if measure_roots and len(bodies) == 1:
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


def _failure_site(exc: BaseException) -> str:
    """Name the deepest line of this module the exception passed through.

    A raw COM error (DISP_E_MEMBERNOTFOUND at f68549253) carries no member
    name; the source line of the call that raised does."""
    import traceback

    frames = [
        frame for frame in traceback.extract_tb(exc.__traceback__)
        if frame.filename == __file__
    ]
    if not frames:
        return type(exc).__name__
    frame = frames[-1]
    return f"{type(exc).__name__} at line {frame.lineno} in {frame.name}: {frame.line}"


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
                measure_roots=True,
            )
            # Each configuration's own tolerance bands, read with it active.
            _assert_configuration_bands(adapter, configuration, teeth)
        except Exception as exc:
            failures.append(f"{configuration}: {_failure_site(exc)}: {exc}")
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
