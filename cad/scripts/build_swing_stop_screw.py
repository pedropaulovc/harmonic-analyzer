"""Build the swing-stop screw from McMaster 90280A196."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A196 import build_90280A196
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "swing-stop-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA = FILLISTER_SIZES["90280A196"][:4]
EMBED_LEN = 6.0
PROUD_LEN = SHANK_LEN - EMBED_LEN


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "90280A196",
                build_90280A196,
                RigidTransform(translation_mm=(0.0, PROUD_LEN, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
