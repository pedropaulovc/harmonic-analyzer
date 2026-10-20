r"""Purchased MHA-CH-06-TL-VN-66 oblique-trammel leadscrew nut screw: Olander 4C50BHCA.

The ``#4-40 X 1/2 BHCS`` (``ch_rocker_arm_tl_vn_oblique_nut_screw_spec``) that holds the Tr8 flanged leadscrew nut to the TL-29 nut bracket, into a blind tap.
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
from _simplified_part import save_simplified_part
from ch_rocker_arm_tl_vn_oblique_nut_screw_spec import SKU
from diagnostics.diag_build_4C50BHCA import build_4C50BHCA

PART_NAME = "ch-rocker-arm-tl-vn-oblique-nut-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_4C50BHCA),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
