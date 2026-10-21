r"""Shared clamp screw: McMaster 90280A201 in its unchanged installed frame."""

from __future__ import annotations

import sys
from math import pi
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_90280A201 import build_90280A201
import sh_vn_clamp_screw_spec as supplier

PART_NAME = "sh-vn-clamp-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90280A201",
                author=build_90280A201,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
