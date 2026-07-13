"""Confirm the fix through the ACTUAL build save path (SaveAs3 Copy|AvoidRebuild).

For each of ForceRebuild3 vs EditRebuild3, save the freshly-loaded assembly via
the same SaveAs3(Silent|Copy|AvoidRebuildOnSave) the build uses, to a temp path,
then reopen and read NeedsRebuild2. Isolates which rebuild persists clean under
the real save options.

    uv run python cad/scripts/diagnostics/probe_editrebuild_saveas.py <abs.SLDASM|stem>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "cad" / "out" / "sldasm"
SAVE_OPTS = 1 | 2 | 8  # Silent | Copy | AvoidRebuildOnSave  (the build's options)


def _nr(model) -> int:
    ext = _read_member(model, "Extension")
    v = _read_member(ext, "NeedsRebuild2")
    return int(v) if v is not None else -999


async def _fresh(adapter, path):
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.open_model(str(path))
    return _early_bound(adapter.currentModel, "IModelDoc2")


async def _trial(adapter, src, rebuild_name):
    model = await _fresh(adapter, src)
    before = _nr(model)
    if rebuild_name == "ForceRebuild3":
        adapter._attempt(lambda: model.ForceRebuild3(False), default=None)
    elif rebuild_name == "EditRebuild3":
        adapter._attempt(lambda: model.EditRebuild3(), default=None)
    else:  # ForceThenEdit: deep rebuild, then EditRebuild3 to set the save mark
        adapter._attempt(lambda: model.ForceRebuild3(False), default=None)
        adapter._attempt(lambda: model.EditRebuild3(), default=None)
    tmp = src.with_name(f"_probe_{rebuild_name}.SLDASM")
    if tmp.exists():
        adapter._attempt(lambda: adapter.swApp.CloseDoc(str(tmp)), default=None)
        tmp.unlink()
    rc = adapter._attempt(lambda: model.SaveAs3(str(tmp), 0, SAVE_OPTS), default=None)
    reopened = await _fresh(adapter, tmp)
    after = _nr(reopened)
    print(f"[{rebuild_name}] open={before} -> SaveAs3(Copy|AvoidRebuild) rc={rc!r} -> reopen={after}"
          + ("   <-- CLEAN" if after == 0 else "   (dirty)"))
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    if tmp.exists():
        tmp.unlink()


async def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "frame"
    src = Path(arg) if arg.lower().endswith(".sldasm") else OUT / f"{arg}.SLDASM"
    adapter = PyWin32Adapter({})
    await adapter.connect()
    await _trial(adapter, src, "ForceRebuild3")
    await _trial(adapter, src, "EditRebuild3")
    await _trial(adapter, src, "ForceThenEdit")


if __name__ == "__main__":
    asyncio.run(main())
