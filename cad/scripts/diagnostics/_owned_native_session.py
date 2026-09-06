"""Connect-only diagnostic runner: native document ownership stays in the probe.

Unlike the build runner, this never clears documents or pins document templates.
The existing adapter disconnect releases COM references without closing documents.
The caller must hold the shared seat and disable automatic launch/recovery.
"""

from __future__ import annotations

import asyncio
import os

import _telemetry
import _watchdog


async def connected_probe(adapter, callback):
    _watchdog.start()
    try:
        await adapter.connect()
        return await callback(adapter)
    finally:
        try:
            await adapter.disconnect()
        finally:
            _watchdog.stop()


def run_owned_diagnostic(callback):
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("owned diagnostic requires the coordinated COM seat")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("owned diagnostic requires HARMONIC_SW_AUTOSTART=0")
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
