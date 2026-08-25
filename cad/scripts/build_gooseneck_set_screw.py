"""Build the gooseneck set screw from McMaster 91410A538."""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_91410A538 import (
    SQ_HH,
    SQ_LEN,
    SQ_MAJOR_R,
    build_91410A538,
)

PART_NAME = "gooseneck-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_AF = 2.0 * SQ_MAJOR_R
HEAD_H = SQ_HH
SHANK_DIA = 2.0 * SQ_MAJOR_R
SHANK_LEN = SQ_LEN


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent("91410A538", build_91410A538),),
        material=MATERIAL,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
