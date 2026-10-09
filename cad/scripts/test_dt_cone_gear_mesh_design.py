"""Production gates for the real source-qualified cutter-native cone packet.

Actual 3D UNION, untared reads, full-source continuation and RootSweep proofs
are produced once by the explicit collector, not silently recomputed during a
native build. The reader checks that whole ALL20 packet and actual core
manufactured profiles. Faithful synthetic reader tests live separately.
"""

from __future__ import annotations

import math

import pytest

import _config
import cone_line
import dt_cone_gear_spec as spec
import dt_cone_mesh_domain as domain_supplier
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
def test_every_count_has_complete_actual_qualified_authority(teeth: int) -> None:
    spec.require_qualified_stock_family()
    data = spec.stock_form_mesh_data(teeth)
    assert data["qualification"] == "qualified"
    assert data["refusal"] is None
    assert spec.stock_form_profile(teeth).teeth == teeth


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_printed_setting_is_actual_and_quantized(teeth: int) -> None:
    profile = spec.stock_form_profile(teeth)
    outside = spec.outside_dia_mm(teeth)
    thickness = spec.tooth_thickness_mm(teeth)
    assert outside == round(outside, 2)
    assert thickness == pytest.approx(round(thickness, 3), abs=1e-9)
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
def test_actual_packet_meets_all_retained_rules(teeth: int) -> None:
    packet = spec.require_qualified_stock_family()
    row = next(row for row in packet["rows"] if row["teeth"] == teeth)
    selected = next(candidate for candidate in row["candidates"]
                    if candidate["setting"] == row["selected"])
    assert len(selected["actual_profile_cases"]) == 17
    for case in selected["actual_profile_cases"]:
        actual = case["calculation"]
        assert actual["qualification"] == "qualified"
        assert min(actual["margins"].values()) >= 0.0
        assert actual["all_corner_actual3d"]["stock_form_coverage_lower"] >= solve.UNION_COVERAGE_MIN
        full = actual["all_corner_actual3d"]
        assert full["production_source_qualified"] is True
        assert full["continuous_source_domain"]["scope"] == "FULL_PRODUCTION_SOURCE_DOMAIN"
        assert full["continuous_source_domain"]["production_source_domain"] is True
        for role, scope in (
            ("nominal_actual3d", "DESIGN_NOMINAL_SUBDOMAIN"),
            ("budget_actual3d", "BUDGET_CLOCK_NOMINAL_SUBDOMAIN"),
        ):
            subdomain = actual[role]
            assert subdomain["source_domain_proved"] is True
            assert subdomain["continuous_source_domain"]["scope"] == scope
            assert subdomain["continuous_source_domain"]["production_source_domain"] is False
            assert [read["actual_driver_phase_rad"] for read in subdomain["actual_read_phases"]] == [
                -index * math.pi for index in range(21)
            ]
            assert all(read["direct_actual_phase_query"] is True
                       and read["periodic_point_substitution"] is False
                       for read in subdomain["actual_read_phases"])
        assert actual["signed_read_matrix"]["all_reads_bounded"]
        for cell in actual["full_period_cells"]:
            proof = cell["root_air"]
            assert proof["qualified"] and not proof["root_is_carrying"]
            assert proof["driver_root_air_lower_mm"] >= spec.ROOT_AIR_MIN_MM
            assert proof["driven_root_air_lower_mm"] >= spec.DRUM_ROOT_AIR_MIN_MM
            assert proof["driver_root_proof"]["status"] == "PROVED"
            reverse = proof["driven_root_material_proof"]
            assert reverse["proof_schema"] == "finite-stock-directed-root-material/1"
            assert reverse["root_owner"] == "driven"
            assert reverse["root_air_lower_mm"] == proof["driven_root_air_lower_mm"]
            assert reverse["material_sweep"]["status"] == "PROVED"
    frozen = spec.stock_form_mesh_data(teeth)
    assert frozen["coverage_min"] >= solve.UNION_COVERAGE_MIN
    assert frozen["oblique_phase_bound_rad"] == pytest.approx(row["oblique_phase_bound_rad"])
    assert frozen["oblique_phase_bound_excluded_terms"] == spec.OBLIQUE_PHASE_EXCLUDED_TERMS
    assert frozen["phase_reserve_rad"] >= 0.0
    assert frozen["noncarrying_gap_mm"] >= 0.0
    assert frozen["te_bound_rad"] >= 0.0


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_actual_tool_corners_pay_support_land_floor_and_web(teeth: int, inputs: solve.DesignInputs) -> None:
    profiles = spec.manufacturing_corner_profiles(teeth)
    assert len(profiles) == 4
    minimum, maximum = spec.floor_limits_mm(teeth)
    assert 0.0 < minimum < maximum
    # Actual RootArc extrema define the inspection witness. A RootMAX filled
    # disk/scalar centre-air screen is not a collision or no-solution proof.
    assert minimum <= 2.0 * min(profile.root_radius_min_mm for profile in profiles)
    assert maximum >= 2.0 * max(profile.root_radius_max_mm for profile in profiles)
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
def test_operating_notch_up_is_a_physical_setup_not_a_planar_tare(teeth: int, inputs: solve.DesignInputs) -> None:
    data = spec.stock_form_mesh_data(teeth)
    placement = domain_supplier.nominal_placement_record(teeth)
    assert data["centre_mm"] == pytest.approx(inputs.centre_mm(teeth))
    assert "home_gap_clocking_rad" not in data
    assert "home_clocking_rad" not in data
    assert placement["driver_clocking_rad"] == pytest.approx(math.pi / teeth)
    assert placement["driven_clocking_rad"] == pytest.approx(math.pi)
    datum = domain_supplier.manufactured_datum_mapping(teeth)
    assert datum["mechanical_zero_rad"] == {"driver": 0.0, "driven": math.pi}
    assert datum["datum_tare_rad"] is None


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
