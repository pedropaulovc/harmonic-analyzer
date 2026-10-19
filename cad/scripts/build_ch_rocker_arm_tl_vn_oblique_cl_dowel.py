r"""Purchased MHA-CH-06-TL-VN-53 oblique-trammel CL locator dowel: McMaster 91595A452.

A Ø6 x 20 m6 alloy-steel dowel (``ch_rocker_arm_tl_vn_oblique_cl_dowel_spec``),
pressed chamfered end first into the carrier's CL hole (finished in place to
Ø6 N7), with the round tip set above the actual installed riser. It passes
the riser's clamp hole and locates the rocker strap blank's CL hole. The stock
recipe ``diagnostics/diag_build_91595A452.py`` models the vendor model's
crowned-chamfer and domed ends, read for dimensions only (not replica-gated,
user ruling 2026-10-17); its standalone run is catalog-only.

Frame: pin axis +Y, chamfered tip at y = 0 (the Top Plane), domed tip at
y = 20.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the stock-part
mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_cl_dowel.py
"""

from __future__ import annotations

import sys

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from ch_rocker_arm_tl_vn_oblique_cl_dowel_spec import SKU
from diagnostics.diag_build_91595A452 import build_91595A452

PART_NAME = "ch-rocker-arm-tl-vn-oblique-cl-dowel"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91595A452),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
