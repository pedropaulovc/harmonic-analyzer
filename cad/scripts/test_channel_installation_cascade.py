"""Offline contracts for the v2 channel-bank installation cascade."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import _cwm
import build_channel_assembly as channel
import clevis_pin_spec
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


def test_adjacent_station_envelopes_have_positive_physical_clearance() -> None:
    assert connecting_rod_spec.SHANK_THICKNESS == 1.0
    assert set(channel._STATION_ENVELOPES) == {"arm", "clevis", "neck", "shank"}
    assert set(channel._PREVIOUS_STATION_ENVELOPES) == set(channel._STATION_ENVELOPES)
    assert all(value > 0.0 for value in channel._ADJACENT_STATION_CLEARANCES.values())
    assert channel._ADJACENT_STATION_PAIR == ("shank", "clevis")
    assert math.isclose(channel._ADJACENT_STATION_CLEARANCE, 0.0565, abs_tol=1e-12)
    assert channel._SHANK_WORLD == (-3.75, -2.75)
    assert channel._PREVIOUS_STATION_ENVELOPES["clevis"][1] == pytest.approx(-3.8065)


def test_one_rigid_clevis_pin_closes_each_rod_and_component_inventory() -> None:
    assert channel.ROD_CLEVIS_FRONT_LOCAL[:2] == channel.ROD_PIN_BORE_LOCAL[:2]
    assert channel.ROD_CLEVIS_FAR_LOCAL[:2] == channel.ROD_PIN_BORE_LOCAL[:2]
    assert math.isclose(
        channel.ROD_CLEVIS_FRONT_LOCAL[2] - channel.ROD_CLEVIS_FAR_LOCAL[2],
        clevis_pin_spec.GRIP_LENGTH,
        abs_tol=1e-12,
    )
    assert channel.FIXED_COMPONENT_COUNT == 8
    assert channel.PER_CHANNEL_COMPONENT_COUNT == len(channel.CHAIN_PARTS) + 5 == 9
    assert channel.EXPECTED_COMPONENT_COUNT == 188
    source = Path(channel.__file__).read_text(encoding="utf-8")
    assert '            "clevis-pin",' in source
    assert 'named_ref(f"Front Plane@{pin}", "PLANE")' in source
    assert 'named_ref(f"Front Plane@{rod}", "PLANE")' in source
    assert 'label=f"clevis-pin ch{j:02d} locked to {rod}"' in source
    assert "len(clevis_pin_by_channel) != CHANNELS" in source
    assert "tracked_component_count != EXPECTED_COMPONENT_COUNT" in source


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
    assert _seed_flip("fulcrum-shaft-1 datum z d=35.41", channel.FULCRUM_SHAFT_Z)


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
