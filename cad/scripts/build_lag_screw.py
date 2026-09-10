"""Build the top-down rocker-support screw from McMaster 92240A539.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT. Manufacturing identity remains the catalog contract:
1/4-20 UNC-2A, 5/8 in under-head length, fully threaded, 18-8 stainless,
ASME B18.2.1. The production origin is its under-head bearing plane, with
the visible hex head along +Y and the threaded shank along -Y.
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_92240A539 import (
    HEX_HEIGHT_MM,
    HEX_WIDTH_MM,
    LENGTH_MM,
    MAJOR_DIAMETER_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
    build_92240A539,
)

PART_NAME = "lag-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

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
        components=(StockComponent("92240A539", build_92240A539),),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
