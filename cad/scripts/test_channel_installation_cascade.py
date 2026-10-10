"""Offline contracts for the v2 channel-bank installation cascade."""

from __future__ import annotations

import math

import pytest

import _config
import build_ch_channel_assembly as channel
import channel_kinematics
import ch_connecting_rod_spec
import cam_plane
import ch_fulcrum_shaft_spec
import rocker_bank_layout
from _assembly import _seed_flip, activate_assembly_contract
from dt_cone_pivot_post_installation import CHANNEL_Z0, DRUM_X, MECHANISM_Z_SHIFT


def test_machine_config_and_channel_interface_share_one_installation_contract() -> None:
    assert math.isclose(
        _config.machine("channels", "station_z0_mm"), CHANNEL_Z0, abs_tol=1e-12
    )
    assert math.isclose(channel.Z0, CHANNEL_Z0, abs_tol=1e-12)
    assert channel.X_DRUM == DRUM_X
    # #743 solid stack: the ring rides the middle of its closed cam slot.
    assert channel.CAM_DZ == pytest.approx(cam_plane.CAM_MID_DZ)
    assert channel.CAM_DZ == pytest.approx(-7.0565 / 2.0)

    phase = math.radians(channel.GEAR_PHASE_DEG)
    assert channel.RING_CENTER == (
        DRUM_X + channel.CAM_ECC * math.sin(phase),
        channel.Y_DRIVE + channel.CAM_ECC * math.cos(phase),
    )


def test_rocker_and_rod_reclose_the_level_plumb_neutral_pose() -> None:
    assert ch_connecting_rod_spec.CENTER_DISTANCE == channel.ROD_C2C
    assert abs(channel_kinematics.ARC["arm_tilt"]) < 0.02
    assert abs(channel_kinematics.ARC["rod_tilt"]) < 0.02


def test_existing_shafts_and_translated_mounts_cover_the_shifted_bank() -> None:
    assert channel.CHANNEL_BANK_REAR_SHIFT == MECHANISM_Z_SHIFT

    row_min = channel.z_station(0) + channel.ARM_MID_DZ - channel.LEVER_THICKNESS / 2.0
    row_max = (
        channel.z_station(channel.CHANNELS - 1)
        + channel.ARM_MID_DZ
        + channel.LEVER_THICKNESS / 2.0
    )

    # #743 PR2: the pivot shaft's origin is its north end; its
    # cylinder spans both bracket ears (rocker_bank_layout).
    pivot_max = channel.PIVOT_SHAFT_Z
    pivot_min = pivot_max - rocker_bank_layout.PIVOT_SHAFT_LENGTH
    assert pivot_min < row_min < row_max < pivot_max
    # 481ec429 (2026-09 pivot-bracket re-derive): the asymmetric A-frame/
    # support mounts became a pivot-bracket pair on the shaft.
    bracket_lo, bracket_hi = rocker_bank_layout.PIVOT_BRACKET_Z
    assert pivot_min < bracket_lo < row_min < row_max < bracket_hi < pivot_max

    fulcrum_min = channel.FULCRUM_SHAFT_Z - ch_fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    fulcrum_max = channel.FULCRUM_SHAFT_Z + ch_fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    assert fulcrum_min < row_min < row_max < fulcrum_max
    # The end keepers carry the shaft just inboard of its domed ends, their
    # outboard feet and screws past the lugs; both lugs float clear of the
    # lever-hub bank, centred on its mid-plane.
    keeper_lo = channel.FULCRUM_SHAFT_Z - channel.KEEPER_Z_OFF
    keeper_hi = channel.FULCRUM_SHAFT_Z + channel.KEEPER_Z_OFF
    assert fulcrum_min < keeper_lo < row_min < row_max < keeper_hi < fulcrum_max
    assert channel.KEEPER_SCREW_Z_OFF - channel.KEEPER_Z_OFF == 8.25
    assert channel.FULCRUM_SHAFT_Z == pytest.approx(rocker_bank_layout.STACK_MID_Z)
    assert channel.KEEPER_HUB_FLOAT == pytest.approx((0.4346, 0.4346), abs=1e-3)


def test_pivot_retention_keeps_both_washers_and_the_wave_spring() -> None:
    # The physical full-bank retention stack remains installed even when
    # CHANNEL_COUNT reduces the number of authored moving channels.
    south_ear, north_ear = rocker_bank_layout.PIVOT_BRACKET_Z
    south_washer = channel.SOUTH_WASHER_Z
    north_washer = channel.NORTH_WASHER_Z
    assert south_ear < south_washer[0] < south_washer[1]
    assert south_washer[1] < north_washer[0] < north_washer[1] < north_ear
    assert channel.ROCKER_SPRING_Z[1] == pytest.approx(south_washer[0])
    assert channel.ROCKER_SPRING_Z[0] < channel.ROCKER_SPRING_Z[1]
    assert len(channel.BRACKET_SCREW_XZ) == 2
    assert len(channel.PIVOT_SHAFT_FLAT_STATIONS) == 2


def test_fulcrum_station_keeps_the_learned_inverted_datum_side() -> None:
    # The bank-centred station is negative; the learned inversion is
    # side-independent (the +- keeper screws share one signature), so the
    # seed is the plain sign rule toggled.
    activate_assembly_contract("ch-channel")
    assert channel.FULCRUM_SHAFT_Z < 0.0
    assert not _seed_flip("ch-fulcrum-shaft-1 datum z d=0.50", channel.FULCRUM_SHAFT_Z)
