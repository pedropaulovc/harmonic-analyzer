"""Build the hanger screw from McMaster 93075A194."""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_93075A194 import (
    HX_HH,
    HX_HW,
    HX_LEN,
    HX_MAJOR_R,
    HX_UNDERSIDE,
    build_93075A194,
)

PART_NAME = "hanger-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_AF = HX_HW
HEAD_H = HX_HH
SHANK_DIA = 2.0 * HX_MAJOR_R
SHANK_LEN = HX_LEN


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "93075A194",
                build_93075A194,
                RigidTransform(
                    translation_mm=(0.0, 0.0, -HX_UNDERSIDE),
                    rotation_radians=(math.pi / 2.0, 0.0, 0.0),
                ),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
