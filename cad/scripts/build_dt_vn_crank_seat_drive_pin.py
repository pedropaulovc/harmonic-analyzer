r"""Purchased MHA-DT-VN-67 crank-seat drive pin: McMaster 98381A434.

A 3/32 x 1/4 alloy-steel dowel (``dt_vn_crank_seat_drive_pin_spec``).  Two are
pressed into the crankshaft collar's seat face (ch23 p.56): the removable
sprocket MHA-PD-09 drops its two Ø2.5 holes over them.  (The knob shaft takes
the shorter MHA-PD-VN-54 transgear-knob-drive-pin.)
The stock recipe ``diagnostics/diag_build_98381A434.py`` models the
nominal cylinder, catalogue-only (no vendor model).

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract both assemblies key it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_vn_crank_seat_drive_pin.py
"""

from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from dt_vn_crank_seat_drive_pin_spec import SKU, SUPPLIER_REFERENCE
from diagnostics.diag_build_98381A434 import build_98381A434

PART_NAME = "dt-vn-crank-seat-drive-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_98381A434)
async def _build_pin_with_supplier_references(adapter, truth=None):
    await build_98381A434(adapter, truth)
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
