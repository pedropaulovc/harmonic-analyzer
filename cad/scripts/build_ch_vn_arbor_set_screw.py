r"""Purchased channel apex set screw: McMaster 91375A106, black (MHA-CH-VN-53).

A #4-40 x 1/4 in hex socket cup-point set screw drops through each
MHA-CH-08 ear's arch apex onto a flat on the rocker pivot shaft
(user, 2026-10-10).

The body is the vendor replica (diagnostics/diag_build_91375A106), lifted so
the cup end sits on the Top plane at y = 0 and the socket face at y = LENGTH;
the channel assembly stands it point-down on the rocker pivot shaft.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_vn_arbor_set_screw.py
"""

from __future__ import annotations

import sys

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from diagnostics.diag_build_91375A106 import HALF, LENGTH, build_91375A106

PART_NAME = "ch-vn-arbor-set-screw"
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
        save_threaded_part=save_simplified_part,
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
