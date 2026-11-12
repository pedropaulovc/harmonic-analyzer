"""Offline lockstep: every restated copy of the channel station pitch and of
station 0 equals the machine config (#1038 re-pitch, plan conflict 11).

``machine/channels.yaml`` owns the pitch and station 0. Some specs restate
them as literals on purpose, so the frame and summing closures do not re-key
on the channel config; until now only the native builds compared some of them
with the config (the lever hub had no offline guard at all). Moving any one of
them alone fails here.
"""

from __future__ import annotations

import pytest

import _config
import _cone_axis_constants as cone_axis
import cam_plane
import ch_channel_lever_spec as lever
import ch_fulcrum_keeper_spec as keeper
import ch_rocker_arm_spec as rocker
import cone_pitch
import dt_cylinder_gear_spec as cylinder_gear
import sm_summing_lever_spec as summing

PITCH = _config.machine("channels", "station_pitch_mm")
STATION_Z0 = _config.machine("channels", "station_z0_mm")

# The parts whose stacking length IS the pitch, and the stations laid out on it.
RESTATED_PITCHES = {
    "ch_rocker_arm_spec.HUB_LENGTH": rocker.HUB_LENGTH,
    "ch_channel_lever_spec.HUB_LENGTH": lever.HUB_LENGTH,
    "ch_fulcrum_keeper_spec._STATION_PITCH": keeper._STATION_PITCH,
    "sm_summing_lever_spec.CHANNEL_PITCH": summing.CHANNEL_PITCH,
    "dt_cylinder_gear_spec.OVERALL_THICKNESS": cylinder_gear.OVERALL_THICKNESS,
}


@pytest.mark.parametrize("name", sorted(RESTATED_PITCHES))
def test_restated_pitch_is_the_config_pitch(name: str) -> None:
    assert RESTATED_PITCHES[name] == PITCH, (
        f"{name} = {RESTATED_PITCHES[name]} but channels.station_pitch_mm = {PITCH}"
    )


def test_cone_seat_input_puts_the_drum_grid_on_the_config_pitch() -> None:
    # cone_incline.drum_seat_nominal_mm is tuned so the exact-tracking drum
    # pitch lands on the station grid (cylinder_bank_layout keeps it >= the
    # gear thickness, so it may only sit above by rounding).
    assert cone_pitch.Z_PITCH == pytest.approx(PITCH, rel=0.0, abs=1e-9)
    assert cone_pitch.Z_PITCH >= PITCH


def test_spring_row_sits_on_the_cam_plane_half_a_pitch_south() -> None:
    assert summing.HOLE_Z_OFFSET == pytest.approx(-PITCH / 2.0, rel=0.0, abs=1e-12)
    assert cam_plane.CAM_MID_DZ == pytest.approx(-PITCH / 2.0, rel=0.0, abs=1e-12)


def test_station_zero_mirrors_agree() -> None:
    assert STATION_Z0 == pytest.approx(cone_axis.CHANNEL_Z0, rel=0.0, abs=1e-9)
    # The summing lever is laid out in the pre-cascade frame and placed at
    # SUMMING_Z, so it restates the former station 0, not the shifted one.
    assert summing.CHANNEL_Z0 == cone_axis.FORMER_CHANNEL_Z0
