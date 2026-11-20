r"""McMaster 91794A559 -- 1/4-28 x 3/4 18-8 stainless fillister screw.

Catalog dimensions come from the McMaster product table (head 0.414 x 0.237
on a 19.05 fully threaded 1/4-28 shank, ``_mcmaster_91794a559``). Reuses the
existing 90280A* parametric family laws unchanged, as 91794A112 does; the
slot, dome, thread/runout and vendor-frame mapping require the native
comparison before release.

Run standalone after harvesting the native reference (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91794A559.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91794a559 import FILLISTER_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


@stock_recipe("91794A559", threaded=True)
def build_91794A559(adapter, truth=None):
    build_fillister(adapter, "91794A559", FILLISTER_SIZE)


if __name__ == "__main__":
    sys.exit(replica_main("91794A559", build_91794A559))
