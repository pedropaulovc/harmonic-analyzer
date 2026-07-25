"""Offline contracts for the v2 channel-bank installation cascade."""

from __future__ import annotations

import math

import _config
import build_channel_assembly as channel
import connecting_rod_spec
import fulcrum_shaft_spec
import pivot_shaft_spec
from _assembly import _seed_flip
from cone_pivot_post_installation import CHANNEL_Z0, DRUM_X, MACHINE_Z_SHIFT


def test_machine_config_and_channel_interface_share_one_installation_contract() -> None:
    assert math.isclose(
        _config.machine("channels", "station_z0_mm"), CHANNEL_Z0, abs_tol=1e-12
    )
    assert math.isclose(channel.Z0, CHANNEL_Z0, abs_tol=1e-12)
    assert channel.X_DRUM == DRUM_X
    assert channel.CAM_DZ == -3.25

    phase = math.radians(channel.GEAR_PHASE_DEG)
    assert channel.RING_CENTER == (
        DRUM_X + channel.CAM_ECC * math.sin(phase),
        channel.Y_DRIVE + channel.CAM_ECC * math.cos(phase),
    )


def test_rocker_and_rod_reclose_the_level_plumb_neutral_pose() -> None:
    assert connecting_rod_spec.CENTER_DISTANCE == channel.ROD_C2C
    assert abs(channel._ARC["arm_tilt"]) < 0.02
    assert abs(channel._ARC["rod_tilt"]) < 0.02


def test_existing_shafts_and_translated_mounts_cover_the_shifted_bank() -> None:
    assert channel.CHANNEL_BANK_REAR_SHIFT == MACHINE_Z_SHIFT

    row_min = channel.z_station(0) + channel.ARM_MID_DZ - channel.LEVER_THICKNESS / 2.0
    row_max = (
        channel.z_station(channel.CHANNELS - 1)
        + channel.ARM_MID_DZ
        + channel.LEVER_THICKNESS / 2.0
    )

    pivot_min = channel.PIVOT_SHAFT_Z - pivot_shaft_spec.SHAFT_LENGTH / 2.0
    pivot_max = channel.PIVOT_SHAFT_Z + pivot_shaft_spec.SHAFT_LENGTH / 2.0
    assert pivot_min < row_min < row_max < pivot_max
    assert pivot_min < channel.AFRAME_MOUNT_Z < channel.SUPPORT_Z < pivot_max

    fulcrum_min = channel.FULCRUM_SHAFT_Z - fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    fulcrum_max = channel.FULCRUM_SHAFT_Z + fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    assert fulcrum_min < row_min < row_max < fulcrum_max
    assert fulcrum_min < channel.LEVER_MOUNT_Z[0] < channel.LEVER_MOUNT_Z[1] < fulcrum_max


def test_positive_fulcrum_station_uses_the_relearned_mate_side() -> None:
    assert _seed_flip(
        "fulcrum-shaft-1 datum z d=35.41", channel.FULCRUM_SHAFT_Z
    )


def test_copied_rod_orientation_uses_the_relearned_spin_side() -> None:
    assert not _seed_flip(
        "J2 rod ch02 swing -> ring -53.0,99.2",
        channel.RING_CENTER[0],
        " @npn",
    )
