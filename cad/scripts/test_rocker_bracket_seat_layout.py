"""Offline contracts for the rocker brackets' hold-down seats (#743 PR2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _interference_contracts
import build_channel_assembly as channel
import build_pedestal_hold_down_screw as hold_down
import pivot_bracket_spec as bracket
import rocker_bracket_seat_layout as seats


def test_layout_screw_is_the_placed_mha_143() -> None:
    assert hold_down.SPEC.skus == ("90280A197",)
    assert seats.SCREW_THREAD == hold_down.THREAD
    assert seats.SCREW_LENGTH == hold_down.SHANK_LEN
    assert seats.SCREW_MAJOR_DIA == pytest.approx(hold_down.SHANK_DIA, abs=1e-3)
    assert seats.SCREW_TIP_CHAMFER == pytest.approx(0.7 * hold_down._PITCH)


def test_channel_places_one_screw_per_seat() -> None:
    assert channel.BRACKET_SCREW_XZ == seats.SEAT_MACHINE_XZ
    assert len(seats.SEAT_MACHINE_XZ) == 2 * len(bracket.HOLE_Z) == 4


def test_top_level_contract_literals_match_the_layout() -> None:
    pairs = _interference_contracts.allowed_interference_pairs("harmonic-analyzer")
    limits = {
        limit
        for pair, limit in pairs.items()
        if "frame-1/rocker-arm-support-1" in pair
        and any(name.startswith("channel-1/pedestal-hold-down-screw-") for name in pair)
    }
    screws = {
        name
        for pair in pairs
        if "frame-1/rocker-arm-support-1" in pair
        for name in pair
        if name.startswith("channel-1/pedestal-hold-down-screw-")
    }
    assert screws == {
        f"channel-1/pedestal-hold-down-screw-{n}"
        for n in range(1, len(seats.SEAT_MACHINE_XZ) + 1)
    }
    (limit,) = limits
    assert limit == pytest.approx(
        _interference_contracts._smooth_annulus_limit_mm3(
            hold_down.SHANK_DIA,
            seats.SEAT_DRILL_DIA,
            seats.SCREW_LENGTH - bracket.FOOT_H,
        )
    )


def test_contract_literals_are_the_layout_and_the_placed_screw() -> None:
    """The bound is written as literals (so no assembly re-keys on the bank
    layout); each one must still be the number it stands for."""
    source = Path(_interference_contracts.__file__).read_text(encoding="utf-8")
    block = source[source.index('"channel-1/pedestal-hold-down-screw"') :]
    match = re.search(
        r"_smooth_annulus_limit_mm3\(\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\s*-\s*([\d.]+)\s*\)",
        block,
    )
    assert match is not None
    major, minor, length, foot = (float(g) for g in match.groups())
    assert major == hold_down.SHANK_DIA
    assert minor == seats.SEAT_DRILL_DIA
    assert length == hold_down.SHANK_LEN == seats.SCREW_LENGTH
    assert foot == bracket.FOOT_H


def test_seat_stack_margins() -> None:
    # The printed worst case, restated: every margin the layout asserts.
    assert seats.ENGAGEMENT_MIN == pytest.approx(10.976, abs=1e-3)
    assert seats.SEAT_THREAD_DEPTH - seats.LINEAR_1PL - seats.SCREW_REACH_MAX == (
        pytest.approx(0.342, abs=1e-3)
    )
    assert seats.RAIL_DEPTH - seats.LINEAR_1PL - seats.SEAT_DRILL_BOTTOM_MAX == (
        pytest.approx(0.362, abs=1e-3)
    )
    assert seats.SEAT_DRILL_NAME == "#29"
