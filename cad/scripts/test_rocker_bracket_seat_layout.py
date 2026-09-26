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
from _hole_spec import DRILL_POINT_H


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
        pytest.approx(2.062, abs=1e-3)
    )
    assert seats.SEAT_DRILL_NAME == "#29"


def test_seat_drill_point_keeps_the_rail_floor_at_the_printed_worst_case() -> None:
    """Codex #936 PRRT_kwDOPHDy386mS91G: the rail at its .X low limit over
    the #29 drill at its .X high limit plus its 118-deg point. The old check
    only kept the point out of the window; the floor it left was 0.36."""
    rail_min = seats.RAIL_DEPTH - seats.LINEAR_1PL
    drill_shoulder_max = seats.SEAT_DRILL_DEPTH + seats.LINEAR_1PL
    point = seats.SEAT_DRILL_DIA / 2.0 * DRILL_POINT_H
    floor = rail_min - (drill_shoulder_max + point)
    assert floor == pytest.approx(seats.SEAT_FLOOR_MIN)
    assert floor >= seats.RULE12_WEB_TARGET
    # The print carries each row at its own precision.
    for value in (seats.RAIL_DEPTH, seats.SEAT_DRILL_DEPTH, seats.SEAT_THREAD_DEPTH):
        assert round(value, 1) == value


def test_bracket_hole_clears_the_screw_junction_fillet() -> None:
    """r743-3C: MHA-123's #19 hole (0.025 radial over the #8-32 major) cut the
    fillister's under-head junction fillet, P/10 in diag_mcmaster_fillister's
    recipe, at the hole mouth: 0.0048 mm^3 per screw in assembly:channel."""
    fillet = hold_down._PITCH / 10.0
    radial = (bracket.HOLE_DIA - seats.SCREW_MAJOR_DIA) / 2.0
    assert radial > fillet
    assert channel.BRACKET_HOLE_FILLET_CLEARANCE == pytest.approx(radial - fillet)
    assert bracket.HOLE_DIA < hold_down.HEAD_DIA
