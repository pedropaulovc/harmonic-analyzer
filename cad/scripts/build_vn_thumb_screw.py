"""Build the magnifier thumb screw from McMaster 91882A221."""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91882A221 import build_91882A221
from _mcmaster_91882a221 import HEAD_STACK_LEN

PART_NAME = "vn-thumb-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material



async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "91882A221",
                build_91882A221,
                RigidTransform(
                    translation_mm=(HEAD_STACK_LEN, 0.0, 0.0),
                    rotation_radians=(0.0, 0.0, math.pi / 2.0),
                ),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
