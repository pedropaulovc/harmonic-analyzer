r"""Purchased 1/16 spring pin: McMaster 98296A027 (MHA-VN-033; the parts registry holds the count).

A 1/16 x 1/2 slotted spring pin to ASME B18.8.2 (vn_pinion_strap_pin_spec): one
runs through each MHA-DT-014 strap foot's cross hole and the MHA-DT-019 torque
shaft, so strap, shaft and strap swing as one group.  The stock recipe models
it as installed, a 1/16 tube with the catalog's 0.012 wall, axis along local
X and centred on the origin: the MHA-DT-030 lever-pin layout.  It is the nominal
1/2 length; vn_pinion_strap_pin_spec proves the longest pin the length band
allows is still buried in the narrowest strap foot (PIN_BURIED_MARGIN).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_pinion_strap_pin.py
"""

from __future__ import annotations

import sys

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_98296A027 import build_98296A027

PART_NAME = "vn-pinion-strap-pin"
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
