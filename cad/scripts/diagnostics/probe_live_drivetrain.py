r"""Throwaway: attach to the LIVE corrupted session (Assem102 in the screenshot,
drive-train<1> red X) and find the actual culprit. Also dumps the raw
GetWhatsWrong return so we parse its shape correctly.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_live_drivetrain.py
"""

from __future__ import annotations

import asyncio

import _telemetry
from _common import _flag, _read_member, log


def _dump_whats_wrong(adapter, model, label):
    ext = _read_member(model, "Extension")
    res = adapter._attempt(lambda: ext.GetWhatsWrong(), default="<call raised>")
    log(f"  [{label}] GetWhatsWrong raw type={type(res).__name__} repr={res!r:.300}")


def _comps(adapter, doc):
    return adapter._attempt(lambda: doc.GetComponents(False), default=None) or []


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

    _dump_whats_wrong(adapter, doc, "top")

    for c in _comps(adapter, doc):
        _flag(c, "IComponent2")
        n = str(_read_member(c, "Name2"))
        if "/" in n:
            continue  # top-level instances only
        # IComponent2 state: GetSuppression2, IsSuppressed, error via GetModelDoc2
        supp = _read_member(c, "GetSuppression2")
        solving = _read_member(c, "Solving")  # 0 rigid, 1 flexible
        sub = adapter._attempt(lambda cc=c: cc.GetModelDoc2(), default=None)
        log(f"\n=== component {n!r} suppression={supp} solving={solving} ===")
        if sub is None:
            log("    GetModelDoc2 -> None")
            continue
        _flag(sub, "IModelDoc2")
        _dump_whats_wrong(adapter, sub, f"{n} internal")

        # Walk the sub's features + mates for per-feature error codes.
        bad = []
        feat = _read_member(sub, "FirstFeature")
        for _ in range(20000):
            if not feat:
                break
            _flag(feat, "IFeature")
            ec = adapter._attempt(lambda f=feat: f.GetErrorCode2(0), default=None)
            code = ec[0] if isinstance(ec, (list, tuple)) else ec
            if code not in (None, 0):
                bad.append((str(_read_member(feat, "Name")),
                            str(_read_member(feat, "GetTypeName2")), code))
            # descend into MateGroup sub-features
            if str(_read_member(feat, "GetTypeName2")) == "MateGroup":
                sf = _read_member(feat, "GetFirstSubFeature")
                for _ in range(20000):
                    if not sf:
                        break
                    _flag(sf, "IFeature")
                    ec = adapter._attempt(lambda f=sf: f.GetErrorCode2(0), default=None)
                    code = ec[0] if isinstance(ec, (list, tuple)) else ec
                    if code not in (None, 0):
                        bad.append((str(_read_member(sf, "Name")),
                                    str(_read_member(sf, "GetTypeName2")), code))
                    sf = _read_member(sf, "GetNextSubFeature")
            feat = _read_member(feat, "GetNextFeature")
        if bad:
            log(f"    {len(bad)} feature(s) with error codes:")
            for name, tn, code in bad[:40]:
                log(f"        [{code}] {name!r} ({tn})")
        else:
            log("    no per-feature error codes found")

    await adapter.disconnect()
    _telemetry.info("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
