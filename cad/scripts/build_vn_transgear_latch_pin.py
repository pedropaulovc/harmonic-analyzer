r"""Purchased MHA-VN-042 transgear latch pin: McMaster 98381A474.

A 1/8 x 7/8 alloy-steel dowel (``vn_transgear_latch_pin_spec``), pressed chamfer
end first into the transgear arm's end face and standing PROUD out of it,
where the latch hook's Ø5.4 hole drops over it.  The stock recipe
``diagnostics/diag_build_98381A474.py`` models the 1/8 series' chamfered and
rounded ends (read off the 98381A473 vendor model); the SKU is not yet read
live, so its standalone run is catalog-only.

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract the paper drive keys it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_transgear_latch_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A474 import build_98381A474
from vn_transgear_latch_pin_spec import SKU

PART_NAME = "vn-transgear-latch-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A474),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
