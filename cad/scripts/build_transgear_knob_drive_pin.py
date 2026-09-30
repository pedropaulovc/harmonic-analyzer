r"""Purchased MHA-155 transgear knob drive pin: McMaster 98381A433.

A 3/32 x 3/16 alloy-steel dowel (``transgear_knob_drive_pin_spec``).  Two are
pressed into blind holes in the knob shaft MHA-078's seat collar (ch23 p.56):
the removable sprocket MHA-081 drops its two Ø2.5 holes over them.  The stock
recipe ``diagnostics/diag_build_98381A433.py`` models the nominal cylinder,
catalogue-only (no vendor model).

Frame: pin axis +Y, pressed end face at y = 0 (the Top Plane), lead end at
y = LENGTH.  The axis is published as ``ScrewAxis`` (Front ∩ Right), the
stock-part mate contract the paper drive keys it by.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_knob_drive_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A433 import build_98381A433
from transgear_knob_drive_pin_spec import SKU

PART_NAME = "transgear-knob-drive-pin"
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
