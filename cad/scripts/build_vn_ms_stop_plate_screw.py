r"""Purchased MHA-VN-054 stop-plate screw: McMaster 90114A124.

The brass slotted fillister retains the supplied family frame: head +Y,
thread -Y, bearing plane Y=0, ScrewAxis = Front intersection Right.
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_90114A124 import build_90114A124
from _mcmaster_90114a124 import SKU

PART_NAME = "vn-ms-stop-plate-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_90114A124, transform=RigidTransform()),
        ),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
        save_threaded_part=save_simplified_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
