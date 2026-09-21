r"""Reproduction script: cone gear (book ch. 12, pp. 16-21) -- parametric prototype.

One part, configuration-driven tooth count across the full T006..T120-by-six
family. All configuration-varying geometry is equation-driven so a switch
regenerates the gear from ``ToothCount``/``DP``/``PA`` alone:

* Equation-manager globals carry the involute math (base/tip radii in
  INCHES, involute parameter span, tooth-gap angles). Two parser facts
  probed live on SW 2026: the equation manager evaluates trig in DEGREES
  (``atn`` returns degrees too), and ``CreateEquationSpline2`` expressions
  evaluate lengths in DOCUMENT units (the configured part template is IPS),
  NOT metres -- inch-valued globals keep the two parsers consistent, and a
  blank-volume self-check right after the first extrude fails fast if the
  template's units ever change.
* The blank is an EXTRUDED disc at tip radius ``Ra`` (origin-snapped
  circle, driving diameter dim equation-linked to ``2*Ra``) -- NOT a
  revolve: on SW 2026 a dimension-driven cut through a revolved body
  freezes at its creation-time profile size (any later change of the
  cut's dimension makes the cut solve to nothing; probed live, see the
  blank section comment). The six-entity tooth-gap profile (two involute
  flanks, base chord, two radial extensions, outer clearance arc) is all
  ``CreateEquationSpline2`` curves referencing the globals; parameter
  ranges are kept numeric (t in [0,1]) so only the expression parser
  needs global support.
* One gap is cut through the blank, then circular-patterned about the gear
  axis; the pattern instance count is equation-linked to ``ToothCount``.

Tooth-gap profile derivation (standard involute, polar form): a point of the
involute of base radius ``Rb`` at parameter t sits at radius ``Rb*sqrt(1+t^2)``
and polar angle ``phi - atan(t)`` where ``phi`` is the rolling angle offset.
With ``Delta = pi/(2N) + inv(PA)`` (half tooth angular thickness at the base
circle, ``inv`` the involute function), the gap between tooth 0 (centred on
+X) and tooth 1 is bounded below by tooth 0's upper flank (the mirrored
involute starting at angle ``+Delta``) and above by tooth 1's lower flank
(the involute starting at ``Gamma - Delta``, ``Gamma = 2*pi/N``).

Prototype scope notes:

* **Configured bore, no keyway** (Appendix C #7 resolution): the shaft steps
  down toward the tip and each bore matches its seat: 3/8" for T024..T120,
  1/4" for T018, 1/8" for T012, and the approved 1/16" journal at T006.
  The bore circle is origin-centred with a DRIVING diameter dimension linked
  to the configured ``BoreDia`` global.  The p.21 macro shows solder at the
  smallest gears; no evidence supports a key, pin, set screw, or hub.
* Circular tooth thickness is a native DRIVING dimension in a construction
  authoring sketch.  Its asymmetric band is derived from the configured
  ``gear_mesh`` backlash; it is not a drawing/model reference-status dimension.
* Root geometry is simplified: the gap floor is the chord at the base circle,
  not the true root circle + trochoid fillet (for N >= 96 the base circle is
  slightly inside root; the 6T gear is severely undercut at standard
  proportions anyway).

Dimensions: cad/DIMENSIONS.md "Chapter 12" -- DP 49.82 / PA 14.5 deg, face
width 6.5 mm (M6.7 mesh packing; annotated 7 is inconsistent with the drum
grid), tooth counts 6k.

Layout: gear axis = Z through the origin, blank extruded +Z from the Front
plane (z = 0..7 mm).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_gear.py
"""

from __future__ import annotations

import math
import sys
import time
from typing import Any

import _config
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_pmi import author_part_pmi
import cone_gear_shaft_spec
from cone_gear_notes import DRAWING_NOTES, gear_data, tooth_thickness_band
from cone_gear_spec import (
    CONFIGURATION_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    SURFACE_FINISHES,
    TOOTH_THICKNESS,
    bore_dia_mm,
    material_specification,
)
from _common import (
    OUT_PNG,
    OUT_SLDPRT,
    SketchDims,
    _early_bound,
    _read_member,
    anchor_point_to_origin,
    apply_custom_properties,
    apply_material,
    check,
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
# NOTE: this module keeps its OWN validating ``set_global`` (below) -- it
# round-trips every gear-math global through the SW equation parser to assert
# the trig/sqr/pi dialect, which the plain ``_common.set_global`` does not do.
# So we deliberately do NOT import ``_common.set_global`` (it would be shadowed
# by the local def anyway). The self-naming helpers above drive only the two
# ORDINARY circle dims (blank OD, bore); the involute tooth-gap profile is left
# undimensioned so it stays free to re-solve from the globals and mesh.

import _telemetry

PART_NAME = "cone-gear"
MATERIAL = "Brass"  # ch. 13 text: polished brass gear stock; cone set matches
# The four smallest tip gears read "more yellow ... a harder metal" (ch.12 p.21)
# -- a high-zinc yellow metal (Muntz/manganese bronze). That muntz_yellow tint is
# applied at the ASSEMBLY-COMPONENT level on the four tip-gear instances (see
# build_drive_train_assembly.py): a per-config PART colour loses to the brass
# material appearance and a body colour bleeds across all 20 configs, whereas a
# component appearance is per-instance and is what the render pipeline reads
# (export_models comp_rgb -> IComponent2.GetMaterialPropertyValues2). The part
# itself stays uniformly brass. See cad/config/materials.yaml.

DP = _config.machine("gear_train", "diametral_pitch")  # cad/config/machine.yaml (DIMENSIONS.md ch12)
PA_DEG = 14.5  # pressure angle, period-typical assumption (low)
# M6.7: the exact-tracking mesh (assembly docstring) fixes the seat
# pitch along the shaft at Z_PITCH*cos(12.52 deg) = 6.889 mm (the finer
# DP 49.82 module gives a shallower incline); face 6.5 leaves 0.39 air,
# and the photo's 7 mm callout still cannot hold -- the annotated cone
# figures stay inconsistent with the drum grid, see DIMENSIONS.md ch. 12.
FACE_WIDTH = 6.5  # mm, derived (photo callout 7, see above)

# Cut clearance radius (inches -- document units, see module docstring)
# beyond the largest tip radius (120T OD/2 = 2.033") so the gap profile
# always closes outside the blank.
R_CLEAR_IN = 60.0 / 25.4

PI_LIT = "3.14159265358979"  # literal pi for equation-manager expressions

# The full cone set: 20 gears, 6..120 teeth step 6 (DIMENSIONS.md ch. 12).
CONFIGS = tuple((f"T{n:03d}", n) for n in CONFIGURATION_TEETH)
DEFAULT_TEETH = CONFIGURATION_TEETH[-1]
TOOTH_GAP_PROFILE = "ToothGapProfile"
TOOTH_GAP_CUT = "ToothGapCut"
TOOTH_PATTERN_FEATURE = "ToothGapPattern"

# Model-owned bands, derived live from their named fit inputs.  Bands use the
# repository's native ``(upper, lower)`` order.
_BORE_CLEARANCE_MIN, _BORE_CLEARANCE_MAX = (
    float(value)
    for value in _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_LAND_UPPER, _LAND_LOWER = cone_gear_shaft_spec.SECTION_DIA_BAND
BORE_DIA_BAND = (
    _LAND_LOWER + _BORE_CLEARANCE_MAX,
    _LAND_UPPER + _BORE_CLEARANCE_MIN,
)
BACKLASH_MM = tuple(float(value) for value in _config.fit("gear_mesh", "backlash_mm"))
TOOTH_THICKNESS_BAND = tooth_thickness_band(BACKLASH_MM)


def bore_dia_in(teeth: int) -> float:
    """Configured bore diameter in inches, matching the stepped-shaft seat."""
    return bore_dia_mm(teeth) / 25.4


def _as_construction(adapter, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def gear_facts(teeth: int, dp: float = DP, pa_deg: float = PA_DEG) -> dict[str, float]:
    """Python mirror of the equation-manager globals (lengths in inches)."""
    pa = math.radians(pa_deg)
    rb = teeth / dp * math.cos(pa) / 2.0
    ra = (teeth + 2.0) / dp / 2.0
    tmax = math.sqrt((ra / rb) ** 2 - 1.0)
    delta = math.pi / (2.0 * teeth) + math.tan(pa) - pa
    gamma = 2.0 * math.pi / teeth
    return {
        "PArad": pa,
        "Rb": rb,
        "Ra": ra,
        "Tmax": tmax,
        "Delta": delta,
        "Gamma": gamma,
        "ThetaL": math.atan(tmax) - tmax + delta,
        "ThetaU": tmax - math.atan(tmax) - delta + gamma,
    }


def gap_area_in_disc(
    teeth: int, samples: int = 2000, dp: float = DP, pa_deg: float = PA_DEG
) -> float:
    """Exact in-blank area of one tooth gap (in^2), by Green's theorem.

    Boundary: lower flank A1->B1, blank-rim arc B1->B2 at ``Ra`` (the
    beyond-rim part of the cut profile removes nothing), upper flank B2->A2
    reversed, base chord A2->A1 -- the same parametrisations as the live
    equation curves, so the expected volume validates the involute shape,
    not just that "some" cut happened.
    """
    f = gear_facts(teeth, dp, pa_deg)
    rb, ra = f["Rb"], f["Ra"]
    tmax, delta, gamma = f["Tmax"], f["Delta"], f["Gamma"]
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank (mirrored involute)
        t = tmax * i / samples
        ph = t - delta
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (t * math.cos(ph) - math.sin(ph)),
        ))
    for i in range(1, samples + 1):  # rim arc ThetaL -> ThetaU
        th = f["ThetaL"] + (f["ThetaU"] - f["ThetaL"]) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank, reversed
        t = tmax * (samples - i) / samples
        ph = t - delta + gamma
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (math.sin(ph) - t * math.cos(ph)),
        ))
    for i in range(1, samples):  # base chord A2 -> A1
        s = i / samples
        pts.append((
            rb * ((1 - s) * math.cos(gamma - delta) + s * math.cos(delta)),
            rb * ((1 - s) * math.sin(gamma - delta) + s * math.sin(delta)),
        ))
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


async def set_global_read(adapter: Any, name: str, expression: str) -> float:
    """Upsert a global variable and return the value SolidWorks evaluated."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=expression)
    )
    data = check(f"global {name} = {expression}", res)
    value = data.get("value")
    if value is None:
        raise RuntimeError(f"global {name}: no evaluated value returned")
    return float(value)


async def set_global(adapter: Any, name: str, expression: str, expected: float) -> None:
    """Upsert a global variable and assert SolidWorks evaluated it correctly.

    The value round-trip is the live test of the equation parser (trig in
    DEGREES -- probed live, see ``build`` -- ``sqr`` = square root, literal-pi
    arithmetic); a mismatch means the expression dialect is wrong and every
    downstream curve would be silently bogus.
    """
    value = await set_global_read(adapter, name, expression)
    tol = max(1e-9, abs(expected) * 1e-6)
    if abs(value - expected) > tol:
        raise RuntimeError(
            f"global {name}: SolidWorks evaluated {value!r}, expected "
            f"{expected:.9g} -- equation-parser dialect mismatch"
        )


async def equation_curve(
    adapter: Any, label: str, x_expr: str, y_expr: str
) -> str:
    """Add a parametric equation curve over t in [0, 1]; return its entity ID."""
    from solidworks_mcp.adapters.base import CreateEquationCurveParameters

    res = await adapter.create_equation_driven_curve(
        CreateEquationCurveParameters(
            x_expression=x_expr,
            y_expression=y_expr,
            range_start="0",
            range_end="1",
        )
    )
    return check(f"curve {label}", res)


def pattern_count_dimension(adapter: Any, feature_name: str, expected: float) -> str:
    """Find the pattern's instance-count dimension name (``D?@<feature>``).

    The circular-pattern dimension layout (which of D1/D2 is the count vs
    the angle) is not documented stably across releases, so probe by value:
    the count dimension is the one reading ``expected`` (the seed count must
    differ from the 360-degree angle for this to be unambiguous).
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for dim in ("D1", "D2", "D3", "D4"):
        full = f"{dim}@{feature_name}"
        param = adapter._attempt(lambda f=full: model.Parameter(f), default=None)
        if param is None:
            continue
        try:
            value = float(_read_member(param, "Value"))
        except (TypeError, ValueError):
            continue
        _telemetry.debug(f"{full} reads {value:g}")
        if abs(value - expected) < 1e-9:
            return full
    raise RuntimeError(
        f"no dimension of {feature_name} reads {expected:g} -- cannot link "
        "the instance count to ToothCount"
    )


def read_dimension(adapter: Any, full_name: str) -> float:
    """Read a dimension's value in the active configuration."""
    param = adapter._attempt(
        lambda: adapter.currentModel.Parameter(full_name), default=None
    )
    if param is None:
        raise RuntimeError(f"cannot read dimension {full_name}")
    return float(_read_member(param, "Value"))


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
    facts = gear_facts(teeth)
    radius_mm = facts["Ra"] * 25.4
    blank_mm3 = math.pi * radius_mm**2 * FACE_WIDTH
    bore_mm3 = math.pi * (bore_dia_in(teeth) * 12.7) ** 2 * FACE_WIDTH
    return (
        blank_mm3
        - teeth * gap_area_in_disc(teeth) * 25.4**2 * FACE_WIDTH
        - bore_mm3
    )


def _configuration_definition_state(
    adapter: Any, configuration: str, *, phase: str
) -> None:
    """Log the equation, seed-feature and pattern-definition persistence state."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    equation_manager = _early_bound(model.GetEquationMgr(), "IEquationMgr")
    wanted = {"ToothCount", "BoreDia", "Rb", "Ra", "Rf", "XMax"}
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

    pattern = _early_bound(
        part.FeatureByName(TOOTH_PATTERN_FEATURE), "IFeature"
    )
    definition = _early_bound(
        pattern.GetDefinition(), "ICircularPatternFeatureData"
    )
    axis_type = int(definition.GetAxisType())
    _telemetry.info(
        f"{phase} cone-gear definition state {configuration}: "
        f"equations={equations!r}, features={feature_states!r}, "
        f"axis_type={axis_type}, "
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
    definition = _early_bound(
        pattern.GetDefinition(), "ICircularPatternFeatureData"
    )
    instances = int(definition.TotalInstances)
    axis_type = int(definition.GetAxisType())
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
        f"{TOOTH_PATTERN_FEATURE} instances={instances}, axis_type={axis_type}, "
        f"suppressed={suppressed}, error={error_code}, warning={is_warning}, "
        f"bodies={len(bodies)}, faces={face_count}, volume={volume:.1f}, "
        f"expected={expected:.1f}"
    )
    _telemetry.info(f"{phase} cone-gear topology: {observation}")
    issues: list[str] = []
    if needs_rebuild:
        issues.append("configuration needs rebuild")
    if instances != teeth:
        issues.append(f"pattern instances {instances} != {teeth}")
    if axis_type != 0:
        issues.append(f"pattern axis type {axis_type} != reference axis 0")
    if suppressed:
        issues.append("pattern is suppressed")
    if error_code:
        issues.append(f"pattern error {error_code} warning={is_warning}")
    if len(bodies) != 1:
        issues.append(f"solid body count {len(bodies)} != 1")
    expected_faces = 4 * teeth + 3
    if face_count != expected_faces:
        issues.append(
            f"solid face count {face_count} != pristine topology {expected_faces}"
        )
    if abs(volume - expected) > 0.01 * expected:
        issues.append(f"volume {volume:.1f} outside 1% of {expected:.1f}")
    if configuration in {CONFIGS[0][0], CONFIGS[-1][0]}:
        _configuration_definition_state(
            adapter, configuration, phase=phase
        )
    return volume, observation, tuple(issues)


def _save3_with_contract(adapter: Any, options: int, *, label: str) -> None:
    """Save in place and consume Save3's BOOL/errors/warnings tuple exactly."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    started = time.perf_counter()
    result = model.Save3(options, 0, 0)
    if isinstance(result, (list, tuple)):
        ok = bool(result[0])
        errors = int(result[1] or 0)
        warnings = int(result[2] or 0)
    else:
        ok = bool(result)
        errors = 0
        warnings = 0
    elapsed = time.perf_counter() - started
    _telemetry.info(
        f"{label}: Save3(options={options}) ok={ok}, errors={errors}, "
        f"warnings={warnings}, elapsed={elapsed:.3f}s"
    )
    if not ok or errors:
        raise RuntimeError(
            f"{label}: Save3 failed: ok={ok}, errors={errors}, "
            f"warnings={warnings}"
        )


async def assert_saved_configuration_topology(
    adapter: Any, *, phase: str = "saved"
) -> dict[str, float]:
    """Probe sentinels first; scan all 20 only if the discriminator passes."""
    sentinels = (CONFIGS[-1], CONFIGS[0], CONFIGS[1], CONFIGS[3])
    ordered = (*sentinels, *(item for item in CONFIGS if item not in sentinels))
    volumes: dict[str, float] = {}
    for configuration, teeth in ordered:
        volume, observation, issues = await _configuration_topology(
            adapter,
            configuration,
            teeth,
            phase=phase,
        )
        volumes[configuration] = volume
        if issues:
            raise RuntimeError(
                f"{phase} cone-gear configuration topology is invalid: "
                f"{observation}; issues={issues!r}"
            )

    _activate_configuration(
        _early_bound(adapter.currentModel, "IModelDoc2"), CONFIGS[-1][0]
    )
    family = [volumes[name] for name, _teeth in CONFIGS]
    if not all(a < b for a, b in zip(family, family[1:], strict=False)):
        raise RuntimeError(f"reopened volumes not monotonic: {volumes!r}")
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


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateConfigurationParameters,
        CreateEquationParameters,
        ExtrusionParameters,
    )

    findings: list[str] = []

    # Deferred drive jobs for the ORDINARY (non-tooth) circle dims: each
    # ``define_*``/``SketchDims.record`` queues a ``(dim@feature, expr)`` here,
    # applied in one batch after the base model + a rebuild exist (every
    # equation target must resolve against the finished part). The tooth-gap
    # profile contributes NOTHING here -- it must mesh with the mating gear, so
    # its flanks are never pinned to a recorded dim.
    drive_jobs: list[tuple[str, str]] = []

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

    # ------------------------------------------------------------------
    # Equation-manager globals. Probes first: live-verified on SW 2026, the
    # equation manager evaluates direct trig in DEGREES (cos(60) = 0.5);
    # the atn return unit is probed because inverse trig need not match.
    # sqr = square root (VBA-style).
    # ------------------------------------------------------------------
    facts = gear_facts(DEFAULT_TEETH)
    await set_global(adapter, "TrigProbe", "cos(60)", 0.5)
    await set_global(adapter, "SqrProbe", "sqr(2)", math.sqrt(2.0))
    atn_probe = await set_global_read(adapter, "AtnProbe", "atn(1)")
    if abs(atn_probe - 45.0) < 1e-6:
        atn_rad = f"atn(%s) * {PI_LIT} / 180"  # atn returns degrees
    elif abs(atn_probe - math.pi / 4.0) < 1e-6:
        atn_rad = "atn(%s)"  # atn returns radians
    else:
        raise RuntimeError(f"atn(1) evaluated to {atn_probe!r} -- unknown dialect")
    _telemetry.debug(f"atn dialect: atn(1) = {atn_probe:g}")
    atn_tmax = atn_rad % '"Tmax"'

    await set_global(adapter, "ToothCount", str(DEFAULT_TEETH), DEFAULT_TEETH)
    await set_global(adapter, "DP", f"{DP:g}", DP)
    await set_global(
        adapter,
        "ToothThickness",
        f'{PI_LIT} / (2 * "DP")',
        TOOTH_THICKNESS / 25.4,
    )
    await set_global(adapter, "PA", f"{PA_DEG:g}", PA_DEG)
    await set_global(adapter, "PArad", f'"PA" * {PI_LIT} / 180', facts["PArad"])
    await set_global(
        adapter, "Rb", '"ToothCount" / "DP" * cos("PA") / 2', facts["Rb"]
    )
    await set_global(
        adapter, "Ra", '("ToothCount" + 2) / "DP" / 2', facts["Ra"]
    )
    await set_global(
        adapter, "Tmax", 'sqr("Ra" * "Ra" / ("Rb" * "Rb") - 1)', facts["Tmax"]
    )
    await set_global(
        adapter,
        "Delta",
        f'{PI_LIT} / (2 * "ToothCount") + tan("PA") - "PArad"',
        facts["Delta"],
    )
    await set_global(adapter, "Gamma", f'2 * {PI_LIT} / "ToothCount"', facts["Gamma"])
    await set_global(
        adapter, "ThetaL", f'{atn_tmax} - "Tmax" + "Delta"', facts["ThetaL"]
    )
    await set_global(
        adapter,
        "ThetaU",
        f'"Tmax" - {atn_tmax} - "Delta" + "Gamma"',
        facts["ThetaU"],
    )

    # ------------------------------------------------------------------
    # Blank: disc at tip radius Ra -- an origin-snapped circle with a
    # DRIVING diameter dimension, extruded. NOT a revolve: a dimension-
    # driven cut through a revolved body freezes at its creation-time
    # profile size on SW 2026 (any later change of the cut's dimension --
    # equation, configured value or plain SystemValue -- makes the cut
    # solve to NOTHING; minimal repro probe_bore11, extrude counterpart
    # passes in probe_bore12). The bore cut below needs an extruded blank.
    # ------------------------------------------------------------------
    ra_default_mm = facts["Ra"] * 25.4
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
    if abs(before - 2.0 * facts["Ra"]) < 1e-6 * facts["Ra"]:
        dim_unit = 1.0  # Value reads in inches
    elif abs(before - 2.0 * ra_default_mm) < 1e-6 * ra_default_mm:
        dim_unit = 25.4  # Value reads in millimetres
    else:
        raise RuntimeError(
            f"{od_dim} reads {before!r}, matches neither {2 * facts['Ra']:.6g} in "
            f"nor {2 * ra_default_mm:.6g} mm"
        )
    _telemetry.debug(f"{od_dim} reads {before:g} (unit factor {dim_unit:g})")

    # ------------------------------------------------------------------
    # Configured bore (Appendix C #7): origin-snapped circle + DRIVING
    # diameter dimension -- no fix, or the dimension goes driven and the
    # configuration link dies. Diameter equation-linked to "BoreDia".
    # The bore MUST precede the circular pattern: cut AFTER the pattern,
    # the same recipe solves to nothing in every configuration whose
    # BoreDia differs from the creation-time value (live SW 2026 finding,
    # probe_bore5/6; the minimal disc+pattern+bore+configs model does NOT
    # reproduce it, so it is specific to this part's downstream-of-pattern
    # chain -- pre-pattern placement regenerates correctly).
    # ------------------------------------------------------------------
    bore_default_in = bore_dia_in(DEFAULT_TEETH)
    await set_global(adapter, "BoreDia", f"{bore_default_in:g}", bore_default_in)
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    bore_circle = check(
        "add_circle bore", await adapter.add_circle(0.0, 0.0, bore_default_in * 12.7)
    )
    check(
        "bore diameter dim (driving)",
        await adapter.add_sketch_dimension(
            bore_circle, None, "diameter", bore_default_in * 25.4
        ),
    )
    # Record the manual driving dim: one display dim, driven by the "BoreDia"
    # global (the same link the inline equation used, now named + deferred).
    bore.record("BoreCutDia", '"BoreDia"')
    status = await adapter.check_sketch_fully_defined()
    state = status.data.get("definition_state") if status.is_success else None
    if state != "fully_defined":
        raise RuntimeError(
            f"bore sketch is {state!r} -- origin snap missing; a fix would "
            "break the BoreDia configuration link, aborting"
        )
    _telemetry.success("bore sketch fully defined (driving dim, no fix)")
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
    mass = await adapter.get_mass_properties()
    bored_volume = float(mass.data.volume)
    expected_bored = expected_blank - math.pi * (bore_default_in * 12.7) ** 2 * FACE_WIDTH
    if abs(bored_volume - expected_bored) > 0.02 * expected_bored:
        raise RuntimeError(
            f"bored blank volume {bored_volume:.1f} mm^3, expected {expected_bored:.1f}"
        )
    _telemetry.success(f"bored blank volume {bored_volume:.1f} mm^3")

    # ------------------------------------------------------------------
    # One tooth gap, all six profile entities equation-driven (t in [0,1]).
    # Loop: A1 ->(lower flank)-> B1 ->(radial)-> arc -> (radial)-> B2
    # ->(upper flank, reversed)-> A2 ->(base chord)-> A1.
    # ------------------------------------------------------------------
    check("create_sketch gap", await adapter.create_sketch("Front"))
    u = '("Tmax" * t)'
    ph_low = f'({u} - "Delta")'
    ph_up = f'({u} - "Delta" + "Gamma")'
    gap_curves = [
        await equation_curve(
            adapter,
            "lower flank (tooth 0 upper, mirrored involute)",
            f'"Rb" * (cos{ph_low} + {u} * sin{ph_low})',
            f'"Rb" * ({u} * cos{ph_low} - sin{ph_low})',
        ),
        await equation_curve(
            adapter,
            "upper flank (tooth 1 lower involute)",
            f'"Rb" * (cos{ph_up} + {u} * sin{ph_up})',
            f'"Rb" * (sin{ph_up} - {u} * cos{ph_up})',
        ),
        await equation_curve(
            adapter,
            "base chord A2->A1",
            '"Rb" * ((1 - t) * cos("Gamma" - "Delta") + t * cos("Delta"))',
            '"Rb" * ((1 - t) * sin("Gamma" - "Delta") + t * sin("Delta"))',
        ),
        await equation_curve(
            adapter,
            "lower radial extension B1->clearance",
            f'("Ra" + t * ({R_CLEAR_IN:g} - "Ra")) * cos("ThetaL")',
            f'("Ra" + t * ({R_CLEAR_IN:g} - "Ra")) * sin("ThetaL")',
        ),
        await equation_curve(
            adapter,
            "outer clearance arc",
            f'{R_CLEAR_IN:g} * cos("ThetaL" + t * ("ThetaU" - "ThetaL"))',
            f'{R_CLEAR_IN:g} * sin("ThetaL" + t * ("ThetaU" - "ThetaL"))',
        ),
        await equation_curve(
            adapter,
            "upper radial extension clearance->B2",
            f'({R_CLEAR_IN:g} + t * ("Ra" - {R_CLEAR_IN:g})) * cos("ThetaU")',
            f'({R_CLEAR_IN:g} + t * ("Ra" - {R_CLEAR_IN:g})) * sin("ThetaU")',
        ),
    ]
    # Whitelisted fix escalation: equation-driven curves re-solve from the
    # equation globals on regeneration -- no static relation/dimension
    # scheme can define them without breaking that.
    try:
        await ensure_fully_defined(
            adapter, "gap sketch", fix_entities=gap_curves, allow_fix_escalation=True
        )
    except RuntimeError as exc:
        findings.append(str(exc))
        _telemetry.warn(f"FINDING  {exc}")
    check("exit_sketch gap", await adapter.exit_sketch())
    # Name the gap profile, but record NO SketchDims: the involute flanks must
    # MESH with the mating gear, so they stay equation-curve-driven and
    # UNdimensioned -- pinning a recorded dim on them would break the mesh.
    # (create_cut_extrude still consumes this most-recent sketch by recency,
    # not by name, so the rename is safe.)
    name_last_feature(adapter, TOOTH_GAP_PROFILE)
    # Single direction: both_directions splits the depth symmetrically about
    # the sketch plane (caught live: a 10 mm both-ways cut covered only
    # z 0..5 of the 7 mm blank, leaving an uncut full disc at z 5..7).
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=FACE_WIDTH + 1.0)
    )
    check("cut tooth gap", gap_cut)
    gap_cut_name = name_last_feature(adapter, TOOTH_GAP_CUT)

    # ------------------------------------------------------------------
    # Pattern the gap about the gear's permanent Top x Right reference axis;
    # select the feature by its returned name instead of projecting a point
    # through the current graphics view.
    # ------------------------------------------------------------------
    from solidworks_mcp.adapters.base import CreateAxisParameters

    axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    check(
        f"circular pattern about {axis.name}",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=axis.name,
                features=[gap_cut_name],
                count=DEFAULT_TEETH,
                geometry_pattern=True,
            )
        ),
    )
    pattern_name = name_last_feature(adapter, TOOTH_PATTERN_FEATURE)
    count_dim = pattern_count_dimension(adapter, pattern_name, DEFAULT_TEETH)
    check(
        f"link {count_dim} to ToothCount",
        await adapter.create_equation(
            CreateEquationParameters(equation=f'"{count_dim}" = "ToothCount"')
        ),
    )

    # ------------------------------------------------------------------
    # Default-config (DEFAULT_TEETH) gear volume, by the same analytic
    # expectation the per-config loop uses (blank - teeth*gap - bore). This is
    # the "last check" the neutrality re-check below reuses.
    # ------------------------------------------------------------------
    bore_default_mm3 = math.pi * (bore_default_in * 12.7) ** 2 * FACE_WIDTH
    v_gear = (
        expected_blank
        - DEFAULT_TEETH * gap_area_in_disc(DEFAULT_TEETH) * 25.4**2 * FACE_WIDTH
        - bore_default_mm3
    )
    await volume_check(adapter, "cone gear (default config)", v_gear, 0.01 * v_gear)

    # Native tooth-system acceptance size.  The involute is generated from the
    # gear equations and exposes no stable feature dimension for circular tooth
    # thickness, so policy rule 2's authoring-reference-sketch pattern gives the
    # print one DRIVING model dimension.  Construction geometry is not drawn,
    # but its dimension imports; a blanked sketch would suppress the dimension.
    tooth_reference = SketchDims()
    check(
        "create_sketch tooth-thickness reference",
        await adapter.create_sketch("Front"),
    )
    set_sketch_direct_db(adapter, True)
    tooth_line = check(
        "tooth-thickness reference line",
        await adapter.add_line(0.0, 0.0, TOOTH_THICKNESS, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, tooth_line)
    check(
        "tooth-thickness reference horizontal",
        await adapter.add_sketch_constraint(tooth_line, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        f"{tooth_line}.end",
        "horizontal_distance",
        TOOTH_THICKNESS,
        "circular tooth thickness",
    )
    tooth_reference.record("ToothThickness", '"ToothThickness"')
    await anchor_point_to_origin(
        adapter,
        f"{tooth_line}.start",
        0.0,
        0.0,
        "tooth-thickness reference",
    )
    await ensure_fully_defined(adapter, "tooth-thickness reference sketch")
    check(
        "exit_sketch tooth-thickness reference",
        await adapter.exit_sketch(),
    )
    tooth_sketch = name_last_feature(adapter, "ToothThicknessReference")
    drive_jobs += tooth_reference.apply(adapter, tooth_sketch)

    # Apply every deferred drive equation after all targets exist: blank and
    # bore circle dimensions plus the construction sketch's native circular
    # tooth thickness.  The configuration sweep below proves the two
    # configuration-dependent solids still regenerate; the construction
    # dimension is volume-neutral.  The involute gap profile remains absent
    # from drive_jobs by design because its flanks must solve from the globals.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cone gear (equations neutral)", v_gear, 0.01 * v_gear
    )

    await apply_material(adapter, MATERIAL)

    # ------------------------------------------------------------------
    # Configurations + the regeneration experiment (plan risk #2): switch
    # through all configs asserting per-config instance count, volume bounds
    # and monotonic growth, then return to the first config and require the
    # volume to reproduce (determinism).
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

    # Author before the existing 20-configuration regeneration sweep.  This is
    # the live regression gate for the model-owned symbol: a face-attached
    # symbol created in the 120T geometry makes every other configuration's
    # component feature rebuild with swFeatureErrorUnknown.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    # Establish the final path once while T120 is active. The per-configuration
    # sweep can then use IModelDoc2.Save3 directly; the adapter's in-place save
    # deliberately adds AvoidRebuildOnSave, which live probes proved does not
    # persist rebuilt inactive-configuration bodies.
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

        count = read_dimension(adapter, count_dim)
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
        cfg = gear_facts(teeth)

        # OD check via the equation-driven diameter dimension (selection-free;
        # the measure tool's point selection proved unreliable on the
        # patterned gear -- it kept grabbing gap-wall faces).
        od = read_dimension(adapter, od_dim)
        if abs(od - 2.0 * cfg["Ra"] * dim_unit) > 2e-4 * cfg["Ra"] * dim_unit:
            raise RuntimeError(
                f"{name}: {od_dim} reads {od:g}, expected "
                f"{2.0 * cfg['Ra'] * dim_unit:g} -- dimension equation did not "
                "regenerate"
            )
        _telemetry.success(f"{name}: blank diameter dim = {od:g}")

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
    description = str(grouped_spec.get("description", "")).strip()
    apply_grouped_bom_properties(
        adapter,
        [name for name, _teeth in CONFIGS],
        part_number=str(grouped_spec.get("number", "")),
        description=description,
    )
    apply_custom_properties(adapter, {"Description": description})
    await report_mass_properties(adapter)

    # Mark the four manufacturing model dimensions.  Both fitted sizes carry
    # bands derived above; their decimal places live on the model and each
    # configuration sheet only imports and arranges them.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreCutDia", *deviations(BORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "ToothThicknessReference",
        "ToothThickness",
        *deviations(TOOTH_THICKNESS_BAND),
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": gear_data(DEFAULT_TEETH, BACKLASH_MM),
            "Manufacturing Notes": DRAWING_NOTES,
        },
    )
    for configuration, teeth in CONFIGS:
        _apply_configuration_properties(
            adapter,
            configuration,
            {
                "Gear Data": gear_data(teeth, BACKLASH_MM),
                "Material Specification": material_specification(teeth),
            },
        )
    artefacts.update(await save_part_and_images(adapter, PART_NAME))
    part_path = artefacts["part"]
    # Rebuild every configuration through the API intended for File > Save All
    # > Rebuild and save document, then serialize all marked configuration
    # caches in one Save3 call. AddRebuildSaveMark controls which caches are
    # written; Save3 alone does not rebuild those configurations.
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    if not bool(manager.AddRebuildSaveMark(2, "")):
        raise RuntimeError("failed to set all-configuration rebuild-save marks")
    for name, _teeth in CONFIGS:
        raw_configuration = model.GetConfigurationByName(name)
        if raw_configuration is None:
            raise RuntimeError(f"{name}: configuration missing while setting save marks")
        configuration = _early_bound(raw_configuration, "IConfiguration")
        if not bool(configuration.AddRebuildSaveMark):
            raise RuntimeError(f"{name}: rebuild-save mark was not set")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    rebuild_started = time.perf_counter()
    if not bool(extension.ForceRebuildAll()):
        raise RuntimeError("ForceRebuildAll failed for cone-gear configurations")
    _telemetry.info(
        "rebuilt all cone-gear configurations in "
        f"{time.perf_counter() - rebuild_started:.3f}s"
    )
    _save3_with_contract(
        adapter,
        1,
        label="rebuild and persist all marked configurations",
    )

    part_title = str(
        _early_bound(adapter.currentModel, "IModelDoc2").GetTitle()
    )
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check("reopen saved cone-gear", await adapter.open_model(part_path))
    await assert_saved_configuration_topology(adapter, phase="reopened")
    raise RuntimeError(
        "diagnostic complete: named reference-axis pattern persistence evidence "
        "captured; refusing to publish probe artefacts"
    )

    if findings:
        summary = "; ".join(findings)
        raise RuntimeError(f"prototype completed with findings: {summary}")
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
