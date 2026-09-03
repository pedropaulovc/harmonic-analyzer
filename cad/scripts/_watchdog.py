"""SolidWorks COM watchdog -- fail loud when the seat process crashes or wedges.

Every COM subprocess (``_common.run_build`` is the single entry) blocks
synchronously inside pywin32 COM calls, so a crashed or hung SolidWorks leaves
the process -- and the machine-global seat it represents -- stuck forever with
no Python-level exception. A daemon thread watches four signals, calibrated
from the telemetry history (2026-07-18 audit of ~3 weeks of ``traces.jsonl``):

* **CRASH (fatal).** ``sldexitapp.exe`` -- SolidWorks' own crash-report
  handler, owner of the ``#32770`` dialog titled "SOLIDWORKS Design" ("...has
  encountered a problem... Generating crash report") -- only ever runs after
  SLDWORKS.exe has crashed. The Windows event log is NOT a usable trigger: the
  handler intercepts WER, and the ``AppCrash_sldworks.exe`` entry lands only
  once the report completes (observed stuck 8.5 h+). Process appearance is the
  earliest reliable event. Pids already alive when the watchdog starts are a
  STALE dialog from a previous crash (the user may run a healthy new SolidWorks
  next to it) -- warned once, then ignored; only a NEW pid is fatal.
* **MODAL DIALOG (fatal).** A visible ``#32770`` message box titled
  "SOLIDWORKS Design", owned by ``sldworks.exe``, whose owner window (the main
  frame) is DISABLED -- the Win32 modal contract. No COM call completes until a
  human clicks, and the one that started this (2026-09-02, mid top-assembly
  build: "Warning! Your system is running critically low on committed
  memory... SOLIDWORKS strongly recommends that you do not continue") precedes
  a crash -- so the safe recovery is kill + relaunch, never clicking Yes. Fatal
  once the box has survived ``_MODAL_CONFIRM_TICKS`` consecutive polls (a
  transient box is only warned about); ``dodo._exec_com`` treats exit 88 like
  a crash: force-recover SolidWorks and retry the task. The start-up .NET splash
  wedge (owner = the ``splash`` window) belongs to the lifecycle library.
* **OP TIMEOUT (fatal).** No telemetry activity -- span boundary or log
  record -- for ``HARMONIC_COM_OP_TIMEOUT`` seconds (default 900). The longest
  single COM operation ever observed is ~230 s (``verify.rebuild``), so 15 min
  is ~4x headroom; whole COM tasks legitimately run ~27 min
  (``assembly:summing``), which is why the timeout keys on per-op activity via
  ``_telemetry.last_activity()``, never on process lifetime.
* **HUNG WINDOW (log-only).** A SLDWORKS.exe top-level window fails
  ``IsHungAppWindow``. Deliberately NOT fatal: SolidWorks legitimately stops
  pumping messages while resolving complex geometry, so this is a noisy
  criterion -- but a throttled ``!!`` line makes a wedge visible in the log
  timeline long before the op timeout fires.

A fatal signal logs ``xx``, flushes telemetry, and hard-exits via
``os._exit`` -- the main thread is blocked inside a COM call on a dead server,
so only a process exit can release it. The doit parent then fails the task and
its ``_com_seat`` context (the seat lock is held by the PARENT, not this
process) releases the machine-global lock: the seat never leaks. Distinct exit
codes make the three fatals diagnosable from the doit console alone.

Disable entirely with ``HARMONIC_COM_WATCHDOG=0``; disable just the idle
timeout with ``HARMONIC_COM_OP_TIMEOUT=0``.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable

import _telemetry

# The SolidWorks-health detection primitives (crash-handler scan + hung-window
# probe) live in the lifecycle library, next to start/stop/recover, so any
# consumer shares one definition of "is SolidWorks crashed or hung?". This
# module owns only the telemetry-idle timeout, the fatal exit contract, and the
# OTel abort recording — the harmonic-analyzer-specific glue that can't move.
try:
    from solidworks_mcp.adapters import sw_recovery as _sw_recovery
except Exception:  # noqa: BLE001 - lib is always present in the build venv; degrade safely
    _sw_recovery = None

EXIT_CRASH = 86
EXIT_OP_TIMEOUT = 87
EXIT_MODAL_DIALOG = 88

DEFAULT_OP_TIMEOUT = 900.0
_POLL_INTERVAL = 15.0
_HUNG_WARN_INTERVAL = 300.0
# A modal box must survive this many consecutive polls before it is fatal.
_MODAL_CONFIRM_TICKS = 2
_MODAL_DIALOG_CLASS = "#32770"
_MODAL_DIALOG_TITLE = "SOLIDWORKS Design"
_SPLASH_TITLE = "splash"

# Gate for the process-wide ``start()``: the probes are Win32-only. Module-level
# so the offline gate can monkeypatch it and exercise start/stop off-Windows.
_WINDOWS = os.name == "nt"


def _warn(message: str, **fields: object) -> None:
    """A watchdog SELF-log. ``watchdog_signal=True`` exempts it from the
    activity heartbeat (``_telemetry._ActivityFilter``): the periodic
    hung-window warn must never reset the idle clock it is warning about,
    or a permanently wedged SolidWorks would warn forever and never time out.
    The same field also makes every watchdog record findable in ``logs.jsonl``
    with one filter (``attributes.watchdog_signal``)."""
    _telemetry.warn(message, watchdog_signal=True, **fields)


def _error(message: str, **fields: object) -> None:
    _telemetry.error(message, watchdog_signal=True, **fields)


def _info(message: str, **fields: object) -> None:
    _telemetry.info(message, watchdog_signal=True, **fields)


def _abort(reason: str, message: str, code: int, **fields: object) -> None:
    """Record a fatal watchdog signal on BOTH telemetry channels, then flush.

    The error log (tagged ``watchdog_signal``) is the human-facing line; the
    ``watchdog.abort`` ERROR span makes the abort visible in ``traces.jsonl``
    too -- the watchdog thread has no ambient span context, so without an
    explicit span a fatal exit would leave no trace-side record at all. Both
    carry the same structured attrs (reason / idle_s / last_op / exit code),
    so either channel alone reconstructs what happened."""
    _error(message, reason=reason, exit_code=code, **fields)
    with contextlib.suppress(Exception):
        with _telemetry.span(
            "watchdog.abort", reason=reason, exit_code=code, **fields
        ) as sp:
            sp.set_status(
                _telemetry.Status(_telemetry.StatusCode.ERROR, f"{reason}: {message}")
            )
    _telemetry.shutdown()

# --------------------------------------------------------------------------- #
# SolidWorks-health probes — delegated to the lifecycle library. Each is        #
# best-effort (benign answer on any error / when the lib is unavailable), so a  #
# probe glitch never takes down a healthy build.                                #
# --------------------------------------------------------------------------- #


def _crash_pids() -> set[int]:
    """Pids of SolidWorks' crash-report handler (``sldexitapp.exe``); a NEW one
    means a crash. Delegated to ``sw_recovery.crash_report_pids``."""
    if _sw_recovery is None:
        return set()
    return _sw_recovery.crash_report_pids()


def _sw_window_hung() -> bool:
    """True when a visible ``sldworks.exe`` top-level window fails IsHungAppWindow.
    Delegated to ``sw_recovery.is_sldworks_window_hung``."""
    if _sw_recovery is None:
        return False
    return _sw_recovery.is_sldworks_window_hung()


def _seat_modal_dialog() -> tuple[int, str] | None:
    """``(hwnd, text)`` of a modal message box blocking the SolidWorks seat, or
    ``None``. The hwnd lets the watchdog count consecutive sightings of the SAME
    box (two different transient boxes on consecutive polls are not one
    persistent one).

    Signature (Win32, no UI Automation): a visible ``#32770`` window titled
    exactly "SOLIDWORKS Design", owned by an ``sldworks.exe`` process, whose
    OWNER window is disabled (a modal child is up) and is not the start-up
    ``splash`` (the .NET wedge the lifecycle library recovers at start). The
    crash-report dialog has the same class + title but belongs to
    ``sldexitapp.exe``, so the pid test excludes it. The message text is read
    off the box's ``Static`` children -- a plain MessageBox exposes it there
    (the low-memory box did; a DirectUI body would read as no text, still
    fatal). Best-effort: ``None`` off-Windows, without the lib, or on any error.
    """
    if not _WINDOWS or _sw_recovery is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        sw_pids = _sw_recovery.pids_of_image(_sw_recovery.SW_MAIN_PROCESS)
        if not sw_pids:
            return None
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        enum_fn = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [enum_fn, wintypes.LPARAM]
        user32.EnumChildWindows.argtypes = [wintypes.HWND, enum_fn, wintypes.LPARAM]
        user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetWindow.restype = wintypes.HWND
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowEnabled.argtypes = [wintypes.HWND]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        def text(h) -> str:
            n = user32.GetWindowTextLengthW(h)
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, b, n + 1)
            return b.value

        def klass(h) -> str:
            b = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, b, 256)
            return b.value

        found: list[tuple[int, str]] = []

        @enum_fn
        def on_window(h, _):
            if (
                not user32.IsWindowVisible(h)
                or klass(h) != _MODAL_DIALOG_CLASS
                or text(h) != _MODAL_DIALOG_TITLE
            ):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value not in sw_pids:
                return True
            owner = user32.GetWindow(h, 4)  # GW_OWNER
            if not owner or user32.IsWindowEnabled(owner) or text(owner) == _SPLASH_TITLE:
                return True
            parts: list[str] = []

            @enum_fn
            def on_child(c, _):
                if klass(c) == "Static":
                    t = text(c).strip()
                    if t:
                        parts.append(t)
                return True

            user32.EnumChildWindows(h, on_child, 0)
            found.append((int(h), " ".join(parts) or "(no readable text)"))
            return False

        user32.EnumWindows(on_window, 0)
        return found[0] if found else None
    except Exception:  # noqa: BLE001 - a probe glitch must never take down a healthy build
        return None


# --------------------------------------------------------------------------- #
# The watchdog proper. Probes/clock/exit are injectable so the offline gate    #
# (check:watchdog, test_watchdog.py) drives every branch without SolidWorks.   #
# --------------------------------------------------------------------------- #


class Watchdog:
    def __init__(
        self,
        *,
        op_timeout: float = DEFAULT_OP_TIMEOUT,
        poll_interval: float = _POLL_INTERVAL,
        hung_warn_interval: float = _HUNG_WARN_INTERVAL,
        crash_pids: Callable[[], set[int]] = _crash_pids,
        hung_probe: Callable[[], bool] = _sw_window_hung,
        dialog_probe: Callable[[], tuple[int, str] | None] = _seat_modal_dialog,
        modal_confirm_ticks: int = _MODAL_CONFIRM_TICKS,
        activity: Callable[[], float] = _telemetry.last_activity,
        exit_fn: Callable[[int], None] = os._exit,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.op_timeout = op_timeout
        self.poll_interval = poll_interval
        self.hung_warn_interval = hung_warn_interval
        self._crash_pids = crash_pids
        self._hung_probe = hung_probe
        self._dialog_probe = dialog_probe
        self.modal_confirm_ticks = max(1, int(modal_confirm_ticks))
        self._modal_ticks = 0
        self._modal_hwnd: int | None = None
        self._activity = activity
        self._exit = exit_fn
        self._clock = clock
        self._stop = threading.Event()
        self._last_hung_warn = -float("inf")
        self._hung_since: float | None = None
        # A dialog already up when we start is a leftover from a PREVIOUS crash;
        # the user may be running a healthy new SolidWorks beside it. Baseline
        # those pids so only a NEW sldexitapp is treated as OUR crash.
        self._baseline_crash_pids = set(self._crash_pids())
        if self._baseline_crash_pids:
            _warn(
                "stale SolidWorks crash dialog present at watchdog start "
                f"(sldexitapp pids {sorted(self._baseline_crash_pids)}) -- "
                "ignoring it; only a NEW crash dialog aborts this task"
            )

    def tick(self) -> str | None:
        """One evaluation of all signals. Returns which signal fired (tests)."""
        idle = self._clock() - self._activity()
        last_op = _telemetry.last_activity_op()

        fresh_crash = self._crash_pids() - self._baseline_crash_pids
        if fresh_crash:
            _abort(
                "crash",
                "SolidWorks CRASHED: crash-report handler sldexitapp.exe is "
                f"running (pids {sorted(fresh_crash)}, dialog 'SOLIDWORKS "
                f"Design') -- aborting COM task (exit {EXIT_CRASH}); last "
                f"activity {idle:.0f}s ago: {last_op}",
                EXIT_CRASH,
                pids=str(sorted(fresh_crash)),
                idle_s=round(idle),
                last_op=last_op,
            )
            self._exit(EXIT_CRASH)
            return "crash"

        dialog = self._dialog_probe()
        if dialog is not None:
            hwnd, dialog = dialog
            if hwnd != self._modal_hwnd:
                # a different box than last poll: start its own count
                self._modal_hwnd = hwnd
                self._modal_ticks = 0
            self._modal_ticks += 1
            if self._modal_ticks >= self.modal_confirm_ticks:
                _abort(
                    "modal-dialog",
                    f"SolidWorks MODAL DIALOG is blocking the seat: {dialog!r} -- no "
                    "COM call completes until a human clicks, and SolidWorks' own "
                    "low-memory warning precedes a crash, so the safe recovery is "
                    "kill + relaunch (doit retries the task) -- aborting COM task "
                    f"(exit {EXIT_MODAL_DIALOG}); last activity {idle:.0f}s ago: {last_op}",
                    EXIT_MODAL_DIALOG,
                    dialog_text=dialog,
                    idle_s=round(idle),
                    last_op=last_op,
                )
                self._exit(EXIT_MODAL_DIALOG)
                return "modal-dialog"
            _warn(
                f"SolidWorks modal dialog up: {dialog!r} -- fatal if still up next "
                f"poll ({self._modal_ticks}/{self.modal_confirm_ticks})",
                dialog_text=dialog,
                idle_s=round(idle),
                last_op=last_op,
            )
            return "modal-pending"
        self._modal_ticks = 0
        self._modal_hwnd = None

        if self.op_timeout > 0 and idle > self.op_timeout:
            _abort(
                "op-timeout",
                f"COM operation timed out: no telemetry activity for {idle:.0f}s "
                f"(> HARMONIC_COM_OP_TIMEOUT={self.op_timeout:.0f}s; longest "
                f"healthy single op on record is ~230s) -- SolidWorks is wedged "
                f"inside: {last_op} -- aborting COM task (exit {EXIT_OP_TIMEOUT})",
                EXIT_OP_TIMEOUT,
                idle_s=round(idle),
                timeout_s=round(self.op_timeout),
                last_op=last_op,
            )
            self._exit(EXIT_OP_TIMEOUT)
            return "timeout"

        if self._hung_probe():
            now = self._clock()
            if self._hung_since is None:
                self._hung_since = now
            if now - self._last_hung_warn >= self.hung_warn_interval:
                self._last_hung_warn = now
                _warn(
                    f"SolidWorks window not responding for {now - self._hung_since:.0f}s "
                    f"(idle {idle:.0f}s, in: {last_op}) -- normal while resolving "
                    f"complex geometry; the op timeout aborts at {self.op_timeout:.0f}s",
                    hung_s=round(now - self._hung_since),
                    idle_s=round(idle),
                    last_op=last_op,
                )
            return "hung"

        if self._hung_since is not None:
            # Episode over -- close the loop so a log reader can bound every
            # hung window without inferring it from warn silence.
            _info(
                f"SolidWorks window responsive again after "
                f"{self._clock() - self._hung_since:.0f}s hung",
                hung_s=round(self._clock() - self._hung_since),
            )
            self._hung_since = None
            self._last_hung_warn = -float("inf")
        return None

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_interval):
            with contextlib.suppress(Exception):
                self.tick()

    def start(self) -> None:
        threading.Thread(
            target=self._loop, name="com-watchdog", daemon=True
        ).start()

    def stop(self) -> None:
        self._stop.set()


_active: Watchdog | None = None


def start() -> Watchdog | None:
    """Start the process-wide watchdog (idempotent). Call right before the COM
    session opens (``run_build`` does); ``stop()`` it once the session closes so
    a long SolidWorks-free tail (pure-python post-processing) can't trip the
    idle timeout. Returns ``None`` when disabled (``HARMONIC_COM_WATCHDOG=0``)
    or off-Windows."""
    global _active
    if not _WINDOWS:
        return None
    if os.environ.get("HARMONIC_COM_WATCHDOG", "1").lower() in {"0", "off", "false"}:
        return None
    if _active is not None:
        return _active
    try:
        timeout = float(os.environ.get("HARMONIC_COM_OP_TIMEOUT", DEFAULT_OP_TIMEOUT))
    except ValueError:
        timeout = DEFAULT_OP_TIMEOUT
    # Poll cadence is the detection granularity: an op timeout is only noticed on
    # a tick, so keep poll <= timeout. Env-overridable (mirrors the timeout knob)
    # to drive the crash/recover chain in a live test without a 15 s wait.
    try:
        poll = float(os.environ.get("HARMONIC_COM_POLL_INTERVAL", _POLL_INTERVAL))
    except ValueError:
        poll = _POLL_INTERVAL
    _active = Watchdog(op_timeout=timeout, poll_interval=poll)
    _active.start()
    # One armed line per COM session so any post-hoc read of logs.jsonl can
    # tell whether -- and with what limits -- the session was protected.
    _info(
        f"COM watchdog armed: crash detect (sldexitapp.exe), modal-dialog "
        f"detect ({_active.modal_confirm_ticks} polls), op timeout "
        f"{timeout:.0f}s, poll {_active.poll_interval:.0f}s, hung-window "
        f"warns throttled to {_active.hung_warn_interval:.0f}s",
        timeout_s=round(timeout),
        poll_s=round(_active.poll_interval),
        baseline_crash_pids=str(sorted(_active._baseline_crash_pids)),
    )
    return _active


def stop() -> None:
    global _active
    if _active is not None:
        _active.stop()
        _active = None
