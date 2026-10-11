"""Build the gooseneck set screw from McMaster 91410A538."""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91410A538 import build_91410A538

PART_NAME = "vn-gooseneck-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material



async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent("91410A538", build_91410A538),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
