"""Re-derive the cutter-native cone design from config, actual forms and settings.

Supported branch-existence coverage is deliberately NOT a true contact ratio.
Its retained named floors are separate from full-period carrying contact and
continuous handover. Actual process/tip/thickness corners and numerical bounds
are paid by the design solver. The three-dimensional oblique contact/TE study
is an additional acceptance, never substituted by this deep planar screen.
"""

from __future__ import annotations

import math

import pytest

import _config
import cone_line
import dt_cone_gear_spec as spec
import dt_cylinder_gear_spec as drum
from diagnostics import solve_stock_form_cones as solve
from stock_form_cutter import translation_for_pitch_tooth_thickness


@pytest.fixture(scope="module")
def inputs() -> solve.DesignInputs:
    return solve.configured_inputs()


def test_inputs_match_the_configured_train(inputs: solve.DesignInputs) -> None:
    assert drum.DIAMETRAL_PITCH == spec.DIAMETRAL_PITCH == inputs.diametral_pitch
    assert drum.PRESSURE_ANGLE_DEG == spec.PRESSURE_ANGLE_DEG == inputs.pressure_angle_deg
    assert spec.MODULE_MM == pytest.approx(25.4 / inputs.diametral_pitch)
    assert drum.TEETH == int(_config.machine("gear_train", "cylinder_teeth"))
    assert spec.CONFIGURATION_TEETH == tuple(range(6, int(_config.machine("gear_train", "fundamental_cone_teeth")) + 1, 6))
    assert spec.BLANK_DIA_BAND == solve.BLANK_DIA_BAND == (0.10, -0.10)
    assert spec.TOOTH_THICKNESS_BAND == solve.TOOTH_THICKNESS_BAND == (0.075, -0.075)
    assert spec.BACKLASH_ACCEPTANCE_MM == solve.BACKLASH_ACCEPTANCE_MM == (0.06, 0.41)
    assert inputs.maximum_bore_mm(6) == pytest.approx(0.849)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_every_count_is_selected_or_explicitly_refused(teeth: int) -> None:
    data = spec.stock_form_mesh_data(teeth)
    assert data["qualification"] in {"qualified", "refused"}
    if data["qualification"] == "refused":
        assert data["refusal"]
        with pytest.raises(ValueError, match="refused"):
            spec.stock_form_profile(teeth)
    else:
        assert not data["refusal"]
        assert spec.stock_form_profile(teeth).teeth == teeth


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_printed_setting_is_actual_and_quantized(teeth: int) -> None:
    profile = spec.stock_form_profile(teeth)
    outside = spec.outside_dia_mm(teeth)
    thickness = spec.tooth_thickness_mm(teeth)
    assert outside == round(outside, 2)
    assert thickness == round(thickness, 3)
    assert profile.blank_radius_mm == pytest.approx(outside / 2.0)
    assert profile.pitch_tooth_thickness_mm == pytest.approx(thickness, abs=1e-9)
    assert profile.radial_translation_mm == pytest.approx(
        translation_for_pitch_tooth_thickness(teeth, profile.template, thickness), abs=1e-9,
    )
    if teeth == 6:
        assert profile.template.name == "DT6-FORM1"
        assert profile.template.cutter_number is None
        assert profile.template.reference_teeth == 6
        assert profile.template.source
    else:
        assert profile.template.reference_teeth == profile.template.teeth_range[0]
        assert profile.template.cutter_number is not None


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_printed_mesh_meets_its_actual_design_rules(teeth: int, inputs: solve.DesignInputs) -> None:
    """Refused designs fail the production gate rather than gaining a fallback."""
    from diagnostics import oblique_cone_mesh_study as study

    profile = spec.stock_form_profile(teeth)
    domain = solve._translation_domain(teeth, profile.template, inputs)
    translations = solve._corner_translations(teeth, profile.template, spec.tooth_thickness_mm(teeth), domain)
    geometry_margins = solve.geometry_margins(
        teeth, spec.outside_dia_mm(teeth), translations, profile.template, inputs,
    )
    assert min(geometry_margins.values()) >= 0.0
    geometry, home = solve.oblique_section_geometry(teeth), solve.home_clocking_rad(teeth)
    pair = study.ContactPair(
        f"cone T{teeth:03d} acceptance", profile, inputs.drum_nominal,
        study.placement_from_geometry(geometry, home),
    )
    cone_corners = spec.manufacturing_corner_profiles(teeth)
    pose_domain = study.configured_pose_domain(
        teeth, inputs, cone_radius_upper_mm=max(corner.blank_radius_mm for corner in cone_corners),
    )
    ball = (
        study.profile_motion_ball(profile, cone_corners)
        + study.profile_motion_ball(inputs.drum_nominal, inputs.drum_corners)
    )
    radial, axial = study.complete_pose_errors(pair, pose_domain, profile_motion_mm=ball)
    cam_clearance = study.configured_cam_exclusion(
        pair, radial_error_mm=radial, profile_motion_mm=ball,
    )
    assert cam_clearance["qualified"], cam_clearance
    actual = study.qualify_actual_pair(
        pair, pose_ball_mm=ball, phases=129, maximum_error_mm=inputs.maximum_error_mm,
        radial_error_mm=radial, axial_error_mm=axial,
        read_phases_rad=tuple(-k * math.pi for k in range(21)),
        planar_centre_mm=inputs.centre_mm(teeth), home=home,
    )
    assert actual["qualification"] == "qualified", actual
    assert min(actual["margins"].values()) >= 0.0, actual
    assert actual["margins"]["cone_root_air_mm"] >= 0.0, actual
    assert actual["margins"]["drum_root_air_mm"] >= 0.0, actual
    # Main's final gate is ALL-count actual 3D branch UNION, including real
    # finite corners/edges. The old small-count FF/CR floors are comparisons.
    required = solve.UNION_COVERAGE_MIN
    frozen = spec.stock_form_mesh_data(teeth)
    coverage_min = actual["all_corner_actual3d"]["stock_form_coverage_lower"]
    assert coverage_min >= required, actual
    assert frozen["coverage_min"] == pytest.approx(coverage_min, abs=1e-9)
    assert frozen["oblique_phase_bound_rad"] == pytest.approx(actual["oblique_phase_bound_rad"], abs=1e-9)
    assert frozen["phase_reserve_rad"] >= 0.0
    assert frozen["noncarrying_gap_mm"] >= 0.0
    assert frozen["te_bound_rad"] >= 0.0


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_actual_tool_corners_pay_support_land_floor_and_web(teeth: int, inputs: solve.DesignInputs) -> None:
    profiles = spec.manufacturing_corner_profiles(teeth)
    assert len(profiles) == 4
    minimum, maximum = spec.floor_limits_mm(teeth)
    assert maximum - minimum >= 0.04 - 1e-9
    closing = inputs.centre_mm(teeth) - inputs.runout_mm
    assert closing - max(gear.blank_radius_mm for gear in inputs.drum_corners) - maximum / 2.0 >= 0.02 - 1e-9
    assert closing - max(gear.blank_radius_mm for gear in inputs.drum_corners) - (maximum + 0.001) / 2.0 < 0.02 + 1e-9
    for profile in profiles:
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.tip_land_mm >= max(0.10, 0.25 * spec.MODULE_MM)
        assert profile.root_radius_min_mm * 2.0 >= minimum - 1e-9
        assert profile.root_radius_max_mm * 2.0 <= maximum + 1e-9
        assert profile.root_radius_min_mm - inputs.maximum_bore_mm(teeth) / 2.0 >= inputs.web_min_mm(teeth) - 1e-9
    if teeth == 6:
        assert min(profile.root_radius_min_mm for profile in profiles) >= 1.173 - 1e-9


def test_fixed_drum_uses_real_finite_process_corners() -> None:
    assert drum.STOCK_FORM.teeth == drum.TEETH
    assert drum.STOCK_FORM.template.reference_teeth == 55
    assert drum.STOCK_FORM.radial_translation_mm == pytest.approx(
        drum.PITCH_DIA / 2.0 - drum.CUTTER_TEMPLATE.pitch_radius_mm,
    )
    assert drum.OUTSIDE_DIA_BAND == (0.0, -0.02)
    assert drum.WHOLE_DEPTH_BAND == (0.05, 0.0)
    for profile in drum.manufacturing_corner_profiles():
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.radial_translation_mm == pytest.approx(
            profile.blank_radius_mm - profile.template.root_radius_mm - profile.plunge_mm,
        )


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_frozen_planar_centre_and_physical_zero_follow_source(teeth: int, inputs: solve.DesignInputs) -> None:
    data = spec.stock_form_mesh_data(teeth)
    assert data["centre_mm"] == pytest.approx(inputs.centre_mm(teeth))
    assert data["home_clocking_rad"] == pytest.approx(solve.home_clocking_rad(teeth))
    assert solve.home_clocking_rad(teeth)[0] == pytest.approx(math.pi / teeth)
    assert solve.home_clocking_rad(teeth)[1] == pytest.approx(-math.radians(_config.machine("gear_train", "cylinder_lock_phase_deg")))


def test_drive_train_clearance_scans_use_the_printed_cone_tip() -> None:
    # Native source consumers remain a separate retained assembly acceptance.
    import build_dt_drive_train_assembly as assembly

    assert assembly._TIP120 == pytest.approx((spec.outside_dia_mm(120) + spec.BLANK_DIA_BAND[0]) / 2.0)
    for teeth in spec.CONFIGURATION_TEETH:
        assert assembly._cone_tip_radius_max(teeth) == pytest.approx((spec.outside_dia_mm(teeth) + spec.BLANK_DIA_BAND[0]) / 2.0)
    assert assembly.PINION_T120_CONCENTRIC["shoulder air"] >= 0.25


def test_face_width_band_holds_the_drum_engaged_zone() -> None:
    import cone_stack_end_play
    import dt_cone_gear_shaft_spec
    import dt_cone_gear_stack

    old_centre_north = (cone_line.CONE_FACE_STATION_REFERENCE - 6.0) / 2.0
    new_centre_north = (cone_line.CONE_FACE_STATION_REFERENCE - spec.FACE_WIDTH) / 2.0
    engaged_zone = tuple(edge + old_centre_north - new_centre_north for edge in (-0.75, 1.35))
    cone_drum_z_stack = (-1.10, 0.55)
    lower = spec.FACE_WIDTH + spec.FACE_WIDTH_BAND[1]
    station_upper, station_lower = dt_cone_gear_stack.STATION_BAND
    collar = dt_cone_gear_shaft_spec.printed_band("CollarWidth")
    cone_north = station_upper + collar + cone_stack_end_play.STACK_FLOAT[1] + cone_stack_end_play.SHAFT_END_PLAY[1]
    cone_south = -station_lower + collar
    north = lower / 2.0 - engaged_zone[1] - cone_drum_z_stack[1] - cone_south
    south = lower / 2.0 + engaged_zone[0] - cone_drum_z_stack[0] - cone_north
    assert min(north, south) >= cone_stack_end_play.MARGIN_SPARE
