r"""Purchased MHA-VN-052 cylinder bank spring: McMaster 9714K392.

A wave disc spring (``vn_cylinder_bank_spring_spec``); on the MHA-DT-013
arbor between the front MHA-DT-026 washer and the front MHA-DT-002 strap, it
holds the 20-gear stack north on its datum (#948 ruling R).  The stock recipe
``diagnostics/diag_build_9714K392.py`` models the installed envelope; no
vendor model was fetched, so its standalone run is catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, the south
bearing face on z = 0 (the Front Plane) and the north one at
z = MODEL_HEIGHT, the installed height.  The axis is published as
``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_cylinder_bank_spring.py
"""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_9714K392 import build_9714K392
from vn_cylinder_bank_spring_spec import SKU

PART_NAME = "vn-cylinder-bank-spring"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the south bearing face
# (recipe y = 0) stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_9714K392, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
