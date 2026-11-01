r"""Purchased MHA-CH-06-TL-VN-66 oblique-trammel feed nut screw: McMaster 91251A113.

The ``#4-40 X 3/4 SHCS`` (``ch_rocker_arm_tl_vn_oblique_nut_screw_spec``) holds the shop-made TL-27 feed nut to the TL-32 integral feed-block lug, tapped THRU.
The stock recipe ``diagnostics/diag_build_91251A113.py`` builds the catalogue screw on
the 91251A family recipe (``diag_mcmaster_socket_head.build_socket_head``);
the recipe's standalone run is catalog-only (no vendor model, no replica
gate).

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_nut_screw.py
"""

from __future__ import annotations

import sys
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from ch_rocker_arm_tl_vn_oblique_nut_screw_spec import SKU
from diagnostics.diag_build_91251A113 import build_91251A113
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as supplier

PART_NAME = "ch-rocker-arm-tl-vn-oblique-nut-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91251A113),),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
        ),
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
