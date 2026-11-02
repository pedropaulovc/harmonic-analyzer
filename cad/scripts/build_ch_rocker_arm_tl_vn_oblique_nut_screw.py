r"""Purchased MHA-CH-06-TL-VN-66 oblique-trammel leadscrew nut screw: Olander 4C50BHCA.

The ``#4-40 X 1/2 BHCS`` (``ch_rocker_arm_tl_vn_oblique_nut_screw_spec``) holds the Tr8 flanged leadscrew nut to the TL-32 integral feed-block lug, into a blind tap.
The stock recipe ``diagnostics/diag_build_4C50BHCA.py`` builds the
catalogue screw on the shared button-head recipe
(``diag_mcmaster_button_head.build_button_head``) plus its nominal underhead
fillet; the recipe's standalone run is catalog-only (no vendor model, no
replica gate).

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_nut_screw.py
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_reference import add_supplier_reference_sketch
from _simplified_part import save_simplified_part
from ch_rocker_arm_tl_vn_oblique_nut_screw_spec import SKU
from diagnostics.diag_build_4C50BHCA import build_4C50BHCA
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as supplier

PART_NAME = "ch-rocker-arm-tl-vn-oblique-nut-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _save_supplier_part(adapter, part_name, suppressed_features) -> dict[str, str]:
    await add_supplier_reference_sketch(
        adapter,
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
    )
    # Supplier sizes print as untoleranced REF; the catalogue governs.
    return await save_simplified_part(adapter, part_name, suppressed_features)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_4C50BHCA),),
        material=MATERIAL,
        save_threaded_part=_save_supplier_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
