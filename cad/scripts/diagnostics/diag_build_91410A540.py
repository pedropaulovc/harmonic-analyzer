r"""McMaster 91410A540 -- square-head cup-point set screw, 1/4"-20 x 3/4".

MHA-VN-023, the gooseneck set screw in the top frame's hub boss since the
2026-10-12 Q5 ruling. McMaster's family row (read live 2026-10-12) lists
every field of 91410A538 but the length: 1/4"-20 UNC-2A, 1/4" square head
3/16" high, cup point, ASME B18.6.2. So this replay is the 91410A538 family
law (``diag_mcmaster_square_set_screw.build_square_set_screw``) at 19.05 mm;
the helix spans L+P (16 revs). No vendor SLDPRT has been harvested for this
length (the download needs a McMaster login), so there is no replica gate yet.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91410A540.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91410a540 import SQUARE_SET_SCREW_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from diagnostics.diag_mcmaster_square_set_screw import (  # noqa: E402
    build_square_set_screw,
)



@stock_recipe("91410A540", threaded=True)
async def build_91410A540(adapter, truth=None):
    """Build 91410A540 by the 91410A538 family law at its 3/4-in length."""
    await build_square_set_screw(
        adapter, sku="91410A540", size=SQUARE_SET_SCREW_SIZE
    )


if __name__ == "__main__":
    sys.exit(replica_main("91410A540", build_91410A540))
