"""Attach-only diagnostics with first-cause-preserving teardown.

Native document ownership stays in the probe. No startup, document cleanup,
preferences, or UserControl writes occur here.
A process hard exit/native crash cannot guarantee Python finally or reporting.
"""

from __future__ import annotations

import asyncio
import os

import win32com.client

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _com import _early_bound
import _telemetry
import _watchdog


def require_owned_diagnostic_environment():
    """Call before the parent seat/preflight wrapper, not just in its worker."""
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("owned diagnostic requires HARMONIC_SW_AUTOSTART=0")


def attach_running(adapter):
    """Bind the existing ROT server, without startup or native state changes."""
    adapter._initialize_com_apartment()
    app = _early_bound(
        win32com.client.GetActiveObject("SldWorks.Application"), "ISldWorks"
    )
    adapter.swApp = app
    pid, revision = int(app.GetProcessID()), str(app.RevisionNumber())
    if pid <= 0 or not revision:
        raise RuntimeError("running SolidWorks returned an invalid readiness witness")
    expected = os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID")
    if expected is not None and pid != int(expected):
        raise RuntimeError(
            f"attached SolidWorks PID {pid} differs from expected {expected}"
        )
    return pid, revision


async def connected_probe(adapter, callback, *, failures=None):
    """Return the callback result or raise the first actual failure after teardown.

    Optional failures is an append-only list of (phase, exception, original_tb).
    Observer failures never skip disconnect/stop or replace an earlier cause.
    """
    if failures is None:
        failures = []
    first = len(failures)
    result = None
    try:
        try:
            _watchdog.start()
        except BaseException as error:
            failures.append(("watchdog.start", error, error.__traceback__))
        if len(failures) == first:
            span = None
            entered = False
            try:
                span = _telemetry.aspan("sw.attach")
                await span.__aenter__()
                entered = True
            except BaseException as error:
                failures.append(("attach.span.enter", error, error.__traceback__))
            if len(failures) == first:
                try:
                    pid, revision = attach_running(adapter)
                except BaseException as error:
                    failures.append(("attach", error, error.__traceback__))
                else:
                    try:
                        _telemetry.info(
                            "attached existing SolidWorks without startup or preferences",
                            pid=pid,
                            revision=revision,
                        )
                    except BaseException as error:
                        failures.append(("attach.observer", error, error.__traceback__))
            if entered:
                try:
                    # The original cause is already retained; do not give an
                    # observer the opportunity to suppress or replace it.
                    await span.__aexit__(None, None, None)
                except BaseException as error:
                    failures.append(("attach.span.exit", error, error.__traceback__))
            if len(failures) == first:
                try:
                    result = await callback(adapter)
                except BaseException as error:
                    failures.append(("body", error, error.__traceback__))
    finally:
        span = None
        entered = False
        try:
            span = _telemetry.aspan("sw.disconnect")
            await span.__aenter__()
            entered = True
        except BaseException as error:
            failures.append(("disconnect.span.enter", error, error.__traceback__))
        # Disconnect must run even when its observer cannot enter a span.
        try:
            await adapter.disconnect()
        except BaseException as error:
            failures.append(("disconnect", error, error.__traceback__))
        if entered:
            try:
                await span.__aexit__(None, None, None)
            except BaseException as error:
                failures.append(("disconnect.span.exit", error, error.__traceback__))
        try:
            _watchdog.stop()
        except BaseException as error:
            failures.append(("watchdog.stop", error, error.__traceback__))
    if len(failures) != first:
        _, error, original_tb = failures[first]
        raise error.with_traceback(original_tb)
    return result


def run_owned_diagnostic(callback, *, failures=None):
    """Existing integer exit API; optional failures exposes actual causes/tbs.

    Existing callers need no migration. A caller needing forensic provenance
    supplies the list rather than fabricating a cause from a return code.
    """
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("owned diagnostic requires the coordinated COM seat")
    require_owned_diagnostic_environment()
    if failures is None:
        failures = []
    first = len(failures)
    try:
        try:
            with _telemetry.build_session("owned-native-diagnostic"):
                try:
                    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter
                    asyncio.run(
                        connected_probe(PyWin32Adapter({}), callback, failures=failures)
                    )
                except BaseException as error:
                    # connected_probe has already retained its original traceback;
                    # only constructor/import/event-loop failures need adding here.
                    if not any(saved is error for _, saved, _ in failures[first:]):
                        failures.append(("runner", error, error.__traceback__))
                try:
                    if len(failures) == first:
                        _telemetry.info("owned diagnostic completed")
                    else:
                        _, error, original_tb = failures[first]
                        _telemetry.error(
                            "owned diagnostic failed; original cause retained",
                            exc_info=(type(error), error, original_tb),
                        )
                except BaseException as error:
                    failures.append(("runner.observer", error, error.__traceback__))
        except BaseException as error:
            # Body failures were caught BEFORE leaving the context manager.
            failures.append(("build_session", error, error.__traceback__))
    finally:
        try:
            _telemetry.shutdown()
        except BaseException as error:
            failures.append(("telemetry.shutdown", error, error.__traceback__))
    return 1 if len(failures) != first else 0
