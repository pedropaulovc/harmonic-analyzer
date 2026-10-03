"""Offline contract: every channel's cam sits axially where its rod can clear
both neighbouring rocker plates (#743 L20 d', #948).

The two banks are laid out by separate modules on purpose: the rocker bank
reads no gear-train config (test_rocker_bank_layout forbids it importing
cylinder_bank_layout). Only a test sees both, so the cross-bank budget lives
here.
"""

from __future__ import annotations

import pytest

import _config
import ch_connecting_rod_spec as rod
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
    """Delta range (cam slot centre less rocker gap, deviations) over which a
    rigid rod can sit clear of both plates: its ring floats in the thinnest
    slot, its head is coplanar with the ring."""
    head_mid = bank.CAM_MID_DZ
    plate_below = rocker.ARM_MID_DZ - rocker.PITCH + arm.ARM_THICKNESS / 2.0
    plate_own = rocker.ARM_MID_DZ - arm.ARM_THICKNESS / 2.0
    south_gap = head_mid - rod.HEAD_THICKNESS / 2.0 - plate_below
    north_gap = plate_own - (head_mid + rod.HEAD_THICKNESS / 2.0)
    ring_float = bank.RING_SLOT_MARGIN / 2.0
    return -(south_gap + ring_float), north_gap + ring_float


def _station_delta(j: int) -> tuple[float, float]:
    """(min, max) Delta at station j: both datums DRO-set, both banks free to
    slide south by their end play (neither is preloaded)."""
    locate = bank.BACK_STRAP_LOCATE_BAND
    washer = bank.DATUM_CHAIN_STACK["back washer thickness"]
    north = bank.COUNT - 1 - j
    cam_upper, cam_lower = bank.partial_stack_band(north)
    half_slot = (gear.FACE_WIDTH_TOLERANCE_MM + gear.OVERALL_THICKNESS_BAND[0]) / 2.0
    cam = (
        -(locate + washer + bank.BANK_END_PLAY[1] + cam_upper + half_slot),
        locate + washer - cam_lower + half_slot,
    )
    hub_upper, hub_lower = _rocker_partial_band(north)
    gap = (
        -(locate + hub_upper + arm.HUB_LENGTH_BAND[0] / 2.0 + rocker.ROCKER_END_PLAY[1]),
        locate - hub_lower,
    )
    return cam[0] - gap[1], cam[1] - gap[0]


def test_the_clear_window_is_the_one_filed_on_948() -> None:
    low, high = _clear_window()
    assert (low, high) == pytest.approx((-0.465, 2.065), abs=0.001)
    # The ring band the window rests on is the title block's 2-place class.
    two_place = _config.title_block("linear_2pl")["value_in"] * 25.4
    assert rod.RING_THICKNESS_BAND[0] == pytest.approx(two_place)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#948: neither bank is preloaded, so E_b 0.55 alone exceeds the ~0.47 "
        "of south room; the rod-pin retention must bring every station's Delta "
        "inside the window"
    ),
)
@pytest.mark.parametrize("j", range(bank.COUNT))
def test_every_rod_can_sit_clear_of_both_rocker_plates(j: int) -> None:
    low, high = _clear_window()
    delta_min, delta_max = _station_delta(j)
    assert low <= delta_min and delta_max <= high
