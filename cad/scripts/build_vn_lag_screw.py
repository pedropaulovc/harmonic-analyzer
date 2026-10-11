"""Build the top-down rocker-support screw from its catalog row's SKU.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT. Manufacturing identity remains the catalog contract:
1/4-20 UNC-2A, fully threaded, 18-8 stainless, ASME B18.2.1, at that SKU's
under-head length. The production origin is its under-head bearing plane,
with the visible hex head along +Y and the threaded shank along -Y.
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_92240A540 import build_92240A540
from vn_lag_screw_spec import SPECIFIED_SKU

PART_NAME = "vn-lag-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

(SKU,) = SPEC.skus
if SKU != SPECIFIED_SKU:
    raise ValueError(
        f"lag-screw catalog row names {SKU}, but vn_lag_screw_spec sizes the frame "
        f"and base seats for {SPECIFIED_SKU}; change both together"
    )


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(SKU, build_92240A540),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
