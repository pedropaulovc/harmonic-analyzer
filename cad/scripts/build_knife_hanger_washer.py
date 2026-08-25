r"""Purchased knife-hanger washer: McMaster 90126A211."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90126A211 import W_ID, W_OD, W_T, build_90126A211

PART_NAME = "knife-hanger-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

OUTER_DIA = W_OD
INNER_DIA = W_ID
THICKNESS = W_T


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90126A211",
                author=build_90126A211,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
