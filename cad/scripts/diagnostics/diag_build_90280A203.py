r"""McMaster 90280A203 -- #8-32 x 1-1/2 steel fillister head slotted screw.

Live catalogue dimensions verified 2026-10-08; the shared fillister recipe
retains its existing family head/slot/thread modelling conventions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_90280a203 import FILLISTER_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


@stock_recipe("90280A203", threaded=True)
async def build_90280A203(adapter, truth=None):
    await build_fillister(adapter, "90280A203", FILLISTER_SIZE)


if __name__ == "__main__":
    sys.exit(replica_main("90280A203", build_90280A203))
