"""Offline contract: every channel's cam sits axially where its flat rod can
join cam and rocker without binding (#743 L20 d', #948).

The rod is flat: its ring rides the cam and its fork straddles the arm in one
plane (rocker_bank_layout.ARM_MID_DZ is cylinder_bank_layout.CAM_MID_DZ), so a
rigid rod held at both ends tolerates only the ring's float in the cam slot
plus the fork's side clearance on the arm. The banks' build-up deviations
are laid out by separate modules; only a test sees both, so the cross-bank
budget lives here.
"""

from __future__ import annotations

import pytest

import _config
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
    rigid flat rod spans without binding: its ring floats in the thinnest
    slot, its fork in the least side clearance on the thickest arm."""
    assert rocker.ARM_MID_DZ == bank.CAM_MID_DZ  # one nominal plane
    ring_float = bank.RING_SLOT_MARGIN / 2.0
    fork_float = pin.BUDGET["side_clearance_min"] / 2.0
    return -(ring_float + fork_float), ring_float + fork_float


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


def test_the_clear_window_is_the_flat_rods() -> None:
    low, high = _clear_window()
    assert (low, high) == pytest.approx((-0.28675, 0.28675), abs=0.001)
    # The ring band the window rests on is the title block's 2-place class.
    two_place = _config.title_block("linear_2pl")["value_in"] * 25.4
    assert rod.RING_THICKNESS_BAND[0] == pytest.approx(two_place)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#948: neither bank is preloaded, so the stations' Delta spans about "
        "-1.19..+1.41 against the flat rod's +/-0.29; bank retention (or a "
        "modelled rod lean) must bring every station's Delta inside the window"
    ),
)
@pytest.mark.parametrize("j", range(bank.COUNT))
def test_every_flat_rod_spans_its_cam_and_arm(j: int) -> None:
    low, high = _clear_window()
    delta_min, delta_max = _station_delta(j)
    assert low <= delta_min and delta_max <= high
