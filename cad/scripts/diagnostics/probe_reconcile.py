"""Validate reconcile_saved_rebuild_state end-to-end on a real artifact.

Reads NeedsRebuild2 on a fresh open, runs the production reconcile helper,
then INDEPENDENTLY reopens the file and re-reads NeedsRebuild2 to prove the
clean mark PERSISTED to disk (not just to the in-memory doc the helper left
open). Touches only the assembly file -- part md5s are printed before/after
to prove no part was rewritten.

    HARMONIC_COM_SEAT=1 uv run python cad/scripts/diagnostics/probe_reconcile.py frame
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _assembly  # noqa: E402
from _common import _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "cad" / "out" / "sldasm"
PARTS = Path(__file__).resolve().parents[3] / "cad" / "out"


def _nr(model) -> int:
    ext = _read_member(model, "Extension")
    v = _read_member(ext, "NeedsRebuild2")
    return int(v) if v is not None else -999


async def _open(adapter, path):
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.open_model(str(path))
    return _early_bound(adapter.currentModel, "IModelDoc2")


def _child_md5s() -> dict[str, str]:
    return {
        p.name: hashlib.md5(p.read_bytes()).hexdigest()
        for p in sorted((PARTS / "sldprt").glob("*.SLDPRT"))
    }


async def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "frame"
    path = Path(arg) if arg.lower().endswith(".sldasm") else OUT / f"{arg}.SLDASM"
    stem = path.stem

    adapter = PyWin32Adapter({})
    await adapter.connect()

    before_open = await _open(adapter, path)
    print(f"[{stem}] NeedsRebuild2 BEFORE reconcile = {_nr(before_open)}", flush=True)
    parts_before = _child_md5s()

    # Production helper (opens fresh itself, reconciles, leaves doc open).
    await _assembly.reconcile_saved_rebuild_state(adapter, stem, path)

    # Independent fresh reopen -> did the clean mark persist to disk?
    after_open = await _open(adapter, path)
    persisted = _nr(after_open)
    print(f"[{stem}] NeedsRebuild2 AFTER reconcile (independent reopen) = {persisted}"
          f"  {'<-- CLEAN' if persisted == 0 else '(STILL DIRTY)'}", flush=True)

    parts_after = _child_md5s()
    changed = [n for n in parts_before if parts_before[n] != parts_after.get(n)]
    print(f"[{stem}] child .SLDPRT files rewritten by reconcile: {changed or 'NONE'}",
          flush=True)

    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


if __name__ == "__main__":
    asyncio.run(main())
