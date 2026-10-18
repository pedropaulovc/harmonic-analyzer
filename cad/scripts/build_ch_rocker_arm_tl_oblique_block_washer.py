r"""Purchased MHA-CH-006-TL-50 oblique-trammel block screw lock washer: McMaster 91812A215.

The #8 wedge-lock washer pair (``ch_rocker_arm_tl_oblique_block_washer_spec``)
under the head of each TL-43 block screw, on the floor of TL-22's counterbore.
The stock recipe ``diagnostics/diag_build_91812A215.py`` builds the pair's
catalogue envelope, a plain annulus; its standalone run is catalog-only (no
vendor model, so no replica gate).

Frame: axis +Y, the bottom face (on the counterbore floor) at y = 0, the top
face (under the screw head) at y = THICKNESS.  The axis is published as
``ScrewAxis`` (Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_block_washer.py
"""

from __future__ import annotations

import sys

from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import StockComponent, build_stock_fastener
from ch_rocker_arm_tl_oblique_block_washer_spec import SKU
from diagnostics.diag_build_91812A215 import build_91812A215

PART_NAME = "ch-rocker-arm-tl-oblique-block-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91812A215),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
