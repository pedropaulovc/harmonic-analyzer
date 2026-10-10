r"""Purchased MHA-VN-053 rocker bank spring: McMaster 9714K24.

A wave disc spring (``vn_rocker_bank_spring_spec``); on the MHA-CH-005
pivot shaft between the MHA-CH-009 washer and the south MHA-CH-008 ear, it
holds the 20-hub stack north on its datum (#948 ruling R).  The stock recipe
``diagnostics/diag_build_9714K24.py`` models the installed envelope; no
vendor model was fetched, so its standalone run is catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, the south
bearing face on z = 0 (the Front Plane) and the north one at
z = MODEL_HEIGHT, the installed height.  The axis is published as
``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_rocker_bank_spring.py
"""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_9714K24 import build_9714K24
from vn_rocker_bank_spring_spec import SKU

PART_NAME = "vn-rocker-bank-spring"
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
            StockComponent(sku=SKU, author=build_9714K24, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
