"""Offline behaviour of the shared two-limit (swTolLIMIT) tolerance helper."""

from __future__ import annotations

import pytest

import _drawing_tolerances
import _limit_tolerance as limits


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


class FakeDisplay:
    """An ``IDisplayDimension`` double that keeps its tolerance places."""

    def __init__(self, *, persist: bool = True) -> None:
        self.tol_places = 2
        self._persist = persist

    def SetPrecision3(self, primary, dual, tolerance, dual_tolerance) -> None:
        assert (primary, dual, dual_tolerance) == (-1, -1, -1)
        if self._persist:
            self.tol_places = tolerance

    def GetPrimaryTolPrecision2(self) -> int:
        return self.tol_places


def _set(monkeypatch, dimension, display=None, **overrides) -> FakeDisplay:
    display = display or FakeDisplay()
    seen: list[tuple[str, str]] = []

    def named(_adapter, feature, name):
        seen.append((feature, name))
        return display, dimension

    monkeypatch.setattr(limits, "_named_dimension", named)
    monkeypatch.setattr(limits, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_drawing_tolerances, "_early_bound", lambda value, _i: value)
    kwargs = {"limits": (0.127, 0.254), "places": 3, "display_unit": "in"}
    kwargs.update(overrides)
    limits.set_limits(None, "Profile", "Chamfer", **kwargs)
    assert seen == [("Profile", "Chamfer")]
    return display


def test_limits_become_deviations_around_the_model_nominal(monkeypatch) -> None:
    dimension = FakeDimension(0.0001905)
    display = _set(monkeypatch, dimension)
    assert dimension.Tolerance.Type == limits.SW_TOL_LIMIT == 3
    assert (dimension.Tolerance.min, dimension.Tolerance.max) == pytest.approx(
        (-0.0000635, 0.0000635)
    )
    # .005/.010 print at three places, though the deviations need four.
    assert display.tol_places == 3


def test_rejects_a_model_nominal_outside_the_limits(monkeypatch) -> None:
    dimension = FakeDimension(0.000254)
    with pytest.raises(RuntimeError, match="outside"):
        _set(monkeypatch, dimension)
    assert dimension.Tolerance.Type == 0


def test_rejects_refused_or_drifting_deviations(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="rejected"):
        _set(monkeypatch, FakeDimension(0.0001905, FakeTolerance(accept=False)))
    with pytest.raises(RuntimeError, match="readback"):
        _set(monkeypatch, FakeDimension(0.0001905, FakeTolerance(drift=1e-9)))


def test_rejects_places_that_round_a_printed_limit(monkeypatch) -> None:
    with pytest.raises(ValueError, match="would round"):
        _set(monkeypatch, FakeDimension(0.0001905), places=2)


def test_rejects_places_that_do_not_persist(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="did not persist"):
        _set(monkeypatch, FakeDimension(0.0001905), display=FakeDisplay(persist=False))
