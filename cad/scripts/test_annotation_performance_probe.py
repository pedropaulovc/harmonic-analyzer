"""Profiler instrumentation must preserve calls, errors and restoration."""

import cProfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from probe_drawing_annotation_performance import (
    dispatch_timings,
    _dispatch_rows,
    _profile_report,
)
import probe_drawing_annotation_performance as control


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


@pytest.mark.parametrize("outcome", ["returned", "raised"])
def test_return_wrapper_timer_preserves_call_and_restores_function(outcome):
    expected = object()
    calls = []

    def wrap(*args, **kwargs):
        calls.append((args, kwargs))
        if outcome == "raised":
            raise ValueError("original wrapping failure")
        return expected

    client = SimpleNamespace(__WrapDispatch=wrap)
    ticks, rows = iter((2.0, 2.25)), _dispatch_rows()
    with control.return_wrapping_timings(client, rows, clock=lambda: next(ticks)):
        if outcome == "raised":
            with pytest.raises(ValueError, match="original wrapping failure"):
                client.__WrapDispatch(expected, "GetDisplayData", None, clsctx=4)
        if outcome == "returned":
            assert (
                client.__WrapDispatch(expected, "GetDisplayData", None, clsctx=4)
                is expected
            )
    assert client.__WrapDispatch is wrap
    assert calls == [((expected, "GetDisplayData", None), {"clsctx": 4})]
    assert rows["GetDisplayData"] == {
        "calls": 1,
        "errors": int(outcome == "raised"),
        "seconds": 0.25,
        "max_seconds": 0.25,
    }


def test_return_wrapper_timer_excludes_actual_worker_thread_calls():
    calls, expected = [], object()

    def wrap(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    client = SimpleNamespace(__WrapDispatch=wrap)
    rows, ticks = _dispatch_rows(), iter((1.0, 1.125))
    with control.return_wrapping_timings(client, rows, clock=lambda: next(ticks)):
        with ThreadPoolExecutor(max_workers=1) as worker:
            assert (
                worker.submit(client.__WrapDispatch, expected, "worker").result()
                is expected
            )
        assert client.__WrapDispatch(expected, userName="main") is expected
    assert len(calls) == 2
    assert set(rows) == {"main"}
    assert rows["main"]["seconds"] == 0.125
    assert client.__WrapDispatch is wrap


def test_dispatch_timer_excludes_actual_worker_thread_calls():
    rows, ticks = _dispatch_rows(), iter((1.0, 1.125))
    with dispatch_timings(FakeDispatch, rows, clock=lambda: next(ticks)):
        with ThreadPoolExecutor(max_workers=1) as worker:
            assert worker.submit(
                FakeDispatch()._ApplyTypes_, 1, 2, (1, 0), (), "worker", None, 42
            ).result() == (42,)
        assert FakeDispatch()._ApplyTypes_(1, 2, (1, 0), (), "main", None, 13) == (13,)
    assert set(rows) == {"FakeDispatch.main"}


def test_measurement_scope_never_runs_layout_controls(monkeypatch):
    monkeypatch.setattr(
        control,
        "_small_controls",
        lambda *_: pytest.fail("read-only scope moved a view"),
    )
    assert control.scope_controls(None, [], control.ProbeScope.MEASUREMENTS) == {
        "status": "not_requested"
    }


def test_layout_control_scope_runs_explicit_controls(monkeypatch):
    expected = {"control": "observed"}
    monkeypatch.setattr(control, "_small_controls", lambda *_: expected)
    assert (
        control.scope_controls(None, [], control.ProbeScope.LAYOUT_CONTROLS) is expected
    )
