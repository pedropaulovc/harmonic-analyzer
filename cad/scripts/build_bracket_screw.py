r"""Purchased bracket screw: McMaster 90280A194 in the assembly local frame."""

from __future__ import annotations

import sys
from math import pi

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A194 import build_90280A194
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "bracket-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZES["90280A194"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90280A194",
                author=build_90280A194,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
