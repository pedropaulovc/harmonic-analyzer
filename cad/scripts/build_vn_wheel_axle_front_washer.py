r"""Purchased MHA-VN-055 wheel-axle front washer: McMaster 92916A250.

A brass #4 washer (``vn_wheel_axle_front_washer_spec``) on the
mg-wheel-axle's #4-40 end between the magnifying wheel's spigot face and the
first wheel-axle nut (``mg_wheel_group``).  The stock recipe
``diagnostics/diag_build_92916A250.py`` models the ID x OD annulus at the
catalogue's nominal thickness; no vendor model was fetched, so its standalone
run is catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, one face
on z = 0 (the Front Plane) and the other at z = MODEL_THICKNESS.  The axis is
published as ``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_wheel_axle_front_washer.py
"""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_92916A250 import build_92916A250
from vn_wheel_axle_front_washer_spec import SKU

PART_NAME = "vn-wheel-axle-front-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the recipe's y = 0 face
# stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_92916A250, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
