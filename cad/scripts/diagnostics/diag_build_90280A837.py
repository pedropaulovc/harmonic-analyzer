r"""McMaster 90280A837 -- #10-32 x 1-3/4 steel narrow fillister screw.

Catalog dimensions come from the supplied 90280A837.pdf. Reuses the existing
90280A* parametric family laws unchanged; the slot, dome, thread/runout and
vendor-frame mapping require the native comparison before release.

Run standalone after harvesting the native reference (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90280A837.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_90280a837 import FILLISTER_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


@stock_recipe("90280A837", threaded=True)
async def build_90280A837(adapter, truth=None):
    await build_fillister(adapter, "90280A837", FILLISTER_SIZE)


if __name__ == "__main__":
    sys.exit(replica_main("90280A837", build_90280A837))
