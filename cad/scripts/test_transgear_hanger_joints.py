"""SolidWorks-free contracts for the ch. 23 hanger's screwed joints.

``transgear_hanger_joints`` judges each joint at the worst case of the printed
bands and refuses to import when one fails. These tests show that each check
still fires when a mating number drifts, and that the MHA-168 sheet line
states the worst case it computes.
"""

from __future__ import annotations

import importlib.util
import math

import pytest

import support_bar_spec as bar
import transgear_arm_geometry as arm
import transgear_arm_plate_geometry as plate
import transgear_hanger_joints as joints
import transgear_latch_pin_spec as latch_pin
import transgear_pivot_screw_spec as pivot
import transgear_pivot_spacer_spec as spacer


def _reload_joints() -> None:
    spec = importlib.util.spec_from_file_location(
        "_hanger_joints_perturbed", joints.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)


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


def test_pivot_head_never_clamps_the_arm(monkeypatch) -> None:
    assert (
        0.0 < joints.HEAD_PLAY_MIN <= joints.HEAD_PLAY_NOMINAL <= joints.HEAD_PLAY_MAX
    )
    # A spacer long by the minimum play closes the gap at the worst case.
    monkeypatch.setattr(spacer, "LENGTH", spacer.LENGTH + joints.HEAD_PLAY_MIN)
    with pytest.raises(AssertionError, match="clamp the arm"):
        _reload_joints()


def test_plate_screws_refuse_a_plate_that_starves_their_engagement(monkeypatch) -> None:
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D
    monkeypatch.setattr(plate, "THICKNESS_OVER_ARM", plate.THICKNESS_OVER_ARM + 2.0)
    with pytest.raises(AssertionError, match="MHA-166 worst engagement"):
        _reload_joints()


def test_pivot_sheet_line_prints_a_worst_engagement_it_never_overstates() -> None:
    printed = joints.PIVOT_ENGAGEMENT_WORST_PRINTED
    assert printed <= joints.PIVOT_ENGAGEMENT_WORST_D < printed + 0.01
    assert f"{printed:.2f}D MIN" in joints.PIVOT_SCREW_INSTALLATION_NOTES
    assert "MHA-074 BLIND TAP" in joints.PIVOT_SCREW_INSTALLATION_NOTES


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
    # A depth band of 1.0 leaves (6.05 - 1.0 - 0.443) / 3.175 = 1.45 D.
    monkeypatch.setattr(arm, "PIN_HOLE_DEPTH_BAND", 1.0)
    with pytest.raises(AssertionError, match="grips the latch pin"):
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
    ids=["support-bar", "transgear-arm", "transgear-arm-plate"],
)
def test_every_wall_holds_the_target_at_the_printed_worst_case(module) -> None:
    for name, (nominal, worst) in module.WALLS.items():
        assert worst <= nominal, name
        assert worst >= module.WALL_TARGET, name


def test_spacer_wall_is_the_one_printed_shortfall() -> None:
    worst = (spacer.OD - spacer.OD_BAND - spacer.BORE_DIA - spacer.BORE_DIA_BAND) / 2.0
    assert math.isclose(spacer.WALL_WORST, worst)
    assert spacer.WALL_WORST_PRINTED <= worst + 1e-9 < 2.0
    assert f"{spacer.WALL_WORST_PRINTED:.2f} MIN" in spacer.WALL_NOTE
