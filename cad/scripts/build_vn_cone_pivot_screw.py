r"""Purchased cone pivot screw: McMaster 91829A560 in its stock local frame."""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_reference import add_supplier_reference_sketch
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _simplified_part import save_simplified_part
from _mcmaster_91829a560 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_TOLERANCES_IN,
)
from diagnostics.diag_build_91829A560 import build_91829A560

PART_NAME = "vn-cone-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _save_supplier_part(adapter, part_name, suppressed_features) -> dict[str, str]:
    await add_supplier_reference_sketch(
        adapter,
        SUPPLIER_REFERENCE_DIMENSIONS,
        starts=SUPPLIER_REFERENCE_STARTS,
        planes=SUPPLIER_REFERENCE_PLANES,
    )
    # These bands identify supplied stock. They govern no manufactured feature.
    for name, (lower, upper) in SUPPLIER_REFERENCE_TOLERANCES_IN.items():
        set_dimension_bilateral_tolerance(
            adapter, "SupplierReference", name, lower * 25.4, upper * 25.4
        )
    return await save_simplified_part(adapter, part_name, suppressed_features)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="91829A560",
                author=build_91829A560,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=_save_supplier_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
