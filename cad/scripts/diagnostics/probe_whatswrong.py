r"""Throwaway: find the correct pywin32 invocation of GetWhatsWrong (3 out
object params need VT_BYREF|VT_VARIANT byrefs; bare call raises). Validate
against the live ActiveDoc.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_whatswrong.py

LATE-BOUND PROBE: this script drives SolidWorks through its own
``GetObject``/``Dispatch`` (or a raw ``adapter.currentModel``), NOT the makepy
wrapper, so its ``[out]`` params land in the ``VT_BYREF`` VARIANTs passed in
rather than in the return tuple. That is the OPPOSITE of the build path, where
``_common._early_bound`` guarantees an early-bound object and the outs ride the
return tuple. Both are correct for their binding -- mixing them is the trap that
reads as "no data" instead of failing. See memory/sw-assembly-mate-diagnostics-api.md.
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, log


def _byref_variant():
    import pythoncom
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)


def _whats_wrong(adapter, model):
    ext = _read_member(model, "Extension")
    f = _byref_variant()
    e = _byref_variant()
    w = _byref_variant()

    def _call():
        ret = ext.GetWhatsWrong(f, e, w)
        return ret, f.value, e.value, w.value

    res = adapter._attempt(_call, default="<raised>")
    return res


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting (ATTACH) ...")
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    res = _whats_wrong(adapter, doc)
    log(f"top GetWhatsWrong (byref) -> {res!r:.400}")

    await adapter.disconnect()
    _telemetry.info("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
