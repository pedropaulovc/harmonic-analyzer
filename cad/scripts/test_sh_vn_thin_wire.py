"""Offline checks of the thin 9666K142 amplification wire (#2398).

Owner ruling 2026-11-12: the wire only lifts a pen, so it is a thin single
wire as on the original, wrapped on the plain drum and knotted. Owner ruling
2026-11-20 on #2687 ("A"): the drum, the rim groove and the fixture groove
seat that wire on the wire centres the 5:1 ratio is laid out on.
"""

from __future__ import annotations

import math

import _mcmaster_9666k142 as stock
import error_budget
import mg_magnifying_bracket_arm_check as arm
import mg_magnifying_wheel_geom as wheel
import mg_output_fixture_geom as fixture
import mg_wheel_group as group
import pn_pen_adjust_screw_spec as stud
import pytest
import sh_vn_music_wire_lever_geom as lever
import sh_vn_music_wire_pen_geom as pen
from _mg_wheel_rim_geometry import GROOVE_BOTTOM_DIA, RIM_WIRE_R
from mg_wheel_drum_geom import DRUM_OD, DRUM_WIRE_R

IN = 25.4
N_PER_LBF = 4.4482216
OLD_WIRE_DIA = 0.031 * IN
# A knot in hard-drawn wire is taken at half the straight wire's strength.
KNOT_EFFICIENCY = 0.5


def _bending_strain(wire_dia: float, wrap_dia: float) -> float:
    return wire_dia / (wrap_dia + wire_dia)


def _knotted_strength_min_n() -> float:
    area_in2 = math.pi / 4.0 * (stock.DIA_MIN / IN) ** 2
    return KNOT_EFFICIENCY * stock.CATALOG_TENSILE_PSI * area_in2 * N_PER_LBF


def test_the_wire_winds_on_the_drum_at_a_third_of_the_old_strain() -> None:
    old = _bending_strain(OLD_WIRE_DIA, DRUM_OD)
    assert old > 0.03  # the issue's 4 %
    # About 1 %: a hard-drawn wire this thin lays round the drum under a
    # finger and knots, where the Ø.031 one sprang off it.
    assert _bending_strain(stock.DIA_MAX, DRUM_OD) < 0.013
    assert _bending_strain(stock.DIA_MAX, DRUM_OD) < old / 3.0


def test_the_knotted_wire_holds_twice_the_working_maximum() -> None:
    # The arm check's wire 1 maximum carries a guide-friction sizing allowance
    # on top of the pen's weight; the thinnest catalogue wire, knotted, still
    # holds twice it and three times the weight alone.
    knotted = _knotted_strength_min_n()
    assert knotted > 2.0 * arm.WIRE1_TENSION_MAX_N
    assert knotted > 3.0 * wheel.WIRE_RATIO * arm.PEN_SIDE_G * arm.G


def test_members_are_the_stock_wire_and_every_seat_is_laid_out_for_it() -> None:
    assert lever.MEMBER_DIA == pen.MEMBER_DIA == pytest.approx(stock.DIA)
    assert lever.WIRE_DIA == pen.WIRE_DIA == fixture.WIRE_DIA == stock.DIA
    # The seats moved out so the wire centres stayed put: the drum's r 9.85,
    # the rim groove's r 49.2 and the fixture hook's 4.5 off the spigot axis.
    assert DRUM_OD / 2.0 + stock.DIA / 2.0 == pytest.approx(9.85)
    assert GROOVE_BOTTOM_DIA / 2.0 + stock.DIA / 2.0 == pytest.approx(49.2)
    assert fixture.HOOK_RADIAL_OFFSET == pytest.approx(4.5)
    assert (DRUM_OD, GROOVE_BOTTOM_DIA, fixture.GROOVE_ROOT_DIA) == pytest.approx(
        (19.4968, 98.1968, 8.2968)
    )


def test_the_wire_passes_every_hole_and_its_toggle_does_not() -> None:
    assert stock.DIA_MAX < wheel.TIE_HOLE_DIA / 4.0
    assert stock.DIA_MAX < stud.EYE_DIA / 4.0
    # The toggle is a straight offcut laid across the hole: it cannot enter
    # while it is longer than the hole is wide, with the wire tied at its
    # middle.
    assert group.TOGGLE_LENGTH > 2.0 * wheel.TIE_HOLE_DIA


def test_the_budget_and_arm_check_use_the_ratio_the_fitted_wire_gives() -> None:
    built = (GROOVE_BOTTOM_DIA + stock.DIA) / (DRUM_OD + stock.DIA)
    assert built == pytest.approx(RIM_WIRE_R / DRUM_WIRE_R)
    assert wheel.WIRE_RATIO == pytest.approx(built)
    assert wheel.WIRE_RATIO == pytest.approx(4.995, abs=5e-4)
    assert error_budget.nominal().wheel_ratio == pytest.approx(built)
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(built * arm.PEN_LOAD_MAX_N)
