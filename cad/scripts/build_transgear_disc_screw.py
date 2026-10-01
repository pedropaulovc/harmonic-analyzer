r"""Purchased transgear disc screw: McMaster 91794A055, 18-8 stainless (x3).

#0-80 x 1/4 slotted fillister, fully threaded (contract §2.6, ruling 4).
Each screw passes the brass hub's flange clearance hole (MHA-159) and
threads into a #0-80 through tap in the 120T disc (MHA-070).

Geometry source: the vendor-model replica ``diagnostics/diag_build_91794A055``
(replica-gated against the local-only harvest; no .SLDPRT committed).

Frame: axis +Y, head up, the under-head bearing face at y = 0 (Top Plane).
The assembly mates the Top Plane to the flange's front face and the screw
axis (Front Plane ∩ Right Plane) to a flange hole's axis.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91794A055 import build_91794A055
from transgear_disc_screw_spec import SKU

PART_NAME = "transgear-disc-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
if SPEC.skus != (SKU,):
    raise AssertionError(f"{PART_NAME} catalogues {SPEC.skus}, not {SKU}")


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91794A055),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
