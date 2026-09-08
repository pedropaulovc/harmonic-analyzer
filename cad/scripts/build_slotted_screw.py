"""Build the alignment-pinion slotted screw from McMaster 90280A199."""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A199 import build_90280A199
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "slotted-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA = FILLISTER_SIZES["90280A199"][:4]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent("90280A199", build_90280A199),),
        material=MATERIAL,
        color=POLISHED_STEEL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
