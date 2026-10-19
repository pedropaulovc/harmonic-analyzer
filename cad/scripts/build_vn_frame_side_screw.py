r"""Purchased frame-side screw: McMaster 91794A080 (#2-56 x 7/16) in its stock local frame."""

from __future__ import annotations

import sys
from functools import partial

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_reference import save_supplier_reference_part
from _mcmaster_91794a080 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
)
from diagnostics.diag_build_91794A080 import build_91794A080

PART_NAME = "vn-frame-side-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91794A080",
                author=build_91794A080,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        color=POLISHED_STEEL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
