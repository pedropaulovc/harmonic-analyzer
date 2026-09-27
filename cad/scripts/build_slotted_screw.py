"""Build the pinion-block hold-down slotted screw from McMaster 90280A201.

Rule 12 (audit E10): U28 raised the pivot block to 20.5, which left the
former #8-32 x 1 (90280A199) only 4.39 mm = 1.05D of worst-case thread in
the base.  The #8-32 x 1-1/4 of the same family engages 11.25 nominal,
10.74 = 2.58D worst case.
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A201 import build_90280A201

PART_NAME = "slotted-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent("90280A201", build_90280A201),),
        material=MATERIAL,
        color=POLISHED_STEEL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
