r"""Purchased pen-rod set screw: McMaster 91375A105, black (MHA-PN-VN-52).

A #4-40 x 3/16 in hex socket cup-point set screw in the pen v-block's tap,
bearing on the pen rod's turned pivot end and locking it in the block.

The body is the catalogue-only recipe (diagnostics/diag_build_91375A105),
lifted so the cup end sits on the Top plane at y = 0 and the socket face at
y = LENGTH; the pen assembly places it cup-down on the rod.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_vn_pen_rod_set_screw.py
"""

from __future__ import annotations

import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91375A105 import HALF, LENGTH, build_91375A105
from pn_vn_pen_rod_set_screw_spec import SKU

PART_NAME = "pn-vn-pen-rod-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # alloy steel, black oxide

__all__ = ["LENGTH", "PART_NAME", "build"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91375A105,
                transform=RigidTransform(translation_mm=(0.0, HALF, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
