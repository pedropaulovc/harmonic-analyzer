r"""Purchased MHA-VN-038 transgear knob drive pin: McMaster 98381A433.

A 3/32 x 3/16 alloy-steel dowel (``vn_transgear_knob_drive_pin_spec``).  Two are
pressed into holes reamed through the knob drive collar MHA-PD-022 (ch23
p.56), set on a stop to their proud length: the removable sprocket MHA-PD-009
drops its two Ø2.5 holes over them.  The stock
recipe ``diagnostics/diag_build_98381A433.py`` models the nominal cylinder,
catalogue-only (no vendor model).

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract the paper drive keys it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_transgear_knob_drive_pin.py
"""

from __future__ import annotations

import sys

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A433 import build_98381A433
from vn_transgear_knob_drive_pin_spec import SKU

PART_NAME = "vn-transgear-knob-drive-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98381A433),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
