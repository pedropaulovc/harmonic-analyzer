"""Build purchased MHA-SM-VN-54: #10 SAE 18-8 flat washer, bottom Y=0."""

from __future__ import annotations

import sys

from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_96659A104 import build_96659A104
from sm_vn_knife_hanger_washer_spec import SKU

PART_NAME = "sm-vn-knife-hanger-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_96659A104),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
