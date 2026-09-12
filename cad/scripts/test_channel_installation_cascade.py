"""Offline contracts for the v2 channel-bank installation cascade."""

from __future__ import annotations

import math

import _config
import build_channel_assembly as channel
import connecting_rod_spec
import fulcrum_shaft_spec
import pivot_shaft_spec
import summing_lever_spec
from channel_axial_spec import CHANNEL_MID_DZ
from cylinder_gear_spec import CAM_THICKNESS, FACE_WIDTH
from _assembly import _seed_flip
from cone_pivot_post_installation import CHANNEL_Z0, DRUM_X, MECHANISM_Z_SHIFT, SUMMING_Z


def test_machine_config_and_channel_interface_share_one_installation_contract() -> None:
    assert math.isclose(
        _config.machine("channels", "station_z0_mm"), CHANNEL_Z0, abs_tol=1e-12
    )
    assert math.isclose(channel.Z0, CHANNEL_Z0, abs_tol=1e-12)
    assert channel.X_DRUM == DRUM_X
    assert CHANNEL_MID_DZ == -(FACE_WIDTH + CAM_THICKNESS) / 2.0

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
    assert channel.CHANNEL_BANK_REAR_SHIFT == MECHANISM_Z_SHIFT

    row_min = channel.z_station(0) + CHANNEL_MID_DZ - channel.LEVER_THICKNESS / 2.0
    row_max = (
        channel.z_station(channel.CHANNELS - 1)
        + CHANNEL_MID_DZ
        + channel.LEVER_THICKNESS / 2.0
    )

    pivot_min = channel.PIVOT_SHAFT_Z - pivot_shaft_spec.SHAFT_LENGTH / 2.0
    pivot_max = channel.PIVOT_SHAFT_Z + pivot_shaft_spec.SHAFT_LENGTH / 2.0
    assert pivot_min < row_min < row_max < pivot_max
    # 481ec429 (2026-09 pivot-bracket re-derive): the asymmetric A-frame/
    # support mounts became a symmetric pivot-bracket pair on the 170 shaft.
    bracket_lo, bracket_hi = channel.PIVOT_BRACKET_Z
    assert pivot_min < bracket_lo < row_min < row_max < bracket_hi < pivot_max

    fulcrum_min = channel.FULCRUM_SHAFT_Z - fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    fulcrum_max = channel.FULCRUM_SHAFT_Z + fulcrum_shaft_spec.SHAFT_LENGTH / 2.0
    assert fulcrum_min < row_min < row_max < fulcrum_max
    # The end keepers grip the shaft ENDS: ball centres 2.25 inboard of each
    # end, feet + screws inboard of the corner-boss lands (2026-08-02 remount).
    keeper_lo = channel.FULCRUM_SHAFT_Z - channel.KEEPER_Z_OFF
    keeper_hi = channel.FULCRUM_SHAFT_Z + channel.KEEPER_Z_OFF
    assert fulcrum_min < keeper_lo < row_min < row_max < keeper_hi < fulcrum_max
    assert channel.KEEPER_Z_OFF - channel.KEEPER_SCREW_Z_OFF == 14.75


def test_positive_fulcrum_station_uses_the_relearned_mate_side() -> None:
    assert _seed_flip(
        "fulcrum-shaft-1 datum z d=35.41", channel.FULCRUM_SHAFT_Z
    )


def test_spring_holes_follow_cam_plane_inside_fixed_summing_casting() -> None:
    for j in range(summing_lever_spec.HOLE_COUNT):
        hole_z = (
            summing_lever_spec.CHANNEL_Z0
            + j * summing_lever_spec.CHANNEL_PITCH
            + summing_lever_spec.HOLE_Z_OFFSET
        )
        assert math.isclose(hole_z + SUMMING_Z, channel.z_station(j) + CHANNEL_MID_DZ)
        assert -summing_lever_spec.PLATE_L / 2.0 < hole_z < summing_lever_spec.PLATE_L / 2.0


