"""Build the shared thumb screw from unchanged McMaster 91882A221 stock."""

from __future__ import annotations

import math
import sys
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_91882A221 import build_91882A221
from sh_vn_thumb_screw_spec import (
    DIAMETER_REFERENCES,
    DIAMETER_REFERENCE_STARTS,
    HEAD_STACK_LEN,
)

PART_NAME = "sh-vn-thumb-screw"
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
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=DIAMETER_REFERENCES,
            starts=DIAMETER_REFERENCE_STARTS,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
