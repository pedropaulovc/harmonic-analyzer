r"""Purchased MHA-183 knob-cup pin: McMaster 98296A031.

A 1/16 x 5/8 slotted spring pin to ASME B18.8.2
(``transgear_knob_cup_pin_spec``): it is pressed through the MHA-157 knob cup
and the MHA-078 knob shaft's journal, in a hole match-drilled through both at
assembly, so the cup is pinned to the shaft as the rear stop of its end
float.  The stock recipe ``diagnostics/diag_build_98296A031.py`` models it as
installed, a 1/16 tube with the catalog's 0.012 wall.

Frame: axis along local X, centred on the origin (MHA-154's layout).  The
axis is published as ``ScrewAxis`` (Front Plane x Top Plane); the Right Plane
is the pin's mid-length plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_knob_cup_pin.py
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98296A031 import build_98296A031
from transgear_knob_cup_pin_spec import SKU

PART_NAME = "transgear-knob-cup-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_98296A031),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Top Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
