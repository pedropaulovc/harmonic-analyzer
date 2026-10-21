"""Purchased MHA-PD-VN-64: two McMaster 93600A189 arm/plate locating dowels.

Catalogue-only nominal cylinder, not a vendor end-form replica.
Axis +Y, first end y=0; ScrewAxis is the existing stock mate convention.
"""
from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from diagnostics.diag_build_93600A189 import build_93600A189
from pd_vn_transgear_arm_plate_locating_pin_spec import SKU, SUPPLIER_REFERENCE

PART_NAME = "pd-vn-transgear-arm-plate-locating-pin"
SPEC = fastener(PART_NAME)


@wraps(build_93600A189)
async def _build_pin_with_supplier_references(adapter, truth=None):
    await build_93600A189(adapter, truth)
    await author_supplier_dowel_references(adapter, SUPPLIER_REFERENCE)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_build_pin_with_supplier_references),),
        material=SPEC.material,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
