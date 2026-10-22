r"""Shared brass fillister screw: McMaster 90114A511 in the installed stock frame."""

from __future__ import annotations

import sys
from math import pi
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_90114A511 import build_90114A511
import sh_vn_brass_fillister_screw_spec as supplier

PART_NAME = "sh-vn-brass-fillister-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90114A511",
                author=build_90114A511,
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
