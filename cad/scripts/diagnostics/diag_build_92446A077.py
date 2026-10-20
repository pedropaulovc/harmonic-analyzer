r"""McMaster 92446A077 -- brass slotted pan head screw, #2-56 x 1/4".

Catalogue (``_mcmaster_92446a077``): #2-56 UNC, 1/4 in (6.35) under the head,
pan head Ø0.167 in (4.2418) x 0.053 in (1.3462) high, brass, ASME B18.6.3;
read live from the product page and its technical drawing on 2026-10-15.

The table gives no crown, slot or thread-runout sizes, so the head is the
shared slotted-head recipe in ``diag_mcmaster_fillister.py`` at the pan
head's catalogue diameter and height ([INFERENCE]: its band = 0.8 HH under a
spherical crown, slot 0.135 HD wide and 1.5 widths deep from the apex, the
90280A* thread, tip and runout laws), as for the 91792A108 pan head.  No
vendor model is downloaded or committed, so this size has no replica gate;
the standalone run is catalog-only and saves the build under
cad/out/reference for inspection.

2026-10-15: the MHA-PD-VN-65 platen-clip screws become this pan head; the
90114A124 fillister's Ø0.124 in least head left 0.05 mm of bearing land
over the clip's largest drilled #2 loose hole.

Frame: head UP, under-head junction (bearing face) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92446A077.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_92446a077 import PAN_HEAD_SIZE, PART_NO  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402


@stock_recipe("92446A077", threaded=True)
async def build_92446A077(adapter, truth=None):
    await build_fillister(adapter, PART_NO, PAN_HEAD_SIZE)


async def build_catalog(adapter) -> dict[str, str]:
    # The oval family's catalog-only driver is SKU-agnostic.
    from diagnostics.diag_mcmaster_oval import catalog_run

    return await catalog_run(adapter, PART_NO, build_92446A077)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build

    sys.exit(run_build(build_catalog))
