"""Localize WHAT in a freshly-loaded assembly reports needs-rebuild.

Opens the saved .SLDASM fresh (CloseAllDocuments first), confirms
NeedsRebuild2=1, then enumerates top-level components and their child docs to
find which one carries the dirty flag / What's Wrong entry — pointing at the
specific build step the migration changed.

    uv run python cad/scripts/diagnostics/probe_saved_rebuild.py frame
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "cad" / "out" / "sldasm"


def _needs_rebuild(model) -> int:
    ext = _read_member(model, "Extension")
    v = _read_member(ext, "NeedsRebuild2")
    return int(v) if v is not None else -999


async def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "frame"
    # Accept either a stem (resolved under this repo's OUT) or an absolute path,
    # so the same probe can point at another worktree's artifact.
    path = Path(arg) if arg.lower().endswith(".sldasm") else OUT / f"{arg}.SLDASM"
    stem = path.stem

    adapter = PyWin32Adapter({})
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.open_model(str(path))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    print(f"[{stem}] assembly NeedsRebuild2 = {_needs_rebuild(model)}")

    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    comps = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    print(f"[{stem}] {len(comps)} top-level components")
    dirty = []
    for c in comps:
        c = _early_bound(c, "IComponent2")
        name = _read_member(c, "Name2")
        child = adapter._attempt(lambda c=c: c.GetModelDoc2(), default=None)
        cs = adapter._attempt(lambda c=c: c.GetConstrainedStatus(), default=None)
        nr = None
        if child is not None:
            child = _early_bound(child, "IModelDoc2")
            nr = _needs_rebuild(child)
        flag = ""
        if nr not in (0, None, -999):
            flag = f"  <-- child NeedsRebuild2={nr}"
            dirty.append(name)
        print(f"   {name!s:<34} constrained={cs} child_rebuild={nr}{flag}")
    print(f"[{stem}] components whose CHILD doc loads dirty: {dirty or 'none'}")

    # What's Wrong on the top assembly (features with faults/rebuild marks).
    ext = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    ww = adapter._attempt(lambda: ext.GetWhatsWrong(), default=None)
    print(f"[{stem}] GetWhatsWrong raw = {ww!r}")


if __name__ == "__main__":
    asyncio.run(main())
