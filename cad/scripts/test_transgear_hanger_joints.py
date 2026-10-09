"""SolidWorks-free contracts for the ch. 23 hanger's screwed joints.

``transgear_hanger_joints`` judges each joint at the worst case of the printed
bands and refuses to import when one fails. These tests show that each check
still fires when a mating number drifts, and that the MHA-VN-041 sheet line
states the worst case it computes.
"""

from __future__ import annotations

import importlib.util
import math

import pytest

import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import transgear_hanger_joints as joints
import paper_drive_arm_registration as registration
import vn_transgear_latch_pin_spec as latch_pin
import vn_transgear_pivot_screw_spec as pivot
import pd_transgear_pivot_spacer_spec as spacer
import vn_transgear_pivot_spring_spec as spring


def _reload_joints():
    spec = importlib.util.spec_from_file_location(
        "_hanger_joints_perturbed", joints.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    return fresh


def test_pivot_screw_refuses_a_tap_drill_it_can_bottom_in(monkeypatch) -> None:
    assert joints.PIVOT_TIP_TO_DRILL_BOTTOM > 0.0
    # The shallowest drill (depth minus its minus limit) now ends at the tip.
    monkeypatch.setattr(
        bar,
        "PIVOT_TAP_DRILL_DEPTH",
        pivot.THREAD_LEN - bar.PIVOT_TAP_DRILL_DEPTH_LIMITS[0],
    )
    with pytest.raises(AssertionError, match="bottoms"):
        _reload_joints()


def test_the_bar_tap_countersink_is_charged_to_the_tap_drill(monkeypatch) -> None:
    """R9-63: full thread starts where a countersink's 45° leg meets the tap
    drill, not the major.  A mouth wide enough to reach the screw's full
    thread from the drill, though not from the major, is refused."""
    drill, major = bar.PIVOT_TAP_DRILL_DIA, pivot.THREAD_MAJOR
    csk = (drill + major) / 2.0 + 2.0 * pivot.FULL_THREAD_START
    assert (csk - major) / 2.0 < pivot.FULL_THREAD_START < (csk - drill) / 2.0
    monkeypatch.setattr(bar, "PIVOT_TAP_CSK_DIA", csk)
    with pytest.raises(AssertionError, match="countersink reaches"):
        _reload_joints()


def test_the_spring_room_stays_inside_the_springs_catalogue_travel(
    monkeypatch,
) -> None:
    """R9-71: the MHA-VN-049 spring holds the arm on the spacer at every printed
    corner, never pressed past its catalogue working height.  The old floor
    (7.00, the free pivot's 0.10..0.35 head play) leaves the spring loose."""
    assert joints.SPRING_ROOM_MIN == pytest.approx(0.70, abs=1e-9)
    assert joints.SPRING_ROOM_MAX == pytest.approx(0.9508, abs=1e-9)
    assert spring.WORKING_HEIGHT <= joints.SPRING_ROOM_MIN
    assert joints.SPRING_ROOM_MAX < spring.FREE_HEIGHT
    assert joints.SPRING_PRELOAD_N == pytest.approx((19.15, 38.91), abs=0.01)
    for floor in (7.0, 6.5):
        monkeypatch.setattr(arm, "SPOT_FACE_FLOOR_FROM_FRONT", floor)
        with pytest.raises(AssertionError, match="leaves the spring"):
            _reload_joints()


def test_seated_hanger_enclosure_uses_actual_spacer_face_grades() -> None:
    assert joints.HANGER_TILT == pytest.approx(
        (spacer.FRONT_FACE_PERPENDICULARITY + spacer.REAR_FACE_PERPENDICULARITY)
        / spacer.FACE_PERPENDICULARITY_ZONE_DIA,
    )


def test_arm_and_plate_weight_inputs_are_actual_cut_geometry() -> None:
    for geometry in (arm, plate):
        source = geometry.nominal_material_properties()
        assert source["volume_mm3"] > 0.0
        assert source["mass_kg"] == pytest.approx(source["volume_mm3"] * 7870.0 * 1e-9)
        assert len(source["centre_of_mass_local_mm"]) == 3
        assert all(math.isfinite(value) for value in source["centre_of_mass_local_mm"])
    # These are two parts, not a substituted scalar whole-hanger certificate.
    assert arm.nominal_material_properties()["mass_kg"] < 0.2
    assert plate.nominal_material_properties()["mass_kg"] < 0.2


def test_reference_entry_pays_published_fillet_and_independent_critical_axes() -> None:
    """Reference datum pose only, not an ISO pin-end whole-body certificate."""
    import vn_transgear_arm_plate_screw_spec as screw
    angle = (math.atan(arm.REDUCER_POSITION_DIAMETER / arm.CLAMP_TAP_PROJECTED_HEIGHT_MM)
             + registration.ARM_PLATE_TILT_MAX_RAD)
    required = (screw.THREAD_MAJOR / 2.0 + screw.UNDER_HEAD_FILLET_RADIUS_MAX_MM) / math.cos(angle)
    expected = plate.SCREW_HOLE_DIA / 2.0 - required - arm.REDUCER_POSITION_RADIUS - plate.REDUCER_POSITION_RADIUS
    assert joints.PLATE_SCREW_REFERENCE_ENTRY_MARGIN_MM == pytest.approx(expected)
    assert expected > 0.0


def test_published_standard_stock_and_entire_head_bounds_do_not_use_receiving_caps(monkeypatch) -> None:
    import vn_transgear_arm_plate_screw_spec as screw
    assert screw.HEAD_DIA_MAX_MM == pytest.approx(0.312 * 25.4)
    assert screw.HEAD_PROTRUSION_MAX_MM == pytest.approx(0.091 * 25.4)
    assert screw.HEAD_PROTRUSION_GAGE_DIA_MM == pytest.approx(0.267 * 25.4)
    slope = math.tan(screw.HEAD_BEARING_HALF_ANGLE_MIN_RAD)
    whole_height = (screw.HEAD_PROTRUSION_MAX_MM
                    + (screw.HEAD_PROTRUSION_GAGE_DIA_MM - screw.THREAD_PITCH_DIA_LIMITS_MM[0]) / (2.0 * slope)
                    + screw.UNDER_HEAD_FILLET_RADIUS_MAX_MM)
    thread_gage_height = (screw.HEAD_PROTRUSION_MAX_MM
                          + (screw.HEAD_PROTRUSION_GAGE_DIA_MM - screw.THREAD_MAJOR_MAX_MM) / (2.0 * slope))
    assert screw.HEAD_WHOLE_METAL_HEIGHT_MAX_MM == pytest.approx(whole_height)
    assert screw.HEAD_TOP_TO_THREAD_GAGE_MAX_MM == pytest.approx(thread_gage_height)
    assert whole_height > thread_gage_height
    # No positive crown REF credit in the published overall-length minimum.
    assert screw.STOCK_OVERALL_LENGTH_MIN_MM == pytest.approx((1.0 - 0.03) * 25.4)
    assert screw.HEAD_AXIS_ECCENTRICITY_MAX_MM == pytest.approx(0.03 * screw.HEAD_DIA_MAX_MM)
    angle = joints.PLATE_SCREW_AXIS_TILT_MAX_RAD
    radial = (screw.HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM + screw.THREAD_MAJOR / 2.0
              + screw.STOCK_BODY_STRAIGHTNESS_MAX_MM)
    proud = ((screw.STOCK_OVERALL_LENGTH_MIN_MM - screw.HEAD_WHOLE_METAL_HEIGHT_MAX_MM) * math.cos(angle)
             - radial * math.sin(angle) - arm.THICKNESS - arm.THICKNESS_BAND
             - plate.THICKNESS_OVER_ARM - plate.THICKNESS_OVER_ARM_BAND
             - joints.PLATE_SCREW_SEAT_HEIGHT_DEBIT_MM)
    assert joints.PLATE_SCREW_STOCK_PROUD_MIN == pytest.approx(proud)
    assert joints.PLATE_SCREW_STOCK_LEAD_MARGIN_MM == pytest.approx(
        proud - joints.PLATE_SCREW_CUT_PROUD_MAX - screw.POINT_CHAMFER_LENGTH_MAX_MM,
    )
    assert joints.PLATE_SCREW_STOCK_LEAD_MARGIN_MM > 0.0
    assert joints.PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM <= arm.CLAMP_TAP_PROJECTED_HEIGHT_MM
    assert joints.PLATE_SCREW_CONTACT_PLATE_LOCAL_Z_MAX_MM <= plate.CLAMP_PLATE_PROJECTED_HEIGHT_MM
    assert joints.PLATE_SCREW_WHOLE_HEAD_ARM_LOCAL_Z_MAX_MM > joints.PLATE_SCREW_CONTACT_ARM_LOCAL_Z_MAX_MM
    assert joints.PLATE_SCREW_WHOLE_HEAD_RADIAL_SUPPORT_MAX_MM > screw.HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM
    monkeypatch.setattr(screw, "STOCK_OVERALL_LENGTH_MIN_MM", 0.5 * 25.4)
    with pytest.raises(AssertionError, match="published-standard stock cannot retain"):
        _reload_joints()


def test_cut_plate_screws_hold_one_and_a_half_d_in_the_thinnest_arm(
    monkeypatch,
) -> None:
    """Pay published two-pitch under-head runout, true head eccentricity,
    both seat signs and the distinct entry/exit/cut-end overlap."""
    import vn_transgear_arm_plate_screw_spec as screw
    internal_span = (arm.THICKNESS - arm.THICKNESS_BAND - arm.PLATE_TAP_ENTRY_LOSS_MAX_MM
                     - max(arm.PLATE_TAP_EXIT_LOSS_MAX_MM, screw.CUT_END_BREAK_MAX))
    assert joints.PLATE_SCREW_INTERNAL_THREAD_SPAN_MIN_MM == pytest.approx(internal_span)
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST < internal_span
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST / screw.THREAD_MAJOR >= 1.5
    # The model is the screw as cut: its tip on the arm's front face.
    assert screw.LENGTH == pytest.approx(plate.THICKNESS_OVER_ARM + arm.THICKNESS)
    assert joints.PLATE_SCREW_TIP_INSIDE_NOMINAL == pytest.approx(0.0, abs=1e-9)
    assert joints.PLATE_SCREW_TIP_PROUD_MAX == joints.PLATE_SCREW_CUT_PROUD_MAX
    # A cut-end break past the arm's 1.5 D margin starves the joint.
    monkeypatch.setattr(screw, "CUT_END_BREAK_MAX", 1.7)
    with pytest.raises(AssertionError, match="MHA-VN-040 worst engagement"):
        _reload_joints()


def test_plate_notch_face_clears_the_arm_edge_at_every_limit(monkeypatch) -> None:
    """Reference-pose graded clearance; the notch does not locate."""
    import pd_transgear_arm_plate_spec as plate_spec

    corner_band = plate_spec.BAND_BY_PLACES[plate_spec.NOTCH_PLACES]
    worst = (plate.NOTCH_RELIEF - corner_band) * math.cos(arm.EDGE_LEAN) - arm.BAND_X
    assert worst > 0.0
    assert joints.NOTCH_REFERENCE_AIR_WORST_MM == pytest.approx(worst)
    # Each corner still sits on the relieved line parallel to the arm edge.
    for xc, yc in (plate.NOTCH_LEFT, plate.NOTCH_RIGHT):
        assert plate.arm_lower_edge_y(xc) - yc == pytest.approx(plate.NOTCH_RELIEF)
    # The face modelled on the edge (no relief) closes at the limits: refused.
    monkeypatch.setattr(plate, "NOTCH_RELIEF", 0.0)
    with pytest.raises(AssertionError, match="notch face meets the arm"):
        _reload_joints()


def test_pivot_sheet_line_prints_a_worst_engagement_it_never_overstates() -> None:
    printed = joints.PIVOT_ENGAGEMENT_WORST_PRINTED
    assert printed <= joints.PIVOT_ENGAGEMENT_WORST_D < printed + 0.01
    assert f"{printed:.2f}D MIN" in joints.PIVOT_SCREW_INSTALLATION_NOTES
    assert "MHA-PD-007 BLIND TAP" in joints.PIVOT_SCREW_INSTALLATION_NOTES


def test_pivot_engagement_starts_below_the_vendor_thread_neck(monkeypatch) -> None:
    # Every 0.02 the full thread starts lower costs 0.02 of engagement...
    monkeypatch.setattr(pivot, "FULL_THREAD_START", pivot.FULL_THREAD_START + 0.02)
    spec = importlib.util.spec_from_file_location(
        "_hanger_joints_neck", joints.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    assert math.isclose(
        joints.PIVOT_ENGAGEMENT_WORST - fresh.PIVOT_ENGAGEMENT_WORST, 0.02, abs_tol=1e-9
    )
    # ...and past the approved shortfall the joint is refused.
    monkeypatch.setattr(pivot, "FULL_THREAD_START", pivot.FULL_THREAD_START + 0.3)
    with pytest.raises(AssertionError, match="approved shortfall"):
        _reload_joints()


def test_the_shallowest_printed_hole_still_grips_the_pressed_pin(monkeypatch) -> None:
    assert joints.LATCH_PIN_ENGAGEMENT_WORST_D >= latch_pin.PRESS_ENGAGEMENT_MIN_D
    # A depth band of 3.6 leaves (8.50 - 3.6 - 0.443) / 3.175 = 1.40 D.
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH_BAND", 3.6)
    with pytest.raises(AssertionError, match="grips the latch pin"):
        _reload_joints()


def test_the_proud_range_counts_the_depth_row_and_the_pin_length_grade() -> None:
    """R9-50: 22.225 -/+ 0.010 in - (8.50 +/- 0.51), printed 12.96 TO 14.49."""
    grade = 0.010 * 25.4
    low = 7 / 8 * 25.4 - grade - (8.50 + 0.51)
    high = 7 / 8 * 25.4 + grade - (8.50 - 0.51)
    assert joints.LATCH_PIN_PROUD_RANGE == pytest.approx((low, high), abs=1e-9)
    assert f"{low:.2f} TO {high:.2f}" == "12.96 TO 14.49"


def test_the_far_face_gate_refuses_the_three_quarter_pin(monkeypatch) -> None:
    """R9-50: the 3/4 dowel stops short of the one-piece hook's far face with
    the ear's 1 deg bend, the screws' drift, the formed band and the length
    grade; the gate refuses it and accepts the 7/8 pin in the 8.50 hole.
    With the latch hole's height at ±0.065 the 3/4 dowel in a 6.10 hole
    barely clears, so the refusal is shown 0.05 deeper."""
    assert joints.LATCH_PIN_FAR_FACE_MARGIN_WORST > 0.6
    monkeypatch.setattr(latch_pin, "LENGTH", 0.75 * 25.4)
    monkeypatch.setattr(latch_pin, "PROUD", 0.75 * 25.4 - 6.10)
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", 6.10)
    clearing = _reload_joints()
    assert 0.0 < clearing.LATCH_PIN_FAR_FACE_MARGIN_WORST < 0.05
    monkeypatch.setattr(latch_pin, "PROUD", 0.75 * 25.4 - 6.15)
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", 6.15)
    with pytest.raises(
        AssertionError,
        match=r"MHA-VN-042 pin / MHA-PD-014 strip far face.* 0\.\d+ short",
    ):
        _reload_joints()


def test_the_pin_hole_depth_is_what_leaves_the_pin_proud(monkeypatch) -> None:
    low, high = joints.LATCH_PIN_PROUD_RANGE
    assert low < latch_pin.PROUD < high
    # The pin bottoms on the floor: a deeper hole sinks it.
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", arm.PIN_HOLE_DEPTH + 0.5)
    with pytest.raises(AssertionError, match="does not leave the latch pin PROUD"):
        _reload_joints()


def test_the_reamed_hole_keeps_the_press_at_both_limits(monkeypatch) -> None:
    assert min(joints.LATCH_PIN_PRESS_INTERFERENCE) > 0.0
    # The dowel is only +0.0025 over nominal: a hole allowed 0.003 over loses it.
    monkeypatch.setattr(arm, "PIN_HOLE_DIA_BAND", (0.003, -0.010))
    with pytest.raises(AssertionError, match="loses the latch pin's press"):
        _reload_joints()


@pytest.mark.parametrize(
    "module",
    [bar, arm, plate],
    ids=["pd-support-bar", "pd-transgear-arm", "pd-transgear-arm-plate"],
)
def test_every_wall_holds_the_target_at_the_printed_worst_case(module) -> None:
    for name, (nominal, worst) in module.WALLS.items():
        assert worst <= nominal, name
        assert worst >= module.WALL_TARGET, name


def test_spacer_wall_is_the_one_printed_shortfall() -> None:
    worst = (spacer.OD - spacer.OD_BAND - spacer.BORE_DIA_MAX) / 2.0
    assert math.isclose(spacer.WALL_WORST, worst)
    assert spacer.WALL_WORST_PRINTED <= worst + 1e-9 < 2.0
    assert f"{spacer.WALL_WORST_PRINTED:.2f} MIN" in spacer.WALL_NOTE
