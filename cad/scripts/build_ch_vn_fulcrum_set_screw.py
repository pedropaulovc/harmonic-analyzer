r"""Purchased fulcrum-shaft set screw: McMaster 91375A942, black (MHA-CH-VN-55).

A #1-72 x 5/32 in hex socket cup-point set screw dropped vertically through
each fulcrum keeper's lug crown top onto the flat on the plain fulcrum shaft,
fixing the shaft axially and in rotation.

The body is the catalogue-only replica (diagnostics/diag_build_91375A942),
lifted so the cup end sits on the Top plane at y = 0 and the socket face at
y = LENGTH; the assembly stands it point-down on the shaft flat.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_vn_fulcrum_set_screw.py
"""

from __future__ import annotations

import sys
from functools import partial

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_91375a942 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
)
from diagnostics.diag_build_91375A942 import HALF, LENGTH, build_91375A942

PART_NAME = "ch-vn-fulcrum-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # alloy steel, black oxide

__all__ = ["LENGTH", "PART_NAME", "build"]


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91375A942",
                author=build_91375A942,
                transform=RigidTransform(translation_mm=(0.0, HALF, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
