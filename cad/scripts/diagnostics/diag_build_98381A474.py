r"""McMaster 98381A474 -- alloy steel dowel pin, 1/8" diameter, 7/8" long.

One of the 98381A* sizes built by the shared recipe in
``diag_mcmaster_dowel.py`` (see its docstring for the catalogue facts).
Used as transgear-latch-pin (MHA-VN-042).  The SKU is [INFERENCE] (the 7/8 in
length of the 1/8 series, not yet read live) and no vendor model is
supplied, so the recipe carries the 98381A473 harvest's end forms and the
standalone run is catalog-only until the vendor check.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98381A474.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_98381a474 import DOWEL_SIZE, ENDS  # noqa: E402
from diagnostics.diag_mcmaster_dowel import build_catalog, build_dowel  # noqa: E402

PART_NO = "98381A474"


@stock_recipe("98381A474", threaded=False)
async def build_98381A474(adapter, truth=None):
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
