r"""McMaster 94025A150 cup-point adjuster; its conical apex is the thrust contact."""

from __future__ import annotations

import sys
from math import pi

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_94025A150 import (
    SS_CONE_Y,
    SS_HALF,
    SS_LEN,
    SS_MAJOR_R,
    SS_TIP_R,
    build_94025A150,
)

PART_NAME = "cone-tip-adjuster"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "5/16-18"
BODY_DIA = 2.0 * SS_MAJOR_R
BODY_LEN = SS_LEN
CUP_DIA = 2.0 * SS_TIP_R
CUP_DEPTH = SS_HALF - SS_CONE_Y


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="94025A150",
                author=build_94025A150,
                transform=RigidTransform(
                    translation_mm=(0.0, SS_HALF, 0.0),
                    rotation_radians=(pi, 0.0, 0.0),
                ),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
