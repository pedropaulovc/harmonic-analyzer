r"""Purchased MHA-PD-VN-58 transgear latch pin: McMaster 98381A474.

A 1/8 x 7/8 alloy-steel dowel (``pd_vn_transgear_latch_pin_spec``), pressed chamfer
end first into the transgear arm's end face and standing PROUD out of it,
where the latch hook's pin hole drops over it.  The stock recipe
``diagnostics/diag_build_98381A474.py`` models the 1/8 series' chamfered and
rounded ends (read off the 98381A473 vendor model). The supplier drawing
confirms size and diameter band, but does not dimension those end forms.

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract the paper drive keys it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_transgear_latch_pin.py
"""

from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from diagnostics.diag_build_98381A474 import build_98381A474
from pd_vn_transgear_latch_pin_spec import SKU, SUPPLIER_REFERENCE

PART_NAME = "pd-vn-transgear-latch-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_98381A474)
async def _build_pin_with_supplier_references(adapter, truth=None):
    await build_98381A474(adapter, truth)
    await author_supplier_dowel_references(adapter, SUPPLIER_REFERENCE)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_build_pin_with_supplier_references),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
