"""Offline contract for the seat startup gate.

No SolidWorks: the seat and the source part are test doubles, and the
assertions read the real OTel spans the leaf would export.

2026-09-28 drawing:crank_hub (swmaker000008) and 2026-09-17
drawing:pinion_handle (swmaker000005) opened their source part as the first
document of a seat launched seconds earlier and read '' for every custom
property of a correctly published part; both drew clean on a warmer seat.
Pinned here:

* the seat is held until ``ISldWorks.StartupProcessCompleted`` says True,
  whatever its age or origin, bounded; a seat that says False (or rejects the
  call as busy) for the whole bound ends the leaf with exit 89, which
  ``dodo._exec_com`` recovers and retries like a crash -- not an exit 1 that
  reads as a drawing defect; on a farm leaf (autostart off, the keeper's seat)
  it re-runs once on the untouched seat instead;
* a read that never returns is cut off at the bound (``_watchdog.deadline``),
  and exit 89 still flushes its spans and logs and names itself;
* a seat without the member, or with an unintelligible answer, is released at
  once rather than polled for a minute.

The seat line, the watchdog hand-off and the per-poll heartbeat are pinned in
``test_failure_forensics.py``, next to the missing-property capture.

    python -m pytest cad/scripts/test_seat_startup_gate.py
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common  # noqa: E402
import _seat_forensics  # noqa: E402
import _telemetry  # noqa: E402
import _watchdog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_PID = 7204


class _ComError(Exception):
    """A ``pythoncom.com_error`` as pywin32 raises it: a SIGNED hresult first."""

    def __init__(self, hresult: int):
        signed = hresult - (1 << 32)
        super().__init__(signed, "COM error", None, None)
        self.hresult = signed


_REJECTED = 0x80010001  # RPC_E_CALL_REJECTED: alive, still starting
_MEMBER_NOT_FOUND = 0x80020003  # DISP_E_MEMBERNOTFOUND


class _Seat:
    """An ``ISldWorks`` whose ``StartupProcessCompleted`` answers from a script.

    Each read consumes the next scripted answer and the last one repeats; an
    exception in the script is raised, as the COM call would raise it.
    """

    def __init__(self, *answers: Any):
        self._answers = list(answers)
        self.reads = 0

    def GetProcessID(self) -> int:
        return _PID

    def RevisionNumber(self) -> str:
        return "34.3.0"

    @property
    def StartupProcessCompleted(self) -> Any:
        answer = self._answers[min(self.reads, len(self._answers) - 1)]
        self.reads += 1
        if isinstance(answer, BaseException):
            raise answer
        return answer


class _MemberlessSeat:
    """A seat whose interface has no ``StartupProcessCompleted`` at all."""

    def GetProcessID(self) -> int:
        return _PID


class _Adapter:
    def __init__(self, sw: Any):
        self.swApp = sw

    def _attempt(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default


@pytest.fixture(autouse=True)
def offline_seat(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    monkeypatch.setattr(_seat_forensics, "_sldworks_pids", lambda: {_PID})
    monkeypatch.setattr(_seat_forensics, "_seat_pids_at_start", frozenset({_PID}))
    monkeypatch.setattr(_seat_forensics, "_seat_identity", {})
    monkeypatch.setattr(_seat_forensics, "_seat_startup", {})
    monkeypatch.setattr(_seat_forensics, "_process_memory", lambda pid: (None, None))
    monkeypatch.setattr(_seat_forensics, "_process_session_id", lambda pid: 1)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_POLL_S", 0.001)
    monkeypatch.setattr(_watchdog, "_seat_fields", {})


def _seat_age(monkeypatch, seconds: float | None) -> None:
    started = None if seconds is None else time.time() - seconds
    monkeypatch.setattr(_seat_forensics, "_process_started_at", lambda pid: started)


@pytest.fixture
def spans():
    _telemetry.configure()
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider()).add_span_processor(
        processor
    )
    _telemetry._span_processors.append(processor)
    _telemetry._aux_providers.clear()
    yield exporter
    _telemetry._span_processors.remove(processor)
    _telemetry._aux_providers.clear()


def _gate_span(exporter: InMemorySpanExporter):
    (span,) = [s for s in exporter.get_finished_spans() if s.name == "sw.startup_wait"]
    return span


def test_a_ready_seat_passes_at_once_and_records_it(monkeypatch, spans):
    """A warm seat costs one read, and still leaves a span to compare against."""
    _seat_age(monkeypatch, 3600)
    seat = _Seat(True)

    prov = _seat_forensics.record_seat_provenance(_Adapter(seat))

    assert seat.reads == 1
    assert prov["seat_startup"] == "already_ready"
    span = _gate_span(spans)
    assert span.attributes["outcome"] == "already_ready"
    assert span.attributes["uptime_s"] >= 3599
    assert span.attributes["seat_origin"] == "attached"
    assert span.attributes["waited_s"] < 1


def test_a_starting_seat_is_held_until_startup_completes(monkeypatch, spans):
    """The crank_hub seat was 20 s old: the gate holds it through its startup,
    including calls it rejects while add-ins load, and only then lets the
    build open a document."""
    _seat_age(monkeypatch, 20)
    seat = _Seat(False, _ComError(_REJECTED), False, True)

    prov = _seat_forensics.record_seat_provenance(_Adapter(seat))

    assert seat.reads == 4
    assert prov["seat_startup"] == "ready_after_wait"
    span = _gate_span(spans)
    assert span.attributes["outcome"] == "ready_after_wait"
    assert span.attributes["reads"] == 4
    assert span.attributes["waited_s"] == prov["seat_startup_wait_s"]


@pytest.mark.parametrize(
    "answer, said",
    [(False, "StartupProcessCompleted=False"), (_ComError(_REJECTED), "rejected")],
    ids=["false", "busy"],
)
def test_a_seat_that_never_finishes_starting_exits_89_for_recovery(
    monkeypatch, spans, answer, said
):
    """Positively not ready past the bound: a seat-health exit, not exit 1.

    ``run_build`` turns every ``Exception`` into exit 1, which ``_exec_com``
    reads as a recipe failure and never retries; the gate's error must get past
    that and reach the process exit as 89. A seat rejecting every call is as
    not-ready as one saying False.
    """
    _seat_age(monkeypatch, 20)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 0.05)

    with pytest.raises(_watchdog.SeatNotReady) as caught:
        _seat_forensics.record_seat_provenance(_Adapter(_Seat(answer)))

    assert not isinstance(caught.value, Exception)
    assert caught.value.code == _watchdog.EXIT_SEAT_NOT_READY == 89
    assert said in str(caught.value)
    assert f"pid={_PID}" in str(caught.value)
    span = _gate_span(spans)
    assert span.attributes["outcome"] == "timeout"
    assert span.status.status_code is StatusCode.ERROR


@pytest.mark.parametrize("uptime", [3600, None], ids=["warm", "age-unknown"])
def test_the_observed_flag_decides_not_the_seats_age(monkeypatch, spans, uptime):
    """An attached seat an hour old, or one whose age cannot be read, that says
    False is held exactly like a young one: age and origin only ride the span.
    Held until True if it comes; exit 89 if it never does."""
    _seat_age(monkeypatch, uptime)
    seat = _Seat(False, False, True)

    prov = _seat_forensics.record_seat_provenance(_Adapter(seat))

    assert (seat.reads, prov["seat_startup"]) == (3, "ready_after_wait")

    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 0.05)
    with pytest.raises(_watchdog.SeatNotReady):
        _seat_forensics.record_seat_provenance(_Adapter(_Seat(False)))


@pytest.mark.parametrize(
    "seat",
    [_MemberlessSeat(), _Seat(_ComError(_MEMBER_NOT_FOUND))],
    ids=["no-attribute", "DISP_E_MEMBERNOTFOUND"],
)
def test_a_seat_without_the_member_is_released_at_once(monkeypatch, spans, seat):
    """Nothing observed wrong, and nothing to wait for: polling a member that
    does not exist for the whole bound would only burn it, then build anyway."""
    _seat_age(monkeypatch, 20)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 2.0)

    prov = _seat_forensics.record_seat_provenance(_Adapter(seat))

    assert prov["seat_startup"] == "unsupported"
    assert prov["seat_startup_wait_s"] < 0.5
    span = _gate_span(spans)
    assert (span.attributes["outcome"], span.attributes["reads"]) == ("unsupported", 1)


@pytest.mark.parametrize(
    "answer", [None, _ComError(0x800706BA)], ids=["not-a-bool", "rpc-unavailable"]
)
def test_an_unintelligible_answer_is_recorded_and_released(monkeypatch, spans, answer):
    _seat_age(monkeypatch, 20)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 2.0)

    prov = _seat_forensics.record_seat_provenance(_Adapter(_Seat(answer)))

    assert prov["seat_startup"] == "unreadable"
    assert prov["seat_startup_wait_s"] < 0.5


class _HangingSeat(_Seat):
    """A read that does not return until the process would have been killed."""

    def __init__(self, released: threading.Event):
        super().__init__(True)
        self._released = released

    @property
    def StartupProcessCompleted(self) -> Any:
        self._released.wait(5)
        return True


def test_a_read_that_never_returns_is_cut_off_at_the_bound(monkeypatch, spans):
    """A COM read blocked inside SolidWorks cannot be interrupted from Python,
    and the op timeout is 900 s away: the gate's own deadline aborts with 89."""
    _seat_age(monkeypatch, 20)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 0.05)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_HANG_GRACE_S", 0.05)
    released = threading.Event()
    aborts: list[tuple[str, int]] = []
    exits: list[int] = []
    monkeypatch.setattr(
        _watchdog, "_abort", lambda reason, message, code, **_f: aborts.append((reason, code))
    )
    monkeypatch.setattr(
        _watchdog, "_hard_exit", lambda code: (exits.append(code), released.set())
    )

    _seat_forensics.record_seat_provenance(_Adapter(_HangingSeat(released)))

    assert exits == [89]
    assert aborts == [("seat-not-ready", 89)]


def test_the_kill_switch_leaves_a_hanging_read_unbounded(monkeypatch, spans):
    """``HARMONIC_COM_WATCHDOG=0`` disables every watchdog hard exit, the
    startup deadline included: an operator debugging a wedged seat must not be
    killed at the bound. The read returns when SolidWorks answers."""
    _seat_age(monkeypatch, 20)
    monkeypatch.setenv("HARMONIC_COM_WATCHDOG", "0")
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 0.05)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_HANG_GRACE_S", 0.05)
    released = threading.Event()
    exits: list[int] = []
    monkeypatch.setattr(_watchdog, "_hard_exit", exits.append)
    monkeypatch.setattr(_watchdog, "_abort", lambda *_a, **_f: None)
    threading.Timer(0.5, released.set).start()

    prov = _seat_forensics.record_seat_provenance(_Adapter(_HangingSeat(released)))

    assert exits == []
    assert prov["seat_startup"] == "already_ready"


def test_a_gate_that_finishes_disarms_its_deadline(monkeypatch, spans):
    _seat_age(monkeypatch, 20)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 0.02)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_HANG_GRACE_S", 0.02)
    exits: list[int] = []
    monkeypatch.setattr(_watchdog, "_hard_exit", exits.append)
    monkeypatch.setattr(_watchdog, "_abort", lambda *_a, **_f: None)

    _seat_forensics.record_seat_provenance(_Adapter(_Seat(True)))
    time.sleep(0.2)

    assert exits == []


def test_exit_89_flushes_its_telemetry_and_names_itself(monkeypatch):
    """``run_build`` flushes only after an ordinary return; exit 89 is a
    ``SystemExit`` that skips it, and OTLP export is batched -- so the session
    itself must flush on the way out, or the one leaf that needs its trace
    loses it. The exit is also named on the console, not just its status."""
    _seat_age(monkeypatch, 20)
    monkeypatch.setattr(_seat_forensics, "_STARTUP_WAIT_S", 0.05)
    seat = _Seat(False)
    seat.CloseAllDocuments = Mock()
    seat.GetCurrentWorkingDirectory = Mock(return_value="C:\\")
    seat.SetCurrentWorkingDirectory = Mock(return_value=True)
    adapter = _Adapter(seat)
    adapter.connect = AsyncMock()
    adapter.disconnect = AsyncMock()
    monkeypatch.setitem(
        sys.modules,
        "solidworks_mcp.adapters.pywin32_adapter",
        SimpleNamespace(PyWin32Adapter=Mock(return_value=adapter)),
    )
    monkeypatch.setattr(_common._watchdog, "start", Mock())
    monkeypatch.setattr(_common._watchdog, "stop", Mock())
    monkeypatch.setattr(_common, "discard_open_documents", Mock())
    monkeypatch.setattr(_common, "_resident_output_documents", lambda _adapter: [])
    monkeypatch.setattr(sys, "argv", ["draw_crank_hub.py"])
    monkeypatch.delenv("TRACEPARENT", raising=False)
    shutdown = Mock()
    monkeypatch.setattr(_telemetry, "shutdown", shutdown)
    errors: list[str] = []
    monkeypatch.setattr(_telemetry, "error", lambda message, **_f: errors.append(message))
    build = AsyncMock(return_value={})

    with pytest.raises(SystemExit) as caught:
        _common.run_build(build)

    assert caught.value.code == 89
    build.assert_not_awaited()
    adapter.disconnect.assert_awaited_once_with()
    shutdown.assert_called_once_with()
    assert any("exit 89" in m and "StartupProcessCompleted=False" in m for m in errors), errors


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dodo"] = module
    spec.loader.exec_module(module)
    return module


def test_exit_89_takes_the_recover_and_retry_path(monkeypatch):
    dodo = _load_dodo()
    assert dodo._EXIT_SEAT_NOT_READY == _watchdog.EXIT_SEAT_NOT_READY
    calls: list[str] = []
    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: True)
    monkeypatch.setattr(dodo, "_com_retry_backoff", lambda: (0,))
    monkeypatch.setattr(
        dodo,
        "_run_subprocess",
        lambda *_a, **_kw: (calls.append("run"), 89 if len(calls) == 1 else 0)[1],
    )
    # SolidWorks still reads connected: only the exit code can say "retry".
    monkeypatch.setattr(dodo._sw_lifecycle, "is_connected", lambda: True)
    monkeypatch.setattr(
        dodo._sw_lifecycle, "force_recover", lambda: (calls.append("recover"), "connected")[1]
    )

    dodo._exec_com(["x"], "drawing:crank_hub")

    assert calls == ["run", "recover", "run"], calls


def _farm_leaf(monkeypatch, *codes: int) -> tuple[Any, list[str]]:
    """``_exec_com`` as a farm leaf runs it: autostart off, the keeper's seat."""
    dodo = _load_dodo()
    calls: list[str] = []
    answers = iter(codes)
    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: False)
    monkeypatch.setattr(
        dodo, "_run_subprocess", lambda *_a, **_kw: (calls.append("run"), next(answers))[1]
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle, "force_recover", lambda: pytest.fail("a farm leaf killed its seat")
    )
    monkeypatch.setattr(
        dodo, "_fail_task", lambda _label, rc, **_kw: calls.append(f"fail {rc}")
    )
    return dodo, calls


def test_a_farm_leaf_reruns_a_still_starting_seat_once_without_touching_it(
    monkeypatch,
):
    dodo, calls = _farm_leaf(monkeypatch, 89, 0)
    dodo._exec_com(["x"], "drawing:crank_hub")
    assert calls == ["run", "run"]


def test_a_farm_leaf_whose_seat_never_starts_fails_after_one_rerun(monkeypatch):
    dodo, calls = _farm_leaf(monkeypatch, 89, 89)
    dodo._exec_com(["x"], "drawing:crank_hub")
    assert calls == ["run", "run", "fail 89"]


@pytest.mark.parametrize("rc", [1, 86, 88])
def test_a_farm_leaf_reruns_nothing_else(monkeypatch, rc):
    """Every other failure stays the pool's call (it classifies a dead or
    dialog-bound seat itself); only a seat that is merely still starting heals
    in place."""
    dodo, calls = _farm_leaf(monkeypatch, rc)
    dodo._exec_com(["x"], "drawing:crank_hub")
    assert calls == ["run", f"fail {rc}"]
