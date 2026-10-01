r"""Purchased MHA-169 transgear latch pin: McMaster 98381A473.

A 1/8 x 3/4 alloy-steel dowel (``transgear_latch_pin_spec``), pressed chamfer
end first into the transgear arm's end face and standing 13.0 proud, where
the latch hook's Ø5.4 hole drops over it.  The stock recipe
``diagnostics/diag_build_98381A473.py`` models the vendor's chamfered and
rounded ends; its standalone run is the replica gate against the vendor model.

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract the paper drive keys it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_latch_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A473 import build_98381A473
from transgear_latch_pin_spec import SKU

PART_NAME = "transgear-latch-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A473),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
