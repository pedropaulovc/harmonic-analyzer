r"""Purchased frame-side screw: McMaster 91794A080 (#2-56 x 7/16) in its stock local frame."""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91794A080 import build_91794A080

PART_NAME = "vn-frame-side-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91794A080",
                author=build_91794A080,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        color=POLISHED_STEEL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
