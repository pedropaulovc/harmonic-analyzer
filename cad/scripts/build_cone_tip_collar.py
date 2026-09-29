r"""Purchased MHA-096 cone tip stack collar: McMaster 9414T1, black oxide.

User ruling 2026-09-29: a stock set-screw shaft collar on the cone shaft's
D-flat replaces the turned brass tip bushing as MHA-096 (see
``cone_tip_collar_spec`` for the fit-up and every catalogue number).

Geometry source: the catalogue, not a vendor model.  The McMaster product page
for 9414T1 (read in a headless browser on 2026-09-29) gives the 1/16 in bore,
1/4 in OD, 3/16 in width and black-oxide 1215 carbon steel; the vendor STEP,
read locally and never committed, gives the edge breaks and the #2-56 set
screw.  ``diagnostics/diag_build_9414T1.py`` builds them; it has no replica
gate, and no McMaster .SLDPRT is committed or used.

Frame: collar axis +Y, south face at y = 0, north face at y = WIDTH, the set
screw along +X at mid-width.  The bore axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract the drive train keys it by.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_9414T1 import build_9414T1

PART_NAME = "cone-tip-collar"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku="9414T1", author=build_9414T1),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
