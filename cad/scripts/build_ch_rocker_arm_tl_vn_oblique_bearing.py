r"""Purchased MHA-CH-06-TL-VN-52 oblique-trammel pivot bearing: McMaster 5972K41.

A sealed 6200-2RS deep-groove ball bearing, 10 x 30 x 9
(``ch_rocker_arm_tl_vn_oblique_bearing_spec``); a pair is pressed into each pivot
block's N6 seats, and the pivot pin's k5 section is pressed through both inner
rings.  The stock recipe ``diagnostics/diag_build_5972K41.py`` models the
vendor model's eleven bodies (two rings, two seals, seven balls), read for
dimensions only (not replica-gated, user ruling 2026-10-17); its standalone
run is catalog-only.

Frame: bearing axis +Y, one side face at y = 0 (the Top Plane), the other at
y = 9.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the stock-part
mate contract: a part-level axis coaxial with the ``InnerRing`` bore and the
``OuterRing`` OD.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_bearing.py
"""

from __future__ import annotations

import sys

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from ch_rocker_arm_tl_vn_oblique_bearing_spec import SKU
from diagnostics.diag_build_5972K41 import build_5972K41

PART_NAME = "ch-rocker-arm-tl-vn-oblique-bearing"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_5972K41),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
