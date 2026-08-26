"""Build the hold-down hex bolt from McMaster 92865A585."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_92865A585 import (
    G5_HH,
    G5_HW,
    G5_LEN,
    G5_MAJOR_R,
    G5_UNDERSIDE,
    build_92865A585,
)

PART_NAME = "hex-bolt"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_AF = G5_HW
HEAD_H = G5_HH
SHANK_DIA = 2.0 * G5_MAJOR_R
SHANK_LEN = G5_LEN


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "92865A585",
                build_92865A585,
                RigidTransform(translation_mm=(0.0, -G5_UNDERSIDE, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
