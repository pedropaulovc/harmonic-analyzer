r"""McMaster 91790A194 -- 18-8 stainless steel slotted 82 deg oval head screw,
8-32 x 1/2 from the top of the bevel, fully threaded.

Built by the shared 91790A oval recipe in ``diag_mcmaster_oval.py`` (see its
docstring for the live-page facts and the [INFERENCE] head, slot and thread
laws).  No vendor SLDPRT is downloaded or committed, so the standalone run is
catalog-only.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91790A194.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_oval import build_oval, catalog_run  # noqa: E402

PART_NO = "91790A194"


async def build_91790A194(adapter, truth=None):
    await build_oval(adapter, PART_NO)


async def build_catalog(adapter) -> dict[str, str]:
    return await catalog_run(adapter, PART_NO, build_91790A194)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
