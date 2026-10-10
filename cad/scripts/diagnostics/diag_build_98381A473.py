r"""McMaster 98381A473 -- alloy steel dowel pin, 1/8" diameter, 3/4" long.

One of the 98381A* sizes built by the shared recipe in
``diag_mcmaster_dowel.py`` (see its docstring for the catalogue facts).
Used as knife-mount-dowel (MHA-VN-051).  Unlike 98381A433/434 this size has a
user-supplied vendor model, so the recipe carries its end forms (chamfer and
round, read off the harvest) and the standalone run is the replica gate
against ``cad/out/reports/mcmaster-98381A473-dump.json``.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98381A473.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_98381a473 import DOWEL_SIZE, ENDS  # noqa: E402
from diagnostics.diag_mcmaster_dowel import build_dowel  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402

PART_NO = "98381A473"


@stock_recipe("98381A473", threaded=False)
async def build_98381A473(adapter, truth=None):
    await build_dowel(adapter, PART_NO, DOWEL_SIZE, ENDS)


if __name__ == "__main__":
    sys.exit(replica_main(PART_NO, build_98381A473))
