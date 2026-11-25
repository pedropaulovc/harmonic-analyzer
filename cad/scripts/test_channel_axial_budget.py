"""Offline contract: every rocker arm is located along the bank by its own
connecting rod (#3114, owner ruling 2026-11-18; #743 L20 d').

The rod is flat: its ring rides the cam and its fork straddles the arm in one
plane (rocker_bank_layout.ARM_MID_DZ is cam_plane.CAM_MID_DZ). The ring, at
the original's .170, slides between the two tooth discs of its cam slot, so
the slot locates the rod; the arm floats on the pivot shaft and its strap
follows the fork. The cam bank's build-up puts each slot up to about 0.45 off
its nominal station, and the arm goes with it: the hubs are shorter than the
pitch so that no arm, and no run of arms, is held off its rod, and the
bracket ears stand clear of the end arms. The two banks are laid out by
separate modules; only a test sees both, so the cross-bank budget lives here.
"""

from __future__ import annotations

import pytest

import cam_plane
import ch_amplitude_bar_spec as bar
import ch_connecting_rod_spec as rod
import ch_rocker_arm_spec as arm
import cylinder_bank_layout as bank
import dt_cylinder_gear_spec as gear
import rocker_bank_layout as rocker
import sh_vn_pivot_pin_rod_spec as pin


def _slot_centre_band(j: int) -> tuple[float, float]:
    """(south, north) deviation of cam slot j's centre from its nominal
    station: the cam bank accumulated from its south datum, the slot centre
    being south datum + sum(T0..Tj-1) + (Tj - FWj)/2."""
    datum = sum(bank.DATUM_CHAIN_STACK.values())
    upper, lower = bank.partial_stack_band(j)
    half_slot = (gear.FACE_WIDTH_TOLERANCE_MM + gear.OVERALL_THICKNESS_BAND[0]) / 2.0
    return -datum + lower - half_slot, datum + upper + half_slot


def _carry() -> float:
    """How far a hub's mid-plane may stand off its rod's ring mid-plane with
    every float centred: the rod's printed locations (#982: the ring's near
    face, the near tine and the slot, all from the fork's datum face, and the
    ring's thickness) and half the strap-to-hub symmetry zone."""
    ring_offset = rod.RING_FACE_BAND[0] + rod.RING_THICKNESS_BAND[0] / 2.0
    slot_offset = rod.TINE_BAND[0] + rod.FORK_SLOT_BAND[0] / 2.0
    return ring_offset + slot_offset + arm.STRAP_HUB_SYMMETRY / 2.0


def _float() -> tuple[float, float]:
    """(least, most) play each side between a cam slot and its arm: the
    ring's in the slot plus the fork's on the strap."""
    slot_max = (
        gear.OVERALL_THICKNESS
        + gear.OVERALL_THICKNESS_BAND[0]
        - (gear.FACE_WIDTH - gear.FACE_WIDTH_TOLERANCE_MM)
    )
    ring_min = rod.RING_THICKNESS + rod.RING_THICKNESS_BAND[1]
    ring = (bank.RING_SLOT_MARGIN / 2.0, (slot_max - ring_min) / 2.0)
    fork = (
        pin.BUDGET["side_clearance_min"] / 2.0,
        pin.BUDGET["side_clearance_max"] / 2.0,
    )
    return ring[0] + fork[0], ring[1] + fork[1]


def _follow_band(j: int) -> tuple[float, float]:
    """(south, north) farthest hub j's mid-plane stands off its nominal
    station while its arm follows its rod."""
    south, north = _slot_centre_band(j)
    reach = _carry() + _float()[1]
    return south - reach, north + reach


def _slot_spacing_min(n: int) -> float:
    """Least distance between the centres of two cam slots n stations apart:
    sum(Ti..Tk-1) + (Tk - Ti)/2 - (FWk - FWi)/2, every gear thin and the two
    face widths opposed."""
    return (
        n * (gear.OVERALL_THICKNESS + gear.OVERALL_THICKNESS_BAND[1])
        - gear.FACE_WIDTH_TOLERANCE_MM
    )


def test_the_arm_plane_is_the_cam_plane() -> None:
    assert rocker.ARM_MID_DZ == cam_plane.CAM_MID_DZ  # one nominal plane


def test_the_ring_is_the_originals_and_slides_in_its_cam_slot() -> None:
    # Owner ruling 2026-11-18: ring about .170, shank about .138 (.13 at the
    # sheet's two places).
    assert rod.RING_THICKNESS == pytest.approx(0.170 * 25.4)
    assert rod.SHANK_THICKNESS == pytest.approx(0.13 * 25.4)
    assert rod.RING_FACE_BAND == rod.RING_THICKNESS_BAND == (0.0508, -0.0508)
    # The thinnest slot passes the thickest ring with the running floor, and
    # the shank is never proud of the ring.
    assert bank.SLOT_MIN == pytest.approx(4.5466)
    assert bank.RING_SLOT_MARGIN == pytest.approx(0.1778)
    assert bank.RING_SLOT_MARGIN >= bank.RUNNING_FLOOR == rocker.RUNNING_FLOOR
    assert min(rod.SHANK_INSIDE_RING_MIN) > 0.0
    assert _float() == pytest.approx((0.1524, 0.3556))
    assert _carry() == pytest.approx(0.2032)


def test_the_rocker_bank_is_not_preloaded() -> None:
    for gone in (
        "ROCKER_SPRING_SET",
        "ROCKER_PRELOAD",
        "STACK_L20_ACCEPT",
        "NORTH_WASHER_Z",
        "SOUTH_WASHER_Z",
    ):
        assert not hasattr(rocker, gone)
    assert arm.HUB_LENGTH_MAX < rocker.PITCH
    assert rocker.HUB_GAP == pytest.approx(0.5588)


def test_the_worst_station_is_mid_bank() -> None:
    spread = {j: _slot_centre_band(j) for j in range(bank.COUNT)}
    worst = max(spread, key=lambda j: spread[j][1] - spread[j][0])
    assert worst == 12
    assert spread[worst] == pytest.approx((-0.4543, 0.4543), abs=1e-4)
    assert _follow_band(worst) == pytest.approx((-1.0131, 1.0131), abs=1e-4)


@pytest.mark.parametrize("j", range(bank.COUNT - 1))
def test_neighbouring_hubs_clear_with_each_arm_centred_on_its_rod(j: int) -> None:
    """With each arm centred in its rod's play, the printed locations alone
    never bring two neighbouring hubs together."""
    clearance = _slot_spacing_min(1) - 2.0 * _carry() - arm.HUB_LENGTH_MAX
    assert clearance == pytest.approx(0.0254)
    assert clearance > 0.0


@pytest.mark.parametrize("n", range(1, bank.COUNT))
def test_no_run_of_hubs_holds_a_rod_off_its_cam_slot(n: int) -> None:
    """Two arms n stations apart, with the n - 1 between them, closed up hub
    on hub at the hubs' longest: the run still fits between the two rods'
    windows with the running floor to spare, so the hubs never push a ring
    onto a tooth disc."""
    windows = _slot_spacing_min(n) - 2.0 * _carry() + 2.0 * _float()[0]
    run = n * arm.HUB_LENGTH_MAX
    assert windows - run >= rocker.RUNNING_FLOOR
    if n == 1:
        assert windows - run == pytest.approx(0.3302)


@pytest.mark.parametrize("j", range(bank.COUNT))
def test_every_rocker_follows_its_rod_inside_the_hub_gaps_and_the_ears(j: int) -> None:
    south, north = _follow_band(j)
    if j == 0:
        assert -south <= rocker.END_ARM_FOLLOW_MAX
        assert -south == pytest.approx(0.7099, abs=1e-4)
    if j == bank.COUNT - 1:
        assert north <= rocker.END_ARM_FOLLOW_MAX
        assert north == pytest.approx(0.8353, abs=1e-4)
    # The bar leans from its lever down to the rocker it rides: over the top
    # notch's depth that lean takes a negligible part of the notch's least
    # float on the lever.
    lean = max(-south, north) / bar.TOP_PIN_Y * bar.TOP_NOTCH_HEIGHT
    assert lean < rocker.RUNNING_FLOOR / 4.0


def test_the_end_hubs_never_reach_their_ears() -> None:
    south, north = rocker.END_CLEARANCE_MIN
    assert (south, north) == pytest.approx((0.5538, 0.2490), abs=1e-4)
    assert min(south, north) >= rocker.RUNNING_FLOOR
    assert rocker.END_FLOAT == pytest.approx((1.6764, 1.27))
    # The same from this test's own stack, the ear at its locate band.
    for j, standoff, locate in (
        (0, rocker.SOUTH_EAR_STANDOFF, rocker.EAR_LOCATE_BAND[0]),
        (bank.COUNT - 1, rocker.NORTH_EAR_STANDOFF, rocker.EAR_LOCATE_BAND[1]),
    ):
        reach = max(abs(v) for v in _follow_band(j)) if j else -_follow_band(j)[0]
        assert standoff - locate - reach - arm.HUB_LENGTH_MAX / 2.0 >= rocker.RUNNING_FLOOR


def test_the_end_bars_never_reach_the_ears() -> None:
    """The end amplitude bar straddles its strap and floats in its foot
    notch; it stays off the ear its arm faces with the floor and the spare."""
    foot_float = (
        bar.BOTTOM_NOTCH_WIDTH
        + bar.BOTTOM_NOTCH_WIDTH_BAND[0]
        - (arm.ARM_THICKNESS + arm.ARM_THICKNESS_BAND[1])
    ) / 2.0
    for j, standoff, locate in (
        (0, rocker.SOUTH_EAR_STANDOFF, rocker.EAR_LOCATE_BAND[0]),
        (bank.COUNT - 1, rocker.NORTH_EAR_STANDOFF, rocker.EAR_LOCATE_BAND[1]),
    ):
        south, north = _follow_band(j)
        # The strap, not the hub: the symmetry zone is out of this chain.
        strap = (-south if j == 0 else north) - arm.STRAP_HUB_SYMMETRY / 2.0
        bar_face = (
            strap + foot_float + bar.NOTCH_OFFSET_TOLERANCE_MM + bar.BAR_WIDTH / 2.0
        )
        assert standoff - locate - bar_face >= rocker.RUNNING_FLOOR + rocker.MARGIN_SPARE
    assert rocker.BAR_TO_EAR == pytest.approx(
        rocker.NORTH_EAR_STANDOFF - bar.BAR_WIDTH / 2.0
    )


def test_adjacent_channel_springs_clear_at_the_catalogue_maximum_od() -> None:
    # Every channel spring's axis lies in its station plane (z_j + ARM_MID_DZ,
    # build_ch_channel_assembly), so neighbours' coils stand one station pitch
    # apart across Z whatever their in-plane angle. At the 9432K31 catalogue
    # maximum coil OD (.250 +.008, owner ruling 2026-11-17, #3044) they keep
    # about 1.07 mm.
    import _config
    import ch_vn_channel_spring_installed_spec as spring

    pitch = _config.machine("channels", "station_pitch_mm")
    od_max = spring.SUPPLIER_COIL_OD_MM + spring.SUPPLIER_COIL_OD_TOLERANCE_MM
    assert pitch - od_max == pytest.approx(1.0668)
    assert pitch - od_max > 1.0
