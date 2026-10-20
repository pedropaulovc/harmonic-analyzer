"""Build purchased ch-rocker-arm-tl-vn-oblique-pivot-cap-screw, native stock recipe; see its pure spec for frame."""
from __future__ import annotations

import sys
import math
from _simplified_part import save_simplified_part
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, RigidTransform, build_stock_fastener
from ch_rocker_arm_tl_vn_oblique_pivot_cap_screw_spec import SKU
from diagnostics.diag_build_NAS1352N4H12 import build_NAS1352N4H12

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-cap-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_NAS1352N4H12, transform=RigidTransform(rotation_radians=(math.pi / 2, 0.0, 0.0))),),
        material=MATERIAL,
        screw_axis_planes=("Right Plane", "Top Plane"),
        save_threaded_part=save_simplified_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
