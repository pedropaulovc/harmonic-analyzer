"""Build the pen set screw from McMaster 99607A213."""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from _mcmaster_99607a213 import HEAD_STACK_LEN
from diagnostics.diag_build_99607A213 import build_99607A213

PART_NAME = "vn-pen-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material



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
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Top Plane", "Front Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
