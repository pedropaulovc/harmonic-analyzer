"""Purchased McMaster 9275K141 cap, opening at Y=0 and top toward +Y."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_9275K141 import build_9275K141

PART_NAME = "tube-frame-cap"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku="9275K141", author=build_9275K141),),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
