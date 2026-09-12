"""Finished bore-fit contracts shared by the native gear and its drawing."""

from __future__ import annotations

import pytest

import cylinder_gear_shaft_spec as arbor
import cylinder_gear_spec as spec


def test_running_bore_limits_follow_the_finished_arbor() -> None:
    # Opposite ends of the arbor size band must not receive one fixed bore band.
    assert spec.matched_bore_limits(9.505) == pytest.approx((9.535, 9.575))
    assert spec.matched_bore_limits(9.525) == pytest.approx((9.555, 9.595))


def test_native_bore_represents_a_finished_running_fit() -> None:
    # Equal nominal bore/arbor diameters previously modeled zero clearance,
    # even though the drawing required a positive matched running clearance.
    minimum, maximum = spec.matched_bore_limits(arbor.SHAFT_DIA)
    assert minimum <= spec.BORE_DIA <= maximum
    assert spec.BORE_DIA - arbor.SHAFT_DIA == pytest.approx(0.050)
