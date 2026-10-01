r"""McMaster 90283A193 -- zinc-plated steel slotted pan head screw, 8-32 x 7/16.

Built by the shared 90283A pan recipe in ``diag_mcmaster_pan.py`` (see its
docstring for the live-page facts and the [INFERENCE] head laws).  No vendor
SLDPRT is downloaded or committed, so the standalone run is catalog-only.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90283A193.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_pan import build_pan, catalog_run  # noqa: E402

PART_NO = "90283A193"


async def build_90283A193(adapter, truth=None):
    await build_pan(adapter, PART_NO)


async def build_catalog(adapter) -> dict[str, str]:
    return await catalog_run(adapter, PART_NO, build_90283A193)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
