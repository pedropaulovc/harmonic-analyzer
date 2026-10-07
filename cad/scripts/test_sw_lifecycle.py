"""Lifecycle telemetry on a fake seat: never import live recovery collaborators."""
from __future__ import annotations

import contextlib
import importlib.util
from enum import Enum
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
from opentelemetry.trace import StatusCode


class State(Enum):
    CONNECTED = "connected"
    STARTING = "starting"
    NOT_RUNNING = "not_running"
    DOTNET_SPLASH_WEDGE = "dotnet_splash_wedge"
    RUNNING_DISCONNECTED = "running_disconnected"


class RecordedSpan:
    def __init__(self, name, attributes):
        self.name = name
        self.attributes = dict(attributes)
        self.status = None
        self.exceptions = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_status(self, status):
        self.status = status

    def record_exception(self, exc):
        self.exceptions.append(exc)


@pytest.fixture
def seat(monkeypatch):
    clock = [0.0]
    spans, events, calls, warnings = [], [], [], []
    recovery = ModuleType("solidworks_mcp.adapters.sw_recovery")
    recovery.SolidWorksState = State
    recovery.detect_state = lambda: State.CONNECTED
    recovery.stop_solidworks = lambda: calls.append("stop") or True
    recovery.start_solidworks = lambda: calls.append("start") or True
    package = ModuleType("solidworks_mcp")
    package.__path__ = []
    adapters = ModuleType("solidworks_mcp.adapters")
    adapters.__path__ = []
    adapters.sw_recovery = recovery
    package.adapters = adapters
    for name, module in (
        ("solidworks_mcp", package),
        ("solidworks_mcp.adapters", adapters),
        ("solidworks_mcp.adapters.sw_recovery", recovery),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    telemetry = ModuleType("_telemetry")
    telemetry.BUILD_INFRA_SERVICE = "build-infra"

    @contextlib.contextmanager
    def span(name, service=None, **attributes):
        recorded = RecordedSpan(name, attributes)
        spans.append(recorded)
        try:
            yield recorded
        except Exception as exc:
            recorded.record_exception(exc)
            recorded.set_status(SimpleNamespace(status_code=StatusCode.ERROR))
            raise

    telemetry.span = span
    telemetry.event = lambda name, **kw: events.append((name, kw))
    telemetry.warn = lambda message, **kw: warnings.append(message)
    for name in ("info", "error", "success"):
        setattr(telemetry, name, lambda *_a, **_kw: None)
    monkeypatch.setitem(sys.modules, "_telemetry", telemetry)
    spec = importlib.util.spec_from_file_location(
        "_lifecycle_fake_seat", Path(__file__).with_name("_sw_lifecycle.py")
    )
    lifecycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lifecycle)
    monkeypatch.setattr(lifecycle, "_monotonic", lambda: clock[0])

    def sleep(seconds):
        assert seconds == 2.0
        clock[0] += seconds

    monkeypatch.setattr(lifecycle, "_sleep", sleep)
    crash_handler_cleanup = lifecycle._kill_crash_handler
    monkeypatch.setattr(lifecycle, "_kill_crash_handler", lambda: calls.append("crash_handler"))
    signin_scan = lifecycle._signin_window
    monkeypatch.setattr(lifecycle, "_signin_window", lambda: None)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    monkeypatch.setenv("HARMONIC_SW_CONNECT_TIMEOUT", "900")
    return SimpleNamespace(
        lifecycle=lifecycle, recovery=recovery, clock=clock, spans=spans,
        events=events, calls=calls, warnings=warnings,
        signin_scan=signin_scan, crash_handler_cleanup=crash_handler_cleanup,
        span=lambda name: next(s for s in spans if s.name == name),
    )


@pytest.mark.parametrize("initial,action,calls", [
    (State.CONNECTED, "none", []),
    (State.STARTING, "wait", []),
    (State.NOT_RUNNING, "start", ["start"]),
    (State.RUNNING_DISCONNECTED, "recover", ["stop", "start"]),
    (State.DOTNET_SPLASH_WEDGE, "recover", ["stop", "start"]),
])
def test_ensure_ready_preserves_existing_decisions(seat, initial, action, calls):
    reads = iter([initial])
    seat.recovery.detect_state = lambda: next(reads, State.CONNECTED)
    assert seat.lifecycle.ensure_ready() == "connected"
    assert seat.calls == calls
    assert seat.span("sw.ensure_ready").attributes["action"] == action


def test_disabled_ensure_only_probes_state(seat, monkeypatch):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    seat.recovery.detect_state = lambda: State.STARTING
    assert seat.lifecycle.ensure_ready() == "starting"
    assert seat.calls == []
    assert seat.spans == []


def test_ensure_wait_error_is_swallowed_and_recorded(seat, monkeypatch):
    seat.recovery.detect_state = lambda: State.STARTING
    monkeypatch.setattr(seat.lifecycle, "_wait", lambda *_a: fail("wait failed"))
    assert seat.lifecycle.ensure_ready() == "error"
    assert_error(seat.span("sw.ensure_ready"), "wait failed")


def fail(message="probe failed"):
    raise RuntimeError(message)


def assert_error(span, message):
    assert span.status.status_code is StatusCode.ERROR
    assert message in span.status.description
    assert [str(exc) for exc in span.exceptions] == [message]


def test_recovery_records_context_transitions_and_dwell_sum(seat):
    def detect():
        t = seat.clock[0]
        return State.NOT_RUNNING if t < 10 else State.STARTING if t < 400 else State.CONNECTED

    seat.recovery.detect_state = detect
    assert seat.lifecycle.force_recover("watchdog_crash", exit_code=86, caller="exec_com") == "connected"
    recover, start = seat.span("sw.force_recover"), seat.span("sw.start")
    assert recover.attributes == {
        "recover.reason": "watchdog_crash", "recover.exit_code": 86,
        "recover.caller": "exec_com", "stop.ok": True,
        "outcome": "connected", "final_state": "connected",
    }
    assert recover.status is None
    assert seat.calls == ["crash_handler", "stop", "start"]
    assert seat.span("sw.stop").attributes["stop.ok"] is True
    assert start.attributes["start.launched"] is True
    assert [kw["state"] for name, kw in seat.events if name == "sw.state"] == [
        "not_running", "starting", "connected",
    ]
    assert start.attributes["dwell.not_running_s"] == 10.0
    assert start.attributes["dwell.starting_s"] == 390.0
    assert sum(v for k, v in start.attributes.items() if k.startswith("dwell.")) == start.attributes["wait.s"] == 400.0
    assert not [kw for name, kw in seat.events if name == "sw.no_process"]


@pytest.mark.parametrize("phase", ["stop", "start", "read", "final_read"])
def test_each_recovery_phase_marks_swallowed_error(seat, phase):
    if phase == "stop":
        seat.recovery.stop_solidworks = lambda: fail("stop failed")
    elif phase == "start":
        seat.recovery.start_solidworks = lambda: fail("start failed")
    elif phase == "read":
        seat.recovery.detect_state = lambda: fail("read failed")
    else:
        reads = iter([State.CONNECTED])

        def detect():
            return next(reads, None) or fail("final_read failed")

        seat.recovery.detect_state = detect
    assert seat.lifecycle.force_recover("manual") == "error"
    assert_error(seat.span("sw.force_recover"), f"{phase} failed")
    if phase == "read":
        assert seat.span("sw.start").attributes["wait.outcome"] == "error"
        assert seat.span("sw.start").attributes["wait.s"] == 0.0
    if phase == "final_read":
        assert seat.span("sw.force_recover").attributes["outcome"] == "connected"


def test_raised_poll_read_keeps_elapsed_and_last_state_dwell(seat):
    def detect():
        if seat.clock[0] >= 6:
            fail("read failed")
        return State.NOT_RUNNING if seat.clock[0] < 2 else State.STARTING

    seat.recovery.detect_state = detect
    assert seat.lifecycle.force_recover("manual") == "error"
    assert_error(seat.span("sw.force_recover"), "read failed")
    attrs = seat.span("sw.start").attributes
    assert attrs["wait.outcome"] == "error"
    assert attrs["dwell.not_running_s"] == 2.0
    assert attrs["dwell.starting_s"] == 4.0
    assert sum(v for k, v in attrs.items() if k.startswith("dwell.")) == attrs["wait.s"] == 6.0


@pytest.mark.parametrize("state,outcome,elapsed", [
    (State.STARTING, "timeout", 900.0),
    (State.DOTNET_SPLASH_WEDGE, "wedge", 0.0),
])
def test_nonconnected_recovery_is_error_without_changing_wait_decision(seat, state, outcome, elapsed):
    seat.recovery.detect_state = lambda: state
    assert seat.lifecycle.force_recover("seat_starting") == state.value
    assert seat.span("sw.force_recover").status.status_code is StatusCode.ERROR
    assert seat.span("sw.force_recover").attributes["outcome"] == outcome
    assert seat.span("sw.start").attributes["wait.s"] == elapsed


def test_refused_launch_never_waits_and_records_failed_stop(seat):
    seat.recovery.stop_solidworks = lambda: False
    seat.recovery.start_solidworks = lambda: False
    seat.recovery.detect_state = lambda: State.RUNNING_DISCONNECTED
    assert seat.lifecycle.force_recover("manual") == "running_disconnected"
    assert seat.clock[0] == 0.0
    assert seat.span("sw.force_recover").attributes["stop.ok"] is False
    assert seat.span("sw.force_recover").attributes["outcome"] == "not_launched"
    assert seat.span("sw.force_recover").status.status_code is StatusCode.ERROR
    assert seat.span("sw.start").attributes == {"start.launched": False}


def test_no_process_and_signin_stalls_emit_once(seat, monkeypatch):
    seat.recovery.detect_state = lambda: State.NOT_RUNNING
    monkeypatch.setattr(seat.lifecycle, "_signin_window", lambda: "Login | 3DEXPERIENCE ID")
    seat.lifecycle.force_recover("manual")
    assert [kw for name, kw in seat.events if name == "sw.no_process"] == [{"elapsed_s": 120.0}]
    assert [kw for name, kw in seat.events if name == "sw.signin_window"] == [
        {"title": "Login | 3DEXPERIENCE ID", "elapsed_s": 0.0},
    ]


def test_grace_is_one_third_budget_and_does_not_emit_launch_stall(seat):
    seat.recovery.detect_state = lambda: State.NOT_RUNNING
    assert seat.lifecycle.wait_until_ready() == "not_running"
    assert seat.clock[0] == 300.0
    assert seat.calls == []
    assert [kw for name, kw in seat.events if name == "sw.grace_abandoned"] == [
        {"grace_s": 300.0, "reason": "timeout"},
    ]
    assert not [kw for name, kw in seat.events if name == "sw.no_process"]


@pytest.mark.parametrize("phase", ["initial_read", "stop", "start", "poll", "final_read"])
def test_ensure_ready_swallowed_errors_are_recorded(seat, phase):
    state = State.RUNNING_DISCONNECTED if phase == "stop" else State.NOT_RUNNING
    if phase == "initial_read":
        seat.recovery.detect_state = lambda: fail(phase)
    else:
        reads = iter([state, State.CONNECTED] if phase == "final_read" else [state])
        seat.recovery.detect_state = lambda: next(reads, None) or fail(phase)
    if phase == "stop":
        seat.recovery.stop_solidworks = lambda: fail(phase)
    elif phase == "start":
        seat.recovery.start_solidworks = lambda: fail(phase)
    assert seat.lifecycle.ensure_ready() == "error"
    assert_error(seat.span("sw.ensure_ready"), phase)


@pytest.mark.parametrize("phase", ["wait", "poll", "final_read"])
def test_wait_ready_swallowed_errors_are_recorded(seat, monkeypatch, phase):
    if phase == "wait":
        monkeypatch.setattr(seat.lifecycle, "_wait", lambda *_a: fail(phase))
    elif phase == "poll":
        reads = iter([None, State.STARTING])
        seat.recovery.detect_state = lambda: next(reads) or fail(phase)
    else:
        reads = iter([State.CONNECTED])
        seat.recovery.detect_state = lambda: next(reads, None) or fail(phase)
    assert seat.lifecycle.wait_until_ready() == ("unknown" if phase == "final_read" else "starting" if phase == "poll" else "connected")
    assert_error(seat.span("sw.wait_ready"), phase)
    if phase != "final_read":
        assert [kw for name, kw in seat.events if name == "sw.grace_abandoned"] == [
            {"grace_s": 300.0, "reason": phase},
        ]
    if phase == "poll":
        assert seat.span("sw.wait_connected").attributes["wait.outcome"] == "error"


def test_current_state_returns_value_and_propagates_probe_failure(seat):
    assert seat.lifecycle.current_state() == "connected"
    seat.recovery.detect_state = lambda: fail()
    with pytest.raises(RuntimeError, match="probe failed"):
        seat.lifecycle.current_state()


@pytest.mark.parametrize("raw", ["0", "-5", "nan", "-inf"])
def test_raw_timeout_skips_polling_without_warning(seat, monkeypatch, raw):
    monkeypatch.setenv("HARMONIC_SW_CONNECT_TIMEOUT", raw)
    seat.recovery.detect_state = lambda: fail("must not poll")
    assert seat.lifecycle._wait(seat.recovery, seat.lifecycle._connect_timeout()) == "timeout"
    assert seat.clock[0] == 0.0
    assert seat.warnings == []


def test_infinite_timeout_keeps_polling_until_connected(seat, monkeypatch):
    monkeypatch.setenv("HARMONIC_SW_CONNECT_TIMEOUT", "inf")
    seat.recovery.detect_state = lambda: State.STARTING if seat.clock[0] < 1000 else State.CONNECTED
    assert seat.lifecycle._wait(seat.recovery, seat.lifecycle._connect_timeout()) == "connected"
    assert seat.clock[0] == 1000.0
    assert seat.warnings == []


def test_nonnumeric_timeout_keeps_existing_fallback(seat, monkeypatch):
    monkeypatch.setenv("HARMONIC_SW_CONNECT_TIMEOUT", "banana")
    assert seat.lifecycle._connect_timeout() == 900.0
    assert seat.warnings == []


@pytest.mark.parametrize("raw,expected", [("450", 450.0), (" 2.5 ", 2.5), ("", 900.0)])
def test_valid_or_empty_timeout(seat, monkeypatch, raw, expected):
    monkeypatch.setenv("HARMONIC_SW_CONNECT_TIMEOUT", raw)
    assert seat.lifecycle._connect_timeout() == expected
    assert seat.warnings == []


@pytest.mark.skipif("sys.platform != 'win32'", reason="Win32 only: stdcall function pointers")
def test_signin_scan_preserves_pointer_width_hwnd(seat, monkeypatch):
    import ctypes
    from ctypes import wintypes

    hwnds = {0x1_0000_0010: "Untitled - Notepad", 0x2_0000_0020: "Login | 3DEXPERIENCE ID"}

    def text(hwnd, buffer, size):
        title = hwnds.get(hwnd, "")[:size - 1]
        ctypes.memmove(buffer, ctypes.create_unicode_buffer(title), (len(title) + 1) * ctypes.sizeof(ctypes.c_wchar))
        return len(title)

    class Unprototyped(ctypes._CFuncPtr):
        _flags_ = ctypes._FUNCFLAG_STDCALL
        _restype_ = ctypes.c_int

    thunks = [
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND)(lambda hwnd: True),
        ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, ctypes.c_void_p, ctypes.c_int)(text),
    ]
    user32 = SimpleNamespace(
        EnumWindows=lambda callback, parameter: all(callback(hwnd, parameter) for hwnd in hwnds),
        IsWindowVisible=Unprototyped(ctypes.cast(thunks[0], ctypes.c_void_p).value),
        GetWindowTextW=Unprototyped(ctypes.cast(thunks[1], ctypes.c_void_p).value),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_a, **_kw: user32)
    assert seat.signin_scan() == "Login | 3DEXPERIENCE ID"
    assert user32.IsWindowVisible.argtypes == [wintypes.HWND]
    assert user32.GetWindowTextW.argtypes == [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]


def test_pointer_width_scan_is_skipped_off_windows(monkeypatch):
    (mark,) = test_signin_scan_preserves_pointer_width_hwnd.pytestmark
    assert mark.name == "skipif" and "Win32 only" in mark.kwargs["reason"]
    for platform, skipped in (("win32", False), ("linux", True), ("darwin", True)):
        monkeypatch.setattr(sys, "platform", platform)
        assert eval(mark.args[0], {"sys": sys}) is skipped


@pytest.mark.parametrize("slow_phase", ["state", "observation"])
def test_slow_probe_crossing_deadline_never_sleeps_or_reprobes(seat, monkeypatch, slow_phase):
    reads = []

    def detect():
        reads.append(seat.clock[0])
        if slow_phase == "state":
            seat.clock[0] += 5
        return State.STARTING

    def observe():
        if slow_phase == "observation":
            seat.clock[0] += 5
        return None

    seat.recovery.detect_state = detect
    monkeypatch.setattr(seat.lifecycle, "_signin_window", observe)
    monkeypatch.setattr(seat.lifecycle, "_sleep", lambda *_a: fail("must not sleep"))
    assert seat.lifecycle._wait(seat.recovery, 3) == "timeout"
    assert reads == [0.0]
    assert seat.span("sw.wait_connected").attributes["wait.s"] == 5.0
    assert seat.span("sw.wait_connected").attributes["dwell.starting_s"] == 5.0


def test_deadline_prevents_probe_at_boundary(seat):
    reads = []
    seat.recovery.detect_state = lambda: reads.append(seat.clock[0]) or State.STARTING
    assert seat.lifecycle._wait(seat.recovery, 2) == "timeout"
    assert reads == [0.0]


@pytest.mark.parametrize("failure", ["oserror", "subprocess", "timeout"])
def test_crash_cleanup_errors_are_recorded_without_blocking_recovery(seat, monkeypatch, failure):
    import subprocess

    error = (
        OSError("cleanup failed") if failure == "oserror"
        else subprocess.SubprocessError("cleanup failed") if failure == "subprocess"
        else subprocess.TimeoutExpired(["taskkill"], 15)
    )
    commands = []

    def run(command, **kwargs):
        commands.append((command, kwargs))
        raise error

    # Patch beneath the real helper before restoring it: no taskkill can execute.
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(seat.lifecycle, "_kill_crash_handler", seat.crash_handler_cleanup)
    assert seat.lifecycle.force_recover("manual") == "connected"
    assert seat.calls == ["stop", "start"]
    assert commands == [(
        ["taskkill", "/F", "/IM", "sldexitapp.exe"],
        {"capture_output": True, "timeout": 15,
         "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)},
    )]
    assert_error(seat.span("sw.force_recover"), str(error))
    assert seat.span("sw.force_recover").attributes["outcome"] == "connected"


def install_native_scan(monkeypatch, scenario):
    """A complete fake Win32 surface, including thread-local last-error semantics."""
    import ctypes

    last_error = [0]
    visited = []

    def text(hwnd, buffer, size):
        if scenario == "title_error":
            last_error[0] = 5
            return 0
        buffer.value = "Login | 3DEXPERIENCE ID" if scenario == "match" else ""
        return len(buffer.value)

    def enumerate_windows(callback, parameter):
        if scenario == "enum_error":
            last_error[0] = 5
            return False
        if scenario == "empty":
            return True
        visited.append(0x2_0000_0020)
        return bool(callback(visited[-1], parameter))

    user32 = SimpleNamespace(
        EnumWindows=enumerate_windows,
        IsWindowVisible=lambda hwnd: True,
        GetWindowTextW=text,
    )

    def dll(*_a, **_kw):
        if scenario == "unavailable":
            raise OSError("desktop unavailable")
        return user32

    monkeypatch.setattr(ctypes, "WinDLL", dll, raising=False)
    monkeypatch.setattr(ctypes, "WINFUNCTYPE", lambda *_a: lambda fn: fn, raising=False)
    monkeypatch.setattr(ctypes, "set_last_error", lambda value: last_error.__setitem__(0, value), raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: last_error[0], raising=False)
    return visited


@pytest.mark.parametrize("scenario,error", [
    ("enum_error", "EnumWindows failed"),
    ("empty", None),
    ("match", None),
    ("title_empty", None),
    ("title_error", "GetWindowTextW failed"),
    ("unavailable", "desktop unavailable"),
])
def test_native_scan_distinguishes_success_match_and_errors(seat, monkeypatch, scenario, error):
    visited = install_native_scan(monkeypatch, scenario)
    if error:
        with pytest.raises(OSError, match=error):
            seat.signin_scan()
    else:
        assert seat.signin_scan() == ("Login | 3DEXPERIENCE ID" if scenario == "match" else None)
    assert bool(visited) == (scenario in ("match", "title_empty", "title_error"))


@pytest.mark.parametrize("scenario", ["enum_error", "title_error", "unavailable"])
def test_observation_error_is_recorded_but_does_not_change_recovery(seat, monkeypatch, scenario):
    install_native_scan(monkeypatch, scenario)
    monkeypatch.setattr(seat.lifecycle, "_signin_window", seat.signin_scan)
    seat.recovery.detect_state = lambda: State.STARTING if seat.clock[0] < 4 else State.CONNECTED
    assert seat.lifecycle.force_recover("manual") == "connected"
    assert seat.calls == ["crash_handler", "stop", "start"]
    start = seat.span("sw.start")
    assert start.status.status_code is StatusCode.ERROR
    assert len(start.exceptions) == 1
    assert start.attributes["wait.outcome"] == "connected"
    assert len([kw for name, kw in seat.events if name == "sw.signin_observation_error"]) == 1
    assert not [kw for name, kw in seat.events if name == "sw.signin_window"]


def test_swallowed_cleanup_error_exports_error_and_exception(seat, monkeypatch):
    sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
    sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
    memory_export = pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")
    import subprocess

    exporter = memory_export.InMemorySpanExporter()
    provider = sdk_trace.TracerProvider()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    @contextlib.contextmanager
    def span(name, service=None, **attributes):
        with tracer.start_as_current_span(name, attributes=attributes) as recorded:
            yield recorded

    def run(*_a, **_kw):
        raise OSError("cleanup exported failure")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(seat.lifecycle, "_kill_crash_handler", seat.crash_handler_cleanup)
    monkeypatch.setattr(seat.lifecycle._telemetry, "span", span)
    try:
        assert seat.lifecycle.force_recover("manual") == "connected"
        recover = next(s for s in exporter.get_finished_spans() if s.name == "sw.force_recover")
        assert recover.status.status_code is StatusCode.ERROR
        assert recover.attributes["final_state"] == "connected"
        assert recover.attributes["outcome"] == "connected"
        exception = next(event for event in recover.events if event.name == "exception")
        assert exception.attributes["exception.message"] == "cleanup exported failure"
        assert exception.attributes["exception.type"].endswith("OSError")
    finally:
        provider.shutdown()
