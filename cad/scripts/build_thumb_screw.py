"""Build the magnifier thumb screw from McMaster 91882A221."""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91882A221 import build_91882A221
from diagnostics.diag_mcmaster_thumb import THUMB_SPECS

PART_NAME = "thumb-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

_THUMB = THUMB_SPECS["91882A221"]
HEAD_DIA = 2.0 * _THUMB["head_r"]
HEAD_H = _THUMB["head_h"]
HEAD_STACK_LEN = _THUMB["collar_h"] + _THUMB["head_h"]
SHANK_DIA = 2.0 * _THUMB["major_r"]
SHANK_LEN = _THUMB["length"]


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
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
