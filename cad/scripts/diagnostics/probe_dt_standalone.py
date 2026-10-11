r"""Throwaway: is dt-drive-train.SLDASM broken ON DISK, or only when flexible?
Open it standalone, rebuild, report What's Wrong with the fixed byref call."""

from __future__ import annotations

import asyncio

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import log
from _com import _flag, _read_member
from _paths import OUT_SLDASM
from _assembly import whats_wrong


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    dt = (OUT_SLDASM / "dt-drive-train.SLDASM").resolve()
    adapter = PyWin32Adapter({})
    await adapter.connect()
    await adapter.open_model(str(dt))
    doc = adapter.currentModel
    _flag(doc, "IModelDoc2")
    log(f"opened {str(_read_member(doc, 'GetTitle'))!r}")
    adapter._attempt(lambda: doc.ForceRebuild3(False))
    ww = whats_wrong(adapter, doc)
    errs = [(n, c) for n, c, w in ww if not w]
    warns = [(n, c) for n, c, w in ww if w]
    log(f"standalone dt-drive-train.SLDASM: {len(errs)} errors, {len(warns)} warnings")
    for n, c in errs[:25]:
        log(f"    ERROR {n!r} code={c}")
    for n, c in warns[:10]:
        log(f"    warn  {n!r} code={c}")
    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
