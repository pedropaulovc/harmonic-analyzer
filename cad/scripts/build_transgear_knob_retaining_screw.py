r"""Purchased transgear knob retaining screw: McMaster 90283A193, zinc plated.

8-32 x 7/16 slotted pan head, fully threaded, flat tip (contract §1.9).  It
clamps the knob cup (MHA-157) on the knob shaft's (MHA-078) rear end face:
the head seats on the cup's counterbore floor and the shank runs through the
cup's bore into the shaft's #8-32 rear tap.

Geometry source: the live McMaster pages, not a vendor model
(``diagnostics/diag_mcmaster_pan.py``; no replica gate, no .SLDPRT committed).

Frame: axis +Y, head up, the under-head bearing face at y = 0 (Top Plane).
The assembly mates the Top Plane to the cup's ``ScrewSeat`` plane and the
screw axis (Front Plane ∩ Right Plane) to the cup's ``Axis1``.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_90283A193 import build_90283A193
from transgear_knob_retaining_screw_spec import SKU

PART_NAME = "transgear-knob-retaining-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_90283A193),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
