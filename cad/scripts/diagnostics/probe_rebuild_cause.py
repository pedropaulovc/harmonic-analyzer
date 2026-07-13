"""Localize WHAT makes a fresh-loaded assembly report NeedsRebuild2=1.

Opens fresh, dumps config count, equations, and each top-level feature's
name/type, and re-checks NeedsRebuild2 after EditRebuild3 (not Force) + a plain
in-place save + reopen — to see whether a normal rebuild+save persists clean.

    uv run python cad/scripts/diagnostics/probe_rebuild_cause.py <abs.SLDASM|stem>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "cad" / "out" / "sldasm"


def _nr(model) -> int:
    ext = _read_member(model, "Extension")
    v = _read_member(ext, "NeedsRebuild2")
    return int(v) if v is not None else -999


async def _fresh(adapter, path):
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.open_model(str(path))
    return _early_bound(adapter.currentModel, "IModelDoc2")


async def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "frame"
    path = Path(arg) if arg.lower().endswith(".sldasm") else OUT / f"{arg}.SLDASM"

    adapter = PyWin32Adapter({})
    with _telemetry.span("probe.rebuild_cause", target=str(path), stem=path.stem):
        await adapter.connect()
        model = await _fresh(adapter, path)
        _telemetry.info(f"[{path.stem}] NeedsRebuild2 on open = {_nr(model)}")

        cfgmgr = _read_member(model, "ConfigurationManager")
        active = _read_member(cfgmgr, "ActiveConfiguration") if cfgmgr else None
        if active is not None:
            active = _early_bound(active, "IConfiguration")
            _telemetry.info(f"[cfg] active={_read_member(active,'Name')!r} "
                            f"NeedsRebuild={_read_member(active,'NeedsRebuild')} "
                            f"AddRebuildSaveMark={_read_member(active,'AddRebuildSaveMark')}")
        names = adapter._attempt(lambda: model.GetConfigurationNames(), default=None)
        _telemetry.info(f"[cfg] configuration names = {names!r}")

        eqmgr = adapter._attempt(lambda: model.GetEquationMgr(), default=None)
        if eqmgr is not None:
            eqmgr = _early_bound(eqmgr, "IEquationMgr")
            n = _read_member(eqmgr, "GetCount")
            _telemetry.info(f"[eq] equation count = {n}")

        # Top-level feature walk: name + type.
        feat = adapter._attempt(lambda: model.FirstFeature(), default=None)
        i = 0
        while feat is not None and i < 60:
            feat = _early_bound(feat, "IFeature")
            nm = _read_member(feat, "Name")
            tp = adapter._attempt(lambda f=feat: f.GetTypeName2(), default="?")
            _telemetry.info(f"[feat] {i:2d} {tp:<22} {nm}")
            feat = adapter._attempt(lambda f=feat: f.GetNextFeature(), default=None)
            i += 1

        # Normal EditRebuild3 + plain in-place save, then reopen.
        m2 = _early_bound(adapter.currentModel, "IModelDoc2")
        _telemetry.info(f"[fix] EditRebuild3 = {adapter._attempt(lambda: m2.EditRebuild3(), default=None)!r} "
                        f"-> in-mem NeedsRebuild2 = {_nr(m2)}")
        _telemetry.info(f"[fix] Save3(Silent) = {adapter._attempt(lambda: m2.Save3(1,0,0), default=None)!r}")
        m3 = await _fresh(adapter, path)
        _telemetry.info(f"[fix] AFTER EditRebuild3+save, reopen NeedsRebuild2 = {_nr(m3)}")


if __name__ == "__main__":
    asyncio.run(main())
