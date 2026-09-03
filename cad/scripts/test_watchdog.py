"""Offline contract for the COM watchdog (check:watchdog, no SolidWorks).

Pins the four signals and their severities: a NEW sldexitapp.exe pid is fatal
(exit 86) while a stale pre-existing one is ignored; a modal message box
blocking the seat is fatal (exit 88) once it survives two polls, and one that
clears in between is not; telemetry silence past the
op timeout is fatal (exit 87) and fresh activity is not; a hung SolidWorks
window only WARNS, throttled -- per the 2026-07-18 decision that
``Responding == False`` is too noisy to kill on (SolidWorks legitimately stops
pumping messages while resolving complex geometry). Also pins the heartbeat:
spans and log records must advance ``_telemetry.last_activity()``, since the
idle timeout is only as good as the instrumentation poking it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import _telemetry
import _watchdog
from _watchdog import EXIT_CRASH, EXIT_MODAL_DIALOG, EXIT_OP_TIMEOUT, Watchdog


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
    dialog_probe=lambda: None,
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
        dialog_probe=dialog_probe,
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


def test_hung_window_warns_but_never_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    # Capture via a test double, not caplog: the harmonic logger has
    # propagate=False, so records never reach caplog's root handler (codex #344).
    warns: list[str] = []
    monkeypatch.setattr(_watchdog, "_warn", lambda msg, **f: warns.append(msg))
    dog, exits = _make(hung=True, idle=100.0)
    assert dog.tick() == "hung"
    assert exits == []
    assert any("not responding" in w for w in warns)


def test_hung_warn_is_throttled(monkeypatch: pytest.MonkeyPatch) -> None:
    warns: list[str] = []
    monkeypatch.setattr(_watchdog, "_warn", lambda msg, **f: warns.append(msg))
    dog, _ = _make(hung=True, idle=100.0)
    dog.tick()
    dog.tick()  # same clock instant -> inside the throttle window
    assert len([w for w in warns if "not responding" in w]) == 1


def test_hung_recovery_closes_the_episode(monkeypatch: pytest.MonkeyPatch) -> None:
    infos: list[str] = []
    monkeypatch.setattr(_watchdog, "_warn", lambda msg, **f: None)
    monkeypatch.setattr(_watchdog, "_info", lambda msg, **f: infos.append(msg))
    dog, _ = _make(hung=True, idle=100.0)
    assert dog.tick() == "hung"
    dog._hung_probe = lambda: False
    assert dog.tick() is None
    assert any("responsive again" in m for m in infos)
    # A later episode warns afresh (throttle reset on recovery).
    assert dog._hung_since is None


_LOW_MEMORY = (
    "Warning! Your system is running critically low on committed memory. "
    "Executing this command might cause SOLIDWORKS to fail."
)


def test_modal_dialog_warns_first_then_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    # 2026-09-02: the low-memory box blocked the seat mid top-assembly build; a
    # first sighting only warns (a transient box must not kill a healthy build),
    # the second consecutive poll aborts with its own exit code so dodo retries
    # after a kill + relaunch.
    warns: list[str] = []
    monkeypatch.setattr(_watchdog, "_warn", lambda msg, **f: warns.append(msg))
    dog, exits = _make(dialog_probe=lambda: (0x1234, _LOW_MEMORY))
    assert dog.tick() == "modal-pending"
    assert exits == [] and any("modal dialog up" in m for m in warns)
    with pytest.raises(_Exit):
        dog.tick()
    assert exits == [EXIT_MODAL_DIALOG]


def test_modal_dialog_that_clears_resets_the_count() -> None:
    seen: list[tuple[int, str] | None] = [(0x1234, _LOW_MEMORY)]
    dog, exits = _make(dialog_probe=lambda: seen[0])
    assert dog.tick() == "modal-pending"
    seen[0] = None
    assert dog.tick() is None
    seen[0] = (0x1234, _LOW_MEMORY)
    assert dog.tick() == "modal-pending"
    assert exits == []


def test_two_different_transient_dialogs_are_not_one_persistent_one() -> None:
    # CodeRabbit (#659): box A closes and box B opens between polls -- neither
    # survived two polls, so the count restarts on the new window handle.
    seen: list[tuple[int, str] | None] = [(0x1111, "box A")]
    dog, exits = _make(dialog_probe=lambda: seen[0])
    assert dog.tick() == "modal-pending"
    seen[0] = (0x2222, "box B")
    assert dog.tick() == "modal-pending"
    assert exits == []
    with pytest.raises(_Exit):
        dog.tick()  # box B, second consecutive poll
    assert exits == [EXIT_MODAL_DIALOG]


def test_modal_dialog_abort_carries_the_dialog_text(monkeypatch: pytest.MonkeyPatch) -> None:
    aborts: list[tuple[str, int, dict]] = []
    monkeypatch.setattr(_watchdog, "_abort", lambda reason, msg, code, **f: aborts.append((reason, code, f)))
    monkeypatch.setattr(_watchdog, "_warn", lambda msg, **f: None)
    dog, _ = _make(dialog_probe=lambda: (0x1234, _LOW_MEMORY))
    dog.tick()
    with pytest.raises(_Exit):
        dog.tick()
    reason, code, fields = aborts[0]
    assert (reason, code) == ("modal-dialog", EXIT_MODAL_DIALOG)
    assert "committed memory" in fields["dialog_text"]
    assert "last_op" in fields and "idle_s" in fields


def test_crash_outranks_a_pending_modal_dialog() -> None:
    # A crash dialog and a leftover modal can coexist; the crash wins immediately.
    dog, exits = _make(baseline=set(), crash={4242}, dialog_probe=lambda: (0x1234, _LOW_MEMORY))
    with pytest.raises(_Exit):
        dog.tick()
    assert exits == [EXIT_CRASH]


def test_fatal_signals_carry_structured_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The abort must be reconstructable from logs.jsonl/traces.jsonl alone:
    # reason, idle, and the operation the pipeline was last seen in.
    aborts: list[tuple[str, int, dict]] = []
    monkeypatch.setattr(
        _watchdog,
        "_abort",
        lambda reason, msg, code, **f: aborts.append((reason, code, f)),
    )
    dog, _ = _make(baseline=set(), crash={4242})
    with pytest.raises(_Exit):
        dog.tick()
    reason, code, fields = aborts[0]
    assert (reason, code) == ("crash", EXIT_CRASH)
    assert "4242" in fields["pids"]
    assert "last_op" in fields and "idle_s" in fields

    aborts.clear()
    dog2, _ = _make(idle=901.0, timeout=900.0)
    with pytest.raises(_Exit):
        dog2.tick()
    reason, code, fields = aborts[0]
    assert (reason, code) == ("op-timeout", EXIT_OP_TIMEOUT)
    assert fields["idle_s"] == 901 and fields["timeout_s"] == 900
    assert "last_op" in fields


def test_watchdog_self_logs_do_not_reset_the_idle_clock() -> None:
    # The P1 regression (codex #344): the periodic hung-window warn goes through
    # the harmonic logger, whose _ActivityFilter pokes the heartbeat -- so a
    # permanently wedged SolidWorks would reset its own idle clock every 5 min
    # and never hit the op timeout. watchdog_signal=True exempts it.
    _telemetry._last_activity = 0.0
    _watchdog._warn("hung-window self log")
    _watchdog._error("crash self log")
    assert _telemetry.last_activity() == 0.0
    _telemetry.warn("a real pipeline warn")
    assert _telemetry.last_activity() > 0.0


def test_env_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARMONIC_COM_WATCHDOG", "0")
    assert _watchdog.start() is None


def test_start_stop_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARMONIC_COM_WATCHDOG", raising=False)
    monkeypatch.setenv("HARMONIC_COM_OP_TIMEOUT", "900")
    # The check:* gates are pure-python and must pass off-Windows too, where the
    # real platform gate would return None (codex #344) -- force it open; the
    # Win32 probes inside are themselves guarded no-ops off-Windows.
    monkeypatch.setattr(_watchdog, "_WINDOWS", True)
    first = _watchdog.start()
    try:
        assert first is not None
        assert _watchdog.start() is first
    finally:
        _watchdog.stop()
    assert _watchdog._active is None


def test_start_logs_the_armed_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARMONIC_COM_WATCHDOG", raising=False)
    monkeypatch.setenv("HARMONIC_COM_OP_TIMEOUT", "900")
    monkeypatch.setattr(_watchdog, "_WINDOWS", True)
    infos: list[str] = []
    monkeypatch.setattr(_watchdog, "_info", lambda msg, **f: infos.append(msg))
    try:
        assert _watchdog.start() is not None
    finally:
        _watchdog.stop()
    assert any("watchdog armed" in m and "900s" in m and "modal-dialog" in m for m in infos)


def test_run_build_wires_the_watchdog() -> None:
    # Pin the INTEGRATION, not just the unit: run_build is the single COM entry
    # and the only caller of start()/stop() -- if a refactor drops either call,
    # every COM subprocess silently runs unprotected while this gate stays
    # green (codex #344). Source-text pin (not an import) so the gate needs no
    # SolidWorks adapter on the machine running it.
    src = (Path(__file__).with_name("_common.py")).read_text(encoding="utf-8")
    assert src.count("def run_build(") == 1
    run_build_src = src.split("def run_build(", 1)[1]
    assert "_watchdog.start()" in run_build_src, "run_build no longer arms the watchdog"
    assert "_watchdog.stop()" in run_build_src, "run_build no longer disarms the watchdog"


def test_span_boundaries_poke_the_heartbeat() -> None:
    _telemetry._last_activity = 0.0
    with _telemetry.span("watchdog.test"):
        pass
    assert _telemetry.last_activity() > 0.0
    # The op label names the boundary, so an idle-timeout abort can say WHICH
    # operation the pipeline was last seen in.
    assert _telemetry.last_activity_op() == "span-end watchdog.test"


def test_log_records_poke_the_heartbeat() -> None:
    _telemetry._last_activity = 0.0
    _telemetry.debug("watchdog heartbeat probe")
    assert _telemetry.last_activity() > 0.0
    assert _telemetry.last_activity_op().startswith("log watchdog heartbeat")
