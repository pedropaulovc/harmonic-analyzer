r"""Purchased MHA-DT-12-TL-VN-50 cam fixture stub: McMaster 97175A344.

The 3/8 x 3/4 pull-out dowel (``dt_cylinder_gear_tl_vn_cam_stub_spec``)
pressed in the MHA-DT-12-TL-01 body at the cam throw. The stock recipe
``diagnostics/diag_build_97175A344.py`` models the nominal cylinder with its
10-32 tap bored to the tap drill, catalogue-only (no vendor model).

Frame: axis +Y, the pressed end face at y = 0 (the Top Plane), the tapped
end at y = LENGTH. The axis is published as ``ScrewAxis`` (Front ∩ Right),
the stock-part mate contract.

Run only through the supervised farm launcher:
``part:dt_cylinder_gear_tl_vn_cam_stub``.
"""

from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from diagnostics.diag_build_97175A344 import build_97175A344
from dt_cylinder_gear_tl_vn_cam_stub_spec import SKU, SUPPLIER_REFERENCE

PART_NAME = "dt-cylinder-gear-tl-vn-cam-stub"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_97175A344)
async def _build_stub_with_supplier_references(adapter, truth=None):
    await build_97175A344(adapter, truth)
    await author_supplier_dowel_references(adapter, SUPPLIER_REFERENCE)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=_build_stub_with_supplier_references),
        ),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
