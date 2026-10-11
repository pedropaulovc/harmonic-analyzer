r"""McMaster 91794A112 -- #4-40 x 5/8 18-8 stainless fillister screw.

Catalog dimensions come from the McMaster product table (head 0.183 x 0.107,
the 90280A108's head on a 15.875 fully threaded shank). Reuses the existing
90280A* parametric family laws unchanged; the slot, dome, thread/runout and
vendor-frame mapping require the native comparison before release.

Run standalone after harvesting the native reference (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91794A112.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91794a112 import FILLISTER_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


@stock_recipe("91794A112", threaded=True)
async def build_91794A112(adapter, truth=None):
    await build_fillister(adapter, "91794A112", FILLISTER_SIZE)


if __name__ == "__main__":
    sys.exit(replica_main("91794A112", build_91794A112))
