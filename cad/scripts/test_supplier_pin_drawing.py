"""Supplier-pin source/geometry invariants; native rendering remains a separate gate."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name", ("vn_crank_seat_drive_pin_spec", "vn_transgear_knob_drive_pin_spec")
)
def test_three_thirty_seconds_source_band_uses_equivalent_limits(module_name) -> None:
    source = importlib.import_module(module_name).SUPPLIER_REFERENCE
    exact_inches = source.diameter_mm / source.unit_mm
    assert exact_inches == pytest.approx(3.0 / 32.0, abs=1e-15)
    lower, upper = (
        source.diameter_nominal + deviation for deviation in source.diameter_band
    )
    assert (lower, upper) == pytest.approx((0.0938, 0.0940), abs=1e-15)
    assert (lower - exact_inches, upper - exact_inches) == pytest.approx(
        (0.00005, 0.00025), abs=1e-15
    )
    assert source.diameter_uses_limits
    assert source.diameter_deviations_mm == pytest.approx(
        (0.00005 * 25.4, 0.00025 * 25.4), abs=1e-12
    )


def test_knob_pin_three_place_print_does_not_round_three_sixteenths_geometry() -> None:
    from vn_transgear_knob_drive_pin_spec import LENGTH

    assert LENGTH == pytest.approx(3.0 / 16.0 * 25.4, abs=1e-12)
    assert LENGTH / 25.4 == pytest.approx(0.1875, abs=1e-15)
    assert LENGTH != 0.188 * 25.4


def test_metric_source_band_preserves_nominal_cylinder() -> None:
    from vn_transgear_arm_plate_locating_pin_spec import DIA, SUPPLIER_REFERENCE

    lower, upper = (
        SUPPLIER_REFERENCE.diameter_nominal + deviation
        for deviation in SUPPLIER_REFERENCE.diameter_band
    )
    assert (lower, upper) == pytest.approx((2.002, 2.008), abs=1e-12)
    assert DIA < lower < upper
    assert not SUPPLIER_REFERENCE.diameter_uses_limits
    assert SUPPLIER_REFERENCE.diameter_deviations_mm == pytest.approx(
        (0.002, 0.008), abs=1e-12
    )


@pytest.mark.parametrize(
    "module_name", ("vn_pinion_strap_pin_spec", "vn_transgear_knob_cup_pin_spec")
)
def test_roll_pin_application_circle_clears_installed_tube(module_name) -> None:
    source = importlib.import_module(module_name).SUPPLIER_REFERENCE
    lower, upper = (limit * source.unit_mm for limit in source.application_hole_limits)
    assert lower < source.diameter_mm < upper
    assert 0.0 < 2.0 * source.wall_mm < source.diameter_mm
    # This is only a numerical separation boundary, not native layout proof.
    center_distance = (
        sum(coordinate**2 for coordinate in source.application_hole_center) ** 0.5
    )
    assert center_distance > (source.diameter_mm + upper) / 2.0
