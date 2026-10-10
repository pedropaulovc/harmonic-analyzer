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
from _simplified_part import (
    assert_simplified_configurations,
    derive_simplified_on_saved_part,
)
from _fit_deviations import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_pmi import author_part_pmi
from _cone_gear_geometry import R_CLEAR_MM, bore_area_mm2
from _cone_gear_readback import (
    _BANDED_DIMENSIONS,
    _TOL_LIMIT,
    _activate_configuration,
    _assert_gap_floor_limits,
    _configuration_topology,
    _expected_configuration_volume,
    _gap_floor_tolerance,
    assert_saved_configuration_topology,
)
from dt_cone_gear_notes import custom_cutter_detail, drawing_notes, gear_data
from dt_cone_gear_spec import (
    BLANK_DIA_BAND,
    BORE_AF_BAND,
    FACE_WIDTH_BAND,
    BORE_DIA_BAND,
    CONFIGS,
    DEFAULT_TEETH,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FLAT_CLOCK_TOLERANCE_DEG,
    GAP_FLOOR_SKETCH,
    MM_PER_IN,
    REFERENCE_SKETCHES,
    SIMPLIFIED_FEATURES_BY_CONFIGURATION,
    SURFACE_FINISHES,
    TOOTH_REFERENCE_SKETCH,
    TOOTH_THICKNESS_BAND,
    bore_dia_mm,
    bore_flat_af_mm,
    bore_flat_offset_mm,
    configuration_number,
    floor_limits_mm,
    gap_floor_deviations_mm,
    floor_radius_min_mm,
    material_specification,
    stock_form_profile,
    tooth_features,
    blank_dia_band,
    tooth_thickness_band,
)
from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _custom_properties import apply_custom_properties
from _dimensions import drive_dimension, name_dimensions
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _paths import OUT_PNG, OUT_SLDPRT
from _rebuild import assert_saved_configurations_regenerate, force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _gear import equation_curve
from _visibility import (
    assert_reference_geometry_hidden,
    assert_reference_geometry_hidden_in_every_configuration,
    blank_reference_geometry,
)

# Equation-parser/unit guards are reused, not their historical ideal profiles.

import _telemetry
from involute_gear import (
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


_SET_IN_SPECIFIC_CONFIGURATIONS = 3  # swSetValueInConfiguration_e
_VISIBILITY_HIDDEN = 1  # swVisibilityState_e

def bore_dia_in(teeth: int) -> float:
    """Configured bore diameter in inches, matching the stepped-shaft seat."""
    return bore_dia_mm(teeth) / MM_PER_IN


def bore_af_in(teeth: int) -> float:
    """Configured bore across-flat in inches, matching its land's flat."""
    return bore_flat_af_mm(teeth) / MM_PER_IN


def floor_dia_in(teeth: int) -> float:
    """Functional minimum root envelope, not the translated cutter root radius."""
    return 2.0 * floor_radius_min_mm(teeth) / MM_PER_IN


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


def _set_configuration_bands(adapter: Any) -> None:
    """Store each configuration's blank and tooth-thickness band.

    The FloorDia form (``_set_gap_floor_limits``): one ``SetValues2`` with
    swSetValue_InSpecificConfigurations per configuration, all twenty, T006
    its own band and the rest the shared one. No readback here: the
    just-written tolerance object answers with what was written, not with the
    active configuration's band (part:dt_cone_gear at 039e557da). The reopened
    audit reads each back with its configuration active
    (``_assert_configuration_bands``).
    """
    import pythoncom
    from win32com.client import VARIANT

    for feature, name, band_for in _BANDED_DIMENSIONS:
        _display, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        for configuration, teeth in CONFIGS:
            band = band_for(teeth)
            lower, upper = deviations(band)
            names = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [configuration])
            if not bool(tolerance.SetValues2(
                lower / 1000.0, upper / 1000.0, _SET_IN_SPECIFIC_CONFIGURATIONS, names
            )):
                raise RuntimeError(
                    f"{name}@{configuration}: SetValues2 rejected the band {band} mm"
                )
    _telemetry.success(
        f"BlankDia and ToothThickness bands set in {len(CONFIGS)} configurations "
        f"(T006: blank {blank_dia_band(6)}, tooth thickness {tooth_thickness_band(6)} mm)"
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


_SW_DISPLAY_ANNOTATIONS = 31  # swUserPreferenceToggle_e.swDisplayAnnotations
_SW_DETAILING_NO_OPTION = 0  # swUserPreferenceOption_e.swDetailingNoOptionSpecified


def _display_model_annotations(adapter: Any, shown: bool) -> None:
    """Show or hide the part's model annotations in every view, and prove it."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    toggle = (_SW_DISPLAY_ANNOTATIONS, _SW_DETAILING_NO_OPTION)
    extension.SetUserPreferenceToggle(*toggle, shown)
    if bool(extension.GetUserPreferenceToggle(*toggle)) != shown:
        raise RuntimeError(f"cone-gear model annotations did not set displayed={shown}")


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
    """Rotate the canonical core gap by pi/N, in main's cut_tooth_gap order."""
    phase = math.pi / teeth
    cosine, sine = f"{math.cos(phase):.17g}", f"{math.sin(phase):.17g}"
    return tuple(
        (
            segment.name,
            f"({cosine})*({segment.x})-({sine})*({segment.y})",
            f"({sine})*({segment.x})+({cosine})*({segment.y})",
        )
        for segment in stock_form_profile(teeth).cut_order_native_segments(
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


def _suppress_rows_and_hide_references(adapter: Any, pattern_axis: str) -> None:
    """With each configuration active, suppress the other rows and hide the
    construction geometry.

    ``_restrict_to_configuration`` specifies the other configurations from the
    row being authored. Probe 3 (187ab61f2) read T012..T120 back unsuppressed
    in T006 after that call returned True, the crank-v4-10 ferrule finding
    (SetSuppression2 specified from another configuration left the cut live).
    So, like the ferrule and the tip-collar builds, each configuration is
    activated and suppresses the foreign rows in this configuration only,
    dependents before parents, and each state is read back.

    Hide/show is per configuration too: blanked with T120 active only, the
    pattern axis and the two authoring sketches rendered in T006..T114
    (7e88be269 farm images), and would in any assembly placing those rows.
    The probes 7 and 8 that seemed to tie a per-configuration blank to
    unsuppressed rows read IsSuppressed2(3, [name]), which answers None.
    """
    from solidworks_mcp.adapters.com_variant import null_variant

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    for configuration in [str(name) for name in model.GetConfigurationNames()]:
        _activate_configuration(model, configuration)
        for row, row_teeth in CONFIGS:
            if row == configuration:
                continue
            for name in reversed(tooth_features(row_teeth)):
                raw = part.FeatureByName(name)
                if raw is None:
                    raise RuntimeError(f"{configuration}: missing configured feature {name}")
                feature = _early_bound(raw, "IFeature")
                states = feature.IsSuppressed2(1, null_variant())
                if isinstance(states, (list, tuple)) and len(states) == 1 and states[0] is True:
                    continue
                if feature.SetSuppression2(0, 1, null_variant()) is not True:
                    raise RuntimeError(f"cannot suppress {name} in {configuration}")
                states = feature.IsSuppressed2(1, null_variant())
                if not isinstance(states, (list, tuple)) or len(states) != 1 or states[0] is not True:
                    raise RuntimeError(f"{name}: suppression did not persist in {configuration}")
        blank_reference_geometry(adapter, ((pattern_axis, "AXIS"),))
        _blank_reference_sketches(adapter)
    _telemetry.success(
        "foreign tooth rows suppressed and construction geometry hidden "
        "with each configuration active"
    )


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
    _suppress_rows_and_hide_references(adapter, pattern_axis)
    check("activate T120 for native PMI", await adapter.set_active_configuration("T120"))

    # Author before the existing 20-configuration regeneration sweep.  This is
    # the live regression gate for the model-owned symbol: a face-attached
    # symbol created in the 120T geometry makes every other configuration's
    # component feature rebuild with swFeatureErrorUnknown.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    # Establish the final path once while T120 is active. The per-configuration
    # sweep can then use IModelDoc2.Save3 directly; the adapter's in-place save
    # deliberately adds AvoidRebuildOnSave, which live probes proved does not
    # persist rebuilt inactive-configuration bodies.  The axis and the two
    # authoring sketches are already hidden in every configuration; this part
    # saves itself, so it runs save_part_and_images' check here (T120), and
    # the saved part, reopened, proves every configuration.
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
    # The bore's model-owned Ra symbol rendered in the T006 image (7e88be269).
    # As on the harmonic base, images are taken with model annotations hidden
    # and the part is saved with them shown.
    _display_model_annotations(adapter, False)
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
            # The saved part's reopened audit reads the roots and bore webs.
            measure_roots=False,
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
    _set_configuration_bands(adapter)
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
    _display_model_annotations(adapter, True)
    artefacts.update(await save_part_and_images(adapter, PART_NAME, views=()))
    # derive_simplified_on_saved_part closes this document without saving, so
    # the hidden-annotation toggle never reaches the saved part.
    _display_model_annotations(adapter, False)
    image = (png_dir / f"{PART_NAME}_isometric.png").resolve()
    check(
        "export_image isometric (annotations hidden)",
        await adapter.export_image(
            {
                "file_path": str(image),
                "format_type": "png",
                "width": 1600,
                "height": 1000,
                "view_orientation": "isometric",
            }
        ),
    )
    artefacts["isometric"] = str(image)
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
    # Hide/show is per configuration: every saved configuration, the derived
    # simplified ones included, is read with itself active.
    assert_reference_geometry_hidden_in_every_configuration(adapter, PART_NAME)
    assert_simplified_configurations(
        adapter, PART_NAME, SIMPLIFIED_FEATURES_BY_CONFIGURATION, placed
    )

    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
