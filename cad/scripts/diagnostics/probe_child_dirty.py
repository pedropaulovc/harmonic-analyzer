"""Mechanism check: does ForceRebuild3(False) dirty the CHILD part documents?

Opens the assembly fresh, reads each unique child doc's GetSaveFlag (dirty =
needs save), then EditRebuild3 -> re-read, then ForceRebuild3(False) -> re-read,
then ForceRebuild3(True) on a fresh open -> re-read. Never saves anything.

    HARMONIC_COM_SEAT=1 uv run python cad/scripts/diagnostics/probe_child_dirty.py <abs.SLDASM|stem>
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


def _children(adapter):
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    comps = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    docs = {}
    for c in comps:
        c = _early_bound(c, "IComponent2")
        child = adapter._attempt(lambda c=c: c.GetModelDoc2(), default=None)
        if child is None:
            continue
        child = _early_bound(child, "IModelDoc2")
        title = adapter._attempt(lambda ch=child: str(ch.GetTitle()), default="?")
        docs[title] = child
    return docs


def _dump(adapter, model, label):
    docs = _children(adapter)
    flags = {t: adapter._attempt(lambda d=d: d.GetSaveFlag(), default="?")
             for t, d in docs.items()}
    dirty = [t for t, f in flags.items() if f is True]
    top_flag = adapter._attempt(lambda: model.GetSaveFlag(), default="?")
    _telemetry.info(f"[{label}] top NeedsRebuild2={_nr(model)} top save_flag={top_flag} "
                    f"child dirty {len(dirty)}/{len(flags)}: {dirty}")


async def _fresh(adapter, path):
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.open_model(str(path))
    return _early_bound(adapter.currentModel, "IModelDoc2")


async def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "frame"
    path = Path(arg) if arg.lower().endswith(".sldasm") else OUT / f"{arg}.SLDASM"
    adapter = PyWin32Adapter({})
    with _telemetry.span("probe.child_dirty", target=str(path), stem=path.stem):
        await adapter.connect()

        model = await _fresh(adapter, path)
        _dump(adapter, model, "open")
        adapter._attempt(lambda: model.EditRebuild3(), default=None)
        _dump(adapter, model, "after EditRebuild3")
        adapter._attempt(lambda: model.ForceRebuild3(False), default=None)
        _dump(adapter, model, "after ForceRebuild3(False)")
        adapter._attempt(lambda: model.EditRebuild3(), default=None)
        _dump(adapter, model, "after Edit (post-force)")

        model = await _fresh(adapter, path)
        _dump(adapter, model, "reopen")
        adapter._attempt(lambda: model.ForceRebuild3(True), default=None)
        _dump(adapter, model, "after ForceRebuild3(True)")
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


if __name__ == "__main__":
    asyncio.run(main())
