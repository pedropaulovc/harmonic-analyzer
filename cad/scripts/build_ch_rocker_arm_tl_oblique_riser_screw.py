r"""Purchased MHA-CH-006-TL-47 oblique-trammel riser screw: McMaster 91771A110.

The ``#4-40 X 1/2 FLAT HEAD`` (``ch_rocker_arm_tl_oblique_riser_screw_spec``) that holds the TL-24 riser to the TL-21 carrier, tapped THRU.
The stock recipe ``diagnostics/diag_build_91771A110.py`` builds the catalogue screw, with the Phillips recess form and the tip
read off the vendor model where the catalogue is silent; the vendor model
is not replica-gated (user ruling 2026-10-17) and the recipe's standalone
run is catalog-only.

Frame: screw axis +Y, head up, the flat top (flush in the countersink) at
y = 0, the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_riser_screw.py
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from ch_rocker_arm_tl_oblique_riser_screw_spec import SKU
from diagnostics.diag_build_91771A110 import build_91771A110

PART_NAME = "ch-rocker-arm-tl-oblique-riser-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91771A110),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
