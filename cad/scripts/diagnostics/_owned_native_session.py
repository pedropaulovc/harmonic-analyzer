"""Attach-only diagnostic runner: native document ownership stays in the probe.

Unlike the build runner, this never clears documents or pins document templates.
The existing adapter disconnect releases COM references without closing documents.
The caller must hold the shared seat and disable automatic launch/recovery.
"""

from __future__ import annotations

import asyncio
import os

import win32com.client

from _common import _early_bound
import _telemetry
import _watchdog


def require_owned_diagnostic_environment():
    """Call before the parent seat/preflight wrapper, not just in its worker."""
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("owned diagnostic requires HARMONIC_SW_AUTOSTART=0")


def attach_running(adapter):
    """Read the existing ROT server only; never launch or write UI preferences."""
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
    _telemetry.info(
        "attached existing SolidWorks without startup or preferences",
        pid=pid,
        revision=revision,
    )


async def connected_probe(adapter, callback):
    _watchdog.start()
    try:
        async with _telemetry.aspan("sw.attach"):
            attach_running(adapter)
        return await callback(adapter)
    finally:
        try:
            async with _telemetry.aspan("sw.disconnect"):
                await adapter.disconnect()
        finally:
            _watchdog.stop()


def run_owned_diagnostic(callback):
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("owned diagnostic requires the coordinated COM seat")
    require_owned_diagnostic_environment()
    try:
        with _telemetry.build_session("owned-native-diagnostic"):
            result = asyncio.run(connected_probe(PyWin32Adapter({}), callback))
            _telemetry.info(f"owned diagnostic result: {result}")
    except Exception as error:
        _telemetry.error(f"owned diagnostic failed: {error}", exc_info=True)
        return 1
    finally:
        _telemetry.shutdown()
    return 0
