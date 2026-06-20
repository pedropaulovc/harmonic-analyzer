r"""Throwaway: open every .SLDASM and report broken mates / rebuild errors
(the staleness-corruption sweep). Top-level last; deep so a sub's internal
errors surface."""

from __future__ import annotations

import asyncio

from _common import (
    OUT_SLDASM,
    _flag,
    _read_member,
    log,
)
from _assembly import whats_wrong

ORDER = ["frame", "channel", "drive-train", "output", "harmonic-analyzer"]


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True))

    for name in ORDER:
        path = (OUT_SLDASM / f"{name}.SLDASM").resolve()
        if not path.exists():
            log(f"{name}: MISSING")
            continue
        await adapter.open_model(str(path))
        doc = adapter.currentModel
        _flag(doc, "IModelDoc2")
        adapter._attempt(lambda: doc.ForceRebuild3(False))

        targets = [(name, doc)]
        comps = adapter._attempt(lambda: doc.GetComponents(False), default=None) or []
        for c in comps:
            _flag(c, "IComponent2")
            cn = str(_read_member(c, "Name2"))
            if "/" in cn:
                continue
            sub = adapter._attempt(lambda cc=c: cc.GetModelDoc2(), default=None)
            if sub is not None and sub is not doc:
                targets.append((cn, sub))

        errs = []
        for tlabel, m in targets:
            for nm, code, warn in whats_wrong(adapter, m):
                if not warn:
                    errs.append(f"{tlabel}:{nm}[{code}]")
        verdict = "CLEAN" if not errs else f"{len(errs)} ERRORS"
        log(f"=== {name}.SLDASM: {verdict}")
        for e in errs[:15]:
            log(f"      {e}")
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True))

    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
