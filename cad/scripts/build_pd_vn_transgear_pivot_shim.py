"""Build purchased MHA-PD-VN-67: DIN 988 5 x 10 x 0.5 shim, bottom Y=0."""

from __future__ import annotations

import sys

from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98055A098 import build_98055A098
from pd_vn_transgear_pivot_shim_spec import SKU

PART_NAME = "pd-vn-transgear-pivot-shim"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98055A098),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
