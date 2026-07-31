"""Offline contracts for the v2 channel-bank installation cascade."""

from __future__ import annotations

import math

import pytest

import _config
import _cwm
import build_channel_assembly as channel
import connecting_rod_spec
import fulcrum_shaft_spec
import pivot_shaft_spec
from _assembly import _seed_flip
from cone_pivot_post_installation import CHANNEL_Z0, DRUM_X, MECHANISM_Z_SHIFT


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


def test_both_amplitude_endpoints_close_on_the_upright_tangent_branch() -> None:
    """The signed +/- travel states must satisfy contact and lever closure."""
    max_travel = float(_config.machine("amplitude", "max_travel_mm"))
    endpoint_angles: list[float] = []

    for amplitude in (-max_travel, max_travel):
        state = channel.solve_state(amplitude)
        beta = -math.radians(state["bar_tilt"])
        bar_u = (math.sin(beta), math.cos(beta))
        foot = (channel.PIVOT[0] + amplitude, state["bar_bottom"])
        arc = (channel._ARC["acx"], channel._ARC["acy"])
        tangent_distance = sum(
            (arc[i] - foot[i]) * bar_u[i] for i in range(2)
        )
        assert math.isclose(
            tangent_distance, channel.BAR_TANGENT_DISTANCE, abs_tol=1e-6
        )

        pin = (
            foot[0] + channel.BAR_TOP_TO_FOOT * bar_u[0],
            foot[1] + channel.BAR_TOP_TO_FOOT * bar_u[1],
        )
        assert math.isclose(
            math.dist(pin, channel.FULCRUM),
            channel.LEVER_BAR_PIN_X,
            abs_tol=1e-6,
        )
        endpoint_angles.append(
            90.0 - (state["bar_tilt"] - state["arm_tilt"])
        )

    assert channel.AMPLITUDE_ANGLE_LIMITS == pytest.approx(
        (min(endpoint_angles), max(endpoint_angles)), abs=1e-9
    )
    assert channel.ROCKER_ANGLE_LIMITS[0] < 90.0 < channel.ROCKER_ANGLE_LIMITS[1]


def test_existing_shafts_and_translated_mounts_cover_the_shifted_bank() -> None:
    assert channel.CHANNEL_BANK_REAR_SHIFT == MECHANISM_Z_SHIFT

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


def test_copied_internal_rod_axial_mate_is_reset_to_the_seed_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Mate:
        Flipped = False
        CanBeFlipped = True

    mate = Mate()
    monkeypatch.setattr(_cwm, "_component_distance_mate", lambda *_a, **_kw: mate)

    assert _cwm.ensure_component_distance_mate_flip(
        object(), "connecting-rod-3", 4.05, True
    )
    assert mate.Flipped is True
    assert not _cwm.ensure_component_distance_mate_flip(
        object(), "connecting-rod-3", 4.05, True
    )
