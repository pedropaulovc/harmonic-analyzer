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

Called once per COM subprocess from ``_common.run_build`` (so a fully-cached
build, which launches no COM subprocess, never starts SolidWorks). A no-op fast
path when already ``CONNECTED``, so a warm seat pays only a process + registry
probe.

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
_DEFAULT_CONNECT_TIMEOUT = 300.0
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
