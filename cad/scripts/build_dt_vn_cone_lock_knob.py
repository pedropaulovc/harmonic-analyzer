r"""Purchased cone lock knob: McMaster 93585A190 in its stock local frame.

At assembly the knob locks the swing platform where the tightest cone meets
a feeler/backlash; it sets the cone-to-drum mesh.
"""

from __future__ import annotations

import sys
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_93585a190 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
)
from diagnostics.diag_build_93585A190 import build_93585A190

PART_NAME = "dt-vn-cone-lock-knob"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="93585A190",
                author=build_93585A190,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
