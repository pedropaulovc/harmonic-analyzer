"""Offline contract for the native seat SEARCH behind spring recalibration.

The search may use ``ClosestDistance`` only to choose where the next trial
lands. A distance the modeller over-reports, under-reports, or returns as zero
must still end in a bracket that the NATIVE evaluations closed to 1e-6 mm, with
the clear endpoint never inside the interfering region.
"""

from __future__ import annotations

import pytest

from diagnostics import _seat_search as search

_CONTACT_OFFSET_MM = 0.0731234567


class _FakeContact:
    """A pair whose contact sits at ``contact``; distance is scaled by ``gain``."""

    contact = _CONTACT_OFFSET_MM
    gain = 1.0

    def __init__(self, adapter, moving, fixed, direction, maximum, label) -> None:
        self.trials = 0
        self.offsets: list[float] = []

    def evaluate(self, offset_mm: float):
        self.trials += 1
        self.offsets.append(offset_mm)
        if offset_mm < self.contact:
            return "interfering", None
        return "clear", (offset_mm - self.contact) * self.gain


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(search, "_ActualContact", _FakeContact)
    return _FakeContact


def _solve(label: str = "fake") -> search.ContactSolution:
    return search.solve_component_contact(
        object(), "spring", "hook", (0.0, 1.0, 0.0), 0.3175, label=label
    )


@pytest.mark.parametrize("gain", [1.0, 1.7, 0.4, 0.0])
def test_bracket_closes_on_the_native_contact_for_any_distance_gain(fake, gain) -> None:
    fake.gain = gain
    solution = _solve()

    assert solution.certificate == "bracketed_native_contact"
    assert solution.interfering_offset_mm is not None
    assert (
        solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    )
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6
    assert solution.offset_mm == solution.clear_offset_mm


class _WireOnWire(_FakeContact):
    """Two round wires closing 30 degrees off the contact normal.

    The minimum distance is convex in the offset (centre distance
    sqrt(D0^2 + 2 D0 g cos + g^2) minus D0), the shape a spring eye riding a
    hook wire shows the search.
    """

    def evaluate(self, offset_mm: float):
        state, distance = super().evaluate(offset_mm)
        if state == "interfering":
            return state, None
        gap = offset_mm - self.contact
        centre = 1.5
        return "clear", self.gain * (
            (centre * centre + 2.0 * centre * gap * 0.866 + gap * gap) ** 0.5 - centre
        )


@pytest.mark.parametrize("gain", [1.0, 0.7, 0.4])
def test_true_distance_converges_in_a_few_trials_not_a_bisection(fake, gain) -> None:
    fake.gain = gain
    linear = _solve()
    fake.gain = 1.0

    assert linear.iterations <= 4


@pytest.mark.parametrize("gain", [1.0, 0.7, 0.4])
def test_wire_on_wire_distance_converges_in_a_few_trials(monkeypatch, gain) -> None:
    monkeypatch.setattr(search, "_ActualContact", _WireOnWire)
    _WireOnWire.gain = gain
    solution = _solve()

    assert solution.iterations <= 8
    assert (
        solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    )
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


def test_zero_distance_falls_back_to_bisection_and_still_converges(fake) -> None:
    fake.gain = 0.0
    solution = _solve()

    assert 19 <= solution.iterations <= 22
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


def test_seated_pose_within_guard_is_certified_without_a_move(fake) -> None:
    fake.gain = 1.0
    fake.contact = -0.5e-5
    try:
        solution = _solve()
    finally:
        fake.contact = _CONTACT_OFFSET_MM

    assert solution.certificate == "already_seated"
    assert solution.witness == "native_distance"
    assert solution.offset_mm == 0.0
