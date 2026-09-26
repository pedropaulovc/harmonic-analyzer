"""Offline contracts for the rocker-bank retention stack (issue #743, PR2)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import amplitude_bar_spec as bar
import cylinder_bank_layout as drum_bank
import pivot_bracket_spec as bracket
import pivot_shaft_spec as shaft
import rocker_arm_spec as arm
import rocker_bank_layout as bank
import rocker_thrust_washer_spec as washer
from _buildgraph import config_files_of, module_deps_of

SCRIPTS = Path(__file__).resolve().parent
_BAND_2PL = _config.title_block("linear_2pl")["value_in"] * 25.4  # 0.508


def test_hub_length_is_the_station_pitch_and_only_comes_out_long() -> None:
    assert arm.HUB_LENGTH == pytest.approx(
        _config.machine("channels", "station_pitch_mm"), abs=1e-9
    )
    upper, lower = arm.HUB_LENGTH_BAND
    assert lower == 0.0 < upper == pytest.approx(0.05)
    assert bank.STACK_L20 == pytest.approx(bank.COUNT * arm.HUB_LENGTH)
    assert bank.STACK_L20_ACCEPT == pytest.approx((bank.STACK_L20, bank.STACK_L20 + 0.20))


def test_end_play_rule_is_the_cylinder_bank_rule() -> None:
    """The rocker layout redefines the feeler rule rather than importing
    cylinder_bank_layout (which would pull gear_train/cone_incline into the
    pivot shaft's config deps); this pins the two in lockstep."""
    assert bank.MIN_END_PLAY == drum_bank.MIN_END_PLAY
    assert bank.MARGIN_SPARE == drum_bank.MARGIN_SPARE
    assert bank.FEELER_STEP == drum_bank.FEELER_STEP
    assert bank.ROCKER_END_FEELER_BAND == drum_bank.BANK_END_FEELER_BAND
    assert bank.ROCKER_END_FEELER == pytest.approx(0.45)
    assert bank.ROCKER_END_PLAY == pytest.approx((0.35, 0.55))


def test_hub_mid_planes_are_the_channel_arm_planes() -> None:
    z0 = _config.machine("channels", "station_z0_mm")
    pitch = _config.machine("channels", "station_pitch_mm")
    assert bank.ARM_MID_DZ == 0.8
    for j in (0, 7, 19):
        assert bank.hub_mid_z(j) == pytest.approx(z0 + pitch * j + 0.8)
    assert bank.STACK_MID_Z == pytest.approx((bank.hub_mid_z(0) + bank.hub_mid_z(19)) / 2)


def test_stack_closes_north_on_the_shoulder_against_the_north_ear() -> None:
    """Reading 1 (user, #743 Q4): the integral shoulder bears on the north
    ear's inner face and hub 19 bears on the shoulder; no north washer."""
    assert bank.HUB19_NORTH_FACE_Z == pytest.approx(bank.hub_mid_z(19) + arm.HUB_LENGTH / 2)
    assert bank.SHOULDER_Z == pytest.approx(
        (bank.HUB19_NORTH_FACE_Z, bank.HUB19_NORTH_FACE_Z + shaft.SHOULDER_LENGTH)
    )
    assert bank.NORTH_EAR_INNER_Z == pytest.approx(bank.SHOULDER_Z[1])
    assert bank.NORTH_EAR_OUTER_Z == pytest.approx(bank.NORTH_EAR_INNER_Z + bracket.EAR_T)
    assert bank.NORTH_EAR_INNER_Z == pytest.approx(75.889, abs=5e-4)


def test_south_bracket_is_feeler_set_off_the_thrust_washer() -> None:
    assert bank.HUB0_SOUTH_FACE_Z == pytest.approx(bank.hub_mid_z(0) - arm.HUB_LENGTH / 2)
    assert bank.SOUTH_WASHER_Z == pytest.approx(
        (bank.HUB0_SOUTH_FACE_Z - washer.THICKNESS, bank.HUB0_SOUTH_FACE_Z)
    )
    assert bank.SOUTH_WASHER_Z[0] - bank.SOUTH_EAR_INNER_Z == pytest.approx(
        bank.ROCKER_END_FEELER
    )
    assert bank.SOUTH_EAR_OUTER_Z == pytest.approx(bank.SOUTH_EAR_INNER_Z - bracket.EAR_T)
    assert bank.SOUTH_EAR_INNER_Z == pytest.approx(-68.691, abs=5e-4)


def test_brackets_sit_on_their_ears_and_move_in_from_78() -> None:
    south, north = bank.PIVOT_BRACKET_Z
    assert south == pytest.approx(bank.SOUTH_EAR_INNER_Z - bracket.EAR_T / 2)
    assert north == pytest.approx(bank.NORTH_EAR_INNER_Z + bracket.EAR_T / 2)
    assert bank.STACK_MID_Z - south < 78.0
    assert north - bank.STACK_MID_Z < 78.0
    # Both feet stay on the rocker-arm-support's +-88.9 top.
    assert south - bracket.EAR_T / 2 > -88.9
    assert north + bracket.EAR_T / 2 < 88.9


def test_shaft_spans_both_ears_shoulder_one_ear_from_the_north_end() -> None:
    assert bank.PIVOT_SHAFT_SOUTH_Z == pytest.approx(bank.SOUTH_EAR_OUTER_Z)
    assert bank.PIVOT_SHAFT_LENGTH == pytest.approx(
        bank.NORTH_EAR_OUTER_Z - bank.SOUTH_EAR_OUTER_Z
    )
    assert bank.NORTH_JOURNAL_LENGTH == pytest.approx(bracket.EAR_T)
    assert bank.PIVOT_SHAFT_SOUTH_Z + bank.PIVOT_SHAFT_LENGTH - bank.NORTH_JOURNAL_LENGTH == (
        pytest.approx(bank.SHOULDER_Z[1])
    )
    assert bank.PIVOT_SHAFT_OVERALL_LENGTH == pytest.approx(
        bank.PIVOT_SHAFT_LENGTH + 2 * shaft.DOME_HEIGHT
    )
    # Domed 1.5 like the arbor ends (user, #743 Q4): SR 4.11 on the 1/4 rod.
    assert shaft.DOME_HEIGHT == 1.5
    assert shaft.DOME_SPHERE_RADIUS == pytest.approx(4.11, abs=5e-3)
    assert 0.0 < shaft.DOME_HEIGHT <= shaft.SHAFT_DIA / 2


def test_shoulder_is_turned_from_the_hub_diameter_bar() -> None:
    assert shaft.SHOULDER_DIA == arm.HUB_DIA == washer.OD == 10.0
    assert shaft.SHOULDER_LENGTH == washer.THICKNESS == 1.5
    assert washer.BORE_DIA == bracket.BORE_DIA


def test_no_keeper_is_needed_at_the_south_extreme() -> None:
    """Shaft and stack pushed south by the full end play: the shoulder leaves
    the north ear by E_r max, the north journal still bears on most of the
    ear, the south end still fills its ear, and both domes stay proud."""
    float_max = bank.ROCKER_END_PLAY[1]
    assert bank.NORTH_JOURNAL_LENGTH - float_max >= 0.9 * bracket.EAR_T
    assert bank.PIVOT_SHAFT_SOUTH_Z - float_max <= bank.SOUTH_EAR_OUTER_Z
    assert shaft.DOME_HEIGHT - float_max > 0.5


def test_south_apex_stays_on_the_support_at_the_worst_case() -> None:
    """Main (a): both ends domed. The plain end is cut flush to +0.5 past the
    south ear, then domed; floated south by E_r max, the apex must stay over
    the rocker-arm-support's -88.9 end and no further out than the retired
    170 shaft's end (-81.2), which nothing outboard ever touched."""
    assert bank.PLAIN_END_CUT_BAND == (0.5, 0.0)
    assert bank.SOUTH_APEX_REACH_MAX == pytest.approx(0.5 + 1.5 + 0.55)
    apex_z = bank.SOUTH_EAR_OUTER_Z - bank.SOUTH_APEX_REACH_MAX
    assert apex_z > -81.2
    assert apex_z - (-88.9) >= 2.0


def test_amplitude_bars_clear_both_thrust_faces_at_the_worst_case() -> None:
    """The bar straddles its arm plate (z_mid +- BAR_WIDTH/2) while the hub
    face's offset from the plate prints at .XX. A plate-wide thrust face on
    hub 0 would reach the ch0 bar; the O10 x 1.5 shoulder / washer (under the
    bar foot, like the hubs) stand the ears off."""
    proud_min = (arm.HUB_LENGTH - arm.ARM_THICKNESS) / 2 - _BAND_2PL
    face_offset_min = arm.ARM_THICKNESS / 2 + proud_min
    for standoff in (shaft.SHOULDER_LENGTH, washer.THICKNESS):
        clearance = standoff - _BAND_2PL + face_offset_min - bar.BAR_WIDTH / 2
        assert clearance >= bank.MIN_END_PLAY + bank.MARGIN_SPARE
    # Without a stand-off the bar would reach the ear.
    assert face_offset_min - bar.BAR_WIDTH / 2 < 0.0
    assert bank.BAR_TO_THRUST_EAR == pytest.approx(
        shaft.SHOULDER_LENGTH + arm.HUB_LENGTH / 2 - bar.BAR_WIDTH / 2
    )


def test_layout_reads_only_the_channel_stations() -> None:
    assert config_files_of(Path(bank.__file__)) == {"machine/channels.yaml"}
    deps = {Path(p).name for p in module_deps_of(Path(bank.__file__))}
    assert deps.isdisjoint(
        {
            "cylinder_bank_layout.py",
            "build_pivot_bracket.py",
            "build_pivot_shaft.py",
            "rocker_arm_notes.py",
        }
    )


def test_pivot_parts_read_no_gear_train_config() -> None:
    shaft_cfg = config_files_of(SCRIPTS / "build_pivot_shaft.py")
    assert "machine/channels.yaml" in shaft_cfg
    assert {"machine/gear_train.yaml", "machine/cone_incline.yaml"}.isdisjoint(shaft_cfg)
    assert not any(t.startswith("machine/") for t in config_files_of(SCRIPTS / "build_pivot_bracket.py"))
    assert not any(
        t.startswith("machine/") for t in config_files_of(SCRIPTS / "build_rocker_thrust_washer.py")
    )
