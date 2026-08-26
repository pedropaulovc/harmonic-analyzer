r"""Purchased cone pivot screw: McMaster 91829A560 in its stock local frame."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _holes import TAP_DRILL_MM
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91829A560 import (
    HEAD_DIA,
    HEAD_T,
    SHOULDER_DIA,
    SHOULDER_LEN,
    THREAD_LEN,
    THREAD_MAJOR,
    UNDERHEAD_LEN,
    build_91829A560,
)

PART_NAME = "cone-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#10-24"
HEAD_H = HEAD_T
THREAD_TAIL_LEN = THREAD_LEN
THREAD_SOLID_DIA = THREAD_MAJOR
THREAD_TAP_DRILL_DIA = TAP_DRILL_MM[THREAD]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91829A560",
                author=build_91829A560,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
