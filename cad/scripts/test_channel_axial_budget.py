"""Offline contract: every channel's cam sits axially where its flat rod can
join cam and rocker without binding (#743 L20 d', #948 ruling R).

The rod is flat: its ring rides the cam and its fork straddles the arm in one
plane (rocker_bank_layout.ARM_MID_DZ is cam_plane.CAM_MID_DZ), so a
rigid rod held at both ends tolerates only the ring's float in the cam slot
plus the fork's side clearance on the arm. The banks' build-up deviations
are laid out by separate modules; only a test sees both, so the cross-bank
budget lives here. Both banks are spring-preloaded onto their mic-compensated
datums (#948 ruling R, PR #1292), so neither carries end play.
"""

from __future__ import annotations

import pytest

import _config
import cam_plane
import ch_connecting_rod_spec as rod
import ch_rod_pivot_pin_spec as pin
import cylinder_bank_layout as bank
import dt_cylinder_gear_spec as gear
import ch_rocker_arm_spec as arm
import rocker_bank_layout as rocker


def _rocker_partial_band(n: int) -> tuple[float, float]:
    """(upper, lower) summed hub-length deviation of any n hubs of an
    accepted rocker stack (the cylinder bank's partial_stack_band rule)."""
    upper, lower = arm.HUB_LENGTH_BAND
    accept_upper, accept_lower = rocker.STACK_L20_ACCEPT_BAND
    rest = rocker.COUNT - n
    return (
        min(n * upper, accept_upper - rest * lower),
        max(n * lower, accept_lower - rest * upper),
    )


def _clear_window() -> tuple[float, float]:
    """Delta range (cam slot centre less rocker plate centre, deviations) a
    rigid flat rod spans without binding: its ring (or shank, the thicker)
    floats in the thinnest slot, its fork in the least side clearance on the
    thickest arm, less what the rod's tine match and the two symmetry
    controls (ring/shank to slot, strap to hub) may offset the mid-planes."""
    assert rocker.ARM_MID_DZ == cam_plane.CAM_MID_DZ  # one nominal plane
    thickest = max(
        rod.RING_THICKNESS + rod.RING_THICKNESS_BAND[0],
        rod.SHANK_THICKNESS + rod.SHANK_THICKNESS_BAND[0],
    )
    ring_float = (bank.SLOT_MIN - thickest) / 2.0
    fork_float = pin.BUDGET["side_clearance_min"] / 2.0
    offsets = (
        rod.FORK_TINE_MATCH / 2.0
        + rod.RING_SLOT_SYMMETRY / 2.0
        + arm.STRAP_HUB_SYMMETRY / 2.0
    )
    half = ring_float + fork_float - offsets
    return -half, half


def _station_delta(j: int) -> tuple[float, float]:
    """(min, max) Delta at station j: both datums DRO-set with the mic
    compensation (back washer, north thrust washer), both banks held north on them
    by their springs (no end play)."""
    cam_datum = sum(bank.DATUM_CHAIN_STACK.values())
    arm_datum = sum(rocker.NORTH_DATUM_STACK.values())
    north = bank.COUNT - 1 - j
    cam_upper, cam_lower = bank.partial_stack_band(north)
    half_slot = (gear.FACE_WIDTH_TOLERANCE_MM + gear.OVERALL_THICKNESS_BAND[0]) / 2.0
    cam = (
        -(cam_datum + cam_upper + half_slot),
        cam_datum - cam_lower + half_slot,
    )
    hub_upper, hub_lower = _rocker_partial_band(north)
    gap = (
        -(arm_datum + hub_upper + arm.HUB_LENGTH_BAND[0] / 2.0),
        arm_datum - hub_lower - arm.HUB_LENGTH_BAND[1] / 2.0,
    )
    return cam[0] - gap[1], cam[1] - gap[0]


def test_the_clear_window_is_the_flat_rods() -> None:
    low, high = _clear_window()
    assert (low, high) == pytest.approx((-0.72725, 0.72725), abs=0.001)
    # The ring and shank bands the window rests on are the title block's
    # 3-place class (#948 ruling R).
    three_place = _config.title_block("linear_3pl")["value_in"] * 25.4
    assert rod.RING_THICKNESS_BAND == pytest.approx((three_place, -three_place))
    assert rod.SHANK_THICKNESS_BAND == pytest.approx((three_place, -three_place))


def test_the_worst_station_keeps_a_spare() -> None:
    worst = max(range(bank.COUNT), key=lambda j: _station_delta(j)[1] - _station_delta(j)[0])
    assert worst == 7
    assert _station_delta(worst) == pytest.approx((-0.5635, 0.6885), abs=1e-4)



@pytest.mark.parametrize("j", range(bank.COUNT))
def test_every_flat_rod_spans_its_cam_and_arm(j: int) -> None:
    low, high = _clear_window()
    delta_min, delta_max = _station_delta(j)
    assert low <= delta_min and delta_max <= high
