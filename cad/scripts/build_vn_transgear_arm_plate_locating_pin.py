"""Purchased MHA-VN-056: two McMaster 98381A434 arm/plate locating dowels.

Catalogue-only nominal cylinder, not a vendor end-form replica.
Axis +Y, first end y=0; ScrewAxis is the existing stock mate convention.
"""
from __future__ import annotations

import sys

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A434 import build_98381A434
from vn_transgear_arm_plate_locating_pin_spec import SKU

PART_NAME = "vn-transgear-arm-plate-locating-pin"
SPEC = fastener(PART_NAME)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A434),),
        material=SPEC.material,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
