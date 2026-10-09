"""Pure contracts for the printed-lattice cutter-native cone design solver."""

from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace

import pytest

from diagnostics import solve_stock_form_cones as solve


def test_printed_lattice_is_inclusive_without_rounding_inward() -> None:
    assert list(solve.lattice_ticks(1.23, 1.25, 0.01)) == [123, 124, 125]
    assert list(solve.lattice_ticks(1.2301, 1.2499, 0.01)) == [124]
    assert list(solve.lattice_ticks(-0.025, -0.015, 0.01)) == [-2]
    assert not solve.lattice_ticks(0.0011, 0.0019, 0.001)


def test_actual_scalar_inversion_has_no_coarse_grid_fallback() -> None:
    answer = solve._bisect_increasing(lambda value: value * value + value, 2.0, 0.0, 2.0)
    assert answer == pytest.approx(1.0, abs=1e-14)
    with pytest.raises(ValueError, match="outside monotone bounds"):
        solve._bisect_increasing(lambda value: value, -1.0, 0.0, 2.0)


def _report(**changes: object) -> SimpleNamespace:
    values = {
        "coverage": 1.12,
        "tight_backlash_mm": 0.061,
        "loose_backlash_mm": 0.409,
        "handover_jump_mm": 0.003,
        "uncovered_phase_rad": 0.0,
        "root_interference": False,
        "qualified_continuous_contact": True,
        "numerical_error_bounds": {
            "coverage": 0.01,
            "backlash_mm": 0.0005,
            "handover_jump_mm": 0.001,
            "uncovered_phase_rad": 0.0,
        },
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_actual_mesh_gates_pay_absolute_numerical_bounds() -> None:
    margins = solve.mesh_margins(42, [_report()])
    assert min(margins.values()) >= 0.0
    assert margins["coverage"] == pytest.approx(0.01)
    assert margins["tight_backlash_mm"] == pytest.approx(0.0005)
    assert margins["loose_backlash_mm"] == pytest.approx(0.0005)
    assert margins["handover_jump_mm"] == pytest.approx(0.001)
    bounds = dict(_report().numerical_error_bounds, backlash_mm=0.002)
    refused = solve.mesh_margins(42, [_report(numerical_error_bounds=bounds)])
    assert refused["tight_backlash_mm"] < 0.0
    assert refused["loose_backlash_mm"] < 0.0


def test_no_gap_and_root_contact_are_separate_from_branch_coverage() -> None:
    assert solve.mesh_margins(42, [_report(uncovered_phase_rad=0.001)])["uncovered_phase_rad"] < 0.0
    assert solve.mesh_margins(42, [_report(root_interference=True)])["carrying_contact"] < 0.0
    assert solve.mesh_margins(42, [_report(qualified_continuous_contact=False)])["carrying_contact"] < 0.0
    bounds = dict(_report().numerical_error_bounds, uncovered_phase_rad=0.001)
    assert solve.mesh_margins(42, [_report(numerical_error_bounds=bounds)])["uncovered_phase_rad"] < 0.0


def test_unbounded_contact_result_never_qualifies() -> None:
    bounds = dict(_report().numerical_error_bounds, coverage=math.inf)
    margins = solve.mesh_margins(42, [_report(numerical_error_bounds=bounds)])
    assert margins["finite_numerical_bounds"] < 0.0
    assert margins["coverage"] < 0.0


def test_historical_named_floors_remain_comparisons_not_release_gates() -> None:
    assert solve.HISTORICAL_COVERAGE_MIN == {6: 0.65, 12: 0.80, 18: 0.90, 24: 0.98, 30: 1.03, 36: 1.08}
    assert solve.UNION_COVERAGE_MIN == 1.1
    assert solve.mesh_margins(6, [_report(coverage=1.085)])["coverage"] < 0.0
    assert solve.BLANK_DIA_BAND == (0.10, -0.10)
    assert solve.TOOTH_THICKNESS_BAND == (0.075, -0.075)
    assert solve.BACKLASH_ACCEPTANCE_MM == (0.06, 0.41)


def test_nonfinite_evidence_is_not_json_numeric_fallback() -> None:
    assert solve.json_evidence({"uncertainty": math.inf, "refused": True}) == {
        "uncertainty": "inf", "refused": True,
    }


def test_numerical_nonqualification_is_not_an_infeasibility_certificate() -> None:
    uncertain = _report(coverage=1.105)
    assert solve.mesh_margins(42, [uncertain])["coverage"] < 0.0
    assert not solve.strict_mesh_refusal(42, [uncertain])
    assert solve.strict_mesh_refusal(42, [_report(coverage=1.08)])


def test_clear_settings_score_does_not_collapse_on_zero_proof_flags() -> None:
    margins = {
        "finite_support_mm": 0.04,
        "tight_backlash_mm": 0.03,
        "coverage": 0.03,
        "carrying_contact": 0.0,
        "finite_numerical_bounds": 0.0,
        "uncovered_phase_rad": 0.0,
    }
    assert solve.setting_score(margins, 0.5) == pytest.approx(0.015)


@pytest.mark.parametrize("teeth", range(6, 121, 6))
def test_every_actual_template_uses_its_authoritative_root_endpoint(teeth: int) -> None:
    inputs = solve.configured_inputs()
    cutter = solve.cutter_for_count(teeth, inputs, six_pitch_thickness_mm=1.05)
    lower, upper = solve._translation_domain(teeth, cutter, inputs)
    assert lower < upper
    for translation in (lower, upper):
        profile = solve._profile_probe(teeth, cutter, translation)
        assert profile.root_radius_min_mm >= inputs.root_min_mm(teeth) - 1e-9
        assert profile.root_radius_max_mm <= teeth * inputs.module_mm / 2 + 1e-9


def test_custom_six_has_real_below_base_support_and_full_printed_band() -> None:
    inputs = solve.configured_inputs()
    cutter = solve.cutter_for_count(6, inputs, six_pitch_thickness_mm=1.05)
    assert cutter.root_radius_mm < cutter.base_radius_mm
    assert cutter.name == "DT6-FORM1"
    assert cutter.cutter_number is None
    domain = solve._translation_domain(6, cutter, inputs)
    actual = tuple(solve._pitch_thickness(6, cutter, translation) for translation in domain)
    nominal = (actual[0] + 0.075, actual[1] - 0.075)
    assert len(solve.lattice_ticks(*nominal, 0.001)) >= 1
    assert actual[1] - actual[0] >= 0.150


@pytest.mark.parametrize("booked,bearing",((.20,.075),(.01,.075),(.20,.30)))
def test_booked_opening_is_total_and_never_discards_larger_derived_stack(
        monkeypatch,booked: float,bearing: float) -> None:
    original = solve._config.fit
    def fitted(group,*keys):
        if (group,keys)==("cone_drum_oblique_mesh",("centre_opening_mm",)):
            return booked
        if (group,keys)==("shaft_in_bushing",("diametral_clearance_mm",)):
            return (.025,bearing)
        return original(group,*keys)
    monkeypatch.setattr(solve._config,"fit",fitted)
    inputs = solve.configured_inputs()
    expected_derived = inputs.runout_mm+bearing
    assert inputs.opening_mm == pytest.approx(max(booked,expected_derived))
    assert inputs.opening_mm != pytest.approx(booked+expected_derived)
    components = dict(inputs.opening_components_mm)
    assert components["cone_gear_runout"]+components["cylinder_gear_runout"] == pytest.approx(inputs.runout_mm)
    assert components["bearing_opening"] == bearing
    assert components["derived_total"] == pytest.approx(expected_derived)
    assert components["booked_total"] == booked
    assert components["selected_total"] == pytest.approx(inputs.opening_mm)
    # Closing retains the existing source class runout; total booking never
    # becomes a new symmetric close penalty or a filled RootMAX floor.
    assert inputs.runout_mm == pytest.approx(
        (solve.cone_spec.BORE_DIA_BAND[0] - solve.lands.GEAR_SEAT_BAND[1]) / 2
        + solve.drum_spec.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2
    )


def test_dimensional_candidates_are_not_pruned_by_filled_root_collision_disks():
    inputs = solve.configured_inputs()
    cutter = solve.cutter_for_count(6, inputs, six_pitch_thickness_mm=1.05)
    domain = solve._translation_domain(6, cutter, inputs)
    impossible_scalar_air = replace(inputs, edge_slack_mm=-1000.0,
                                   runout_mm=1000.0, opening_mm=1000.0)
    assert solve._translation_domain(6, cutter, impossible_scalar_air) == domain
    translations = (domain[0], domain[0])
    od_low, od_high = solve._od_domain(6, translations, cutter)
    outside = (od_low + od_high) / 2
    first = solve.geometry_margins(6, outside, translations, cutter, inputs)
    second = solve.geometry_margins(6, outside, translations, cutter, impossible_scalar_air)
    assert first == second
    assert not {"floor_air_mm", "floor_window_dia_mm", "drum_root_air_mm"} & first.keys()
    assert {"finite_support_mm", "blank_above_root_mm", "web_mm", "tip_land_mm",
            "gap_foot_width_mm", "special_root_min_mm"} <= first.keys()
