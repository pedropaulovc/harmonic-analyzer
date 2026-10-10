"""Offline contracts; these do not replace the final source-SHA native receipt."""

from __future__ import annotations

import ast
import inspect
import math
import struct
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_pd_transgear_knob_shaft as part
import draw_pd_transgear_knob_shaft as drawing
import pd_transgear_arm_plate_geometry as plate
import pd_transgear_knob_shaft_spec as spec
import pd_transgear_knob_thrust_ring_spec as ring
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
import paper_drive_stock_native
from paper_drive_stock_inspection import span_contact_points_mm, toothspace_gauge_contact_mm
from stock_form_cutter import CutterTemplate, StockFormProfile, translation_for_tangent_span


F_MACHINE_Z = -148.1


def _calls(function, name: str) -> list[ast.Call]:
    tree = ast.parse(inspect.getsource(function))
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name) and node.func.id == name
            or isinstance(node.func, ast.Attribute) and node.func.attr == name
        )
    ]


def _keyword(call: ast.Call, name: str) -> str:
    return ast.unparse(next(item.value for item in call.keywords if item.arg == name))


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.name == "pd-transgear-knob-shaft.SLDDRW"
    assert drawing.PDF.name == "pd-transgear-knob-shaft.pdf"
    assert drawing.PNG.name == "pd-transgear-knob-shaft_drawing.png"
    assert DRAWINGS_BY_NAME["pd_transgear_knob_shaft"].script == Path(drawing.__file__).resolve()


def test_native_stock_source_is_the_selected_12t_48dp_master() -> None:
    import pd_rack_pinion_spec as disc

    profile = spec.STOCK_PROFILE
    assert spec.TEETH == profile.teeth == disc.MESH_PINION_TEETH == 12
    assert spec.DIAMETRAL_PITCH == disc.DIAMETRAL_PITCH == 48
    assert profile.template == spec.CUTTER_TEMPLATE == CutterTemplate(12, 48, 20)
    assert profile.template.cutter_number == 8
    assert profile.template.reference_teeth == 12
    assert profile.radial_translation_mm == spec.RADIAL_SETTING
    assert profile.blank_radius_mm == spec.OUTSIDE_DIA / 2
    assert spec.OUTSIDE_DIA == 7.40
    assert spec.OUTSIDE_DIA_BAND == (0.0, -0.02)
    assert spec.CUTTER_DIA == 44.45
    assert spec.CUTTER_ARBOR_BORE == 22.225
    assert spec.CUTTER_SKU == "10-289-488"
    assert part.STOCK_PROFILE is profile
    assert "PROFILE SHIFT" not in spec.GEAR_DATA
    assert "RIGID TRANSLATION" in spec.GEAR_DATA


def test_span_is_actual_finite_contact_and_printed_limits_are_inverted() -> None:
    assert spec.SPAN_TEETH == 2
    assert spec.SPAN_PLACES == 4
    assert spec.SPAN_NOMINAL == pytest.approx(spec.STOCK_PROFILE.tangent_span_mm(2))
    assert spec.SPAN_DEVIATIONS == pytest.approx(
        (spec.SPAN_LIMITS[0] - spec.SPAN_NOMINAL, spec.SPAN_LIMITS[1] - spec.SPAN_NOMINAL)
    )
    for setting, tip in ((p.radial_translation_mm, p.blank_radius_mm) for p in spec.manufactured_profiles()):
        profile = StockFormProfile(12, spec.CUTTER_TEMPLATE, tip, setting)
        assert spec.RADIAL_SETTING_LIMITS[0] <= setting <= spec.RADIAL_SETTING_LIMITS[1]
        actual = profile.tangent_span_mm(2)
        error = 2 * profile.geometry_error_bound_mm
        assert spec.SPAN_LIMITS[0] - error <= actual <= spec.SPAN_LIMITS[1] + error
        a, b = span_contact_points_mm(profile, 2)
        assert math.dist(a, b) == pytest.approx(actual, abs=1e-10)
    assert spec.SPAN_PREFIX == "CONTROL SPAN 2 TEETH "
    assert "BISECTOR" in spec.SPAN_ORIENTATION and "MAXIMUM" in spec.SPAN_ORIENTATION
    # Rounded limits, not the old provisional setting band, define acceptance.
    lo, hi = spec.RADIAL_SETTING_LIMITS
    assert lo < spec.RADIAL_SETTING < hi
    outside = hi + 0.001
    rejected_span = StockFormProfile(12, spec.CUTTER_TEMPLATE, 3.69, outside).tangent_span_mm(2)
    assert rejected_span > spec.SPAN_LIMITS[1]
    with pytest.raises(ValueError):
        translation_for_tangent_span(
            12, spec.CUTTER_TEMPLATE, rejected_span, 2,
            translation_bounds_mm=spec.RADIAL_SETTING_LIMITS,
        )


def test_all_accepted_corners_keep_genuine_finite_ground_tip_in_air() -> None:
    for profile in spec.manufactured_profiles():
        tip = profile.flank_point(profile.template.flank_parameter_max)
        assert math.hypot(*tip) - profile.blank_radius_mm > profile.geometry_error_bound_mm
        assert 2 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
        assert profile.root_point(profile.root_half_angle_rad)[0] >= spec.ROOT_DEPTH_X_MIN
    with pytest.raises(ValueError):
        replace(spec.STOCK_PROFILE, blank_radius_mm=spec.CUTTER_TEMPLATE.tip_radius_mm + 0.02)


def test_front_core_and_actual_rear_terminal_window() -> None:
    assert spec.FRONT_CORE_AIR_MIN > 0.0
    assert spec.FULL_DEPTH_MIN >= spec.DISC_REAR_FROM_F_WORST
    assert spec.CUTTER_RUNOUT_END_WORST < spec.CUTTER_RUNOUT_MAX < spec.HUB_BORE_FROM_F_WORST
    assert spec.PINION_REAR_Z < spec.CUTTER_RUNOUT_END_Z < spec.HUB_BORE_FROM_F_WORST
    assert spec.CUTTER_AXIS_R == pytest.approx(
        spec.CUTTER_DIA / 2 + spec.STOCK_PROFILE.root_point(spec.STOCK_PROFILE.root_half_angle_rad)[0]
    )
    assert spec.CUTTER_AXIS_R != pytest.approx(spec.CUTTER_DIA / 2 + spec.ROOT_DIA / 2)
    # Negative controls: a larger catalogue disk and an enlarged core are not equivalent.
    assert spec.FULL_DEPTH_MAX + spec.cutter_runout(2.75 * 25.4, spec.RUNOUT_RISE_WORST) > spec.CUTTER_RUNOUT_MAX
    assert spec.ROOT_DIA_EXACT_MIN - 5.1 - spec.CORE_TOTAL_RUNOUT - spec.TOOTH_SPACE_RUNOUT_TIR_MM < 0.0


def test_real_d_core_thread_and_six_mm_g6_source() -> None:
    assert spec.CORE_DIA == 4.9 and spec.CORE_DIA_BAND == (0.0, -0.008)
    assert spec.CORE_FLAT_FROM_AXIS == 2.15 and spec.CORE_FLAT_BAND == (0.0, -0.015)
    assert spec.JOURNAL_DIA == 6.0 and spec.JOURNAL_DIA_BAND == (-0.004, -0.012)
    assert spec.THREAD == "#8-32" and spec.THREAD_CALLOUT == "#8-32 UNC"
    assert spec.RELIEF_DIA_MAX < spec.THREAD_ROOT_2A_MIN
    assert spec.TIP_CHAMFER_MAX < spec.THREAD_PITCH
    assert spec.THREAD_MAJOR_2A[0] <= spec.THREAD_BLANK_LIMITS[0]
    assert spec.THREAD_BLANK_LIMITS[1] <= spec.THREAD_MAJOR_2A[1]
    assert ring.LENGTH == 5.2


def test_machine_and_float_stations_are_unchanged() -> None:
    for local, machine in (
        (spec.TIP_Z, -172.0), (spec.THREAD_END_Z, -155.6),
        (spec.PINION_REAR_Z, -142.2), (spec.REAR_END_Z, -101.26),
    ):
        assert F_MACHINE_Z + local == pytest.approx(machine, abs=0.005)
    assert spec.CUP_FACE_STATION == pytest.approx(ring.LENGTH + plate.HUB_TO_BOSS + spec.END_FLOAT)
    assert spec.END_FLOAT > spec.END_FLOAT_SET_TOL
    assert spec.JOURNAL_LENGTH == pytest.approx(spec.CUP_FACE_STATION + spec.JOURNAL_REAR_EXTENSION)
    assert spec.OVERALL_LENGTH == pytest.approx(70.74, abs=0.005)


def test_builder_has_no_ideal_or_flat_slot_cutover_path() -> None:
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {
        "build_fixed_gear", "build_stock_form_gear", "PROFILE_SHIFT", "RUNOUT_SLOT_WIDTH",
        "V_RUNOUT_SLOT", "CUTTER_DIA_MAX", "cutter_arc_points",
    }
    straight = _calls(part._straight_stock_gaps, "ExtrusionParameters")
    assert {"FACE_WIDTH", "FULL_DEPTH"} <= {_keyword(call, "depth") for call in straight}
    native = _calls(part._straight_stock_gaps, "cut_order_native_segments")
    assert len(native) == 1
    end = _calls(part._stock_cutter_endcut, "author_cutter_endcut")
    assert len(end) == 1
    assert [ast.unparse(arg) for arg in end[0].args[1:]] == ["STOCK_PROFILE", "CUTTER_DIA", "FULL_DEPTH"]
    assert _calls(part._stock_cutter_endcut, "endcut_volume_bounds_mm3")
    assert _calls(part.build, "author_span") and _calls(part.build, "author_root_envelope")
    assert _calls(part.build, "apply_span_limits")
    body = inspect.getsource(part.build)
    assert body.index("_journal_profile(") < body.index("_stock_cutter_endcut(")
    assert body.index("_stud_profile(") < body.index("_stock_cutter_endcut(")
    assert _calls(part._native_volume_check, "measure_one_solid_body_volume")
    for builder in (part._straight_stock_gaps, part._stock_cutter_endcut):
        stock_patterns = _calls(builder, "pattern_stock_feature")
        assert len(stock_patterns) == 1 and ast.unparse(stock_patterns[0].args[2]) == "TEETH"
    patterns = _calls(paper_drive_stock_native.pattern_stock_feature, "CircularPatternParameters")
    assert len(patterns) == 1 and _keyword(patterns[0], "count") == "count"
    assert _keyword(patterns[0], "geometry_pattern") == "False"


def test_d_flat_uses_signed_physical_round_tool_end_and_real_neck() -> None:
    source = inspect.getsource(part._cut_core_flat)
    assert "CORE_FRONT_FROM_F" in source and "CORE_FLAT_FROM_AXIS" in source
    assert "CORE_FLAT_CUT_END_Z" in source and "CORE_FLAT_TOOL_END_RADIUS" in source
    assert "both_directions=True" in source
    assert "CoreFlatProfile" in source and "FlatToAxis" in source and "FlatEnd" in source
    assert _calls(part._cut_core_flat, "_native_arc")
    assert _calls(part._create_sketch, "suppress_dimension_input")
    assert spec.FRONT_RELIEF_DIA == 4.0
    assert spec.FRONT_RELIEF_WIDTH == 0.4
    assert spec.FRONT_CORNER_RADIUS == 0.05
    assert spec.FRONT_CORNER_RADIUS_MAX == 0.1
    assert spec.CORE_ACTIVE_LENGTH == pytest.approx(4.85)
    assert -spec.CORE_FLAT_CUT_END_Z == pytest.approx(0.110)
    upper, lower = spec.CORE_FLAT_CUT_END_BAND
    assert -spec.CORE_FLAT_CUT_END_Z + lower == pytest.approx(0.050)
    assert -spec.CORE_FLAT_CUT_END_Z + upper == pytest.approx(0.170)
    assert spec.FRONT_RELIEF_WIDTH_MIN - 0.170 >= 0.100 - 1e-12
    # .XXX general ±.130 on the terminal could overrun F; not equivalent.
    assert 0.110 - 0.130 < 0.0
    # The old4.050 neck misses the adopted full-relative-axis D-plane charge.
    assert 2.150 - 0.015 - ((4.050 + 0.130) / 2 + 0.050) < 0.0
    assert 2.150 - 0.015 - ((spec.FRONT_RELIEF_DIA + 0.130) / 2 + 0.050) > 0.0


def test_neck_radius_is_real_equal_tangent_geometry_not_a_dummy_carrier() -> None:
    arcs = _calls(part._stud_profile, "_native_arc")
    assert len(arcs) == 2
    radius_dimensions = _calls(part._stud_profile, "add_sketch_dimension")
    assert any(
        [ast.unparse(arg) for arg in call.args][-4:] == [
            "front_corner", "None", "'radial'", "FRONT_CORNER_RADIUS"
        ]
        for call in radius_dimensions
    )
    assert "equal physical neck radii" in inspect.getsource(part._stud_profile)
    assert "FrontCornerRadius" in inspect.getsource(part._apply_neck_and_flat_limits)
    assert spec.FRONT_CORNER_RADIUS_TOL_TYPE == 3
    hi, lo = spec.FRONT_CORNER_RADIUS_BAND
    assert spec.FRONT_CORNER_RADIUS + lo == 0.0
    assert spec.FRONT_CORNER_RADIUS + hi == pytest.approx(0.1)
    for function in (part._stud_profile, part._journal_profile):
        assert _calls(function, "_revolve_profile")
    assert _calls(part._revolve_profile, "create_revolve")
    arc_call = _calls(part._native_arc, "CreateArc")
    assert len(arc_call) == 1 and len(arc_call[0].args) == 10
    assert ast.unparse(arc_call[0].args[-1]) == "1"
    assert "arc is None" in inspect.getsource(part._native_arc)


def test_complete_nominal_native_volume_uses_bounded_rear_disk_and_true_d() -> None:
    end_lo, end_hi = spec.endcut_volume_bounds_mm3(absolute_error_mm3=0.05 / spec.TEETH)
    assert 0.0 < end_lo <= end_hi
    lower, upper = spec.expected_volume_bounds_mm3()
    r = spec.CORE_DIA / 2
    h = spec.CORE_FLAT_FROM_AXIS
    flat_removed = (r*r*math.acos(h/r) - h*math.sqrt(r*r-h*h)) * spec.CORE_ACTIVE_LENGTH
    straight = spec.TEETH * spec.STOCK_PROFILE.gap_area_mm2 * spec.FULL_DEPTH
    before_end = (
        math.pi * spec.STOCK_PROFILE.blank_radius_mm**2 * spec.FACE_WIDTH
        + part.V_STUD + part.V_JOURNAL - flat_removed - straight
    )
    assert lower <= before_end - spec.TEETH * (end_lo + end_hi) / 2 <= upper
    assert upper - lower <= 0.051
    assert before_end > upper  # omitting the true terminal cannot meet the oracle
    assert _calls(part.build, "expected_volume_bounds_mm3")
    with pytest.raises(ValueError):
        spec.endcut_volume_bounds_mm3(full_depth_mm=spec.FACE_WIDTH + 0.1)
    with pytest.raises(ValueError):
        spec.endcut_volume_bounds_mm3(profile=replace(spec.STOCK_PROFILE, teeth=13))


def test_every_native_dimension_is_placed_once_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_DIMENSIONS["CoreFlatProfile"] == {"FlatToAxis", "FlatEnd", "FlatToolRadius"}
    assert spec.DRAWING_DIMENSIONS["SpanProfile"] == {"ToothSpan"}
    assert spec.DRAWING_DIMENSIONS["RootInspectionProfile"] == {"RootEnvelope"}
    assert {"FullDepth", "CutterRunout"} <= spec.DRAWING_DIMENSIONS["StudProfile"]
    assert "RootEnvelope" in drawing.END_KEEP and "ToothSpan" in drawing.END_KEEP
    assert "FlatToAxis" in drawing.SIDE_KEEP


def test_model_bands_and_source_linked_properties() -> None:
    bands = model_toleranced_dimensions(part)
    assert bands[("StudProfile", "CoreDia")] == "*deviations(CORE_DIA_BAND)"
    assert bands[("JournalProfile", "JournalDia")] == "*deviations(JOURNAL_DIA_BAND)"
    assert bands[("CoreFlatProfile", "FlatToAxis")] == "*deviations(CORE_FLAT_BAND)"
    assert bands[("StudProfile", "OutsideDia")] == "*deviations(OUTSIDE_DIA_BAND)"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(source, filename=drawing.__file__)
    for property_name in ("Gear Data", "Manufacturing Notes", "Root Acceptance"):
        assert property_name in inspect.getsource(part.build)
        assert property_name in inspect.getsource(drawing.build)
    assert "datums=PART_DATUMS" in inspect.getsource(part.build)
    assert "controls=GEOMETRIC_CONTROLS" in inspect.getsource(part.build)
    assert "JOURNAL_DIA" in inspect.getsource(drawing.build)

    controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
    assert set(drawing.CONTROL_ATTACHMENTS) == set(controls)
    assert drawing.CONTROL_ATTACHMENTS["core_total_runout"][0] != drawing.CONTROL_ATTACHMENTS["front_neck_total_runout"][0]
    for key, control in controls.items():
        assert control.datums == ("A",)
        assert float(control.tolerance) == spec.CORE_TOTAL_RUNOUT
    assert f"Ø{spec.ROOT_DIA_MIN:.2f} MIN" in spec.ROOT_ACCEPTANCE
    assert "Tooth Cut Features" in inspect.getsource(part.build)
    assert "Tooth Cut Features" in inspect.getsource(drawing.build)
    callouts = _calls(drawing.build, "add_toothspace_callout")
    assert len(callouts) == 1
    assert _keyword(callouts[0], "profile") == "STOCK_PROFILE"
    assert _keyword(callouts[0], "actual_pin_diameter_mm") == "TOOTH_SPACE_GAUGE_PIN_DIA_MM"
    assert _keyword(callouts[0], "rotate_rad") == "math.pi / TEETH"
    assert _keyword(callouts[0], "axial_stations_mm") == "(0.0,)"
    assert _keyword(callouts[0], "tooth_features") == "tooth_features"
    assert (
        "require_source_control(source_properties[TOOTH_SPACE_CALLOUT_PROPERTY], TOOTH_SPACE_CALLOUT,"
        in " ".join(inspect.getsource(drawing.build).split()).replace("( ", "(")
    )

def test_supported_certified_pin_inspects_all_actual_finite_corners() -> None:
    pin_diameter = spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM
    assert pin_diameter == 1.0
    contacts = spec.tooth_space_gauge_contacts(pin_diameter)
    profiles = spec.manufactured_profiles()
    assert len(contacts) == len(profiles) == 4
    for profile, contact in zip(profiles, contacts, strict=True):
        assert profile.flank_parameter_min < contact.parameter < profile.flank_parameter_max
        assert contact.root_air_mm > 0.0 and contact.tip_air_mm > 0.0
        assert contact.center_radius_error_bound_mm > 0.0
        assert math.dist(contact.flank_point_mm, (contact.center_radius_mm, 0.0)) == pytest.approx(pin_diameter / 2)
    assert min(c.root_air_mm for c in contacts) == spec.TOOTH_SPACE_GAUGE_ROOT_AIR_MIN_MM
    assert min(c.tip_air_mm for c in contacts) == spec.TOOTH_SPACE_GAUGE_TIP_AIR_MIN_MM


def test_indicator_grade_has_one_live_source_and_span_does_not_certify_eccentricity() -> None:
    from _gear_quality import toothspace_runout_tir_mm

    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM == toothspace_runout_tir_mm() == 0.005
    assert spec.TOOTH_SPACE_CALLOUT.splitlines()[0] == "TOOTH SPACE RADIAL INDICATOR TIR 0.005 MAX TO A"
    assert spec.TOOTH_SPACE_CALLOUT_PROPERTY == "Tooth Space Inspection"
    assert all(word not in spec.TOOTH_SPACE_CALLOUT for word in ("CANDIDATE", "TODO", "GATE"))
    contact = toothspace_gauge_contact_mm(spec.STOCK_PROFILE, spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    eccentricity = 0.004
    a, b = span_contact_points_mm(spec.STOCK_PROFILE, spec.SPAN_TEETH)
    tree = ast.parse(inspect.getsource(spec))
    grade_assignments = [
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "TOOTH_SPACE_RUNOUT_TIR_MM" for target in node.targets)
    ]
    assert len(grade_assignments) == 1
    assert isinstance(grade_assignments[0], ast.Call)
    assert isinstance(grade_assignments[0].func, ast.Name)
    assert grade_assignments[0].func.id == "toothspace_runout_tir_mm"
    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM > 0.0
    moved = tuple((x + eccentricity, y) for x, y in (a, b))
    assert math.dist(*moved) == pytest.approx(math.dist(a, b))
    indication = (contact.center_radius_mm + eccentricity) - (contact.center_radius_mm - eccentricity)
    assert indication == pytest.approx(2 * eccentricity)
    assert indication > spec.TOOTH_SPACE_RUNOUT_TIR_MM


def test_native_inspection_callout_keeps_live_index_and_certified_pin_rows() -> None:
    from _gear_quality import (
        pinion_pitch_index_deviation_mm,
        pitch_index_measurement_uncertainty_mm,
    )

    assert spec.PITCH_INDEX_DEVIATION_MM == pinion_pitch_index_deviation_mm() > 0.0
    assert spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM == pitch_index_measurement_uncertainty_mm() > 0.0
    assert spec.PITCH_INDEX_REFERENCE_RADIUS_MM == spec.PITCH_DIA / 2.0
    contact = toothspace_gauge_contact_mm(spec.STOCK_PROFILE, spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    assert spec.PITCH_INDEX_REFERENCE_RADIUS_MM != pytest.approx(contact.center_radius_mm)
    assert spec.TOOTH_SPACE_CALLOUT.splitlines() == [
        f"TOOTH SPACE RADIAL INDICATOR TIR {spec.TOOTH_SPACE_RUNOUT_TIR_MM:.3f} MAX TO A",
        f"PITCH INDEX RANGE+2U {spec.PITCH_INDEX_DEVIATION_MM} mm MAX AT REF Ø{spec.PITCH_DIA:.3f}",
        f"ALL SPACES + WRAP; ABS POSITION U {spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM} mm MAX",
        f"CERTIFIED PIN Ø{spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM:.3f} mm; ALL {spec.TEETH} SPACES",
    ]
    tree = ast.parse(inspect.getsource(spec))
    for field, getter in (
        ("PITCH_INDEX_DEVIATION_MM", "pinion_pitch_index_deviation_mm"),
        ("PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM", "pitch_index_measurement_uncertainty_mm"),
    ):
        assignments = [
            node.value for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == field for target in node.targets)
        ]
        assert len(assignments) == 1
        assert isinstance(assignments[0], ast.Call)
        assert isinstance(assignments[0].func, ast.Name)
        assert assignments[0].func.id == getter
    receiving = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "require_pitch_index_errors_mm"
    )
    delegates = [
        node for node in ast.walk(receiving)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "require_pitch_index_measurements_mm"
    ]
    assert len(delegates) == 1
    assert {
        keyword.arg: keyword.value.id for keyword in delegates[0].keywords
        if isinstance(keyword.value, ast.Name)
    } == {
        "measured_index_errors_mm": "measured_index_errors_mm",
        "required_stations": "PITCH_INDEX_STATIONS",
        "relative_deviation_limit_mm": "PITCH_INDEX_DEVIATION_MM",
        "absolute_measurement_uncertainty_mm": "PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM",
    }


def test_index_receiving_requires_every_space_wrap_and_paid_uncertainty() -> None:
    assert spec.PITCH_INDEX_STATIONS == tuple(range(spec.TEETH + 1))
    uncertainty = spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM
    grade = spec.PITCH_INDEX_DEVIATION_MM
    assert 0.0 < 2.0 * uncertainty <= grade
    measured = dict.fromkeys(spec.PITCH_INDEX_STATIONS, 0.0)
    assert spec.require_pitch_index_errors_mm(measured) == pytest.approx(2.0 * uncertainty)
    for missing in (0, spec.TEETH):
        incomplete = {station: value for station, value in measured.items() if station != missing}
        with pytest.raises(ValueError, match="every specified station"):
            spec.require_pitch_index_errors_mm(incomplete)
    with pytest.raises(ValueError, match="every specified station"):
        spec.require_pitch_index_errors_mm({**measured, spec.TEETH + 1: 0.0})
    unpaid_pass = {**measured, spec.TEETH // 2: grade - uncertainty}
    assert max(unpaid_pass.values()) - min(unpaid_pass.values()) < grade
    with pytest.raises(ValueError, match="paid pitch/index range"):
        spec.require_pitch_index_errors_mm(unpaid_pass)
    with pytest.raises(ValueError, match="finite numeric"):
        spec.require_pitch_index_errors_mm({**measured, spec.TEETH: math.nan})


@pytest.mark.parametrize("pin_diameter", [0.001, 10.0, 0.0, math.nan])
def test_wrong_inspection_pin_cannot_certify_an_unsupported_contact(pin_diameter: float) -> None:
    with pytest.raises(ValueError):
        toothspace_gauge_contact_mm(spec.STOCK_PROFILE, pin_diameter)


def test_shared_callout_refuses_circle_wrong_endpoint_tangent_and_native_status(monkeypatch) -> None:
    import paper_drive_stock_drawing as ink

    profile = spec.STOCK_PROFILE
    contact = toothspace_gauge_contact_mm(profile, spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    phase = math.pi / spec.TEETH
    point_xy = ink._rotate(contact.flank_point_mm, phase)
    point = (point_xy[0] / 1000, point_xy[1] / 1000, 0.0)
    angle = profile.template.half_space_base_angle_rad + contact.parameter + phase
    tangent = (math.cos(angle), math.sin(angle), 0.0)
    success = struct.unpack("<d", struct.pack("<ii", 1, 0))[0]
    ends = [
        (*tuple(value / 1000 for value in ink._rotate(profile.flank_point(u), phase)), 0.0)
        for u in (profile.flank_parameter_min, profile.flank_parameter_max)
    ]

    class Curve:
        circular = False
        status = success
        direction = tangent
        shift = 0.0

        def IsCircle(self):
            return self.circular

        def IsLine(self):
            return False

        def GetClosestPointOn(self, x, y, z):
            return (x + self.shift, y, z, contact.parameter, 0.0)

        def Evaluate2(self, parameter, derivatives):
            assert parameter == contact.parameter and derivatives == 1
            return (*point, *self.direction, self.status)

    curve = Curve()
    params = SimpleNamespace(
        UMinValue=profile.flank_parameter_min,
        UMaxValue=profile.flank_parameter_max,
        StartPoint=ends[0], EndPoint=ends[1],
    )
    edge = SimpleNamespace(GetCurve=lambda: curve, GetCurveParams3=lambda: params)
    monkeypatch.setattr(ink, "_early_bound", lambda value, interface: value)
    ink._validate_flank_edge(edge, profile, contact, phase, (0.0,))
    curve.circular = True
    with pytest.raises(RuntimeError, match="OD/root"):
        ink._validate_flank_edge(edge, profile, contact, phase, (0.0,))
    curve.circular = False
    params.EndPoint = (ends[1][0] + 0.001, ends[1][1], 0.0)
    with pytest.raises(RuntimeError, match="endpoints"):
        ink._validate_flank_edge(edge, profile, contact, phase, (0.0,))
    params.EndPoint = ends[1]
    curve.direction = (0.0, 0.0, 1.0)
    with pytest.raises(RuntimeError, match="tangent"):
        ink._validate_flank_edge(edge, profile, contact, phase, (0.0,))
    curve.direction = tangent
    curve.status = 0.0
    with pytest.raises(RuntimeError, match="evaluation failed"):
        ink._validate_flank_edge(edge, profile, contact, phase, (0.0,))
    curve.status = success
    curve.shift = 0.001
    with pytest.raises(RuntimeError, match="gauge contact"):
        ink._validate_flank_edge(edge, profile, contact, phase, (0.0,))


def test_shared_callout_requires_source_roundtrip_body_and_tooth_feature(monkeypatch) -> None:
    import paper_drive_stock_drawing as ink

    body = SimpleNamespace(GetType=lambda: 0)
    foreign_body = SimpleNamespace(GetType=lambda: 0)
    tooth_feature, blank_feature = object(), object()
    first_face = SimpleNamespace(GetBody=lambda: body, GetFeature=lambda: tooth_feature)
    second_face = SimpleNamespace(GetBody=lambda: body, GetFeature=lambda: blank_feature)
    drawing_edge = object()
    canonical = SimpleNamespace(
        GetBody=lambda: body,
        GetTwoAdjacentFaces2=lambda: (first_face, second_face),
    )
    extension = SimpleNamespace(GetCorrespondingEntity2=lambda edge: canonical)
    source = SimpleNamespace(
        GetType=lambda: 1, GetBodies2=lambda kind, visible: (body,),
        Extension=extension, FeatureByName=lambda name: tooth_feature,
    )
    view = SimpleNamespace(
        ReferencedDocument=source, GetCorrespondingEntity=lambda edge: drawing_edge,
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    monkeypatch.setattr(ink, "_early_bound", lambda value, interface: value)
    assert ink._source_edge(adapter, view, drawing_edge, ("StraightToothGap",)) is canonical
    canonical.GetBody = lambda: foreign_body
    with pytest.raises(RuntimeError, match="another body"):
        ink._source_edge(adapter, view, drawing_edge, ("StraightToothGap",))
    canonical.GetBody = lambda: body
    view.GetCorrespondingEntity = lambda edge: object()
    with pytest.raises(RuntimeError, match="roundtrip"):
        ink._source_edge(adapter, view, drawing_edge, ("StraightToothGap",))
    view.GetCorrespondingEntity = lambda edge: drawing_edge
    first_face.GetFeature = lambda: blank_feature
    with pytest.raises(RuntimeError, match="tooth-cut feature"):
        ink._source_edge(adapter, view, drawing_edge, ("StraightToothGap",))
    extension.GetCorrespondingEntity2 = lambda edge: None
    with pytest.raises(RuntimeError, match="no source correspondence"):
        ink._source_edge(adapter, view, drawing_edge, ("StraightToothGap",))


def test_shared_callout_reads_real_linked_ink_and_postrebuild_native_edge() -> None:
    import paper_drive_stock_drawing as ink

    source = inspect.getsource(ink.add_toothspace_callout)
    assert _calls(ink.add_toothspace_callout, "model_point_in_view")
    assert _calls(ink.add_toothspace_callout, "add_property_linked_callout")
    assert _calls(ink.add_toothspace_callout, "GetCustomInfoValue")
    assert _calls(ink.add_toothspace_callout, "GetText")
    assert "PropertyLinkedText" in source
    assert "GetAttachedEntities3" in source and "GetAttachedEntityTypes" in source
    assert "_source_edge" in source and "_validate_flank_edge" in source
    assert "1e-6" in inspect.getsource(ink._validate_flank_edge)  # mm:1nm native kernel
    assert "except" not in source


def test_single_native_solid_volume_has_no_adapter_fallback(monkeypatch) -> None:
    import paper_drive_stock_native as native

    class Body:
        def GetType(self):
            return 0

        def GetMassProperties(self, density):
            assert density == 1.0
            return (0.0, 0.0, 0.0, 1.25e-9, 0.0, 1.25e-9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class NativePart:
        def __init__(self, bodies):
            self.bodies = bodies

        def GetBodies2(self, kind, visible_only):
            assert kind == 0 and visible_only is False
            return self.bodies

    monkeypatch.setattr(native, "_early_bound", lambda value, interface: value)
    model = NativePart((Body(),))
    adapter = SimpleNamespace(currentModel=model)
    assert native.measure_one_solid_body_volume(adapter) == pytest.approx(1.25)
    for bodies in (None, (), (None,), (Body(), Body())):
        model.bodies = bodies
        with pytest.raises(RuntimeError, match="one native solid"):
            native.measure_one_solid_body_volume(adapter)


def test_part_record_and_running_finishes() -> None:
    config = _config.parts("pd-transgear-knob-shaft")
    assert config["number"] == "MHA-PD-008"
    assert config["material_specification"] == "SAE 1018 CF bar, ASTM A108-24"
    assert int(config["quantity"]) == 1
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    assert faces["journal"].diameter_mm == spec.JOURNAL_DIA
    assert faces["core"].diameter_mm == spec.CORE_DIA
    assert spec.CORE_FRONT_Z < faces["core"].contains_z_mm < spec.CORE_REAR_Z
    assert drawing.DIMENSION_CALLOUTS_BELOW == {"TipChamfer": spec.CHAMFER_CALLOUT}
