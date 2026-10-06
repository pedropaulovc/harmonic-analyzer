r"""Purchased MHA-VN-044 crank-seat drive pin: McMaster 98381A434.

A 3/32 x 1/4 alloy-steel dowel (``vn_crank_seat_drive_pin_spec``).  Two are
pressed into the crankshaft collar's seat face (ch23 p.56): the removable
sprocket MHA-PD-009 drops its two Ø2.5 holes over them.  (The knob shaft takes
the shorter MHA-VN-038 transgear-knob-drive-pin.)
The stock recipe ``diagnostics/diag_build_98381A434.py`` models the
nominal cylinder, catalogue-only (no vendor model).

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract both assemblies key it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_crank_seat_drive_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from vn_crank_seat_drive_pin_spec import SKU
from diagnostics.diag_build_98381A434 import build_98381A434

PART_NAME = "vn-crank-seat-drive-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A434),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
