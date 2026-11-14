"""Offline checks of the thin 9666K142 amplification wire (#2398).

Owner ruling 2026-11-12: the wire only lifts a pen, so it is a thin single
wire as on the original, wrapped on the plain drum and knotted. The drum, the
grooves and the tie holes keep the Ø0.8 lanes they were laid out for.
"""

from __future__ import annotations

import math

import _mcmaster_9666k142 as stock
import error_budget
import mg_magnifying_bracket_arm_check as arm
import mg_magnifying_lever_geom as lever_rod
import mg_magnifying_wheel_geom as wheel
import mg_output_fixture_geom as fixture
import mg_wheel_group as group
import pn_pen_adjust_screw_spec as stud
import pytest
import sh_vn_music_wire_lever_geom as lever
import sh_vn_music_wire_pen_geom as pen
from _mg_wheel_rim_geometry import GROOVE_BOTTOM_DIA
from mg_wheel_drum_geom import DRUM_OD

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
    assert knotted > 3.0 * lever.BUILT_WIRE_RATIO * arm.PEN_SIDE_G * arm.G


def test_members_are_the_stock_wire_on_the_lane_centrelines() -> None:
    assert lever.MEMBER_DIA == pen.MEMBER_DIA == pytest.approx(stock.DIA)
    assert lever.WIRE_DIA == pen.WIRE_DIA == fixture.WIRE_DIA
    assert stock.DIA_MAX < lever.WIRE_DIA
    assert lever.LANE_INSET == pytest.approx((lever.WIRE_DIA - stock.DIA) / 2.0)


def test_the_wire_passes_every_hole_and_its_toggle_does_not() -> None:
    assert stock.DIA_MAX < wheel.TIE_HOLE_DIA / 4.0
    assert stock.DIA_MAX < stud.EYE_DIA / 4.0
    # The toggle is a straight offcut laid across the hole: it cannot enter
    # while it is longer than the hole is wide, with the wire tied at its
    # middle.
    assert group.TOGGLE_LENGTH > 2.0 * wheel.TIE_HOLE_DIA


def test_the_budget_and_arm_check_use_the_built_ratio() -> None:
    built = (GROOVE_BOTTOM_DIA + stock.DIA) / (DRUM_OD + stock.DIA)
    assert lever.BUILT_WIRE_RATIO == pytest.approx(built)
    assert 1.02 < built / wheel.WIRE_RATIO < 1.03
    assert error_budget.nominal().wheel_ratio == pytest.approx(built)
    assert arm.WIRE1_TENSION_MAX_N == pytest.approx(built * arm.PEN_LOAD_MAX_N)


def test_the_clamp_travel_covers_the_built_ratio() -> None:
    """The lanes' gain is had with the clamp about 4 mm nearer the knife."""
    nominal = error_budget.nominal()
    low, built_r, high = lever_rod.operating_clamp_radius_band()
    arm_built = error_budget.wire_moment_arm(nominal, built_r)
    station = error_budget.clamp_radius_for_arm(
        nominal, arm_built * wheel.WIRE_RATIO / lever.BUILT_WIRE_RATIO
    )
    assert built_r - station == pytest.approx(4.0, abs=0.5)
    assert low + 50.0 < station < built_r < high
