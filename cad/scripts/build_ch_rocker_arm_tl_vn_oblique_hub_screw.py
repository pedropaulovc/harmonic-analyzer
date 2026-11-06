r"""Purchased MHA-CH-06-TL-VN-85 oblique-trammel hub screw: McMaster 92220A163.

The ``#10-24 X 1/2 LOW-HEAD SHCS`` (``ch_rocker_arm_tl_vn_oblique_hub_screw_spec``) that clamps the strap through the TL-35 brass washer into the TL-33 hub stud's blind nose tap, used full length.
The stock recipe ``diagnostics/diag_build_92220A163.py`` builds the catalogue screw on
the 91251A family recipe (``diag_mcmaster_socket_head.build_socket_head``);
the recipe's standalone run is catalog-only (no replica gate, user ruling
2026-10-17).

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_hub_screw.py
"""

from __future__ import annotations

import sys
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from ch_rocker_arm_tl_vn_oblique_hub_screw_spec import SKU
from diagnostics.diag_build_92220A163 import build_92220A163
import ch_rocker_arm_tl_vn_oblique_hub_screw_spec as supplier

PART_NAME = "ch-rocker-arm-tl-vn-oblique-hub-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_92220A163),),
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
