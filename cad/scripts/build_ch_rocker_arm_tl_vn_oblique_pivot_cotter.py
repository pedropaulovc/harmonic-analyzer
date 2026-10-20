"""Build purchased ch-rocker-arm-tl-vn-oblique-pivot-cotter, native stock recipe; see its pure spec for frame."""
from __future__ import annotations

import sys
import math
from ch_rocker_arm_tl_oblique_retention_hardware_spec import COTTER_WIDTH
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, RigidTransform, build_stock_fastener
from ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec import SKU
from diagnostics.diag_build_CP_062_0500 import build_CP_062_0500

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-cotter"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_CP_062_0500, transform=RigidTransform(rotation_radians=(math.pi / 2, 0.0, 0.0), translation_mm=(0.0, COTTER_WIDTH / 2, 0.0))),),
        material=MATERIAL,
        screw_axis_planes=("Right Plane", "Top Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
