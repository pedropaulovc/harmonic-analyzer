r"""McMaster 92443A077 -- brass slotted binding head screw, #2-56 x 1/4".

Catalogue (``_mcmaster_92443a077``): #2-56 UNC, 1/4 in (6.35) under the head,
binding head Ø0.181 in (4.5974) x 0.05 in (1.27) high, brass, ASME B18.6.3;
read live from the product page and its 2-D drawing on 2026-11-08.

The table gives no crown, slot, undercut or thread-runout sizes, so the head
is the shared slotted-head recipe in ``diag_mcmaster_fillister.py`` at the
binding head's catalogue diameter and height ([INFERENCE]: its band = 0.8 HH
under a spherical crown, slot 0.135 HD wide and 1.5 widths deep from the
apex, the 90280A* thread, tip and runout laws), as for the 92446A077 pan
head.  McMaster's STEP files (threaded SHA-256 8ed25d48...98571da, no-threads
b199cfaa...263592a8) were downloaded for measurement only and are not
committed, so this size has no replica gate; the standalone run is
catalog-only and saves the build under cad/out/reference for inspection.

2026-11-08 (owner ruling, #2144 item 9.2): the MHA-DT-VN-70 keeper-chain
screw clamps the 3603T354 jack chain's end link flat to the MHA-DT-06 crank
arm through the link's eye.

Frame: head UP, under-head junction (bearing face) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92443A077.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_92443a077 import BINDING_HEAD_SIZE, PART_NO  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402


@stock_recipe("92443A077", threaded=True)
async def build_92443A077(adapter, truth=None):
    await build_fillister(adapter, PART_NO, BINDING_HEAD_SIZE)


async def build_catalog(adapter) -> dict[str, str]:
    # The oval family's catalog-only driver is SKU-agnostic.
    from diagnostics.diag_mcmaster_oval import catalog_run

    return await catalog_run(adapter, PART_NO, build_92443A077)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build

    sys.exit(run_build(build_catalog))
