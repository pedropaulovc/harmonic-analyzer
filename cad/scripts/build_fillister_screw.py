r"""Purchased brass fillister screw: McMaster 90114A511 in the assembly frame."""

from __future__ import annotations

import sys
from math import pi

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90114A511 import (
    BF_HEAD_R,
    BF_HH,
    BF_LEN,
    BF_MAJOR_R,
    build_90114A511,
)

PART_NAME = "fillister-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#4-40"
HEAD_DIA = 2.0 * BF_HEAD_R
HEAD_H = BF_HH
SHANK_DIA = 2.0 * BF_MAJOR_R
SHANK_LEN = BF_LEN


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90114A511",
                author=build_90114A511,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
