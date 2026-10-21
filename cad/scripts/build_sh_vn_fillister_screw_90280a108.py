r"""Shared McMaster 90280A108 in the unshifted stock foot-screw frame.

The under-head junction is at y = 0 and the screw axis is +Y. The native
ScrewAxis preserves the latch-hook mate contract. Foot/latch application colours
belong to their assembly occurrences, not to this shared purchased part.
"""

from __future__ import annotations

import sys
from functools import partial

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from diagnostics.diag_build_90280A108 import build_90280A108
import sh_vn_fillister_screw_90280a108_spec as supplier

PART_NAME = "sh-vn-fillister-screw-90280a108"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90280A108",
                author=build_90280A108,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
        ),
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
