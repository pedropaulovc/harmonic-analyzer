r"""One-off: apply the M6.8 photo-tuning palette to the saved SLDPRTs in
place (the build scripts now set the same colours on rebuild).

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\fix_colors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (  # noqa: E402
    PANEL_BLACK,
    POLISHED_STEEL,
    SPRING_BLACK,
    STAINED_OAK,
    apply_color,
    check,
    run_build,
)

ROOT = Path(__file__).resolve().parents[1]
JOBS = {
    "tube-frame": POLISHED_STEEL,
    "platen": PANEL_BLACK,
    "platen-clip": PANEL_BLACK,
    "knife-mount": PANEL_BLACK,
    "counter-spring": SPRING_BLACK,
    "channel-spring": SPRING_BLACK,
    "channel-spring-installed": SPRING_BLACK,
    "crank-handle": STAINED_OAK,
}


async def build(adapter) -> dict[str, str]:
    results: dict[str, str] = {}
    for stem, rgb in JOBS.items():
        path = ROOT / "out" / "sldprt" / f"{stem}.SLDPRT"
        check(f"open {stem}", await adapter.open_model(str(path)))
        await apply_color(adapter, rgb)
        check(f"save {stem}", await adapter.save_file())
        print(f"  {stem}: {rgb}")
        results[stem] = str(rgb)
    return results


if __name__ == "__main__":
    sys.exit(run_build(build))
