"""Profiler instrumentation must preserve calls, errors and restoration."""

import cProfile

import pytest

from probe_drawing_annotation_performance import (
    dispatch_timings,
    _dispatch_rows,
    _profile_report,
)


class FakeDispatch:
    def _ApplyTypes_(
        self, dispid, flags, return_type, argument_types, member, clsid, *arguments
    ):
        if member == "Rejected":
            raise ValueError("original dispatch failure")
        return arguments


def test_dispatch_timer_preserves_arguments_and_return_values():
    original = FakeDispatch._ApplyTypes_
    rows = _dispatch_rows()
    ticks = iter((1.0, 1.25))
    with dispatch_timings(FakeDispatch, rows, clock=lambda: next(ticks)):
        assert FakeDispatch()._ApplyTypes_(
            1, 2, (1, 0), (), "Position", None, 3.0, 4.0
        ) == (3.0, 4.0)
    assert FakeDispatch._ApplyTypes_ is original
    assert rows["FakeDispatch.Position"] == {
        "calls": 1,
        "errors": 0,
        "seconds": 0.25,
        "max_seconds": 0.25,
    }


def test_dispatch_timer_preserves_exception_and_restores_class():
    original = FakeDispatch._ApplyTypes_
    rows = _dispatch_rows()
    ticks = iter((1.0, 1.5))
    with pytest.raises(ValueError, match="original dispatch failure"):
        with dispatch_timings(FakeDispatch, rows, clock=lambda: next(ticks)):
            FakeDispatch()._ApplyTypes_(1, 2, (1, 0), (), "Rejected", None)
    assert FakeDispatch._ApplyTypes_ is original
    assert rows["FakeDispatch.Rejected"] == {
        "calls": 1,
        "errors": 1,
        "seconds": 0.5,
        "max_seconds": 0.5,
    }


def test_cprofile_report_keeps_function_locations_and_counts():
    def measured_control():
        return sum(range(10))

    profiler = cProfile.Profile()
    assert profiler.runcall(measured_control) == 45
    report = _profile_report(profiler)
    row = next(
        row for row in report["functions"] if row["function"] == "measured_control"
    )
    assert row["calls"] == 1
    assert row["line"] > 0
    assert row["file"].endswith("test_annotation_performance_probe.py")
    assert "measured_control" in report["summary"]
