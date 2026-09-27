"""Build the swing-stop screw from shared McMaster 90280A199 stock."""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A199 import build_90280A199
from swing_stop_screw_spec import PROUD_LEN

PART_NAME = "swing-stop-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "90280A199",
                build_90280A199,
                RigidTransform(translation_mm=(0.0, PROUD_LEN, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
