r"""McMaster 91792A108 -- 18-8 stainless slotted pan head screw, #4-40 x 3/8".

Catalogue: the McMaster "Stainless Steel Pan Head Slotted Screws" family
table, read live in a headless browser on 2026-10-11 (``_mcmaster_91792a108``):
#4-40 UNC class 2A, 3/8 in (9.525) under the head, fully threaded, flat tip,
pan head Ø0.219 in (5.5626) x 0.068 in (1.7272) high, 100 ksi, ASME B18.6.3.

The page gives no crown, slot or thread-runout sizes, so the head is the
shared slotted-head recipe in ``diag_mcmaster_fillister.py`` at the pan
head's catalogue diameter and height ([INFERENCE]: its band = 0.8 HH under a
spherical crown, slot 0.135 HD wide and 1.5 widths deep from the apex, the
90280A* thread, tip and runout laws). No vendor model is downloaded or
committed, so this size has no replica gate; the standalone run is
catalog-only and saves the build under cad/out/reference for inspection.

2026-10-11 (R9-31's low head, made slotted): the MHA-PD-VN-60 guide-lock screws
are slotted, as the book's guide-lock plates show (ch22 img05), not hex socket.

Frame: head UP, under-head junction (bearing face) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91792A108.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91792a108 import PAN_HEAD_SIZE, PART_NO  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402


@stock_recipe("91792A108", threaded=True)
async def build_91792A108(adapter, truth=None):
    await build_fillister(adapter, PART_NO, PAN_HEAD_SIZE)


async def build_catalog(adapter) -> dict[str, str]:
    # The oval family's catalog-only driver is SKU-agnostic.
    from diagnostics.diag_mcmaster_oval import catalog_run

    return await catalog_run(adapter, PART_NO, build_91792A108)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build

    sys.exit(run_build(build_catalog))
