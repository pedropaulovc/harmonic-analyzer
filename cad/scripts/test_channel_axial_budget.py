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
    thickest arm, less what the rod's printed locations (#982: the plate's
    near face, near tine and slot, all from the fork's datum face, and the
    plate's thickness) and the strap-to-hub symmetry control may offset the
    mid-planes."""
    assert rocker.ARM_MID_DZ == cam_plane.CAM_MID_DZ  # one nominal plane
    thickest = max(
        rod.RING_THICKNESS + rod.RING_THICKNESS_BAND[0],
        rod.SHANK_THICKNESS + rod.SHANK_THICKNESS_BAND[0],
    )
    ring_float = (bank.SLOT_MIN - thickest) / 2.0
    fork_float = pin.BUDGET["side_clearance_min"] / 2.0
    # Ring mid-plane from the datum face: the near face's band plus half the
    # thickness's. Slot mid-plane from it: the near tine's band plus half the
    # slot's.
    ring_offset = rod.RING_FACE_BAND[0] + rod.RING_THICKNESS_BAND[0] / 2.0
    slot_offset = rod.TINE_BAND[0] + rod.FORK_SLOT_BAND[0] / 2.0
    offsets = ring_offset + slot_offset + arm.STRAP_HUB_SYMMETRY / 2.0
    half = ring_float + fork_float - offsets
    return -half, half


def _station_delta(j: int) -> tuple[float, float]:
    """(min, max) Delta at j: cam bank accumulated from the south disc;
    rocker bank accumulated from its unchanged north thrust washer."""
    cam_datum = sum(bank.DATUM_CHAIN_STACK.values())
    arm_datum = sum(rocker.NORTH_DATUM_STACK.values())
    north = bank.COUNT - 1 - j
    # Cam-slot centre = south cam datum + sum(T0..Tj-1) + (Tj-FWj)/2.
    cam_upper, cam_lower = bank.partial_stack_band(j)
    half_slot = (gear.FACE_WIDTH_TOLERANCE_MM + gear.OVERALL_THICKNESS_BAND[0]) / 2.0
    cam = (
        -cam_datum + cam_lower - half_slot,
        cam_datum + cam_upper + half_slot,
    )
    hub_upper, hub_lower = _rocker_partial_band(north)
    gap = (
        -(arm_datum + hub_upper + arm.HUB_LENGTH_BAND[0] / 2.0),
        arm_datum - hub_lower - arm.HUB_LENGTH_BAND[1] / 2.0,
    )
    return cam[0] - gap[1], cam[1] - gap[0]


def test_the_clear_window_is_the_flat_rods() -> None:
    low, high = _clear_window()
    assert (low, high) == pytest.approx((-0.72905, 0.72905), abs=1e-6)
    # The plate's near face prints from the fork's datum face and its
    # thickness at the ring (#982 review r1): the same window the two face
    # ordinates (+/-0.05 each) spent.
    assert rod.RING_FACE_BAND == rod.RING_THICKNESS_BAND == (0.05, -0.05)
    assert rod.SHANK_THICKNESS_BAND == rod.RING_THICKNESS_BAND


def test_the_worst_station_keeps_a_spare() -> None:
    worst = max(range(bank.COUNT), key=lambda j: _station_delta(j)[1] - _station_delta(j)[0])
    assert worst == 12
    assert _station_delta(worst) == pytest.approx((-0.5673, 0.6923), abs=1e-4)



@pytest.mark.parametrize("j", range(bank.COUNT))
def test_every_flat_rod_spans_its_cam_and_arm(j: int) -> None:
    low, high = _clear_window()
    delta_min, delta_max = _station_delta(j)
    assert low <= delta_min and delta_max <= high
