"""Offline contract: the amplitude bar's top notch straddles its channel lever,
and the MHA-CH-011 pin is pressed into both notch cheeks and runs in the
lever, with every fit held at the worst case of its printed bands (policy
rule 12).

``ch_bar_pivot_pin_spec`` reads only the two parts it joins; the restated
floors and bands are pinned to their sources here.
"""

from __future__ import annotations

import math

import pytest

import _config
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_spec as pin
import ch_channel_lever_spec as lever
import rocker_bank_layout as bank
from _hole_spec import NUMBER_DRILL_MM


def test_restated_floors_are_their_sources() -> None:
    drilled = _config.title_block("drilled_hole")
    assert (drilled["minus_mm"], drilled["plus_mm"]) == (0.0, pin.DRILLED_PLUS)
    assert pin.RUNNING_FLOOR == bank.RUNNING_FLOOR
    # The levers' hubs set the pitch the neighbour stack is judged at.
    assert lever.HUB_LENGTH == bank.PITCH
    assert pin.BAR_HOLE_DIA is bar.TOP_PIN_HOLE_DIA
    assert pin.BAR_HOLE_BAND is bar.TOP_PIN_HOLE_BAND
    # ANSI B4.1 FN2, 0-0.12 in: 0.85 thousandths of an inch at most.
    assert pin.PRESS_INTERFERENCE_MAX == pytest.approx(0.02159, abs=1e-6)


def test_the_pin_is_flush_with_the_bar_and_runs_in_the_lever() -> None:
    assert pin.PIN_INSTALLED_LENGTH == bar.BAR_WIDTH
    assert pin.PIN_END_PROUD_MAX == 0.0
    assert pin.PIN_DIA == pytest.approx(5.0 / 64.0 * 25.4)
    assert lever.BAR_PIN_HOLE_SPEC.size == "#47"
    assert NUMBER_DRILL_MM["#47"] == 1.994


def test_worst_case_joint_budget() -> None:
    b = pin.BUDGET
    # Press in the reamed cheeks: real at both band extremes, inside FN2.
    assert b["interference_min"] == pytest.approx(0.001375, abs=1e-6)
    assert b["interference_max"] == pytest.approx(0.021375, abs=1e-6)
    assert 0.0 < b["interference_min"] < b["interference_max"]
    assert b["interference_max"] <= pin.PRESS_INTERFERENCE_MAX
    # Running fit in the lever's #47 hole.
    assert b["running_clearance_min"] == pytest.approx(0.004625, abs=1e-6)
    assert b["running_clearance_max"] == pytest.approx(0.114625, abs=1e-6)
    # Flush ends leave the #1038 top-notch gap untouched.
    assert b["neighbour_clearance_min"] == pytest.approx(0.1065, abs=1e-6)
    assert b["neighbour_clearance_min"] >= pin.RUNNING_FLOOR
    assert b["hole_face_wall_min"] == pytest.approx(2.1606, abs=1e-6)
    assert b["hole_face_wall_min"] >= pin.RULE12_WALL_TARGET
    assert b["blank_excess_min"] == pytest.approx(0.12, abs=1e-6)
    assert b["blank_excess_max"] == pytest.approx(0.4308, abs=1e-6)


def test_the_cheeks_the_pin_presses_into_are_the_1038_shortfall_unchanged() -> None:
    """The printed ledge cheek holds the rule-12 floor; the far cheek, derived
    from the widest notch on the narrowest stock, is the pre-existing #1038
    shortfall. The pin fills the hole it presses into and changes neither."""
    b = pin.BUDGET
    assert b["tine_min_printed"] == pytest.approx(1.525, abs=1e-6)
    assert b["tine_min_printed"] >= pin.RULE12_WALL_FLOOR
    assert b["tine_min_derived"] == pytest.approx(1.1742, abs=1e-6)
    assert b["tine_min_derived"] < pin.RULE12_WALL_FLOOR  # #1038, not this pin


def test_neighbour_stack_closes_the_inter_bar_gap_exactly() -> None:
    """The gap (pitch less the widest bar) holds the bar's float on its lever,
    both dressed pin ends and the neighbour clearance: nothing left out."""
    b = pin.BUDGET
    notch_max = bar.TOP_NOTCH_WIDTH + bar.NOTCH_WIDTH_BAND[0]
    lever_min = lever.LEVER_THICKNESS - bar.LEVER_THICKNESS_TOLERANCE
    assert bank.PITCH - (
        bar.BAR_WIDTH + (notch_max - lever_min) + 2.0 * pin.PIN_END_PROUD_MAX
    ) == pytest.approx(b["neighbour_clearance_min"])


def test_the_assembly_press_allowance_is_this_joint() -> None:
    """_interference_contracts restates the modelled press as literals (every
    assembly imports it); they must be the nominal pin, the reamed hole and
    the two cheeks, and name channel j's pin with channel j's bar only."""
    import _interference_contracts as ic

    pin_dia, hole_dia, engaged = ic.BAR_PIVOT_PIN_PRESS
    assert pin_dia == pytest.approx(pin.PIN_DIA, abs=1e-9)
    assert hole_dia == bar.TOP_PIN_HOLE_DIA
    assert engaged == pytest.approx(bar.BAR_WIDTH - bar.TOP_NOTCH_WIDTH, abs=1e-9)
    # The rod pins' press pairs share the table (test_ch_rod_pivot_fit holds
    # the union to exactly the two pin joints).
    pairs = {
        pair: limit
        for pair, limit in ic.allowed_interference_pairs("ch-channel").items()
        if any(name.startswith("ch-bar-pivot-pin-") for name in pair)
    }
    assert set(pairs) == {
        frozenset((f"ch-bar-pivot-pin-{n}", f"ch-amplitude-bar-{n}"))
        for n in range(1, 21)
    }
    nominal = math.pi / 4.0 * (pin_dia**2 - hole_dia**2) * engaged
    assert all(limit == pytest.approx(1.10 * nominal) for limit in pairs.values())
