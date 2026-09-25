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
idle timeout is only as good as the instrumentation poking it. And the session
contract ``run_build`` owes the NEXT leaf: the teardown leaves the seat holding
no ``cad/out`` document AND no directory of this checkout (SolidWorks parks its
own process current directory in the last directory it opened, which on a farm
worker blocks the agent from removing the source root). ``package_native``
attaches through comtypes, not ``run_build``, so its own arming is pinned too:
a Pack-and-Go open that never returns must end in the op-timeout exit, naming
the document.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import _common
import _seat_forensics  # noqa: E402
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
    seq = [
        set(baseline or set()),
        set(crash if crash is not None else baseline or set()),
    ]

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


def test_modal_dialog_warns_first_then_is_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_modal_dialog_abort_carries_the_dialog_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aborts: list[tuple[str, int, dict]] = []
    monkeypatch.setattr(
        _watchdog,
        "_abort",
        lambda reason, msg, code, **f: aborts.append((reason, code, f)),
    )
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
    dog, exits = _make(
        baseline=set(), crash={4242}, dialog_probe=lambda: (0x1234, _LOW_MEMORY)
    )
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
    assert any(
        "watchdog armed" in m and "900s" in m and "modal-dialog" in m for m in infos
    )


def test_run_build_cleans_up_when_session_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        swApp=SimpleNamespace(CloseAllDocuments=Mock()),
    )
    constructor = Mock(return_value=adapter)
    monkeypatch.setitem(
        sys.modules,
        "solidworks_mcp.adapters.pywin32_adapter",
        SimpleNamespace(PyWin32Adapter=constructor),
    )
    monkeypatch.setattr(_common._watchdog, "start", Mock())
    monkeypatch.setattr(_common._watchdog, "stop", Mock())
    monkeypatch.setattr(_common, "discard_open_documents", Mock())
    monkeypatch.setattr(
        _common, "_resident_output_documents", lambda _adapter: ["stuck.SLDDRW"]
    )
    monkeypatch.setattr(_common._telemetry, "shutdown", Mock())
    monkeypatch.setattr(sys, "argv", ["build_probe.py"])
    monkeypatch.delenv("TRACEPARENT", raising=False)
    build = AsyncMock()

    assert _common.run_build(build) == 1
    build.assert_not_awaited()
    adapter.disconnect.assert_awaited_once_with()
    # Setup discarded once and failed on the survivor; teardown still discards
    # (the seat must be left empty even when the session never built).
    assert _common.discard_open_documents.call_args_list == [
        ((adapter,),),
        ((adapter,),),
    ]
    _common._watchdog.start.assert_called_once_with()
    _common._watchdog.stop.assert_called_once_with()


def _seat(
    start: str, *, moved: object = True
) -> tuple[SimpleNamespace, SimpleNamespace]:
    """A seat whose working directory is STATE, not a fixed answer sequence.

    The seat is read more than once per session -- connect samples it for the
    provenance attributes, teardown reads it before and after the re-point --
    and a fake keyed to call ORDER silently mis-answers (and then raises
    ``StopIteration``) the moment a caller adds a reading. So the fake owns a
    directory and the setter moves it.

    ``moved`` is what ``SetCurrentWorkingDirectory`` does: ``True`` accepts the
    move, ``False`` refuses it, ``"ignored"`` answers True without moving --
    the case that proves the readback, not the return value, is the evidence --
    and ``"blank"`` answers True and leaves the seat unable to say where it is.
    Each is a property of the SEAT, so it holds for every read, however many
    readings a caller takes.
    """

    seat = SimpleNamespace(cwd=start)

    def _set(target: str) -> object:
        if moved is True:
            seat.cwd = target
        elif moved == "blank":
            seat.cwd = ""
        return True if moved in ("ignored", "blank") else moved

    app = SimpleNamespace(
        CloseAllDocuments=Mock(),
        GetCurrentWorkingDirectory=Mock(side_effect=lambda: seat.cwd),
        SetCurrentWorkingDirectory=Mock(side_effect=_set),
    )
    adapter = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        swApp=app,
        _attempt=lambda call, default=None: call(),
    )
    return adapter, app


def _session(
    monkeypatch: pytest.MonkeyPatch, adapter: SimpleNamespace
) -> SimpleNamespace:
    """Run one clean ``run_build`` session; return its warnings and success fields."""

    monkeypatch.setitem(
        sys.modules,
        "solidworks_mcp.adapters.pywin32_adapter",
        SimpleNamespace(PyWin32Adapter=Mock(return_value=adapter)),
    )
    monkeypatch.setattr(_common._watchdog, "start", Mock())
    monkeypatch.setattr(_common._watchdog, "stop", Mock())
    monkeypatch.setattr(_common, "discard_open_documents", Mock())
    monkeypatch.setattr(_common, "_resident_output_documents", lambda _adapter: [])
    monkeypatch.setattr(_common, "_pin_default_part_template", Mock())
    # Seat provenance is resolved once per PROCESS and cached in a module
    # global, so one session's reading (or its failure) would otherwise leak
    # into every later test in the same pytest run.
    monkeypatch.setattr(_seat_forensics, "_seat_identity", {})
    monkeypatch.setattr(_common._telemetry, "shutdown", Mock())
    monkeypatch.setattr(sys, "argv", ["build_probe.py"])
    monkeypatch.delenv("TRACEPARENT", raising=False)
    session = SimpleNamespace(warnings=[], fields={})
    monkeypatch.setattr(
        _common._telemetry,
        "warn",
        lambda message, **_f: session.warnings.append(message),
    )
    monkeypatch.setattr(
        _common._telemetry,
        "success",
        lambda _message, **fields: session.fields.update(fields),
    )
    assert _common.run_build(AsyncMock(return_value={})) == 0
    return session


def test_teardown_moves_the_seat_out_of_the_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SolidWorks' own process current directory follows the documents it opens,
    # and Windows will not remove a directory that is any process's cwd. On a
    # farm worker this checkout is a source root the agent removes between
    # leaves, so a seat left parked in cad/out fails an unrelated leaf's cleanup
    # with WinError 32 (2026-09-18, swmaker000006). Closing documents does not
    # release it: the cwd belongs to the process, not to a document.
    # The helper's own answer, not tempfile.gettempdir(): on a worker whose
    # TEMP sits under FARM_WORK_ROOT the two differ, and check:watchdog runs
    # on workers. Hard-coding gettempdir() would fail for an environmental
    # reason rather than a behavioural one.
    temp = str(_seat_forensics._seat_park_directory())
    parked = str(_common.CAD_ROOT / "out" / "sldprt")
    adapter, app = _seat(parked)

    session = _session(monkeypatch, adapter)

    assert session.warnings == []
    app.SetCurrentWorkingDirectory.assert_called_once_with(temp)
    # Emitted under the same key the seat provenance samples at CONNECT, so one
    # query reads both ends: where a leaf left the seat, and where the next leaf
    # found it. A connect-time reading under the farm work root means some leaf
    # skipped or failed this teardown.
    assert session.fields["seat_working_directory"] == temp


def test_a_seat_left_in_a_sibling_source_root_is_unparked_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A worker keeps several source roots, and the one that failed was pinned by
    # a leaf OTHER than the running one (2026-09-18: the export leaf's root was
    # fa07428b, the pinned root 6621e07a). A teardown that only left its own
    # checkout would leave that root pinned until the seat died, so the seat is
    # parked unconditionally.
    temp = str(_seat_forensics._seat_park_directory())
    sibling = r"C:\harmonic\work\sources\6621e07aabfb412916eeae68\workspace\cad\out"
    adapter, app = _seat(sibling)

    assert _session(monkeypatch, adapter).warnings == []

    app.SetCurrentWorkingDirectory.assert_called_once_with(temp)


def test_a_seat_already_parked_there_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, app = _seat(str(_seat_forensics._seat_park_directory()))

    assert _session(monkeypatch, adapter).warnings == []

    app.SetCurrentWorkingDirectory.assert_not_called()


def test_a_seat_that_refuses_to_move_warns_instead_of_failing_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same standing as the teardown close: a directory this session cannot
    # release is the NEXT leaf's hazard, not a failure of work already done.
    adapter, _app = _seat(str(_common.CAD_ROOT / "out" / "sldprt"), moved=False)

    warnings = _session(monkeypatch, adapter).warnings

    assert [w for w in warnings if "seat working directory" in w]


def test_a_move_the_seat_ignored_is_not_reported_as_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SetCurrentWorkingDirectory answering True is not evidence: the readback is.
    parked = str(_common.CAD_ROOT / "out" / "sldprt")
    adapter, _app = _seat(parked, moved="ignored")

    session = _session(monkeypatch, adapter)

    assert [w for w in session.warnings if "did not move" in w]
    assert "seat_working_directory" not in session.fields


def test_an_unreadable_working_directory_is_not_papered_over() -> None:
    app = SimpleNamespace(
        GetCurrentWorkingDirectory=Mock(return_value=None),
        SetCurrentWorkingDirectory=Mock(),
    )
    with pytest.raises(RuntimeError, match="unreadable"):
        _seat_forensics.release_seat_working_directory(app)
    app.SetCurrentWorkingDirectory.assert_not_called()


def test_an_empty_readback_from_the_park_directory_is_not_a_move(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # ``os.path.realpath("")`` is the PROCESS current directory, so an empty
    # readback normalizes onto the park target itself whenever the helper runs
    # from there -- and a seat that cannot say where it is would be reported as
    # parked. Reachable off the farm: gettempdir() falls back to the process
    # directory with TMPDIR/TEMP/TMP unusable, which makes target == cwd.
    monkeypatch.setattr(_seat_forensics.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.chdir(tmp_path)
    # The precondition that makes the hole reachable, asserted so this test
    # cannot quietly stop exercising it.
    assert _seat_forensics._normal_path("") == _seat_forensics._normal_path(
        _seat_forensics._seat_park_directory()
    )
    _adapter, app = _seat(str(_common.CAD_ROOT / "out" / "sldprt"), moved="blank")

    with pytest.raises(RuntimeError, match="unreadable after move"):
        _seat_forensics.release_seat_working_directory(app)

    app.SetCurrentWorkingDirectory.assert_called_once_with(str(tmp_path))


def test_an_empty_reading_before_the_move_is_not_already_parked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The BEFORE side of the same ``realpath("")`` hole, and the worse half:
    # the after-side failure at least warns, while an empty reading accepted
    # here normalizes onto the park target, returns None as "already there",
    # and moves nothing -- no warning, no seat_working_directory row, and the
    # seat still pinned in a disposable source root for the next leaf's
    # cleanup to die on with nothing in the log naming the cause.
    #
    # Passing None would only exercise the ``type(before) is not str`` clause;
    # this pins ``not before``, so deleting it fails here instead of silently
    # skipping the move.
    monkeypatch.setattr(_seat_forensics.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert _seat_forensics._normal_path("") == _seat_forensics._normal_path(
        _seat_forensics._seat_park_directory()
    )
    _adapter, app = _seat("")

    with pytest.raises(RuntimeError, match="unreadable"):
        _seat_forensics.release_seat_working_directory(app)

    app.SetCurrentWorkingDirectory.assert_not_called()


def test_a_temp_directory_inside_this_checkout_is_never_the_park_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # tempfile.gettempdir() is not a constant: it takes TMPDIR/TEMP/TMP from
    # the environment and, with none usable, falls back to the PROCESS CURRENT
    # DIRECTORY -- which under the farm helper is the workspace being torn
    # down. Parking there would make the whole re-point a silent no-op.
    #
    # The checkout is SYNTHESIZED rather than pointed at the real ``cad/out``,
    # which is gitignored and carries no tracked file. On a fresh source root
    # it does not exist, and ``_seat_park_directory`` skips a candidate that is
    # not a directory BEFORE it asks whether the candidate is disposable -- so
    # against the real path this passed for the wrong reason and could not
    # distinguish the guard's presence from its absence. A farm source root IS
    # a fresh extraction and check:watchdog runs there, so the fleet ran the
    # vacuous variant. Same ``mkdir`` the sibling-root test below already does.
    checkout = tmp_path / "workspace"
    inside = checkout / "cad" / "out"
    inside.mkdir(parents=True)
    monkeypatch.setattr(_common, "CAD_ROOT", checkout / "cad")
    monkeypatch.setattr(_seat_forensics.tempfile, "gettempdir", lambda: str(inside))
    # Without this the candidate is skipped as a non-directory and the
    # disposable filter never runs at all.
    assert inside.is_dir()

    target = _seat_forensics._seat_park_directory()

    assert target.is_dir()
    assert _seat_forensics._normal_path(target) != _seat_forensics._normal_path(inside)
    assert (
        _seat_forensics._normal_path(checkout) not in _seat_forensics._normal_path(target).parents
    )
    adapter, app = _seat(str(inside / "sldprt"))
    assert _session(monkeypatch, adapter).warnings == []
    app.SetCurrentWorkingDirectory.assert_called_once_with(str(target))


def test_a_sibling_source_root_is_not_a_park_target_either(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A worker keeps several source roots under one work root and removes them
    # with the same housekeeping, so "outside MY checkout" is not enough:
    # parking in a sibling root just moves which leaf fails. FARM_WORK_ROOT is
    # the worker's own name for that tree, and job_environment passes it on.
    work_root = tmp_path / "harmonic" / "work"
    mine = work_root / "sources" / "aaa" / "workspace"
    sibling = work_root / "sources" / "bbb" / "workspace"
    (mine / "cad").mkdir(parents=True)
    sibling.mkdir(parents=True)
    monkeypatch.setattr(_common, "CAD_ROOT", mine / "cad")
    monkeypatch.setenv("FARM_WORK_ROOT", str(work_root))
    monkeypatch.setattr(_seat_forensics.tempfile, "gettempdir", lambda: str(sibling))

    target = _seat_forensics._normal_path(_seat_forensics._seat_park_directory())

    assert _seat_forensics._normal_path(work_root) not in target.parents


def test_a_close_that_fails_still_moves_the_seat_out_of_the_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # package_native's release: an exit that dies mid-teardown is exactly the
    # one that leaves a seat parked in a disposable source root, so the
    # re-point cannot sit behind a close that raises.
    import package_native

    # The state-based seat, not a ``side_effect`` list: an answer sequence
    # keyed to call ORDER passes for the wrong reason the moment the
    # implementation reorders or adds a read, and then fails as a
    # ``StopIteration`` that ``_release_seat``'s ``except Exception`` turns
    # into a warning -- surfacing as a confusing assert on the setter.
    target = str(_seat_forensics._seat_park_directory())
    _adapter, app = _seat(str(_common.CAD_ROOT / "out" / "sldasm"))
    monkeypatch.setattr(
        package_native,
        "_discard_open_documents",
        Mock(side_effect=RuntimeError("modal")),
    )

    with pytest.raises(RuntimeError, match="modal"):
        package_native._release_seat(app)

    app.SetCurrentWorkingDirectory.assert_called_once_with(target)


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


def test_connect_is_split_into_dispatch_identity_and_discard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # sw.connect costs ~2.2 s p50 in every COM subprocess; its three steps each
    # get a child span so that cost is attributable without log archaeology.
    opened: list[str] = []
    span, aspan = _common._telemetry.span, _common._telemetry.aspan

    def record_span(name, /, **attrs):
        opened.append(name)
        return span(name, **attrs)

    def record_aspan(name, /, **attrs):
        opened.append(name)
        return aspan(name, **attrs)

    monkeypatch.setattr(_common._telemetry, "span", record_span)
    monkeypatch.setattr(_common._telemetry, "aspan", record_aspan)
    adapter, _app = _seat(str(_seat_forensics._seat_park_directory()))

    _session(monkeypatch, adapter)

    connect = opened.index("sw.connect")
    assert opened[connect + 1 : connect + 4] == [
        "sw.dispatch",
        "seat.identity",
        "seat.discard",
    ]
def _package_seat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, open_doc):
    """package_native pointed at a tmp top assembly and a mock seat whose
    ``OpenDoc6`` is ``open_doc``; returns the prepared-tree directory."""
    import package_native

    sldasm = tmp_path / "sldasm"
    sldasm.mkdir()
    (sldasm / f"{package_native.TOP_ASSEMBLY}.SLDASM").write_bytes(b"asm")
    monkeypatch.setattr(package_native, "OUT_SLDASM", sldasm)
    monkeypatch.setattr(package_native, "RELEASE_DIR", tmp_path / "release")
    monkeypatch.setattr(
        package_native._seat_forensics, "release_seat_working_directory", lambda _sw: None
    )
    seat = SimpleNamespace(
        IActiveDoc2=None, CloseAllDocuments=Mock(), CloseDoc=Mock(), OpenDoc6=open_doc
    )
    monkeypatch.setattr(package_native, "attach_solidworks", lambda: (seat, "34.0"))
    return tmp_path / "release" / "native"


def test_a_pack_and_go_open_that_never_returns_trips_the_watchdog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rekey2, 2026-09-25: package:release sat 78 min inside one drawing's open
    with nothing to end it -- package_native attaches through comtypes, not
    run_build, so the watchdog was never armed. The real Watchdog, a short op
    timeout and a seat whose OpenDoc6 blocks: the idle abort must fire with the
    op-timeout exit code and name the document the seat wedged on."""
    import package_native

    released = threading.Event()
    aborts: list[dict[str, object]] = []
    exits: list[int] = []

    def open_doc(path, *_args):
        released.wait(5)
        raise RuntimeError(f"seat killed while opening {Path(path).name}")

    def record_abort(reason, message, code, **fields):
        aborts.append({"reason": reason, "code": code, **fields})

    def record_exit(code):
        exits.append(code)
        released.set()

    dogs: list[Watchdog] = []

    def start():
        dog = Watchdog(
            op_timeout=0.3,
            poll_interval=0.05,
            crash_pids=set,
            hung_probe=lambda: False,
            dialog_probe=lambda: None,
            exit_fn=record_exit,
        )
        dog.start()
        dogs.append(dog)
        return dog

    monkeypatch.setattr(_watchdog, "_abort", record_abort)
    monkeypatch.setattr(_watchdog, "start", start)
    monkeypatch.setattr(_watchdog, "stop", lambda: dogs[-1].stop())
    out = _package_seat(tmp_path, monkeypatch, open_doc)

    with pytest.raises(RuntimeError, match="seat killed while opening"):
        package_native.package_native(out)

    assert exits[:1] == [EXIT_OP_TIMEOUT]
    assert (aborts[0]["reason"], aborts[0]["code"]) == ("op-timeout", EXIT_OP_TIMEOUT)
    assert aborts[0]["last_op"] == (
        f"span-start package.open {package_native.TOP_ASSEMBLY}.SLDASM"
    )
    assert dogs[-1]._stop.is_set()  # disarmed on the way out, even on failure


def test_package_native_arms_the_watchdog_around_the_seat_session_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Armed before attach, disarmed after the seat is released (Pack-and-Go AND
    the release stamping are inside), and NOT armed for the SolidWorks-free print
    checks and sidecar write -- the order run_build keeps."""
    import package_native

    events: list[str] = []
    monkeypatch.setattr(_watchdog, "start", lambda: events.append("arm"))
    monkeypatch.setattr(_watchdog, "stop", lambda: events.append("disarm"))
    out = _package_seat(tmp_path, monkeypatch, Mock())
    attach = package_native.attach_solidworks
    monkeypatch.setattr(
        package_native, "attach_solidworks", lambda: (events.append("attach"), attach())[1]
    )
    monkeypatch.setattr(
        package_native,
        "package_top_assembly",
        lambda _sw, _out: (events.append("top"), ())[1],
    )
    monkeypatch.setattr(
        package_native,
        "package_drawings",
        lambda _sw, _out, _sources: (events.append("drawings"), {})[1],
    )
    monkeypatch.setattr(
        package_native,
        "stamp_release",
        lambda _sw, _out, _revision: (events.append("stamp"), {"pdfs": {}})[1],
    )
    monkeypatch.setattr(
        package_native, "_release_seat", lambda _sw: events.append("release")
    )
    monkeypatch.setattr(
        package_native,
        "finish_release_prints",
        lambda *_a: (events.append("prints"), {})[1],
    )
    monkeypatch.setattr(
        package_native,
        "write_sidecar",
        lambda *_a, **_k: (events.append("sidecar"), {"solidworks_revision": "34.0"})[1],
    )

    package_native.package_native(out)

    assert events == [
        "arm", "attach", "release", "top", "drawings", "stamp", "release", "disarm",
        "prints", "sidecar",
    ]
