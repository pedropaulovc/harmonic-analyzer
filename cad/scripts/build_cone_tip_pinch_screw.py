r"""Purchased cone tip pinch screw: McMaster 90280A108 in its stock local frame."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A108 import build_90280A108
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "cone-tip-pinch-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZES["90280A108"]


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
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
