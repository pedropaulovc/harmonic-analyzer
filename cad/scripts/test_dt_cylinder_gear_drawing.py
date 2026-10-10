"""Finished-fit and tooth-system contracts consumed by the native drawing."""

from __future__ import annotations

import ast
import math
import runpy
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _gear_fit_limits import gear_tip_band_mm
import build_dt_cylinder_gear as part
import dt_cylinder_gear_notes as notes
import dt_cylinder_gear_shaft_spec as arbor
import dt_cylinder_gear_spec as spec
import draw_dt_cylinder_gear as drawing


def test_running_bore_limits_follow_the_finished_arbor() -> None:
    # Opposite ends of the arbor size band must not receive one fixed bore band.
    assert spec.matched_bore_limits(9.505) == pytest.approx((9.535, 9.575))
    assert spec.matched_bore_limits(9.525) == pytest.approx((9.555, 9.595))


def test_native_bore_represents_a_finished_running_fit() -> None:
    # Equal nominal bore/arbor diameters previously modeled zero clearance,
    # even though the drawing required a positive matched running clearance.
    minimum, maximum = spec.matched_bore_limits(arbor.SHAFT_DIA)
    assert minimum <= spec.BORE_DIA <= maximum
    assert spec.BORE_DIA - arbor.SHAFT_DIA == pytest.approx(0.050)


def test_blank_and_tooth_profile_follow_the_same_configured_pitch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_pitch = 40.0  # Deliberately differs from the current machine setting.
    original_machine = _config.machine

    def machine_value(*keys: str):
        if keys == ("gear_train", "diametral_pitch"):
            return configured_pitch
        return original_machine(*keys)

    monkeypatch.setattr(_config, "machine", machine_value)
    dimensions = runpy.run_path(spec.__file__)
    profile = dimensions["STOCK_FORM"]
    assert profile.template.diametral_pitch == configured_pitch
    assert profile.teeth == dimensions["TEETH"]
    assert dimensions["OUTSIDE_DIA"] / 2.0 == pytest.approx(profile.blank_radius_mm)
    assert dimensions["SUPPORT_OUTSIDE_DIA_MM"] == pytest.approx(
        2.0 * profile.support_radius_max_mm
    )


def test_tooth_system_and_reference_cutter_are_spec_owned() -> None:
    assert spec.TEETH == int(_config.machine("gear_train", "cylinder_teeth"))
    assert spec.DIAMETRAL_PITCH == _config.machine("gear_train", "diametral_pitch")
    assert spec.PRESSURE_ANGLE_DEG == _config.machine(
        "gear_train", "pressure_angle_deg"
    )
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.CUTTER_REFERENCE_TEETH == spec.CUTTER_TEETH_RANGE[0]
    assert spec.STOCK_FORM.template == spec.CUTTER_TEMPLATE
    assert spec.STOCK_FORM.teeth == spec.TEETH
    assert spec.CUTTER_RADIAL_TRANSLATION_MM == pytest.approx(
        spec.PITCH_DIA / 2.0 - spec.CUTTER_TEMPLATE.pitch_radius_mm
    )
    assert spec.ROOT_ENVELOPE_DIA_MM == pytest.approx(
        (2.0 * spec.STOCK_FORM.root_radius_min_mm, 2.0 * spec.STOCK_FORM.root_radius_max_mm)
    )
    assert spec.ROOT_ENVELOPE_DIA_MM[0] < spec.ROOT_ENVELOPE_DIA_MM[1]
    assert spec.WHOLE_DEPTH == pytest.approx(spec.STOCK_FORM.plunge_mm)
    assert spec.MAX_CUT_DEPTH_MM > spec.WHOLE_DEPTH
    assert spec.OUTSIDE_DIA <= spec.MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA + 0.01 > spec.MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA_BAND == gear_tip_band_mm("contact_critical")
    assert spec.WHOLE_DEPTH_BAND == (0.05, 0.0)
    assert spec.CUTTER_NUMBER == 2
    assert spec.CUTTER_TEETH_RANGE == (55, 134)
    assert spec.CUTTER_TEETH_RANGE[0] <= spec.TEETH <= spec.CUTTER_TEETH_RANGE[1]
    for row in (
        f"NUMBER OF TEETH:  {spec.TEETH}",
        f"DIAMETRAL PITCH:  {spec.DIAMETRAL_PITCH:.2f}",
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f} DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        f"ROOT ENVELOPE DIAMETER (mm, REF):  "
        f"{spec.ROOT_ENVELOPE_DIA_MM[0]:.3f}-{spec.ROOT_ENVELOPE_DIA_MM[1]:.3f}",
        f"CUTTER PLUNGE (mm):  {spec.WHOLE_DEPTH:.3f} "
        f"+{spec.WHOLE_DEPTH_BAND[0]:.2f}/{spec.WHOLE_DEPTH_BAND[1]:.2f}",
        f"FORM CUTTER (REF):  #{spec.CUTTER_NUMBER}, "
        f"{spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T; "
        f"{spec.CUTTER_REFERENCE_TEETH}T REFERENCE",
        "TOOTH FORM:  TRANSLATED STOCK FORM; FINITE FLANKS AND OFF-CENTRE ROOT ARC",
    ):
        assert row in notes.GEAR_DATA
    assert "NONSTANDARD" not in notes.GEAR_DATA
    assert "OUTSIDE DIAMETER" not in notes.GEAR_DATA


def test_cam_and_notch_oracles_use_actual_off_centre_root_material() -> None:
    import math

    profile = spec.STOCK_FORM
    assert spec.CAM_ROOT_WEB_MIN_MM == pytest.approx(
        profile.root_radius_min_mm - (spec.CAM_DIA / 2.0 + spec.ECCENTRICITY)
    )
    assert spec.CAM_ROOT_WEB_MIN_MM > 0.0
    assert part.is_solid(0.0, 0.0)
    assert not part.is_solid(spec.OUTSIDE_DIA / 2.0 + 0.01, 0.0)
    radius = (profile.root_radius_min_mm + profile.root_radius_max_mm) / 2.0
    root_parameter = profile.template.flank_parameter_min
    root_angle = (
        profile.template.half_space_base_angle_rad
        + root_parameter
        - math.atan(root_parameter)
    )
    reference_root = profile.template.root_radius_mm
    endpoint_angle = math.atan2(
        reference_root * math.sin(root_angle),
        profile.radial_translation_mm + reference_root * math.cos(root_angle),
    )
    # A circular actual-axis root would classify both points identically.
    assert profile.contains_material(radius, 0.0)
    assert not profile.contains_material(
        radius * math.cos(endpoint_angle), radius * math.sin(endpoint_angle)
    )
    for angle in (0.0, endpoint_angle, math.pi / spec.TEETH, math.pi / 2.0):
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        assert part.is_solid(x, y) == profile.contains_material(
            x, y, rotate_rad=math.pi / spec.TEETH
        )


def test_critical_tip_is_a_marked_native_dimension() -> None:
    assert spec.DRAWING_DIMENSIONS["GearBlankProfile"] == {"OutsideDia"}
    assert "OutsideDia" in drawing.RIGHT_KEEP
    source = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set_dimension_bilateral_tolerance"
    ]
    assert any(
        len(call.args) == 4
        and ast.literal_eval(call.args[1]) == "GearBlankProfile"
        and ast.literal_eval(call.args[2]) == "OutsideDia"
        and ast.unparse(call.args[3]) == "*deviations(OUTSIDE_DIA_BAND)"
        for call in calls
    )
    assert part.OUTSIDE_DIA_BAND == spec.OUTSIDE_DIA_BAND


def test_reference_axis_iterator_uses_nullable_dispatch_not_truthiness(monkeypatch) -> None:
    from types import SimpleNamespace

    class Feature:
        def __init__(self, name, specific=None, next_feature=None):
            self.Name = name  # IFeature.Name is a BSTR property.
            self.specific = specific
            self.next_feature = next_feature

        def __bool__(self):
            raise AssertionError("VT_DISPATCH features must not be truth-tested")

        def GetNextFeature(self):  # VT_DISPATCH method, nullable return.
            return self.next_feature

        def GetSpecificFeature2(self):
            return self.specific

    axis = SimpleNamespace(GetRefAxisParams=lambda: (0.01, 0.02, 0.03, 0.04, 0.05, 0.06))
    target = Feature("Axis3", axis)
    first = Feature("GearBlank", next_feature=target)
    model = SimpleNamespace(FirstFeature=lambda: first)  # nullable VT_DISPATCH method
    adapter = SimpleNamespace(currentModel=model, _attempt=lambda fn, default=None: fn())
    monkeypatch.setattr(part, "_flag", lambda _obj, _interface: None)
    assert part._ref_axis_start_mm(adapter, "Axis3") == pytest.approx((10.0, 20.0, 30.0))
    assert part._ref_axis_start_mm(adapter, "missing") is None
    model.FirstFeature = lambda: None
    assert part._ref_axis_start_mm(adapter, "Axis3") is None


def test_printed_plunge_corners_keep_finite_actual_cutter_support() -> None:
    depth_limits = spec.whole_depth_limits_mm()
    nominal = round(spec.WHOLE_DEPTH, spec.WHOLE_DEPTH_PLACES)
    upper, lower = spec.WHOLE_DEPTH_BAND
    assert depth_limits == pytest.approx((nominal + lower, nominal + upper))
    profiles = spec.manufacturing_corner_profiles()
    assert len(profiles) == 4
    for profile, (tip, depth) in zip(
        profiles,
        (
            (tip, depth)
            for tip in spec.outside_dia_limits_mm()
            for depth in depth_limits
        ),
        strict=True,
    ):
        assert profile.template == spec.CUTTER_TEMPLATE
        assert profile.teeth == spec.TEETH
        assert profile.blank_radius_mm == pytest.approx(tip / 2.0)
        assert profile.radial_translation_mm == pytest.approx(
            tip / 2.0 - spec.CUTTER_TEMPLATE.root_radius_mm - depth
        )
        assert profile.plunge_mm == pytest.approx(depth)
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.root_radius_min_mm > spec.CAM_DIA / 2.0 + spec.ECCENTRICITY


def test_tip_limits_follow_printed_nominal_and_shared_grade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nominal = round(spec.OUTSIDE_DIA, spec.DRAWING_PRECISION_BY_NAME["OutsideDia"])
    upper, lower = gear_tip_band_mm("contact_critical")
    assert spec.outside_dia_limits_mm() == pytest.approx(
        (nominal + lower, nominal + upper), abs=1e-12
    )
    assert spec.outside_dia_limits_mm()[1] <= spec.SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA < (spec.TEETH + 2) * spec.MODULE_MM
    original_fit = _config.fit
    changed_band = [0.0, -0.01]

    def fit_value(*keys: str):
        if keys == ("gear_tip", "contact_critical_band_mm"):
            return changed_band
        return original_fit(*keys)

    monkeypatch.setattr(_config, "fit", fit_value)
    dimensions = runpy.run_path(spec.__file__)
    assert dimensions["OUTSIDE_DIA_BAND"] == tuple(changed_band)
    assert dimensions["outside_dia_limits_mm"]() == pytest.approx(
        (nominal - 0.01, nominal), abs=1e-12
    )


def test_every_marked_dimension_has_exactly_one_view_owner() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    ownership = Counter(
        name
        for view_dimensions in (
            drawing.FRONT_KEEP,
            drawing.RIGHT_KEEP,
            drawing.NOTCH_DETAIL_DIMENSIONS,
        )
        for name in view_dimensions
    )
    assert ownership == Counter(marked)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: places are the tolerance, so the .SLDPRT carries them.

    Three places only where a three-place band rides the dimension (the
    matched bore's reference nominal, the cam eccentricity); four on the
    stacking thickness that sets the station pitch, 7.0565 +/-0.025, exact
    only at four (#743, user ruling L20 d'); the cam thickness is the one
    sheet-derived value, a parenthesised reference.
    """
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places == 3} == {
        "BoreDia",
        "CamCy",
    }
    assert {name for name, places in by_name.items() if places == 4} == {
        "OverallThickness",
    }
    assert spec.DRAWING_REFERENCE_PRECISION == {"cam thickness reference": 2}
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The sheet reads the places back and never rewrites them.
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


@pytest.mark.parametrize(
    ("assembly_script", "reads_cylinder_spec"),
    (
        ("build_ch_channel_assembly.py", True),
        ("build_dt_drive_train_assembly.py", True),
        # paper-drive read the cylinder spec only through the drive-train
        # script; it now takes the crank axis from cone_line (#880).
        ("build_pd_paper_drive_assembly.py", False),
    ),
)
def test_assembly_recipes_exclude_cylinder_drawing_prose(
    assembly_script: str, reads_cylinder_spec: bool
) -> None:
    dependencies = {
        Path(path).name
        for path in module_deps_of(Path(__file__).with_name(assembly_script))
    }
    assert ("dt_cylinder_gear_spec.py" in dependencies) is reads_cylinder_spec
    assert dependencies.isdisjoint({"build_dt_cylinder_gear.py", "dt_cylinder_gear_notes.py"})


def test_stacking_thickness_is_the_held_marked_dimension() -> None:
    import dt_cylinder_gear_notes as notes

    # The overall thickness sets every station of the solid bank (#743), so it
    # is a marked model dimension printed to four places with its own band;
    # the cam thickness between it and the face width is only a reference.
    assert spec.DRAWING_DIMENSIONS["CamBoss"] == {"OverallThickness"}
    assert spec.DRAWING_PRECISION_BY_NAME["OverallThickness"] == 4
    assert "OverallThickness" in drawing.RIGHT_KEEP
    # The bank is preloaded (#948 ruling R, PR #1292): no ring overhangs its
    # cam, so the stacking callout states no overhang bound.
    assert "OVERHANG" not in notes.STACK_FIT_CALLOUT
    assert "MHA-DT-013" in notes.STACK_FIT_CALLOUT


class _RimEdge:
    """IEdge double of a circular boundary at ``station_mm`` along the axis."""

    def __init__(
        self,
        station_mm: float,
        *,
        radius_mm: float = spec.CAM_DIA / 2.0,
        center_y_mm: float = spec.ECCENTRICITY,
        axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
    ) -> None:
        self.curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(
                0.0,
                center_y_mm / 1000.0,
                station_mm / 1000.0,
                *axis,
                radius_mm / 1000.0,
            ),
        )

    def GetCurve(self):  # noqa: N802 - the COM member name
        return self.curve


class _CamFace:
    """IFace2 double of a cylinder about the eccentric axis, cam-boss long."""

    def __init__(
        self, edges: list[_RimEdge], diameter_mm: float = spec.CAM_DIA
    ) -> None:
        self.edges = edges
        self.surface = SimpleNamespace(
            Identity=4002,  # swSurfaceTypes_e.CYLINDER_TYPE
            CylinderParams=(
                0.0,
                spec.ECCENTRICITY / 1000.0,
                0.0,
                0.0,
                0.0,
                1.0,
                diameter_mm / 2000.0,
            ),
        )

    def GetSurface(self):  # noqa: N802
        return self.surface

    def GetBox(self):  # noqa: N802
        r = spec.CAM_DIA / 2000.0
        y = spec.ECCENTRICITY / 1000.0
        return (
            -r,
            y - r,
            spec.FACE_WIDTH / 1000.0,
            r,
            y + r,
            spec.OVERALL_THICKNESS / 1000.0,
        )

    def GetEdges(self):  # noqa: N802
        return self.edges


class _CamView:
    """The right view's visible faces (swViewEntityType_Face = 3)."""

    def __init__(self, faces: list[_CamFace]) -> None:
        self.faces = faces

    def GetVisibleComponents(self):  # noqa: N802
        return ["dt-cylinder-gear"]

    def GetVisibleEntities2(self, component, kind):  # noqa: N802
        return self.faces if kind == 3 else []


def test_cam_thickness_takes_only_the_cam_faces_two_rims() -> None:
    """Farm run 20261002T180658288Z: coordinate picks for the cam thickness
    produced a dimension reading 1570.8 -- pi/2, an angle.  The reference now
    dimensions the controlled cam face's two circular rims, and nothing else on
    it or on another cylinder: not the bore circle at the rear station, not a
    rim at another station, not the gear blank's circle."""
    shoulder = _RimEdge(spec.FACE_WIDTH)
    rear = _RimEdge(spec.OVERALL_THICKNESS, axis=(0.0, 0.0, -1.0))
    bore = _RimEdge(
        spec.OVERALL_THICKNESS, radius_mm=spec.BORE_DIA / 2.0, center_y_mm=0.0
    )
    origin = _RimEdge(0.0)
    cam = _CamFace([rear, bore, shoulder, origin])
    gear = _CamFace([_RimEdge(spec.FACE_WIDTH)], spec.OUTSIDE_DIA)

    rims = drawing._cam_thickness_rims(_CamView([gear, cam]))

    assert rims == {spec.FACE_WIDTH: shoulder, spec.OVERALL_THICKNESS: rear}
    span_mm = (
        rims[spec.OVERALL_THICKNESS].curve.CircleParams[2]
        - rims[spec.FACE_WIDTH].curve.CircleParams[2]
    ) * 1000.0
    assert span_mm == pytest.approx(spec.CAM_THICKNESS)


@pytest.mark.parametrize(
    "fault", ("missing", "radius", "center", "axis", "station", "ambiguous")
)
def test_cam_thickness_refuses_a_wrong_or_ambiguous_rim(fault: str) -> None:
    edges = [_RimEdge(spec.FACE_WIDTH)]
    if fault == "radius":
        edges.append(
            _RimEdge(spec.OVERALL_THICKNESS, radius_mm=spec.CAM_DIA / 2.0 + 1.0)
        )
    elif fault == "center":
        edges.append(
            _RimEdge(spec.OVERALL_THICKNESS, center_y_mm=spec.ECCENTRICITY + 1.0)
        )
    elif fault == "axis":
        edges.append(_RimEdge(spec.OVERALL_THICKNESS, axis=(1.0, 0.0, 0.0)))
    elif fault == "station":
        edges.append(_RimEdge(spec.OVERALL_THICKNESS + 1.0))
    elif fault == "ambiguous":
        edges.extend(
            [_RimEdge(spec.OVERALL_THICKNESS), _RimEdge(spec.OVERALL_THICKNESS)]
        )
    with pytest.raises(RuntimeError, match="expected one circular cam rim"):
        drawing._cam_thickness_rims(_CamView([_CamFace(edges)]))


@pytest.mark.parametrize("count", (0, 2))
def test_cam_thickness_refuses_a_missing_or_ambiguous_cam_face(count: int) -> None:
    faces = [
        _CamFace([_RimEdge(spec.FACE_WIDTH), _RimEdge(spec.OVERALL_THICKNESS)])
        for _ in range(count)
    ]
    with pytest.raises(RuntimeError, match=f"expected one cam face, got {count}"):
        drawing._cam_thickness_rims(_CamView(faces))


def test_pattern_notch_reference_uses_the_actual_seed_gap() -> None:
    kerf_axis = math.pi / 2.0 + math.radians(spec.NOTCH_PHASE_DEG)
    assert spec.TOOTH_PATTERN_GAP_RAD == pytest.approx(math.pi / spec.TEETH)
    assert math.degrees(kerf_axis - spec.TOOTH_PATTERN_GAP_RAD) == pytest.approx(
        spec.PATTERN_NOTCH_REF_ANGLE_DEG
    )
    assert spec.PATTERN_NOTCH_REF_ANGLE_DEG == 90.0
    assert spec.CAM_PHASE_TOLERANCE_DEG == 0.25
    assert spec.DRAWING_PRECISION["NotchProfile"]["NotchPhase"] == 1
    assert spec.DRAWING_PRECISION["NotchProfile"]["PatternNotchPhase"] == 0
    assert "PatternNotchPhase" in drawing.FRONT_KEEP


def test_pattern_notch_is_an_untoleranced_reference_with_no_method_text() -> None:
    """Main's MHA-DT-012 eye pass: the kerf is sawn into a root the indexing
    already cut, so tooth pattern to notch is not a separate operation. The
    90 deg prints (90°) REF; the ±0.02 deg grade and the INSPECT text are gone
    (the callout-above slot never rendered, so its readback was a false pass).
    Cam lobe to notch stays toleranced on NotchPhase."""
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    expected_names = {
        keyword.value.id
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "add_angular_reference_dimension"
        for keyword in node.keywords
        if keyword.arg == "expected_degrees" and isinstance(keyword.value, ast.Name)
    }
    assert {"NOTCH_PHASE_DEG", "PATTERN_NOTCH_REF_ANGLE_DEG"} <= expected_names
    assert not any(
        isinstance(node.func, ast.Name) and node.func.id == "set_dimension_basic_tolerance"
        for node in calls
    )
    assert any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_sketch_constraint"
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "pattern_ray"
        and isinstance(node.args[-1], ast.Constant)
        and node.args[-1].value == "fix"
        for node in calls
    )
    for gone in ("BASIC_DIMENSIONS", "pattern_notch_phase_callouts"):
        assert not hasattr(spec, gone) and not hasattr(drawing, gone)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "INSPECT" not in source and "GetText(3)" not in source
    assert "drum_tooth_to_cam_notch_clock_deg" not in (
        Path(spec.__file__).parents[1] / "config" / "tolerances.yaml"
    ).read_text(encoding="utf-8")


def test_pattern_notch_drawing_consumes_pure_specification() -> None:
    from _drawing_contract import drawing_specification_violations

    assert drawing.PATTERN_NOTCH_REF_ANGLE_DEG is spec.PATTERN_NOTCH_REF_ANGLE_DEG
    assert drawing_specification_violations(
        Path(drawing.__file__).read_text(encoding="utf-8")
    ) == ()


class _PatternDimension:
    """Faithful method/property and nullable-dispatch shape, not native evidence."""

    def __init__(self, fault=None):
        self.fault = fault

    def __bool__(self):
        raise AssertionError("nullable IDimension must be checked with is None")

    @property
    def FullName(self):
        return (
            "NotchPhase@NotchProfile@test.SLDPRT"
            if self.fault == "wrong_name"
            else "PatternNotchPhase@NotchProfile@test.SLDPRT"
        )

    @property
    def DrivenState(self):
        return 0 if self.fault == "driving" else 1

    @property
    def SystemValue(self):
        return math.radians(1.5 if self.fault == "cam_angle" else 90.0)

    def GetToleranceType(self):
        return 1 if self.fault == "basic" else 0


class _PatternDisplay:
    def __init__(self, fault=None):
        self.fault = fault
        self.dimension = None if fault == "null_dimension" else _PatternDimension(fault)
        self.text = {}

    @property
    def Type2(self):
        return 2 if self.fault == "linear" else 3

    def SetText(self, part, text):
        if self.fault != "parentheses_unmoved":
            self.text[part] = text

    def GetText(self, part):
        return self.text.get(part, "")

    def GetDimension2(self, index):
        assert index == 0
        return self.dimension


class _PatternAnnotation:
    def __init__(self, fault=None):
        self.display = None if fault == "null_display" else _PatternDisplay(fault)

    def GetSpecificAnnotation(self):
        return self.display


def _pattern_bindings(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        drawing, "dimension_name", lambda adapter, annotation: "PatternNotchPhase"
    )
    import _drawing_common

    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag", lambda value, *_names: value
    )
    monkeypatch.setattr(_drawing_common, "rebuild_drawing", lambda adapter, label: None)
    return SimpleNamespace(_attempt=lambda fn, default=None: fn())


def test_pattern_notch_prints_as_a_parenthesized_reference(monkeypatch) -> None:
    adapter = _pattern_bindings(monkeypatch)
    annotation = _PatternAnnotation()
    display = drawing._pattern_notch_reference(adapter, [annotation])
    assert display is annotation.display
    # Main's reference form, as (Ø9.575): f68549253's ShowParenthesis printed 90°.
    assert (display.GetText(1), display.GetText(2)) == ("(", ")")


@pytest.mark.parametrize(
    "fault",
    (
        "null_display", "null_dimension", "wrong_name", "driving", "cam_angle", "linear",
        "basic", "parentheses_unmoved",
    ),
)
def test_pattern_notch_reference_refuses_non_authoritative_native_state(
    monkeypatch, fault
) -> None:
    adapter = _pattern_bindings(monkeypatch)
    with pytest.raises(RuntimeError):
        drawing._pattern_notch_reference(adapter, [_PatternAnnotation(fault)])


@pytest.mark.parametrize("count", (0, 2))
def test_pattern_notch_reference_requires_one_named_locator(monkeypatch, count) -> None:
    adapter = _pattern_bindings(monkeypatch)
    with pytest.raises(RuntimeError, match="expected one actual PatternNotchPhase"):
        drawing._pattern_notch_reference(
            adapter, [_PatternAnnotation() for _ in range(count)]
        )
