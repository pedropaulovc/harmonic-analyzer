"""Build the swing-stop screw from shared McMaster 90280A108 stock.

The stop only limits the disengaged swing; it plays no part in meshing.
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_90280A108 import build_90280A108
from vn_swing_stop_screw_spec import PROUD_LEN

PART_NAME = "vn-swing-stop-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "90280A108",
                build_90280A108,
                RigidTransform(translation_mm=(0.0, PROUD_LEN, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
