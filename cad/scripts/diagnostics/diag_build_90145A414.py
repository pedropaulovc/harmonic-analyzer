r"""McMaster 90145A414 -- 18-8 stainless steel dowel pin, 1/16" diameter, 3/16" long.

Built by the shared 98381A* dowel recipe in ``diag_mcmaster_dowel.py`` (the
geometry is a plain cylinder either way); this SKU's own diameter band is
``_mcmaster_90145a414.DIA_BAND_IN``.  Used as transgear-collar-flat-pin
(MHA-PD-VN-70).  The page states chamfer ends without their size and no
vendor model is tracked, so the recipe is the nominal cylinder, catalogue-only.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90145A414.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_90145a414 import DOWEL_SIZE, ENDS  # noqa: E402
from diagnostics.diag_mcmaster_dowel import build_catalog, build_dowel  # noqa: E402

PART_NO = "90145A414"


@stock_recipe("90145A414", threaded=False)
async def build_90145A414(adapter, truth=None):
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
