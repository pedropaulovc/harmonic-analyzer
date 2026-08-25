"""Build the rocker-support hold-down screw from McMaster 91783A722."""

from __future__ import annotations

import math
import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91783A722 import (
    RH_HEAD_R,
    RH_HH,
    RH_LEN,
    RH_MAJOR_R,
    build_91783A722,
)

PART_NAME = "lag-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_DIA = 2.0 * RH_HEAD_R
HEAD_H = RH_HH
SHANK_DIA = 2.0 * RH_MAJOR_R
SHANK_LEN = RH_LEN


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "91783A722",
                build_91783A722,
                RigidTransform(rotation_radians=(math.pi, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
