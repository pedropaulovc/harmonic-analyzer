r"""One-off: body-level colour for the Oak-material parts.

apply_material("Oak") attaches the polished-oak TEXTURE appearance at
part scope; doc MPV only retints its primary colour, so the wood image
kept rendering over the overrides (paper showed oak grain, the handle
washed out pale). Body appearances outrank part appearances, so
re-applying through the upgraded _common.apply_color (doc + body MPV)
fixes the saved SLDPRTs without a rebuild.

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\fix_body_colors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (  # noqa: E402
    PAPER_WHITE,
    STAINED_OAK,
    apply_color,
    check,
    run_build,
)

import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

FIXES = {
    "platen-paper": PAPER_WHITE,
    "crank-handle": STAINED_OAK,
}


async def build(adapter) -> dict[str, str]:
    for part, rgb in FIXES.items():
        path = ROOT / "out" / "sldprt" / f"{part}.SLDPRT"
        check(f"open {part}", await adapter.open_model(str(path)))
        await apply_color(adapter, rgb)
        check(f"save {part}", await adapter.save_file())
        _telemetry.info(f"{part}: body colour {rgb}")
    return {"diag": "done"}


if __name__ == "__main__":
    sys.exit(run_build(build))
