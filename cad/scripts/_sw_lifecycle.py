"""Ensure SolidWorks is up and connector-ready before a COM session.

Thin pipeline-facing wrapper over ``solidworks_mcp.adapters.sw_recovery`` (the
Makers/3DEXPERIENCE start/stop/recover library) that applies this repo's policy
and threads every action through the OpenTelemetry spine (``_telemetry``) instead
of the library's own loguru logs:

    Before a COM subprocess connects, make sure SolidWorks is running and the
    3DEXPERIENCE connector has loaded. Start it when down; recover it when stuck
    on the "Failed to load Microsoft .NET Framework." splash wedge (which never
    becomes COM-attachable, so a build would otherwise just block on
    ``sw.connect``) or otherwise disconnected.

Driven from ``dodo.py``, NOT per COM subprocess:

- ``ensure_ready()`` runs **once per doit worker**, before the first COM task's
  build (inside ``_exec_com``), so SolidWorks is up before any COM work — SW-free
  invocations (``doit list`` / ``check:math``) never reach it, so they never start
  SolidWorks. A no-op fast path when already ``CONNECTED``.
- ``force_recover()`` is the **reactive retry** path: when a COM subprocess fails
  in a SolidWorks way (watchdog crash/op-timeout exit 86/87, or SW no longer
  connected), ``dodo._exec_com`` retries up to 3× with 1/2/4-min backoff, calling
  ``force_recover`` between attempts. Unlike ``ensure_ready`` it does NOT trust
  ``detect_state`` — a crashed SW is a zombie process that still reads
  ``CONNECTED`` — so it always stop→start and first clears the crash handler.

Opt out with ``HARMONIC_SW_AUTOSTART=0`` (hand-manage SolidWorks); tune the
post-launch connect wait with ``HARMONIC_SW_CONNECT_TIMEOUT`` (seconds).

Telemetry: every operation is a ``build-infra`` span (like the COM seat queue and
the artefact cache), so a trace answers "did this build have to start or recover
SolidWorks, and how long did it wait?" in one filter. ``sw.ensure_ready`` carries
``initial_state`` / ``action`` / ``final_state``; ``sw.start`` / ``sw.stop`` /
``sw.wait_connected`` time the sub-steps.
"""

from __future__ import annotations

import os

import _telemetry

_DISABLE_ENV = "HARMONIC_SW_AUTOSTART"
_CONNECT_TIMEOUT_ENV = "HARMONIC_SW_CONNECT_TIMEOUT"
# A COLD 3DEXPERIENCE start is far slower than a warm attach: the connector
# authenticates against the cloud tenant before SolidWorks is COM-attachable.
# 300 s was calibrated on a warm relaunch and is simply too short for a cold one.
# Measured across two crash recoveries mid-fleet-pass (2026-07-28), identically:
#
#   1st force_recover  307 / 309 s -> final_state=starting   (budget ran out)
#   2nd force_recover  110 / 114 s -> connected
#
# So the seat needs ~420 s to become attachable. Each first attempt then released
# a retry that died on the adapter's own 60 s attach window ("running but did not
# become COM-attachable") -- a slot burned on a SolidWorks that could not answer.
# 900 s matches the COM watchdog's op timeout and clears the measured 420 s with
# ~2x headroom.
_DEFAULT_CONNECT_TIMEOUT = 900.0
# Post-recovery grace window, as a fraction of the connect budget -- see
# wait_until_ready. A third of 900 s is 300 s, comfortably more than the ~110 s
# the second force_recover needed in both measured incidents.
_READY_GRACE_FRACTION = 1.0 / 3.0
# The one state value that means "ready to build". Callers compare the state
# force_recover RETURNS against this rather than re-probing via is_connected():
# force_recover returns "error" exactly when detect_state() raised, so a second
# probe would re-raise that failure into the caller and abort the retry path.
CONNECTED_STATE = "connected"
_INFRA = _telemetry.BUILD_INFRA_SERVICE


def _disabled() -> bool:
    return os.environ.get(_DISABLE_ENV, "1").strip().lower() in ("0", "false", "no", "off")


def _connect_timeout() -> float:
    try:
        return float(os.environ.get(_CONNECT_TIMEOUT_ENV, _DEFAULT_CONNECT_TIMEOUT))
    except ValueError:
        return _DEFAULT_CONNECT_TIMEOUT


def ensure_ready() -> str:
    """Bring SolidWorks to a connected state before a COM session.

    Returns the final :class:`SolidWorksState` value (a string). Best-effort: any
    failure is logged and swallowed so the caller still proceeds to
    ``adapter.connect()`` (which has its own attach/launch path and the watchdog
    behind it) rather than turning autostart into a new hard failure mode.
    """
    from solidworks_mcp.adapters import sw_recovery
    from solidworks_mcp.adapters.sw_recovery import SolidWorksState

    if _disabled():
        _telemetry.info("[sw] autostart disabled (HARMONIC_SW_AUTOSTART=0); skipping ensure_ready")
        return sw_recovery.detect_state().value

    with _telemetry.span("sw.ensure_ready", service=_INFRA) as span:
        try:
            state = sw_recovery.detect_state()
            span.set_attribute("initial_state", state.value)
            _telemetry.info(f"[sw] ensure_ready: state={state.value}")

            if state is SolidWorksState.CONNECTED:
                span.set_attribute("action", "none")
                span.set_attribute("final_state", state.value)
                return state.value

            timeout = _connect_timeout()
            if state is SolidWorksState.STARTING:
                span.set_attribute("action", "wait")
                _wait(sw_recovery, timeout)
            elif state is SolidWorksState.NOT_RUNNING:
                span.set_attribute("action", "start")
                _start(sw_recovery, timeout)
            else:  # DOTNET_SPLASH_WEDGE, RUNNING_DISCONNECTED
                span.set_attribute("action", "recover")
                _telemetry.warn(f"[sw] recovering SolidWorks from state={state.value}")
                _recover(sw_recovery, timeout)

            final = sw_recovery.detect_state()
            span.set_attribute("final_state", final.value)
            if final is SolidWorksState.CONNECTED:
                _telemetry.success(f"[sw] ready (state={final.value})")
            else:
                _telemetry.warn(f"[sw] still not connected after ensure_ready (state={final.value})")
            return final.value
        except Exception as exc:  # noqa: BLE001 - autostart must never harden into a new failure
            _telemetry.error(f"[sw] ensure_ready failed ({exc}); proceeding to connect anyway",
                             exc_info=True)
            return "error"


def is_connected() -> bool:
    """True when SolidWorks is running and the connector reports loaded."""
    from solidworks_mcp.adapters import sw_recovery
    from solidworks_mcp.adapters.sw_recovery import SolidWorksState

    return sw_recovery.detect_state() is SolidWorksState.CONNECTED


def force_recover() -> str:
    """Unconditional kill → relaunch → wait-connected for the COM-failure retry path.

    Unlike :func:`ensure_ready`, does NOT trust ``detect_state()`` — a crashed
    SolidWorks is a zombie process that still reads ``CONNECTED`` — so it always
    stop→start, and first clears the crash-report handler (``sldexitapp.exe``) so a
    crashed session's modal can't block the relaunch. Best-effort; returns the final
    state value.
    """
    from solidworks_mcp.adapters import sw_recovery

    timeout = _connect_timeout()
    with _telemetry.span("sw.force_recover", service=_INFRA) as span:
        try:
            _kill_crash_handler()
            with _telemetry.span("sw.stop", service=_INFRA):
                _telemetry.event("sw.stop")
                sw_recovery.stop_solidworks()
            _start(sw_recovery, timeout)
            final = sw_recovery.detect_state().value
            span.set_attribute("final_state", final)
            return final
        except Exception as exc:  # noqa: BLE001 - recovery must not harden into a new failure
            _telemetry.error(f"[sw] force_recover failed ({exc})", exc_info=True)
            return "error"


def wait_until_ready() -> str:
    """Give a still-starting SolidWorks a SHORT grace window, then give up.

    For the retry path after :func:`force_recover` reports anything other than
    connected. Deliberately a fraction of the connect budget, not another full
    one: ``force_recover`` has already waited that budget out, and the measured
    cold start needs ~420 s total, which the 900 s budget covers on its own. This
    is the safety net for a start slower than anything measured -- so a genuinely
    DEAD seat costs one extra grace window per retry, not a second full budget.
    Doubling up would turn a dead seat into ~30 min per retry and ~90 min before
    the build finally fails, which is worse than the wasted retry it prevents.

    Best-effort like the rest of this module -- returns the final state rather
    than raising, because a recovery helper that can itself fail the build
    defeats its own purpose. The caller retries either way.
    """
    from solidworks_mcp.adapters import sw_recovery

    grace = _connect_timeout() * _READY_GRACE_FRACTION
    with _telemetry.span("sw.wait_ready", service=_INFRA) as span:
        span.set_attribute("grace_s", grace)
        try:
            _wait(sw_recovery, grace)
        except Exception as exc:  # noqa: BLE001 - recovery must never fail the build
            _telemetry.warn(f"[sw] wait_until_ready gave up after {grace:.0f}s ({exc})")
        final = _state_value(sw_recovery)
        span.set_attribute("final_state", final)
        return final


def _state_value(sw_recovery) -> str:
    try:
        return str(sw_recovery.detect_state().value)
    except Exception:  # noqa: BLE001 - a state read must not fail the build
        return "unknown"


def _kill_crash_handler() -> None:
    """Best-effort taskkill of ``sldexitapp.exe`` (SolidWorks' crash-report dialog),
    so a crashed session doesn't leave a modal that blocks the relaunch."""
    import subprocess

    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "sldexitapp.exe"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _wait(sw_recovery, timeout: float) -> None:
    with _telemetry.span("sw.wait_connected", service=_INFRA):
        sw_recovery.wait_until_connected(timeout=timeout)


def _start(sw_recovery, timeout: float) -> None:
    with _telemetry.span("sw.start", service=_INFRA):
        _telemetry.event("sw.start", via="connector-launch")
        if sw_recovery.start_solidworks():
            sw_recovery.wait_until_connected(timeout=timeout)


def _recover(sw_recovery, timeout: float) -> None:
    with _telemetry.span("sw.stop", service=_INFRA):
        _telemetry.event("sw.stop")
        sw_recovery.stop_solidworks()
    _start(sw_recovery, timeout)
