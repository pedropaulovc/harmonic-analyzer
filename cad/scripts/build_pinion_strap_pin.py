r"""Purchased 1/16 spring pin: McMaster 98296A027 (MHA-145, 3 used: E-a strap pins and the R1a collar pin).

A 1/16 x 1/2 slotted spring pin to ASME B18.8.2 (pinion_strap_pin_spec): one
runs through each MHA-056 strap foot's cross hole and the MHA-062 torque
shaft, so strap, shaft and strap swing as one group.  The stock recipe models
it as installed, a 1/16 tube with the catalog's 0.012 wall, axis along local
X and centred on the origin: the MHA-135 lever-pin layout.  It is the nominal
1/2 length; pinion_strap_pin_spec proves the longest pin the length band
allows is still buried in the narrowest strap foot (PIN_BURIED_MARGIN).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_strap_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_98296A027 import build_98296A027

PART_NAME = "pinion-strap-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="98296A027",
                author=build_98296A027,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        color=POLISHED_STEEL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
