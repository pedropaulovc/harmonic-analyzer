"""SolidWorks COM watchdog -- fail loud when the seat process crashes or wedges.

Every COM subprocess (``_common.run_build`` is the single entry) blocks
synchronously inside pywin32 COM calls, so a crashed or hung SolidWorks leaves
the process -- and the machine-global seat it represents -- stuck forever with
no Python-level exception. A daemon thread watches three signals, calibrated
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
codes make the two fatals diagnosable from the doit console alone.

Disable entirely with ``HARMONIC_COM_WATCHDOG=0``; disable just the idle
timeout with ``HARMONIC_COM_OP_TIMEOUT=0``.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.wintypes as wintypes
import os
import threading
import time
from collections.abc import Callable

import _telemetry

EXIT_CRASH = 86
EXIT_OP_TIMEOUT = 87

_CRASH_IMAGE = "sldexitapp.exe"
_SW_IMAGE = "sldworks.exe"

DEFAULT_OP_TIMEOUT = 900.0
_POLL_INTERVAL = 15.0
_HUNG_WARN_INTERVAL = 300.0

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
# Win32 probes (ctypes only -- no psutil dependency). Each is best-effort:    #
# a probe failure must never take down a healthy build, so callers get the    #
# benign answer on any error.                                                 #
# --------------------------------------------------------------------------- #


def _pids_of(image_name: str) -> set[int]:
    """Pids of every running process whose image name matches (case-insensitive)."""
    pids: set[int] = set()
    if os.name != "nt":
        return pids
    with contextlib.suppress(Exception):
        TH32CS_SNAPPROCESS = 0x2

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == wintypes.HANDLE(-1).value:
            return pids
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            wanted = image_name.lower()
            ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() == wanted:
                    pids.add(int(entry.th32ProcessID))
                ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snap)
    return pids


def _crash_pids() -> set[int]:
    return _pids_of(_CRASH_IMAGE)


def _sw_window_hung() -> bool:
    """True when a visible SLDWORKS.exe top-level window fails IsHungAppWindow."""
    if os.name != "nt":
        return False
    try:
        sw_pids = _pids_of(_SW_IMAGE)
        if not sw_pids:
            return False
        user32 = ctypes.windll.user32
        hung = False

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _on_window(hwnd, _lparam):
            nonlocal hung
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in sw_pids and user32.IsHungAppWindow(hwnd):
                hung = True
                return False
            return True

        user32.EnumWindows(_on_window, 0)
        return hung
    except Exception:  # noqa: BLE001 - probe is best-effort, never fatal
        return False


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
        activity: Callable[[], float] = _telemetry.last_activity,
        exit_fn: Callable[[int], None] = os._exit,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.op_timeout = op_timeout
        self.poll_interval = poll_interval
        self.hung_warn_interval = hung_warn_interval
        self._crash_pids = crash_pids
        self._hung_probe = hung_probe
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
    _active = Watchdog(op_timeout=timeout)
    _active.start()
    # One armed line per COM session so any post-hoc read of logs.jsonl can
    # tell whether -- and with what limits -- the session was protected.
    _info(
        f"COM watchdog armed: crash detect (sldexitapp.exe), op timeout "
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
