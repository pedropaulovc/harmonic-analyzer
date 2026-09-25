"""Build the top-down rocker-support screw from its catalog row's SKU.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT. Manufacturing identity remains the catalog contract:
1/4-20 UNC-2A, fully threaded, 18-8 stainless, ASME B18.2.1, at that SKU's
under-head length. The production origin is its under-head bearing plane,
with the visible hex head along +Y and the threaded shank along -Y.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics import diag_build_92240A539, diag_build_92240A540
from diagnostics.diag_build_92240A539 import (
    HEX_HEIGHT_MM,
    HEX_WIDTH_MM,
    MAJOR_DIAMETER_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
)

PART_NAME = "lag-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# The 2026-09-25 machinist review specified the 3/4 screw: the 5/8 engages
# the base 1.456D, under 1.5D. Its replay is staged, but the vendor SLDPRT
# it must match is not harvested, so the catalog row still names the 5/8.
# Flipping that row (with its STOCK_RECIPES entry and yaml) moves this
# part, the frame placement and the base seats together, and
# test_harmonic_base_drawing then demands deleting the base's
# RELEASE_BLOCKER_SHORT_ENGAGEMENT entry.
SPECIFIED_SKU = "92240A540"
REPLAYS = {
    "92240A539": (diag_build_92240A539.LENGTH_MM, diag_build_92240A539.build_92240A539),
    "92240A540": (diag_build_92240A540.LENGTH_MM, diag_build_92240A540.build_92240A540),
}
(SKU,) = SPEC.skus
LENGTH_MM, _REPLAY = REPLAYS[SKU]

HEAD_AF = HEX_WIDTH_MM
HEAD_H = HEX_HEIGHT_MM
SHANK_DIA = MAJOR_DIAMETER_MM
SHANK_LEN = LENGTH_MM
THREAD_LEN = LENGTH_MM
THREAD_SIZE = "1/4-20"
THREAD_CLASS = "2A"
THREAD_PITCH = PITCH_MM
BEARING_OFFSET = WASHER_DEPTH_MM


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(SKU, _REPLAY),),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
