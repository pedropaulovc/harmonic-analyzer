r"""Purchased MHA-VN-059 platen-clip screw: McMaster 92446A077 in the assembly frame.

The brass #2-56 x 1/4 slotted pan head lands in the MHA-VN-006 fillister
screw's frame: head toward -Z, under-head plane at z=0, shank along +Z.
"""

from __future__ import annotations

import sys
from functools import partial
from math import pi

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_reference import save_supplier_reference_part
from _mcmaster_92446a077 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_FORMATS,
)
from diagnostics.diag_build_92446A077 import build_92446A077
from vn_platen_clip_screw_spec import SKU

PART_NAME = "vn-platen-clip-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_92446A077,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
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
