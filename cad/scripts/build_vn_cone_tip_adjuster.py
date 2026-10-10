r"""McMaster 94025A164 #10-32 cup-point adjuster (rule-12 E11); its conical apex is the thrust contact."""

from __future__ import annotations

import sys
from math import pi

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from _mcmaster_94025a164 import SS_HALF
from diagnostics.diag_build_94025A164 import build_94025A164

PART_NAME = "vn-cone-tip-adjuster"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material



async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="94025A164",
                author=build_94025A164,
                transform=RigidTransform(
                    translation_mm=(0.0, SS_HALF, 0.0),
                    rotation_radians=(pi, 0.0, 0.0),
                ),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
