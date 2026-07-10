r"""Diagnostic: dump the under-constrained component set of each built assembly.

Read-only seat probe backing ``verify._ALLOWED_FREE_STEMS`` (the exact-set
direction of the free-DOF soundness gate): opens each named assembly, re-solves
once, prints every top-level component that reads under-constrained plus the
collapsed stem set, and closes without saving. Run it after a coupling change
to re-pin an assembly's allowed list.

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\dump_under_constrained.py [name ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _assembly import _under_constrained_components  # noqa: E402
from _common import OUT_SLDASM, check, log, run_build  # noqa: E402

DEFAULT_NAMES = ("drive-train", "magnifier", "paper-drive", "channel",
                 "summing", "pen")


async def build(adapter) -> dict[str, str]:
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(DEFAULT_NAMES)
    out: dict[str, str] = {}
    for name in names:
        sldasm = OUT_SLDASM / f"{name}.SLDASM"
        if not sldasm.exists():
            log(f"{name}: not built -- skipped")
            continue
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
        check(f"open {name}", await adapter.open_model(str(sldasm)))
        under = sorted(_under_constrained_components(adapter))
        stems = sorted({re.sub(r"-\d+$", "", n) for n in under})
        log(f"{name}: {len(under)} under-constrained")
        for n in under:
            log(f"  {n}")
        log(f"{name} stems ({len(stems)}): {stems}")
        out[name] = ", ".join(stems)
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    return out


if __name__ == "__main__":
    sys.exit(run_build(build))
