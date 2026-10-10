r"""Purchased foot screw: McMaster 90280A108 with the machine's black finish."""

from __future__ import annotations

import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_90280A108 import build_90280A108

PART_NAME = "vn-foot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90280A108",
                author=build_90280A108,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
