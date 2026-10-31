r"""McMaster 98381A542 -- alloy steel dowel pin, 1/4" diameter, 1" long.

One of the 98381A* sizes built by the shared recipe in
``diag_mcmaster_dowel.py`` (see its docstring for the catalogue facts).
Used as the oblique-trammel CL locator dowel (MHA-CH-06-TL-VN-53).  Its end
forms are read off McMaster's STEP (``_mcmaster_98381a542``, whose docstring
carries the source and the numbers), for dimensions only: the model is not
replica-gated and the standalone run is catalog-only.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98381A542.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_98381a542 import DOWEL_SIZE, ENDS  # noqa: E402
from diagnostics.diag_mcmaster_dowel import build_catalog, build_dowel  # noqa: E402

PART_NO = "98381A542"


@stock_recipe("98381A542", threaded=False)
async def build_98381A542(adapter, truth=None):
    await build_dowel(adapter, PART_NO, DOWEL_SIZE, ENDS)


async def _catalog(adapter) -> dict[str, str]:
    return await build_catalog(adapter, PART_NO, DOWEL_SIZE, ENDS)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build

    sys.exit(run_build(_catalog))
