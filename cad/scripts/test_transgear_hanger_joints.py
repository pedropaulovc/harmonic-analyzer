"""SolidWorks-free contracts for the ch. 23 hanger's screwed joints.

``transgear_hanger_joints`` judges each joint at the worst case of the printed
bands and refuses to import when one fails. These tests show that each check
still fires when a mating number drifts.
"""

from __future__ import annotations

import importlib.util
import math

import pytest

from _column_clamp_interface import BAR_DEPTH
from _inch_wall_limits import WALL_TARGET_MM
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import transgear_hanger_joints as joints
import paper_drive_arm_registration as registration
import pd_vn_transgear_latch_pin_spec as latch_pin
import pd_vn_transgear_pivot_screw_spec as pivot
import pd_transgear_pivot_spacer_spec as spacer
import pd_vn_transgear_pivot_spring_spec as spring


def _reload_joints():
    spec = importlib.util.spec_from_file_location(
        "_hanger_joints_perturbed", joints.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    return fresh


def test_pivot_screw_refuses_a_bar_too_thin_for_one_and_a_half_d(monkeypatch) -> None:
    # Thinnest bar, deepest recess, one pitch charged at the faced tip and the
    # vendor neck: (9.373 - 0.508) - 0.794 - 1.7653 = 6.306 = 1.514 D.
    assert joints.PIVOT_ENGAGEMENT_WORST == pytest.approx(
        BAR_DEPTH
        - bar.BAR_DEPTH_BAND
        - pivot.TIP_RECESS[1]
        - pivot.INCOMPLETE_TIP_LEN_MAX
        - pivot.FULL_THREAD_START
    )
    assert joints.PIVOT_ENGAGEMENT_WORST_D == pytest.approx(1.514, abs=1e-3)
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        0.102, abs=1e-3
    )
    # A .X depth band (+/-0.25) on the bar leaves 6.19 = 1.49 D: refused.
    monkeypatch.setattr(bar, "BAR_DEPTH_BAND", 0.25)
    with pytest.raises(AssertionError, match="worst engagement"):
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
    """R9-71: the MHA-PD-VN-63 spring holds the arm on the spacer at every printed
    corner, never pressed past its catalogue working height.  A deeper floor
    (7.0) presses it past that height; the old 6.4 floor, without the retired
    MHA-PD-VN-67 shim, leaves it loose."""
    assert joints.SPRING_ROOM_MIN == pytest.approx(0.693, abs=1e-3)
    assert joints.SPRING_ROOM_MAX == pytest.approx(0.957, abs=1e-3)
    assert spring.WORKING_HEIGHT <= joints.SPRING_ROOM_MIN
    assert joints.SPRING_ROOM_MAX < spring.FREE_HEIGHT
    assert joints.SPRING_PRELOAD_N == pytest.approx((18.63, 39.43), abs=0.01)
    for floor in (7.0, 6.4):
        monkeypatch.setattr(arm, "SPOT_FACE_FLOOR_FROM_FRONT", floor)
        with pytest.raises(AssertionError, match="leaves the spring"):
            _reload_joints()


def test_the_shallower_spot_face_gives_the_spring_its_model_room(monkeypatch) -> None:
    """Owner ruling 2026-10-31 (#290): the 9.5 bar grew 0.5 rearward and the
    spacer gave it up (5.5 -> 5.0); the spot-face floor rises 0.5 (6.4 ->
    6.9) in place of the retired shim, so the room keeps the spring's 0.80
    model height."""
    assert spacer.LENGTH + arm.SPOT_FACE_FLOOR_FROM_FRONT == pytest.approx(
        pivot.SHOULDER_LEN - spring.MODEL_HEIGHT
    )
    assert joints.SPRING_ROOM_NOMINAL == pytest.approx(spring.MODEL_HEIGHT)
    monkeypatch.setattr(arm, "SPOT_FACE_FLOOR_FROM_FRONT", 6.905)
    with pytest.raises(AssertionError, match="nominal room"):
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


def test_plate_weight_input_is_the_native_recipe_volume() -> None:
    """The analytic plate volume is the native recipe's: each section's own
    outline (an independent shoelace over its vertices plus the end round's
    sector) times its depth, less the recipe's cuts."""
    import build_pd_transgear_arm_plate as recipe

    def outline_area(left, right):
        vertices, (start, end) = plate.section_outline(left, right)
        # The sector runs from the vertex before K to the vertex after it.
        k = vertices.index((0.0, 0.0))
        for neighbour, angle in ((vertices[k + 1], start), (vertices[k - 1], end)):
            assert math.hypot(*neighbour) == pytest.approx(plate.END_R)
            assert math.atan2(neighbour[1], neighbour[0]) == pytest.approx(angle)
        shoelace = sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(vertices, vertices[1:] + vertices[:1])
        )
        return abs(shoelace) / 2.0 + plate.END_R**2 * (end - start) / 2.0

    sections = (
        outline_area(plate.TOP_LEFT, plate.TOP_RIGHT) * plate.THICKNESS_OVER_ARM
        + outline_area(plate.NOTCH_LEFT, plate.NOTCH_RIGHT) * plate.NOTCH_DEPTH
    )
    assert recipe.V_PLATE + recipe.V_LOWER == pytest.approx(sections, rel=1e-12)
    native = (
        sections + recipe.V_HUB + recipe.V_BOSS - recipe.V_BORE - recipe.V_HOLES
        - len(plate.SCREW_HOLES) * recipe.V_CSK
        - len(plate.LOCATOR_SITES_MM) * math.pi * (plate.LOCATOR_HOLE_DIA_MM / 2.0)**2
        * plate.THICKNESS_OVER_ARM
    )
    assert plate.nominal_material_properties()["volume_mm3"] == pytest.approx(native, rel=1e-12)


def test_reference_entry_pays_published_fillet_and_independent_critical_axes() -> None:
    """Reference datum pose only, not an ISO pin-end whole-body certificate."""
    import pd_vn_transgear_arm_plate_screw_spec as screw
    angle = (math.atan(arm.REDUCER_POSITION_DIAMETER / arm.CLAMP_TAP_PROJECTED_HEIGHT_MM)
             + registration.ARM_PLATE_TILT_MAX_RAD)
    required = (screw.THREAD_MAJOR / 2.0 + screw.UNDER_HEAD_FILLET_RADIUS_MAX_MM) / math.cos(angle)
    # The plate hole's zone runs into the arm: inside the plate its axis is
    # extrapolated to the deepest stock's rear face.
    in_plate = plate.REDUCER_POSITION_RADIUS + (
        plate.THICKNESS_OVER_ARM + plate.THICKNESS_OVER_ARM_BAND
    ) * plate.REDUCER_POSITION_DIAMETER / plate.CLAMP_PLATE_PROJECTED_HEIGHT_MM
    expected = plate.SCREW_HOLE_DIA / 2.0 - required - arm.REDUCER_POSITION_RADIUS - in_plate
    assert joints.PLATE_SCREW_REFERENCE_ENTRY_MARGIN_MM == pytest.approx(expected)
    assert expected > 0.0


def test_published_standard_stock_and_entire_head_bounds_do_not_use_receiving_caps(monkeypatch) -> None:
    import pd_vn_transgear_arm_plate_screw_spec as screw
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
    import pd_vn_transgear_arm_plate_screw_spec as screw
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
    with pytest.raises(AssertionError, match="MHA-PD-VN-56 worst engagement"):
        _reload_joints()


def test_plate_notch_face_clears_the_arm_edge_at_every_limit(monkeypatch) -> None:
    """Reference-pose graded clearance; the notch does not locate."""
    import pd_transgear_arm_plate_spec as plate_spec

    corner_band = plate_spec.BAND_BY_PLACES[plate_spec.NOTCH_PLACES]
    worst = (plate.NOTCH_RELIEF - corner_band) * math.cos(arm.EDGE_LEAN) - arm.OUTLINE_BAND
    assert worst > 0.0
    assert joints.NOTCH_REFERENCE_AIR_WORST_MM == pytest.approx(worst)
    # Each corner still sits on the relieved line parallel to the arm edge.
    for xc, yc in (plate.NOTCH_LEFT, plate.NOTCH_RIGHT):
        assert plate.arm_lower_edge_y(xc) - yc == pytest.approx(plate.NOTCH_RELIEF)
    # The face modelled on the edge (no relief) closes at the limits: refused.
    monkeypatch.setattr(plate, "NOTCH_RELIEF", 0.0)
    with pytest.raises(AssertionError, match="notch face meets the arm"):
        _reload_joints()


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
    # ...and below 1.5 D the joint is refused.
    monkeypatch.setattr(pivot, "FULL_THREAD_START", pivot.FULL_THREAD_START + 0.3)
    with pytest.raises(AssertionError, match="worst engagement"):
        _reload_joints()


def test_the_shallowest_printed_hole_still_grips_the_pressed_pin(monkeypatch) -> None:
    assert joints.LATCH_PIN_ENGAGEMENT_WORST_D >= latch_pin.PRESS_ENGAGEMENT_MIN_D
    # A depth band of 3.6 leaves (8.50 - 3.6 - 0.443) / 3.175 = 1.40 D.
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH_BAND", 3.6)
    with pytest.raises(AssertionError, match="grips the latch pin"):
        _reload_joints()


def test_the_proud_range_counts_the_depth_row_and_the_pin_length_grade() -> None:
    """R9-50: 22.225 -/+ 0.010 in - (8.50 at its printed .33 reach)."""
    grade = 0.010 * 25.4
    reach = arm.PIN_HOLE_DEPTH_BAND
    assert reach == pytest.approx(8.50 - (0.33 - 0.01) * 25.4)
    low = 7 / 8 * 25.4 - grade - (8.50 + reach)
    high = 7 / 8 * 25.4 + grade - (8.50 - reach)
    assert joints.LATCH_PIN_PROUD_RANGE == pytest.approx((low, high), abs=1e-9)


def test_the_far_face_gate_refuses_the_three_quarter_pin(monkeypatch) -> None:
    """R9-50: the 3/4 dowel stops short of the one-piece hook's far face with
    the ear's 1 deg bend, the screws' drift, the formed band and the length
    grade; the gate refuses it and accepts the 7/8 pin in the 8.50 hole.
    At the printed bands the 3/4 dowel in a 6.20 hole barely clears, so the
    refusal is shown 0.05 deeper."""
    assert joints.LATCH_PIN_FAR_FACE_MARGIN_WORST > 0.6
    monkeypatch.setattr(latch_pin, "LENGTH", 0.75 * 25.4)
    monkeypatch.setattr(latch_pin, "PROUD", 0.75 * 25.4 - 6.20)
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", 6.20)
    clearing = _reload_joints()
    assert 0.0 < clearing.LATCH_PIN_FAR_FACE_MARGIN_WORST < 0.05
    monkeypatch.setattr(latch_pin, "PROUD", 0.75 * 25.4 - 6.25)
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", 6.25)
    with pytest.raises(
        AssertionError,
        match=r"MHA-PD-VN-58 pin / MHA-PD-14 strip far face.* 0\.\d+ short",
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
    target = getattr(module, "WALL_TARGET", WALL_TARGET_MM)
    for name, (nominal, worst) in module.WALLS.items():
        assert worst <= nominal, name
        assert worst >= getattr(module, "WALL_FLOORS", {}).get(name, target), name


def test_the_latch_pin_ligament_is_the_arm_s_one_tracked_shortfall() -> None:
    # Owner ruling 2026-10-27 (#1379, tracked in #2019): the full-budget
    # ligament, at the .XXX height reach (coordinator ruling (a)), stays under
    # the .080 target until the next stock size up.
    assert arm.WALL_FLOORS == {"pin hole to faces": arm.LATCH_PIN_WALL_FLOOR}
    worst = arm.WALLS["pin hole to faces"][1]
    assert arm.LATCH_PIN_WALL_FLOOR == pytest.approx(0.060 * 25.4)
    assert arm.LATCH_PIN_WALL_FLOOR <= worst < arm.WALL_TARGET
    assert worst == pytest.approx(1.6744, abs=1e-4)


def test_spacer_wall_holds_the_target_with_both_rim_breaks() -> None:
    worst = (
        (spacer.OD - spacer.OD_BAND - spacer.BORE_DIA_MAX) / 2.0
        - spacer.BORE_ECCENTRICITY
        - 2.0 * spacer.EDGE_BREAK
    )
    assert math.isclose(spacer.WALL_WORST, worst)
    assert worst >= spacer.WALL_TARGET
    assert not hasattr(spacer, "WALL_NOTE")
