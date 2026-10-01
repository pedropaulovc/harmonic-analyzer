r"""Purchased MHA-154 drive-collar cross pin: McMaster 98296A026.

A 1/16 x 9/16 slotted spring pin to ASME B18.8.2
(``transgear_collar_cross_pin_spec``): it is sprung through the MHA-078 knob
shaft's core and lies in the MHA-177 drive collar's rear slot, so collar and
shaft turn as one.  The stock recipe ``diagnostics/diag_build_98296A026.py``
models it as installed, a 1/16 tube with the catalog's 0.012 wall.

Frame: axis along local X, centred on the origin (MHA-145's layout).  The
axis is published as ``ScrewAxis`` (Front Plane x Top Plane); the Right Plane
is the pin's mid-length plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_collar_cross_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98296A026 import build_98296A026
from transgear_collar_cross_pin_spec import SKU

PART_NAME = "transgear-collar-cross-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98296A026),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Top Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
