"""Pure mechanical corner contracts for the actual 48DP integral knob pinion.

No native part/build/drawing imports. Parent integration owns executing these
alongside the migrated stack tests and the native/farm gates.
"""

from __future__ import annotations

import importlib.util
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
    assert shaft.TEETH == 15
    assert shaft.DIAMETRAL_PITCH == 48.0
    assert shaft.PRESSURE_ANGLE_DEG == 20.0
    assert shaft.CUTTER_TEMPLATE.reference_teeth == 14
    assert shaft.CUTTER_NUMBER == 7
    assert shaft.CUTTER_TOOTH_RANGE == (14, 16)
    assert not hasattr(shaft, "PROFILE_SHIFT")
    profiles = shaft.manufactured_profiles()
    assert len(profiles) == 4
    assert {p.radial_translation_mm for p in profiles} == set(shaft.RADIAL_SETTING_LIMITS)
    assert {p.blank_radius_mm for p in profiles} == {
        (shaft.OUTSIDE_DIA + d) / 2.0 for d in shaft.OUTSIDE_DIA_BAND
    }
    # OUTWARD printing widens the ±0.005 design band on both sides; holding
    # the shop to the design band alone would reject accepted spans.
    high, low = shaft._SPAN_DESIGN_SETTING_BAND
    assert shaft.RADIAL_SETTING_LIMITS[0] < shaft.RADIAL_SETTING + low
    assert shaft.RADIAL_SETTING_LIMITS[1] > shaft.RADIAL_SETTING + high
    assert shaft.RADIAL_SETTING_LIMITS == pytest.approx(
        (0.2609517064666221, 0.27103193914373097)
    )
    for profile in profiles:
        error = 2.0 * profile.geometry_error_bound_mm + 8.0 * math.ulp(shaft.SPAN_NOMINAL)
        assert shaft.SPAN_LIMITS[0] - error <= (
            profile.tangent_span_mm(shaft.SPAN_TEETH)
        ) <= shaft.SPAN_LIMITS[1] + error
        profile.require_tip_land(0.25 * shaft.MODULE_MM)
    # Deeper than the standard 1.25-module dedendum root at the deepest corner.
    assert shaft.ROOT_DIA_EXACT_MIN < shaft.PITCH_DIA - 2.5 * shaft.MODULE_MM
    assert shaft.ROOT_DIA_EXACT_MIN == pytest.approx(6.6050463363483365)
    assert shaft.ROOT_DIA_MIN <= shaft.ROOT_DIA_EXACT_MIN
    assert shaft.ROOT_DIA_MIN == 6.60
    # The disc's convention: the finite tip vector at the lowest accepted
    # setting caps the blank; the margin is the 0.01 floor's remainder.
    assert shaft.CUTTER_SUPPORT_MARGIN_MIN > 0.0
    assert shaft.CUTTER_SUPPORT_MARGIN_MIN == pytest.approx(1.32789629217811e-4, abs=1e-9)
    # Negative control: a blank 0.001 over the printed tip limit is unsupported.
    support = shaft._MIN_SETTING_SUPPORT
    assert (
        support.support_radius_max_mm - support.geometry_error_bound_mm
        - (shaft.OUTSIDE_DIA + max(shaft.OUTSIDE_DIA_BAND) + 0.001) / 2.0
    ) < 0.0
    # Same construction as the disc: both blanks are the floored support, on
    # each sheet's grid (0.01 mm; the inch disc .0001 in).
    for spec, per_mm in ((shaft, 100.0), (shaft.DISC, 1e4 / 25.4)):
        lowest = spec._MIN_SETTING_SUPPORT
        floored = math.floor(
            (
                2.0 * lowest.support_radius_max_mm
                - 2.0 * lowest.geometry_error_bound_mm
                - spec.OUTSIDE_DIA_BAND[0]
            )
            * per_mm
            + 1e-9
        ) / per_mm
        assert spec.OUTSIDE_DIA == pytest.approx(floored, abs=1e-9)


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
    # Negative control: a core grown to the printed root limit has no air
    # once its runout and the tooth-space TIR are charged.
    assert root_min - (
        shaft.ROOT_DIA_MIN / 2.0 + shaft.CORE_TOTAL_RUNOUT / 2.0
        + shaft.TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
    ) - error < 0.0
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
    # LIMITS 3.95/3.82 (owner ruling, machinist review r8).
    assert shaft.FRONT_RELIEF_DIA_MIN == pytest.approx(3.82)
    assert shaft.FRONT_RELIEF_DIA_MAX == pytest.approx(3.95)
    assert shaft.CORE_FLAT_CUT_END_FROM_F == pytest.approx(0.110)
    assert shaft.CORE_FLAT_CUT_END_LIMITS == (0.050, 0.170)
    assert shaft.CORE_FLAT_CUT_END_Z == -shaft.CORE_FLAT_CUT_END_FROM_F
    assert min(shaft.CORE_FLAT_CUT_END_LIMITS) >= 0.050
    assert shaft.FRONT_RELIEF_WIDTH_MIN - max(shaft.CORE_FLAT_CUT_END_LIMITS) == pytest.approx(0.100)
    # Rounding is already INCLUDED in the physical foremost-point dimension.
    assert shaft.CORE_FLAT_GEAR_AIR_MIN == pytest.approx(0.050)
    assert shaft.CORE_FLAT_REACH_PAST_SHOULDER_MIN == pytest.approx(0.100)
    # The tool end lies in air under the neck: detail B prints both limits as
    # the part's own FlatEnd (LIMIT from F) and FlatToolRadius (MAX)
    # dimensions, from these constants; no note repeats them.
    assert {"FlatEnd", "FlatToolRadius"} <= shaft.DRAWING_DIMENSIONS["CoreFlatProfile"]
    assert shaft.TEETH == 15
    assert not hasattr(shaft, "CORE_FLAT_TOOL_REACH_NOTE")
    assert shaft.CORE_FLAT_TOOL_END_RADIUS_MAX == pytest.approx(0.100)
    assert shaft.FRONT_RELIEF_WIDTH_MIN > 2.0 * shaft.FRONT_CORNER_RADIUS_MAX


def test_torque_contact_uses_no_favourable_bore_float_credit():
    flat_min = shaft.CORE_FLAT_FROM_AXIS + min(shaft.CORE_FLAT_BAND)
    neck_crown = (
        shaft.FRONT_RELIEF_DIA_MAX / 2.0
        + (shaft.CORE_TOTAL_RUNOUT + shaft.FRONT_RELIEF_TOTAL_RUNOUT) / 2.0
    )
    assert flat_min - neck_crown == pytest.approx(0.085)
    assert collar.NECK_TORQUE_FLAT_AIR_MIN == pytest.approx(flat_min - neck_crown)
    assert collar.NECK_CORNER_D_BORE_AIR_MIN == pytest.approx(0.129853316221)
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
    assert shaft.CORE_ACTIVE_LENGTH_MIN == pytest.approx(4.21)
    assert collar.D_DRIVE_AREA_MIN == pytest.approx(6.654325210394)
    assert shaft.FRONT_RELIEF_AREA_MIN == pytest.approx(math.pi * 3.82**2 / 4.0)
    assert collar.D_DRIVE_AREA_MIN > 0.0
    assert collar.LENGTH == collar.SET_NOMINAL == 6.2
    assert (collar.LENGTH_FITTED_MIN, collar.LENGTH_FITTED_MAX) == (3.870, 6.900)
    assert collar.BODY_BLANK_LENGTH_MIN >= collar.LENGTH_FITTED_MAX + collar.FACING_ALLOWANCE
    assert collar.BODY_REAR_FACE_FROM_F == 0.0


def _journal_envelope_removal(profile, journal_dia: float) -> tuple[float, float]:
    """The disk end's removal over a journal of ``journal_dia`` with the TIR."""
    return cutter_end_volume_bounds_mm3(
        profile, shaft.CUTTER_DIA,
        outer_radius_mm=(journal_dia + shaft.TOOTH_SPACE_RUNOUT_TIR_MM) / 2.0,
        inner_radius_mm=0.0, start_offset_mm=0.0, end_offset_mm=shaft.JOURNAL_LENGTH,
        absolute_error_mm3=0.001,
    )


def _spec_with_journal_band(monkeypatch, band: tuple[float, float]):
    """A fresh execution of the shaft spec with the g6 journal band patched."""
    monkeypatch.setattr(fits, "SHAFT_G6_3_TO_6_MM", band)
    fresh_spec = importlib.util.spec_from_file_location(
        "_knob_shaft_perturbed", shaft.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_straight_through_cutter_clears_the_journal_at_worst_case(monkeypatch):
    # #2034: every gap is cut straight through the face; the cutter runs out
    # over the journal, whose largest g6 size stays under the formed root.
    assert shaft.CUTTER_DIA == 44.45
    assert shaft.CUTTER_ARBOR_BORE == 22.225
    assert shaft.CUTTER_SKU == "10-289-487"
    profiles = shaft.manufactured_profiles()
    journal_max = shaft.JOURNAL_DIA + max(shaft.JOURNAL_DIA_BAND)
    assert journal_max == pytest.approx(5.99492)
    air = (
        2.0 * min(p.root_radius_min_mm for p in profiles)
        - journal_max - shaft.TOOTH_SPACE_RUNOUT_TIR_MM
    ) / 2.0 - max(p.geometry_error_bound_mm for p in profiles)
    assert air == pytest.approx(shaft.JOURNAL_CUTTER_AIR_MIN)
    assert shaft.JOURNAL_CUTTER_AIR_FLOOR == 0.035
    assert shaft.JOURNAL_CUTTER_AIR_MIN > shaft.JOURNAL_CUTTER_AIR_FLOOR
    assert shaft.JOURNAL_CUTTER_AIR_MIN == pytest.approx(0.2800631681739132)
    # The independent disk-envelope oracle removes nothing from the journal.
    for profile in profiles:
        lo, hi = _journal_envelope_removal(profile, journal_max)
        assert lo == 0.0
        assert hi < 1e-6
    # Negative control: a Ø6.7 journal stands in the cutter's path; the
    # envelope removes real stock from it and the spec refuses to load.
    assert (
        shaft.ROOT_DIA_EXACT_MIN - 6.7 - shaft.TOOTH_SPACE_RUNOUT_TIR_MM
    ) / 2.0 < 0.0
    lo, _hi = _journal_envelope_removal(shaft.STOCK_PROFILE, 6.7)
    assert lo > 0.0
    real_band = fits.SHAFT_G6_3_TO_6_MM
    with pytest.raises(AssertionError, match="over the journal"):
        _spec_with_journal_band(monkeypatch, (0.700, 0.690))
    # Positive control: the same fresh execution with the real band loads.
    fresh = _spec_with_journal_band(monkeypatch, real_band)
    assert fresh.JOURNAL_CUTTER_AIR_MIN == pytest.approx(shaft.JOURNAL_CUTTER_AIR_MIN)


def test_bearing_material_charges_breaks_axis_error_and_loose_float():
    assert collar.FRONT_BEARING_INNER_RADIUS_MAX > (collar.BORE_DIA + max(collar.BORE_DIA_BAND)) / 2.0
    # Regression value, not a load floor: the spec's physical gate is a
    # positive face. It charges bore, entry break, D-axis error at F and
    # half the 0.05 tooth-space TIR, so it sits below the uncharged ring.
    assert collar.FRONT_BEARING_AREA_MIN == pytest.approx(23.1902, abs=1e-3)
    assert shaft.RING_TRANSVERSE_FLOAT_MAX >= (ring.ID + max(ring.ID_BAND) - shaft.JOURNAL_DIA_MIN) / 2.0
    assert shaft.RING_TRANSVERSE_FLOAT_MAX == pytest.approx(0.10864110728935561)
    assert collar.D_SUPPORT_LENGTH_MIN == pytest.approx(3.692234843105)
    assert collar.D_AXIS_AT_F_FROM_JOURNAL_MAX == pytest.approx(0.060796633879)
    assert shaft.REAR_BEARING_INNER_RADIUS_MAX == pytest.approx(3.4586411072893553)
    assert shaft.REAR_BEARING_INNER_RADIUS_MAX > shaft.ROOT_DIA_EXACT_MIN / 2.0
    assert shaft.REAR_BEARING_AREA_MIN > 1.0
    assert shaft.REAR_BEARING_AREA_MIN == pytest.approx(11.322316949949155)
    # Not the uncharged centred claim on the bare ring bore.
    centred = shaft.gear_bearing_area_lower(shaft.STOCK_PROFILE, ring.ID / 2.0)
    assert centred == pytest.approx(18.906670346162162)
    assert shaft.REAR_BEARING_AREA_MIN < centred
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
    assert min(cup.BORE_JOURNAL_CLEARANCE) == pytest.approx(0.00508)
    assert max(cup.BORE_JOURNAL_CLEARANCE) == pytest.approx(0.0247)
    assert ring.LENGTH == 5.2
    assert plate.HUB_LENGTH == 12.6
    assert shaft.CUP_FACE_Z == pytest.approx(40.3375)
    assert shaft.REAR_END_Z == pytest.approx(46.8375)
    assert collar.COLLAR_DISC_AIR_MIN == 0.10
    assert "ONE FULL TURN" in collar.COLLAR_DISC_AIR_PHRASE


def test_actual_arbor_mount_has_room_and_a_manufacturable_spacer_wall():
    assert shaft.CUTTER_MOUNT_OD_MAX == 31.75
    assert (shaft.CUTTER_MOUNT_OD_MAX - shaft.CUTTER_ARBOR_BORE) / 2.0 >= 2.0
    # The arbor stands on the deepest ground X, not the polar root radius.
    deep_x = min(p.root_point(p.root_half_angle_rad)[0] for p in shaft.manufactured_profiles())
    assert deep_x == shaft.ROOT_DEPTH_X_MIN
    assert deep_x < shaft.ROOT_DIA_EXACT_MIN / 2.0
    assert shaft.CUTTER_MOUNT_AIR_MIN > 5.0
    assert shaft.CUTTER_MOUNT_AIR_MIN == pytest.approx(5.124269671663278)


def test_complete_nominal_volume_is_straight_full_face_gaps():
    lo, hi = shaft.expected_volume_bounds_mm3()
    assert 0.0 < lo <= hi
    assert hi - lo <= 1e-6
    gaps = shaft.TEETH * shaft.STOCK_PROFILE.gap_area_mm2 * shaft.FACE_WIDTH
    assert gaps > 0.0
    # Negative control: the retired straight pass to 4.65 of the 5.9 face,
    # without its endcut, leaves stock the full-face oracle refuses.
    left = shaft.TEETH * shaft.STOCK_PROFILE.gap_area_mm2 * (shaft.FACE_WIDTH - 4.65)
    assert lo + left > hi + 1.0
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
        "paper_drive_stock_inspection",
        "stock_form_cutter",
        "_fit_deviations",
        "_gear_quality",
        "_config",
    } <= modules
    # The retired rear endcut model no longer reaches the recipe's cache key.
    assert "paper_drive_stock_envelope" not in modules
    tokens = graph.config_files_of(script)
    assert "tolerances/stock_form_quality.yaml" in tokens
    assert "test_pd48_knob_mechanics" not in modules

