r"""Purchased MHA-MG-VN-53 magnifying-bracket screw: McMaster 91794A078.

The passivated 18-8 stainless stock screw retains its frame: head +Y, shank -Y,
junction at Y=0, ``ScrewAxis`` = Front ∩ Right.
"""

from __future__ import annotations

import sys
from functools import partial

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_91794a078 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
)
from diagnostics.diag_build_91794A078 import build_91794A078
from mg_vn_magnifying_bracket_screw_spec import SKU

PART_NAME = "mg-vn-magnifying-bracket-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_91794A078, transform=RigidTransform()),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
