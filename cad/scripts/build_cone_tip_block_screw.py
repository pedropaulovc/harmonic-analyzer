r"""Purchased cone tip block hold-down screw: McMaster 91255A148, black oxide.

U30: one #6-32 x 1/2 in button head hex drive screw rises from the swing
platform's counterbored slot (MHA-091), through the shim pack (MHA-141), into
the tip block's foot tap (MHA-092).  Rule-12 W22 replaced the socket head
91251A148 with this button head.  The recipe models it from catalog
dimensions; no vendor SLDPRT is used (see diagnostics/diag_build_91255A148.py).
"""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91255A148 import build_91255A148

PART_NAME = "cone-tip-block-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#6-32"


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91255A148",
                author=build_91255A148,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
