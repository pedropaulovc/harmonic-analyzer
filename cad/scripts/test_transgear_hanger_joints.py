"""SolidWorks-free contracts for the ch. 23 hanger's screwed joints.

``transgear_hanger_joints`` judges each joint at the worst case of the printed
bands and refuses to import when one fails. These tests show that each check
still fires when a mating number drifts, and that the MHA-VN-041 sheet line
states the worst case it computes.
"""

from __future__ import annotations

import importlib.util
import itertools
import math

import pytest

import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import transgear_hanger_joints as joints
import vn_transgear_latch_pin_spec as latch_pin
import vn_transgear_pivot_screw_spec as pivot
import pd_transgear_pivot_spacer_spec as spacer
import vn_transgear_pivot_spring_spec as spring
from _hole_spec import TAP_DRILL_MM


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


def test_the_hanger_tilt_is_the_spacers_squareness_not_the_bore_float() -> None:
    """Codex P1 on 6c385465d: free on its shoulder the arm tilted by the bore
    clearance, 0.0421 rad.  Preloaded on the pressed spacer it tilts by the
    two face perpendicularities over the smallest face, 0.02 / 8.47."""
    assert joints.HANGER_TILT == pytest.approx(0.02 / 8.47, rel=1e-9)
    assert joints.HANGER_TILT < 0.042144 / 10.0


def test_the_hanger_still_falls_onto_its_hook_and_stays_square(monkeypatch) -> None:
    """The preload's friction never holds the hanger off the latch hook, and
    its weakest end still holds the arm square against the hanger's forward
    weight.  The rejected 9712K58 pair, ~3.5 times stiffer, held it off."""
    assert joints.HANGER_SWING_MARGIN >= 2.0
    assert joints.HANGER_TILT_HOLD_MARGIN >= 2.0
    monkeypatch.setattr(spring, "RATE_N_PER_MM", spring.RATE_N_PER_MM * 3.5)
    with pytest.raises(AssertionError, match="off the hook"):
        _reload_joints()
    monkeypatch.setattr(spring, "RATE_N_PER_MM", spring.RATE_N_PER_MM / 3.5 / 2.0)
    with pytest.raises(AssertionError, match="tilt moment"):
        _reload_joints()


def test_both_plate_screws_enter_their_taps_at_the_worst_pitch_mismatch(
    monkeypatch,
) -> None:
    """The arm's tap pitch at one limit, the plate's hole pitch at the other:
    the bands the two builds apply on the stations, against the float of two
    basic #8-32 majors in the smallest drilled holes."""
    import vn_transgear_arm_plate_screw_spec as screw
    import pd_transgear_arm_plate_spec as plate_spec
    import pd_transgear_arm_spec as arm_spec

    taps = arm.PLATE_TAP_STATIONS
    holes = [x for x, _y in plate.SCREW_HOLES]
    worst = 0.0
    for da1, da2, dp1, dp2 in itertools.product((-1.0, 1.0), repeat=4):
        tap_pitch = (taps[1] + da2 * arm_spec.HOLE_POSITION_TOLERANCE) - (
            taps[0] + da1 * arm_spec.HOLE_POSITION_TOLERANCE
        )
        hole_pitch = (holes[1] + dp2 * plate_spec.HOLE_POSITION_TOLERANCE) - (
            holes[0] + dp1 * plate_spec.HOLE_POSITION_TOLERANCE
        )
        worst = max(worst, abs(tap_pitch - hole_pitch))
    # Each shank may stand (hole - major) / 2 off its hole's axis.
    float_ = 2.0 * (plate.SCREW_HOLE_DIA - screw.THREAD_MAJOR) / 2.0
    assert worst < float_
    assert joints.PLATE_SCREW_PITCH_MARGIN == pytest.approx(float_ - worst)
    # The former Ø4.4 hole floats 0.234 over a 0.260 mismatch: refused.
    monkeypatch.setattr(plate, "SCREW_HOLE_DIA", 4.4)
    with pytest.raises(AssertionError, match="cannot enter both arm taps"):
        _reload_joints()


def _eccentric_corner():
    """The plate-screw corner from the printed rows, independent of the
    joint module: (eccentric lift, countersink seat shift, tap entry loss)."""
    import vn_transgear_arm_plate_screw_spec as screw
    import pd_transgear_arm_plate_spec as plate_spec
    import pd_transgear_arm_spec as arm_spec

    taps = arm.PLATE_TAP_STATIONS
    holes = [x for x, _y in plate.SCREW_HOLES]
    # The tap pitch at one limit, the hole pitch at the other.
    mismatch = max(
        abs(
            (taps[1] + da2 * arm_spec.HOLE_POSITION_TOLERANCE)
            - (taps[0] + da1 * arm_spec.HOLE_POSITION_TOLERANCE)
            - (holes[1] + dp2 * plate_spec.HOLE_POSITION_TOLERANCE)
            + (holes[0] + dp1 * plate_spec.HOLE_POSITION_TOLERANCE)
        )
        for da1, da2, dp1, dp2 in itertools.product((-1.0, 1.0), repeat=4)
    )
    # Each head seats half the mismatch off its countersink's axis and rides
    # up the 82° cone before it bears.
    cone = math.tan(math.radians(screw.HEAD_ANGLE_DEG / 2.0))
    lift = mismatch / 2.0 / cone
    shift = plate_spec.BAND_BY_PLACES[plate_spec.CSK_DIA_PLACES] / 2.0 / cone
    # Full thread starts where the countersink's 45° leg meets the tap drill
    # (R9-63), not the major: (4.3 - 3.454) / 2 = 0.423.
    entry = (arm.PLATE_TAP_CSK_DIA - TAP_DRILL_MM["#8-32"]) / 2.0
    return lift, shift, entry


def test_every_stock_plate_screw_stands_past_the_cut_on_an_eccentric_seat(
    monkeypatch,
) -> None:
    """R9-44: shortest stock screw (ASME B18.6.3, +0/-0.03 in), thickest
    plate and arm, head proud on a small countersink and riding its eccentric
    seat: the tip still clears the highest cut by its incomplete first thread."""
    import vn_transgear_arm_plate_screw_spec as screw
    import pd_transgear_arm_plate_spec as plate_spec

    lift, shift, entry = _eccentric_corner()
    assert lift == pytest.approx(0.1495, abs=5e-4)
    thick_plate = (
        plate.THICKNESS_OVER_ARM
        + plate_spec.BAND_BY_PLACES[plate_spec.THICKNESS_PLACES]
    )
    shortest = screw.STOCK_LENGTH - 0.03 * 25.4
    proud = shortest - thick_plate - shift - lift - (arm.THICKNESS + arm.THICKNESS_BAND)
    assert proud >= joints.PLATE_SCREW_CUT_PROUD_MAX + screw.PITCH
    assert joints.PLATE_SCREW_STOCK_PROUD_MIN == pytest.approx(proud)
    # The uncut 1/2 in screw this replaced stopped inside the arm, where its
    # own corner (lead and entry countersink lost) held under 1.5 D.
    uncut = 0.5 * 25.4 - 0.03 * 25.4 - thick_plate - shift - lift
    uncut -= screw.PITCH + entry
    assert uncut / screw.THREAD_MAJOR < joints.ENGAGEMENT_TARGET_D
    monkeypatch.setattr(screw, "STOCK_LENGTH", 0.5 * 25.4)
    with pytest.raises(AssertionError, match="too short to cut its lead off"):
        _reload_joints()


def test_cut_plate_screws_hold_one_and_a_half_d_in_the_thinnest_arm(
    monkeypatch,
) -> None:
    """Cut flush: full thread from the rear tap countersink to the front face,
    where the front countersink and the cut-end break overlap."""
    import vn_transgear_arm_plate_screw_spec as screw

    _lift, _shift, entry = _eccentric_corner()
    worst = arm.THICKNESS - arm.THICKNESS_BAND - entry - max(entry, 0.1)
    assert worst / screw.THREAD_MAJOR >= 1.5
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST == pytest.approx(worst)
    # Machinist review of 8b5e1f354: counted to the major, the sheet's 7.74
    # overstated the 7.07 the countersinks leave.
    assert worst == pytest.approx(7.0661, abs=1e-4)
    # The model is the screw as cut: its tip on the arm's front face.
    assert screw.LENGTH == pytest.approx(plate.THICKNESS_OVER_ARM + arm.THICKNESS)
    assert joints.PLATE_SCREW_TIP_INSIDE_NOMINAL == pytest.approx(0.0, abs=1e-9)
    assert joints.PLATE_SCREW_TIP_PROUD_MAX == joints.PLATE_SCREW_CUT_PROUD_MAX
    # A cut-end break past the arm's 1.5 D margin starves the joint.
    monkeypatch.setattr(screw, "CUT_END_BREAK_MAX", 1.7)
    with pytest.raises(AssertionError, match="MHA-VN-040 worst engagement"):
        _reload_joints()


def test_plate_notch_face_clears_the_arm_edge_at_every_limit(monkeypatch) -> None:
    """The face is not a locating surface: worst air stays positive with the
    plate floated to its extremes on the two screws."""
    import vn_transgear_arm_plate_screw_spec as screw
    import pd_transgear_arm_plate_spec as plate_spec

    c = (plate.SCREW_HOLE_DIA + plate.DRILL_GROWTH - screw.THREAD_MAJOR_MIN) / 2.0
    (x1, _), (x2, _) = sorted(plate.SCREW_HOLES)
    shift = 0.0
    for u1, u2 in itertools.product((-c, c), repeat=2):
        for xc, _yc in (plate.NOTCH_LEFT, plate.NOTCH_RIGHT):
            shift = max(shift, u1 + (u2 - u1) * (xc - x1) / (x2 - x1))
    corner_band = plate_spec.BAND_BY_PLACES[plate_spec.NOTCH_PLACES]
    closing = corner_band + plate.HOLE_POSITION_BAND + shift
    lean = math.cos(arm.EDGE_LEAN)
    worst = (plate.NOTCH_RELIEF - closing) * lean - arm.BAND_X
    assert worst > 0.0
    assert joints.NOTCH_AIR_WORST == pytest.approx(worst)
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
    With the hook's screw holes at ±0.05 the 3/4 dowel in its 6.05 hole
    keeps only 0.010, so the refusal is shown 0.05 deeper."""
    assert joints.LATCH_PIN_FAR_FACE_MARGIN_WORST > 0.6
    monkeypatch.setattr(latch_pin, "LENGTH", 0.75 * 25.4)
    monkeypatch.setattr(latch_pin, "PROUD", 0.75 * 25.4 - 6.05)
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", 6.05)
    clearing = _reload_joints()
    assert 0.0 < clearing.LATCH_PIN_FAR_FACE_MARGIN_WORST < 0.02
    monkeypatch.setattr(latch_pin, "PROUD", 0.75 * 25.4 - 6.10)
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH", 6.10)
    with pytest.raises(
        AssertionError,
        match=r"MHA-VN-042 pin / MHA-PD-014 strip far face.* 0\.040 short",
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
