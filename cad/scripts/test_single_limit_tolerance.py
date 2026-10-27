"""Offline behaviour of the shared single-limit tolerance helper."""

from __future__ import annotations

import pytest

import _single_limit_tolerance as single


class FakeTolerance:
    """An ``IDimensionTolerance`` double: stores what the helper sets."""

    def __init__(self, *, accept: bool = True, drift: float = 0.0) -> None:
        self.Type = 0
        self.min = self.max = None
        self._accept = accept
        self._drift = drift

    def SetValues(self, lower: float, upper: float) -> bool:
        if self._accept:
            self.min, self.max = lower, upper
        return self._accept

    def GetMinValue(self) -> float:
        return self.min + self._drift

    def GetMaxValue(self) -> float:
        return self.max


class FakeDimension:
    """An ``IDimension`` double with a model value (metres) and a tolerance."""

    def __init__(self, system_value: float, tolerance: FakeTolerance | None = None):
        self.SystemValue = system_value
        self.Tolerance = tolerance or FakeTolerance()


def _set(monkeypatch, dimension: FakeDimension, **overrides) -> None:
    seen: list[tuple[str, str]] = []

    def named(_adapter, feature, name):
        seen.append((feature, name))
        return None, dimension

    monkeypatch.setattr(single, "_named_dimension", named)
    kwargs = {"limit": 0.5, "band": (0.0, -0.5), "tol_type": single.SW_TOL_MAX}
    kwargs.update(overrides)
    single.set_single_limit(None, "Fillet", "R", **kwargs)
    assert seen == [("Fillet", "R")]


def test_max_limit_sets_type_and_deviations_from_the_band(monkeypatch) -> None:
    dimension = FakeDimension(0.0005)
    _set(monkeypatch, dimension)
    assert dimension.Tolerance.Type == single.SW_TOL_MAX == 6
    # (upper, lower) band -> (lower, upper) deviations, in metres.
    assert (dimension.Tolerance.min, dimension.Tolerance.max) == pytest.approx(
        (-0.0005, 0.0)
    )


def test_min_limit_uses_the_native_min_type(monkeypatch) -> None:
    dimension = FakeDimension(0.0003)
    _set(monkeypatch, dimension, limit=0.3, band=(0.1, 0.0), tol_type=single.SW_TOL_MIN)
    assert dimension.Tolerance.Type == single.SW_TOL_MIN == 5
    assert (dimension.Tolerance.min, dimension.Tolerance.max) == pytest.approx(
        (0.0, 0.0001)
    )


def test_rejects_a_type_that_is_not_a_single_limit(monkeypatch) -> None:
    dimension = FakeDimension(0.0005)
    with pytest.raises(ValueError, match="not a single limit"):
        _set(monkeypatch, dimension, tol_type=2)  # swTolBILAT
    assert dimension.Tolerance.Type == 0


def test_rejects_a_model_value_that_is_not_the_limit(monkeypatch) -> None:
    dimension = FakeDimension(0.0006)
    with pytest.raises(RuntimeError, match="is not the MAX limit 0.5"):
        _set(monkeypatch, dimension)
    assert dimension.Tolerance.Type == 0


def test_rejects_deviations_solidworks_refuses(monkeypatch) -> None:
    dimension = FakeDimension(0.0005, FakeTolerance(accept=False))
    with pytest.raises(RuntimeError, match="SetValues rejected"):
        _set(monkeypatch, dimension)


def test_rejects_a_readback_that_changed(monkeypatch) -> None:
    dimension = FakeDimension(0.0005, FakeTolerance(drift=1e-6))
    with pytest.raises(RuntimeError, match="MAX-limit tolerance readback changed"):
        _set(monkeypatch, dimension)
