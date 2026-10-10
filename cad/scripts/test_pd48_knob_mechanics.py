"""Pure mechanical corner contracts for the actual 12T48DP integral knob.

No native part/build/drawing imports. Parent integration owns executing these
alongside the migrated stack tests and the native/farm gates.
"""

from __future__ import annotations

import math

import pytest

import _fit_close_running as fits
import _gear_quality as quality
import pd_transgear_arm_plate_geometry as plate
import pd_transgear_drive_collar_spec as collar
import pd_transgear_knob_cup_spec as cup
import pd_transgear_knob_shaft_spec as shaft
import pd_transgear_knob_thrust_ring_spec as ring
from paper_drive_stock_envelope import (
    cutter_end_section_area_bounds_mm2,
    cutter_end_volume_bounds_mm3,
)


def test_actual_stock_master_and_real_printed_span_family():
    assert shaft.TEETH == 12
    assert shaft.DIAMETRAL_PITCH == 48.0
    assert shaft.PRESSURE_ANGLE_DEG == 20.0
    assert shaft.CUTTER_TEMPLATE.reference_teeth == 12
    assert shaft.CUTTER_NUMBER == 8
    assert shaft.CUTTER_TOOTH_RANGE == (12, 13)
    assert not hasattr(shaft, "PROFILE_SHIFT")
    profiles = shaft.manufactured_profiles()
    assert len(profiles) == 4
    assert {p.radial_translation_mm for p in profiles} == set(shaft.RADIAL_SETTING_LIMITS)
    assert {p.blank_radius_mm for p in profiles} == {
        (shaft.OUTSIDE_DIA + d) / 2.0 for d in shaft.OUTSIDE_DIA_BAND
    }
    # OUTWARD printing admits a slightly negative T; ignoring it is unsafe.
    assert shaft.RADIAL_SETTING_LIMITS[0] < 0.0
    assert shaft.RADIAL_SETTING_LIMITS[1] > 0.010
    for profile in profiles:
        error = 2.0 * profile.geometry_error_bound_mm + 8.0 * math.ulp(shaft.SPAN_NOMINAL)
        assert shaft.SPAN_LIMITS[0] - error <= (
            profile.tangent_span_mm(shaft.SPAN_TEETH)
        ) <= shaft.SPAN_LIMITS[1] + error
        profile.require_tip_land(0.25 * shaft.MODULE_MM)
    assert shaft.ROOT_DIA_EXACT_MIN < 5.027083333333334
    assert shaft.ROOT_DIA_MIN <= shaft.ROOT_DIA_EXACT_MIN
    assert shaft.CUTTER_SUPPORT_MARGIN_MIN > 0.004


def test_actual_pin_is_supported_at_every_manufactured_corner():
    assert shaft.TOOTH_SPACE_GAUGE_PIN_DIA_MM == 1.0
    contacts = shaft.tooth_space_gauge_contacts(shaft.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    assert len(contacts) == 4
    assert min(c.root_air_mm for c in contacts) > 0.0
    assert min(c.tip_air_mm for c in contacts) > 0.0
    for diameter in (0.0, 1000.0):
        with pytest.raises(ValueError):
            shaft.tooth_space_gauge_contacts(diameter)
    assert shaft.TOOTH_SPACE_RUNOUT_TIR_MM == quality.toothspace_runout_tir_mm()
    assert shaft.CORE_TOTAL_RUNOUT == quality.shaft_turned_runout_mm()
    assert shaft.JOURNAL_DIA_BAND is fits.SHAFT_G6_3_TO_6_MM
    assert "TO A" in shaft.TOOTH_SPACE_CALLOUT
    assert shaft.TOOTH_SPACE_CALLOUT_POINT_MM[2] == 0.0


def test_true_front_disk_clears_active_core_and_both_neck_corners():
    profiles = shaft.manufactured_profiles()
    root_min = min(p.root_radius_min_mm for p in profiles)
    error = max(p.geometry_error_bound_mm for p in profiles)
    core_air = root_min - (
        (shaft.CORE_DIA + max(shaft.CORE_DIA_BAND)) / 2.0
        + shaft.CORE_TOTAL_RUNOUT / 2.0
        + shaft.TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
    ) - error
    neck_air = root_min - (
        shaft.FRONT_RELIEF_DIA_MAX / 2.0 + shaft.FRONT_CORNER_RADIUS_MAX
        + shaft.FRONT_RELIEF_TOTAL_RUNOUT / 2.0
        + shaft.TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
    ) - error
    assert core_air == pytest.approx(shaft.FRONT_CORE_AIR_MIN)
    assert neck_air == pytest.approx(shaft.FRONT_NECK_AIR_MIN)
    assert core_air > 0.035
    assert neck_air > 0.320
    # The old unstepped front core is a concrete physical counterexample.
    assert root_min - 6.345 / 2.0 < 0.0
    for profile in profiles:
        lo, hi = cutter_end_volume_bounds_mm3(
            profile, shaft.CUTTER_DIA,
            outer_radius_mm=(
                shaft.CORE_DIA + shaft.CORE_TOTAL_RUNOUT + shaft.TOOTH_SPACE_RUNOUT_TIR_MM
            ) / 2.0,
            inner_radius_mm=0.0, start_offset_mm=0.0, end_offset_mm=5.25,
            absolute_error_mm3=0.001,
        )
        assert lo == 0.0
        assert hi < 1e-6


def test_physical_flat_terminal_has_two_actual_end_limits():
    assert shaft.FRONT_RELIEF_DIA == 3.95
    assert shaft.FRONT_RELIEF_DIA_MIN == pytest.approx(3.82)
    assert shaft.FRONT_RELIEF_DIA_MAX == pytest.approx(4.08)
    assert shaft.CORE_FLAT_CUT_END_FROM_F == pytest.approx(0.110)
    assert shaft.CORE_FLAT_CUT_END_LIMITS == (0.050, 0.170)
    assert shaft.CORE_FLAT_CUT_END_Z == -shaft.CORE_FLAT_CUT_END_FROM_F
    assert min(shaft.CORE_FLAT_CUT_END_LIMITS) >= 0.050
    assert shaft.FRONT_RELIEF_WIDTH_MIN - max(shaft.CORE_FLAT_CUT_END_LIMITS) == pytest.approx(0.100)
    # Rounding is already INCLUDED in the physical foremost-point dimension.
    assert shaft.CORE_FLAT_GEAR_AIR_MIN == pytest.approx(0.050)
    assert shaft.CORE_FLAT_REACH_PAST_SHOULDER_MIN == pytest.approx(0.100)
    assert {"FlatEnd", "FlatToolRadius"} <= shaft.DRAWING_DIMENSIONS["CoreFlatProfile"]
    assert shaft.FRONT_RELIEF_WIDTH_MIN > 2.0 * shaft.FRONT_CORNER_RADIUS_MAX


def test_torque_contact_uses_no_favourable_bore_float_credit():
    flat_min = shaft.CORE_FLAT_FROM_AXIS + min(shaft.CORE_FLAT_BAND)
    neck_crown = (
        shaft.FRONT_RELIEF_DIA_MAX / 2.0
        + (shaft.CORE_TOTAL_RUNOUT + shaft.FRONT_RELIEF_TOTAL_RUNOUT) / 2.0
    )
    assert flat_min - neck_crown == pytest.approx(0.020)
    assert collar.NECK_TORQUE_FLAT_AIR_MIN == pytest.approx(flat_min - neck_crown)
    assert collar.NECK_CORNER_D_BORE_AIR_MIN == pytest.approx(0.064853316221)
    # A legal zero general edge break would seat on the gear-side fillet.
    assert flat_min - neck_crown - shaft.FRONT_CORNER_RADIUS_MAX < 0.0
    assert collar.BORE_ENTRY_BREAK_MIN == pytest.approx(0.150)
    assert collar.BORE_ENTRY_BREAK_MAX == pytest.approx(0.250)
    assert collar.BORE_ENTRY_BREAK_ANGLE_LIMITS == pytest.approx((44.0, 46.0))
    assert collar.BORE_ENTRY_BREAK_LEG_MIN == pytest.approx(0.144853316221)
    assert collar.BORE_ENTRY_BREAK_LEG_MAX == pytest.approx(0.258882578448)
    assert collar.FLAT_TO_AXIS == pytest.approx(2.1525)
    assert collar.FLAT_LIMITS == (2.145, 2.160)
    assert min(collar.FLAT_CLEARANCE) > 0.0
    assert collar.STUD_D_BORE_AIR > 0.0


def test_shortened_drive_face_is_real_not_old_full_core_length():
    assert shaft.CORE_FRONT_FROM_F == 5.25
    assert shaft.CORE_ACTIVE_LENGTH == pytest.approx(4.85)
    assert shaft.CORE_ACTIVE_LENGTH_MIN == pytest.approx(4.59)
    assert collar.D_DRIVE_AREA_MIN == pytest.approx(7.339179692138)
    assert collar.D_DRIVE_AREA_MIN > 0.0
    assert shaft.FRONT_RELIEF_AREA_MIN == pytest.approx(math.pi * 3.82**2 / 4.0)
    assert collar.LENGTH == collar.SET_NOMINAL == 6.2
    assert (collar.LENGTH_FITTED_MIN, collar.LENGTH_FITTED_MAX) == (3.870, 6.900)
    assert collar.BODY_BLANK_LENGTH_MIN >= collar.LENGTH_FITTED_MAX + collar.FACING_ALLOWANCE
    assert collar.BODY_REAR_FACE_FROM_F == 0.0


def test_rear_disk_chord_uses_deep_ground_x_not_polar_root():
    assert shaft.CUTTER_DIA == 44.45
    assert shaft.CUTTER_ARBOR_BORE == 22.225
    deep_x = min(p.root_point(p.root_half_angle_rad)[0] for p in shaft.manufactured_profiles())
    assert deep_x == shaft.ROOT_DEPTH_X_MIN
    assert deep_x < shaft.ROOT_DIA_EXACT_MIN / 2.0
    rise = (
        (shaft.JOURNAL_DIA + max(shaft.JOURNAL_DIA_BAND)) / 2.0
        + shaft.TOOTH_SPACE_RUNOUT_TIR_MM / 2.0 - deep_x
    )
    end = shaft.FULL_DEPTH_MAX + math.sqrt(shaft.CUTTER_DIA * rise - rise**2)
    assert end == pytest.approx(shaft.CUTTER_RUNOUT_END_WORST)
    assert end < 9.59  # 10.6 printed limit less its 1.0 margin (0.05 TIR)
    assert shaft.CUTTER_RUNOUT_MAX - end > 1.0
    assert shaft.HUB_BORE_FROM_F_WORST == pytest.approx(10.92)
    assert shaft.CUTTER_RUNOUT_MAX < shaft.HUB_BORE_FROM_F_WORST
    old_rise = (8.5 - 0.005) / 2.0 + shaft.TOOTH_SPACE_RUNOUT_TIR_MM / 2.0 - deep_x
    old_end = shaft.FULL_DEPTH_MAX + math.sqrt(shaft.CUTTER_DIA * old_rise - old_rise**2)
    assert old_end > shaft.CUTTER_RUNOUT_MAX


def test_bearing_material_charges_breaks_axis_error_and_loose_float():
    assert collar.FRONT_BEARING_INNER_RADIUS_MAX > (collar.BORE_DIA + max(collar.BORE_DIA_BAND)) / 2.0
    # Regression value, not a load floor: the spec's physical gate is a
    # positive face. It charges bore, entry break, D-axis error at F and
    # half the 0.05 tooth-space TIR, so it sits below the uncharged ring.
    assert collar.FRONT_BEARING_AREA_MIN == pytest.approx(7.9219, abs=1e-3)
    assert shaft.RING_TRANSVERSE_FLOAT_MAX >= (ring.ID + max(ring.ID_BAND) - shaft.JOURNAL_DIA_MIN) / 2.0
    assert shaft.RING_TRANSVERSE_FLOAT_MAX == pytest.approx(0.10960380794239155)
    assert collar.D_SUPPORT_LENGTH_MIN == pytest.approx(4.072234843105)
    assert collar.D_AXIS_AT_F_FROM_JOURNAL_MAX == pytest.approx(0.058542058772)
    assert shaft.REAR_BEARING_INNER_RADIUS_MAX >= 3.4585
    assert shaft.REAR_BEARING_AREA_MIN > 1.0
    assert shaft.REAR_BEARING_AREA_MIN < 2.0  # not the uncharged centred claim
    assert shaft.gear_bearing_area_lower(shaft.STOCK_PROFILE, shaft.OUTSIDE_DIA) == 0.0
    with pytest.raises(ValueError):
        shaft.gear_bearing_area_lower(shaft.STOCK_PROFILE, -1.0)


def test_retained_walls_and_axial_stations_need_no_new_waiver():
    assert collar.PILOT_WALL_WORST >= 2.0
    assert collar.BORE_PIN_WALL_WORST >= 2.0
    assert ring.WALL_WORST >= 2.0
    assert cup.RADIAL_WALL_WORST >= 2.0
    assert (shaft.JOURNAL_DIA_MIN - 1.65) / 2.0 >= 2.0
    assert plate.BORE_DIA == 6.0
    assert plate.BORE_DIA_LIMITS == (0.0, 0.012)
    assert min(cup.BORE_JOURNAL_CLEARANCE) == pytest.approx(0.004)
    assert max(cup.BORE_JOURNAL_CLEARANCE) == pytest.approx(0.024)
    assert ring.LENGTH == 5.2
    assert plate.HUB_LENGTH == 12.6
    assert shaft.CUP_FACE_Z == pytest.approx(40.3375)
    assert shaft.REAR_END_Z == pytest.approx(46.8375)
    assert collar.COLLAR_DISC_AIR_MIN == 0.10
    assert "ONE FULL TURN" in collar.COLLAR_DISC_AIR_PHRASE


def test_actual_arbor_mount_has_room_and_a_manufacturable_spacer_wall():
    assert shaft.CUTTER_MOUNT_OD_MAX == 31.75
    assert (shaft.CUTTER_MOUNT_OD_MAX - shaft.CUTTER_ARBOR_BORE) / 2.0 >= 2.0
    assert shaft.CUTTER_MOUNT_AIR_MIN > 5.0


def test_complete_nominal_volume_includes_d_neck_and_true_endcut_interval():
    lo, hi = shaft.expected_volume_bounds_mm3(absolute_error_mm3=0.05)
    assert 0.0 < lo <= hi
    assert hi - lo <= 0.05 + 1e-7
    far_lo, far_hi = cutter_end_section_area_bounds_mm2(
        shaft.STOCK_PROFILE, shaft.CUTTER_DIA,
        outer_radius_mm=shaft.JOURNAL_DIA / 2.0,
        inner_radius_mm=0.0, offset_mm=30.0, absolute_error_mm2=0.001,
    )
    assert far_lo == 0.0
    assert far_hi < 1e-6
    with pytest.raises(ValueError, match="finite ground tip/closure"):
        cutter_end_volume_bounds_mm3(
            shaft.STOCK_PROFILE, shaft.CUTTER_DIA,
            outer_radius_mm=shaft.OUTSIDE_DIA, inner_radius_mm=0.0,
            start_offset_mm=0.0, end_offset_mm=1.0, absolute_error_mm3=0.001,
        )


def test_public_end_section_counts_both_sides_exactly_once():
    profile = shaft.STOCK_PROFILE
    lo, hi = cutter_end_section_area_bounds_mm2(
        profile, shaft.CUTTER_DIA, outer_radius_mm=profile.blank_radius_mm,
        inner_radius_mm=0.0, offset_mm=0.0, absolute_error_mm2=0.005,
    )
    # At the actual terminal plane, the disk reproduces the exact 2D gap.
    # Missing or duplicating the ±Y factor fails this independent Green-area oracle.
    assert lo <= profile.gap_area_mm2 + profile.gap_area_error_bound_mm2
    assert hi >= profile.gap_area_mm2 - profile.gap_area_error_bound_mm2
    assert hi - lo <= 0.005 + 1e-10


def test_public_end_volume_disjoint_slab_composition():
    profile = shaft.STOCK_PROFILE
    def interval(start, end, error):
        return cutter_end_volume_bounds_mm3(
            profile, shaft.CUTTER_DIA, outer_radius_mm=profile.blank_radius_mm,
            inner_radius_mm=0.0, start_offset_mm=start, end_offset_mm=end,
            absolute_error_mm3=error,
        )
    whole = interval(0.0, 1.25, 0.01)
    first = interval(0.0, 0.5, 0.005)
    second = interval(0.5, 1.25, 0.005)
    split = (first[0] + second[0], first[1] + second[1])
    assert max(whole[0], split[0]) <= min(whole[1], split[1])
    assert 0.0 < whole[0] <= whole[1]
    for error in (0.0, math.inf, math.nan):
        with pytest.raises(ValueError):
            interval(0.0, 1.25, error)
    with pytest.raises(ValueError):
        interval(1.0, 0.0, 0.01)


@pytest.mark.parametrize(
    "builder",
    ("build_pd_transgear_knob_shaft.py", "build_pd_transgear_drive_collar.py"),
)
def test_production_recipe_contains_real_profile_cap_and_grade_sources(builder):
    # Exercise the ACTUAL production graph, not a copied AST fixture.
    import _buildgraph as graph
    from pathlib import Path

    script = graph.SCRIPTS_DIR / builder
    modules = {Path(path).stem for path in graph.module_deps_of(script)}
    assert {
        "pd_transgear_knob_shaft_spec",
        "paper_drive_stock_envelope",
        "paper_drive_stock_inspection",
        "stock_form_cutter",
        "_fit_deviations",
        "_gear_quality",
        "_config",
    } <= modules
    tokens = graph.config_files_of(script)
    assert "tolerances/stock_form_quality.yaml" in tokens
    assert "test_pd48_knob_mechanics" not in modules


def test_angular_index_receiving_uses_actual_pitch_reference_and_live_grades():
    assert shaft.PITCH_INDEX_REFERENCE_RADIUS_MM == shaft.PITCH_DIA / 2.0
    assert shaft.PITCH_INDEX_REFERENCE_RADIUS_MM == pytest.approx(3.175)
    assert shaft.PITCH_INDEX_DEVIATION_MM == quality.pinion_pitch_index_deviation_mm()
    uncertainty = quality.pitch_index_measurement_uncertainty_mm()
    assert shaft.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM == uncertainty
    assert shaft.PITCH_INDEX_STATIONS == tuple(range(13))
    rows = shaft.TOOTH_SPACE_CALLOUT.splitlines()
    assert rows == [
        f"TOOTH SPACE RUNOUT {shaft.TOOTH_SPACE_RUNOUT_TIR_MM:.2f} TIR TO A",
        "Ø1.000 PIN, ALL 12 SPACES",
        f"INDEX RANGE {shaft.PITCH_INDEX_DEVIATION_MM:.2f} MAX",
    ]
    # Measurement uncertainty is method, never a printed requirement.
    assert "U " not in shaft.TOOTH_SPACE_CALLOUT
    measurements = {station: 0.0 for station in shaft.PITCH_INDEX_STATIONS}
    assert shaft.require_pitch_index_errors_mm(measurements) == 2.0 * uncertainty
    interior = dict(measurements)
    interior[5] = 0.999 * (shaft.PITCH_INDEX_DEVIATION_MM - 2.0 * uncertainty)
    assert shaft.require_pitch_index_errors_mm(interior) <= shaft.PITCH_INDEX_DEVIATION_MM


def test_angular_index_requires_wrap_and_rejects_paid_actual_errors():
    measurements = {station: 0.0 for station in shaft.PITCH_INDEX_STATIONS}
    missing_wrap = dict(measurements)
    del missing_wrap[shaft.TEETH]
    with pytest.raises(ValueError, match="every specified station"):
        shaft.require_pitch_index_errors_mm(missing_wrap)
    extra = dict(measurements)
    extra[shaft.TEETH + 1] = 0.0
    with pytest.raises(ValueError, match="every specified station"):
        shaft.require_pitch_index_errors_mm(extra)
    for invalid in (math.nan, math.inf, True):
        invalid_measurements = dict(measurements)
        invalid_measurements[3] = invalid
        with pytest.raises(ValueError, match="finite numeric"):
            shaft.require_pitch_index_errors_mm(invalid_measurements)
    over_range = dict(measurements)
    over_range[5] = shaft.PITCH_INDEX_DEVIATION_MM
    over_range[6] = -shaft.PITCH_INDEX_DEVIATION_MM
    with pytest.raises(ValueError, match="REJECT paid pitch/index range"):
        shaft.require_pitch_index_errors_mm(over_range)
