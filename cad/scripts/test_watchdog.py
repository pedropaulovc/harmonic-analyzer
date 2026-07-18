"""Offline contract for the COM watchdog (check:watchdog, no SolidWorks).

Pins the three signals and their severities: a NEW sldexitapp.exe pid is fatal
(exit 86) while a stale pre-existing one is ignored; telemetry silence past the
op timeout is fatal (exit 87) and fresh activity is not; a hung SolidWorks
window only WARNS, throttled -- per the 2026-07-18 decision that
``Responding == False`` is too noisy to kill on (SolidWorks legitimately stops
pumping messages while resolving complex geometry). Also pins the heartbeat:
spans and log records must advance ``_telemetry.last_activity()``, since the
idle timeout is only as good as the instrumentation poking it.
"""

from __future__ import annotations

import logging

import pytest

import _telemetry
import _watchdog
from _watchdog import EXIT_CRASH, EXIT_OP_TIMEOUT, Watchdog


class _Exit(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


def _make(
    *,
    crash: set[int] | None = None,
    baseline: set[int] | None = None,
    hung: bool = False,
    idle: float = 0.0,
    timeout: float = 900.0,
) -> tuple[Watchdog, list[int]]:
    exits: list[int] = []

    def _exit(code: int) -> None:
        exits.append(code)
        raise _Exit(code)

    now = 10_000.0
    # First call happens in __init__ (the baseline snapshot); every later call
    # (tick) sees the ``crash`` set.
    seq = [set(baseline or set()), set(crash if crash is not None else baseline or set())]

    dog = Watchdog(
        op_timeout=timeout,
        crash_pids=lambda: set(seq.pop(0)) if len(seq) > 1 else set(seq[0]),
        hung_probe=lambda: hung,
        activity=lambda: now - idle,
        exit_fn=_exit,
        clock=lambda: now,
    )
    return dog, exits


def test_new_crash_pid_is_fatal() -> None:
    dog, exits = _make(baseline=set(), crash={4242})
    with pytest.raises(_Exit):
        dog.tick()
    assert exits == [EXIT_CRASH]


def test_stale_crash_dialog_is_ignored() -> None:
    # sldexitapp already running when the watchdog starts = a leftover dialog
    # from a previous crash; a healthy build next to it must not be killed.
    dog, exits = _make(baseline={1111}, crash={1111})
    assert dog.tick() is None
    assert exits == []


def test_stale_plus_new_crash_pid_still_fatal() -> None:
    dog, exits = _make(baseline={1111}, crash={1111, 2222})
    with pytest.raises(_Exit):
        dog.tick()
    assert exits == [EXIT_CRASH]


def test_idle_past_timeout_is_fatal() -> None:
    dog, exits = _make(idle=901.0, timeout=900.0)
    with pytest.raises(_Exit):
        dog.tick()
    assert exits == [EXIT_OP_TIMEOUT]


def test_fresh_activity_is_healthy() -> None:
    dog, exits = _make(idle=100.0, timeout=900.0)
    assert dog.tick() is None
    assert exits == []


def test_timeout_zero_disables_idle_check() -> None:
    dog, exits = _make(idle=1e9, timeout=0.0)
    assert dog.tick() is None
    assert exits == []


def test_hung_window_warns_but_never_exits(caplog: pytest.LogCaptureFixture) -> None:
    dog, exits = _make(hung=True, idle=100.0)
    with caplog.at_level(logging.WARNING, logger="harmonic"):
        assert dog.tick() == "hung"
    assert exits == []
    assert any("not responding" in r.message for r in caplog.records)


def test_hung_warn_is_throttled(caplog: pytest.LogCaptureFixture) -> None:
    dog, _ = _make(hung=True, idle=100.0)
    with caplog.at_level(logging.WARNING, logger="harmonic"):
        dog.tick()
        dog.tick()  # same clock instant -> inside the throttle window
    warns = [r for r in caplog.records if "not responding" in r.message]
    assert len(warns) == 1


def test_env_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARMONIC_COM_WATCHDOG", "0")
    assert _watchdog.start() is None


def test_start_stop_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARMONIC_COM_WATCHDOG", raising=False)
    monkeypatch.setenv("HARMONIC_COM_OP_TIMEOUT", "900")
    first = _watchdog.start()
    try:
        assert first is not None
        assert _watchdog.start() is first
    finally:
        _watchdog.stop()
    assert _watchdog._active is None


def test_span_boundaries_poke_the_heartbeat() -> None:
    _telemetry._last_activity = 0.0
    with _telemetry.span("watchdog.test"):
        pass
    assert _telemetry.last_activity() > 0.0


def test_log_records_poke_the_heartbeat() -> None:
    _telemetry._last_activity = 0.0
    _telemetry.debug("watchdog heartbeat probe")
    assert _telemetry.last_activity() > 0.0
