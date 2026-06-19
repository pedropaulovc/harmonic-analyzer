r"""Throwaway: validate assert_model_healthy / whats_wrong against the live doc."""

from __future__ import annotations

import asyncio

from _common import (
    _flag,
    _read_member,
    log,
)
from _assembly import (
    assert_model_healthy,
    whats_wrong,
)


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")
    log(f"whats_wrong(top) = {whats_wrong(adapter, doc)}")
    try:
        assert_model_healthy(adapter, label="live", deep=True)
        log("assert_model_healthy: PASSED (no raise)")
    except RuntimeError as exc:
        log(f"assert_model_healthy RAISED: {exc}")
    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
