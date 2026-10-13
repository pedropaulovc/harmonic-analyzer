r"""McMaster 91410A538 -- square-head cup-point set screw, 1/4"-20 x 5/8".

The MHA-VN-023 gooseneck set screw until the 2026-10-12 Q5 ruling moved the
top frame to 91410A540 (the same screw 3/4 in long); this diagnostic stays
as the replica of the harvested vendor part whose law 91410A540 reuses.

Two boss revolves (shank+cup point, then the head), the square cut as a
ThroughAll FeatureCut4 with Flip=True (remove OUTSIDE the 6.35-square --
the head revolve's OD is major_d*sqrt(2) so the square's corners land
exactly on it), 75-deg chamfer cones top+bottom of the head, split at
the junction, tip-seeded ascending helix L+P (13.5 revs, vendor stores
start angle 90 explicitly), the SYMMETRIC 90114A511 cutter law at
tip - 7P/16 in air, sweep scoped to the shank, 60-deg runout frustum at
the junction (re-merges).  Cup point: 45-deg outer chamfer to the rim,
59-deg interior cone (rim radius 1.739789 as solved in Sketch2).
Frame: junction y=0, head +y (vendor origin is the junction too).
The law lives in ``diag_mcmaster_square_set_screw.build_square_set_screw``.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91410A538.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91410a538 import SQUARE_SET_SCREW_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from diagnostics.diag_mcmaster_square_set_screw import (  # noqa: E402
    build_square_set_screw,
)



@stock_recipe("91410A538", threaded=True)
async def build_91410A538(adapter, truth=None):
    """Build the harvested 91410A538 geometry in the vendor coordinate frame."""
    await build_square_set_screw(
        adapter, sku="91410A538", size=SQUARE_SET_SCREW_SIZE
    )


if __name__ == "__main__":
    sys.exit(replica_main("91410A538", build_91410A538))
