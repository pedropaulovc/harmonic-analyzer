"""Numerical regressions for exact supplier-reference geometry validation."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import _supplier_dimensions as supplier


@pytest.fixture(autouse=True)
def native_boundary(monkeypatch):
    monkeypatch.setattr(supplier, "_early_bound", lambda obj, _interface: obj)


def _native(system_value, kind=11):
    return SimpleNamespace(
        Type2=kind,
        GetDimension2=lambda _index: SimpleNamespace(SystemValue=system_value),
    )


def _measure(display, expected_mm):
    return supplier._measured_supplier_value(
        display,
        label="supplier length",
        presentation="length",
        expected_mm=expected_mm,
        expected_degrees=None,
    )


def test_rounded_supplier_text_is_not_an_exact_model_length():
    native = _native((7 / 16) * 0.0254)
    assert _measure(native, 11.1125) == pytest.approx(11.1125, abs=1e-12)
    # McMaster 91794A080 prints .438, not its exact seven-sixteenths value.
    with pytest.raises(RuntimeError, match="!= exact expected"):
        _measure(native, 0.438 * 25.4)


def test_nonfinite_native_value_is_not_a_matching_length():
    with pytest.raises(RuntimeError, match="native value nan"):
        _measure(_native(math.nan), 11.1125)


def test_infinite_expected_value_is_not_a_supplier_size():
    with pytest.raises(ValueError, match="finite and positive"):
        _measure(_native(0.0111125), math.inf)


def test_angle_dimension_is_not_interpreted_as_a_length():
    with pytest.raises(RuntimeError, match="dimension type 3 is not length"):
        _measure(_native(math.pi / 4, kind=3), 45.0)


def test_native_angular_si_value_is_converted_to_degrees_not_millimetres():
    measured = supplier._measured_supplier_value(
        _native(math.radians(82.0), kind=3),
        label="supplier included angle",
        presentation="angle",
        expected_mm=None,
        expected_degrees=82.0,
    )
    assert measured == pytest.approx(82.0, abs=1e-12)


def test_inch_fraction_rejects_rounding_exact_nonrepresentable_geometry():
    display = _native(0.003)
    display.GetOverride = lambda: False
    display.ShowDimensionValue = True
    display.GetAnnotation = lambda: SimpleNamespace(
        IsDangling=lambda: False, GetAttachedEntities3=lambda: (object(),)
    )
    # Three millimetres cannot be represented exactly in thirty-seconds.
    # No setter/rebuild fake exists: rejection must happen before formatting.
    with pytest.raises(ValueError, match="cannot display that inch fraction"):
        supplier.supplier_reference_dimension(
            None,
            display,
            label="nonrepresentable fraction",
            units="in",
            precision=3,
            expected_mm=3.0,
            fraction_denominator=32,
        )
