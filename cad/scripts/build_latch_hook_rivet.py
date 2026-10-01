r"""Purchased MHA-175 latch-hook rivet: McMaster 97482A015.

A 1/16 x 3/16 1100-aluminium domed-head solid rivet (``latch_hook_rivet_spec``);
two join the latch hook's strip to the latch-hook bracket's flap.  The stock
recipe ``diagnostics/diag_build_97482A015.py`` models the catalogue sizes;
there is no vendor model, so its standalone run is catalog-only.

Frame: rivet axis +Y, the head's flat bearing face at y = 0 (the Top Plane),
shank to y = -LENGTH, dome to y = HEAD_H.  The axis is published as
``ScrewAxis`` (Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_latch_hook_rivet.py
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_97482A015 import build_97482A015
from latch_hook_rivet_spec import SKU

PART_NAME = "latch-hook-rivet"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_97482A015),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
