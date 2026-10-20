"""Build purchased ch-rocker-arm-tl-vn-oblique-pivot-lock-wire, native stock recipe; see its pure spec for frame."""
from __future__ import annotations

import sys
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec import SKU
from diagnostics.diag_build_05_02685 import build_05_02685

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-lock-wire"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_05_02685),),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
