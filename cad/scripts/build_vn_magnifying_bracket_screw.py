r"""Purchased MHA-VN-050 magnifying-bracket screw: McMaster 91794A077.

The passivated 18-8 stainless stock screw retains its frame: head +Y, shank -Y,
junction at Y=0, ``ScrewAxis`` = Front ∩ Right.
"""

from __future__ import annotations

import sys

from _common import POLISHED_STEEL, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91794A077 import build_91794A077
from vn_magnifying_bracket_screw_spec import SKU

PART_NAME = "vn-magnifying-bracket-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_91794A077, transform=RigidTransform()),
        ),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
