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
from _common import _early_bound, _read_member, check
from _cone_gear_geometry import bore_area_mm2, cone_facts, cone_gap_area_in_disc
from dt_cone_gear_spec import (
    BORE_DIA_BAND,
    CONFIGS,
    FACE_WIDTH,
    TOOTH_GAP_CUT,
    TOOTH_GAP_PROFILE,
    TOOTH_PATTERN_FEATURE,
    bore_dia_mm,
    floor_radius_mm,
    floor_tmin,
)
from involute_gear import DP, PA_DEG


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
    facts = cone_facts(teeth)
    radius_mm = facts["Ra"] * 25.4
    blank_mm3 = math.pi * radius_mm**2 * FACE_WIDTH
    bore_mm3 = bore_area_mm2(teeth) * FACE_WIDTH
    return (
        blank_mm3
        - teeth * cone_gap_area_in_disc(teeth) * 25.4**2 * FACE_WIDTH
        - bore_mm3
    )


def _native_minimum_chord_floor_radius_mm(
    body: Any, *, teeth: int
) -> tuple[float, int]:
    """Measure the minimum radius of the planar BREP root-chord edges.

    Root candidates lie on one end plane and have both endpoints on the
    flank-foot circle (the base circle unless the floor is raised).  This
    topology filter excludes axial edges
    and the vertex-free cylindrical bore.  ``IEdge.GetClosestPointOn`` then
    measures the persisted edge itself without assuming the equation curve was
    simplified to an analytic line, using screen-space selection, approximate
    boxes, or substituting a volume proxy.
    """
    pressure_angle = math.radians(PA_DEG)
    foot_radius_mm = (teeth / DP * math.cos(pressure_angle) / 2.0 * 25.4) * math.hypot(
        1.0, floor_tmin(teeth)
    )
    candidates: list[float] = []
    for raw_edge in tuple(_early_bound(body, "IBody2").GetEdges() or ()):
        edge = _early_bound(raw_edge, "IEdge")
        raw_start = edge.GetStartVertex()
        raw_end = edge.GetEndVertex()
        if raw_start is None or raw_end is None:
            continue
        start = tuple(
            float(value) * 1000.0
            for value in _early_bound(raw_start, "IVertex").GetPoint()
        )
        end = tuple(
            float(value) * 1000.0
            for value in _early_bound(raw_end, "IVertex").GetPoint()
        )
        if abs(start[2] - end[2]) > 1e-6:
            continue
        start_radius = math.hypot(start[0], start[1])
        end_radius = math.hypot(end[0], end[1])
        if (
            max(
                abs(start_radius - foot_radius_mm),
                abs(end_radius - foot_radius_mm),
            )
            > 0.002
        ):
            continue
        closest = tuple(
            float(value) * 1000.0
            for value in edge.GetClosestPointOn(
                0.0,
                0.0,
                start[2] / 1000.0,
            )
        )
        if len(closest) < 3:
            raise RuntimeError(
                f"T{teeth:03d}: unreadable root-edge closest point {closest!r}"
            )
        candidates.append(math.hypot(closest[0], closest[1]))
    if not candidates:
        raise RuntimeError(f"T{teeth:03d}: no planar gap-floor edge in solid BREP")
    return min(candidates), len(candidates)


def _configuration_definition_state(
    adapter: Any, configuration: str, *, phase: str
) -> None:
    """Log the equation, seed-feature and pattern-definition persistence state."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    equation_manager = _early_bound(model.GetEquationMgr(), "IEquationMgr")
    wanted = {"ToothCount", "BoreDia", "BoreAF", "Rb", "Ra", "Rf", "XMax"}
    equations: dict[str, tuple[str, float]] = {}
    count = int(_read_member(equation_manager, "GetCount") or 0)
    for index in range(count):
        equation = str(equation_manager.Equation(index) or "")
        left, _, _right = equation.partition("=")
        name = left.strip().strip('"')
        if name in wanted:
            equations[name] = (equation, float(equation_manager.Value(index)))

    feature_states: dict[str, tuple[bool, int, bool]] = {}
    for name in (TOOTH_GAP_PROFILE, TOOTH_GAP_CUT, TOOTH_PATTERN_FEATURE):
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

    pattern = _early_bound(part.FeatureByName(TOOTH_PATTERN_FEATURE), "IFeature")
    definition = _early_bound(pattern.GetDefinition(), "ICircularPatternFeatureData")
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
    raw_pattern = part.FeatureByName(TOOTH_PATTERN_FEATURE)
    if raw_pattern is None:
        raise RuntimeError(f"{configuration}: {TOOTH_PATTERN_FEATURE} is missing")
    pattern = _early_bound(raw_pattern, "IFeature")
    states = pattern.IsSuppressed2(3, [configuration])
    if not isinstance(states, (list, tuple)):
        states = (states,)
    suppressed = len(states) != 1 or bool(states[0])
    definition = _early_bound(pattern.GetDefinition(), "ICircularPatternFeatureData")
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
        int(_early_bound(bodies[0], "IBody2").GetFaceCount()) if len(bodies) == 1 else 0
    )
    root_observation = ""
    root_issues: list[str] = []
    if teeth == CONFIGS[0][1] and len(bodies) == 1:
        native_root, chord_edges = _native_minimum_chord_floor_radius_mm(
            bodies[0], teeth=teeth
        )
        expected_root = floor_radius_mm(teeth)
        maximum_bore_radius = (bore_dia_mm(teeth) + BORE_DIA_BAND[0]) / 2.0
        minimum_web = native_root - maximum_bore_radius
        root_observation = (
            f", native_chord_floor_radius={native_root:.6f}, "
            f"equivalent_diameter={2.0 * native_root:.6f}, "
            f"expected_chord_floor_radius={expected_root:.6f}, "
            f"minimum_bore_web={minimum_web:.6f}, "
            f"chord_edges={chord_edges}"
        )
        if abs(native_root - expected_root) > 0.002:
            root_issues.append(
                f"native chord-floor radius {native_root:.6f} differs from "
                f"source equation {expected_root:.6f}"
            )
        if chord_edges < teeth:
            root_issues.append(
                f"native chord-edge count {chord_edges} < tooth count {teeth}"
            )
        if minimum_web <= 0.0:
            root_issues.append(
                f"native minimum bore web is nonpositive: {minimum_web:.6f}"
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
        f"{TOOTH_PATTERN_FEATURE} instances={instances}, "
        f"suppressed={suppressed}, error={error_code}, warning={is_warning}, "
        f"bodies={len(bodies)}, faces={face_count}, volume={volume:.1f}, "
        f"expected={expected:.1f}{root_observation}"
    )
    _telemetry.info(f"{phase} cone-gear topology: {observation}")
    issues: list[str] = []
    issues.extend(root_issues)
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
    if abs(volume - expected) > 0.01 * expected:
        issues.append(f"volume {volume:.1f} outside 1% of {expected:.1f}")
    if configuration in {CONFIGS[0][0], CONFIGS[-1][0]}:
        _configuration_definition_state(adapter, configuration, phase=phase)
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
