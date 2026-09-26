r"""Purchased cylinder-arbor apex set screw: McMaster 91375A106, black (MHA-147).

A #4-40 x 1/4 in hex socket cup-point set screw dropped radially through each
arbor pedestal's crown apex onto the arbor (user ruling on #743, Q3). Its cup
bears in a spot drilled into the arbor through the tap at fit-up.

The body is the vendor replica (diagnostics/diag_build_91375A106), lifted so
the cup end sits on the Top plane at y = 0 and the socket face at y = LENGTH;
the assembly stands it point-down on the arbor.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_arbor_set_screw.py
"""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91375A106 import HALF, LENGTH, build_91375A106

PART_NAME = "arbor-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # alloy steel, black oxide

__all__ = ["LENGTH", "PART_NAME", "build"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91375A106",
                author=build_91375A106,
                transform=RigidTransform(translation_mm=(0.0, HALF, 0.0)),
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
