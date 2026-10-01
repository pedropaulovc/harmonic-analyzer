r"""Purchased transgear pivot screw: McMaster 91829A205, 18-8 stainless.

Slotted precision shoulder screw, shoulder Ø3/16 x 1/2, 8-32 x 3/16
(contract §3.5).  The hanger arm (MHA-164) swings on its shoulder: the head
sits in the arm's rear spot face, the shoulder runs through the arm and the
pivot spacer (MHA-167), and the shoulder end bears on the support bar's
(MHA-074) back face with the thread in the bar's blind #8-32 tap.

Geometry source: the live McMaster page, not a vendor model
(``diagnostics/diag_build_91829A205.py``; no replica gate, no .SLDPRT
committed).

Frame: axis +Y, head up, the under-head shoulder face at y = 0 (Top Plane).
The assembly mates the screw axis (``ScrewAxis``, Front Plane ∩ Right Plane)
to the arm's pivot bore axis and the Top Plane to the arm's spot-face floor
plus the head play.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91829A205 import build_91829A205
from transgear_pivot_screw_spec import SKU

PART_NAME = "transgear-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91829A205),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
