"""Build the pen set screw from McMaster 99607A213."""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_99607A213 import (
    TS_HEAD_H,
    TS_HEAD_R,
    TS_LEN,
    TS_MAJOR_R,
    TS_PITCH,
    TS_SH_H,
    build_99607A213,
)

PART_NAME = "pen-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_DIA = 2.0 * TS_HEAD_R
HEAD_H = TS_HEAD_H
HEAD_STACK_LEN = TS_SH_H + TS_HEAD_H
SHANK_DIA = 2.0 * TS_MAJOR_R
SHANK_LEN = TS_LEN
TIP_CHAMFER = TS_PITCH * 0.75


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "99607A213",
                build_99607A213,
                RigidTransform(
                    translation_mm=(HEAD_STACK_LEN, 0.0, 0.0),
                    rotation_radians=(0.0, 0.0, math.pi / 2.0),
                ),
            ),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Front Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
