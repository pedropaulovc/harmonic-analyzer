"""Build the raised pinion-block hold-down screw from McMaster 90280A203.

The #8-32 x 1-1/2 stock length preserves full thread engagement through
the raised block. Its shared-family head envelope is unchanged.
"""

from __future__ import annotations

import sys

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_90280A203 import build_90280A203

PART_NAME = "vn-slotted-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent("90280A203", build_90280A203),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        color=POLISHED_STEEL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
