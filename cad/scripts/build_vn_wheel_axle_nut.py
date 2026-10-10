r"""Purchased MHA-VN-025 wheel-axle nut: McMaster 92671A005.

A brass #4-40 hex nut (``vn_wheel_axle_nut_spec``), two per wheel on the
mg-wheel-axle's #4-40 end: the first is run down until the wheel turns free
without rattle, the second jams it (``mg_wheel_group``).  The stock recipe
``diagnostics/diag_build_92671A005.py`` models the hex with a plain bore at
the thread major; no vendor model was fetched, so its standalone run is
catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, one
bearing face on z = 0 (the Front Plane) and the other at z = THICKNESS.
The axis is published as ``ScrewAxis`` (Top ∩ Right), the stock-part mate
contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_wheel_axle_nut.py
"""

from __future__ import annotations

import math
import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_92671A005 import build_92671A005
from vn_wheel_axle_nut_spec import SKU

PART_NAME = "vn-wheel-axle-nut"
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
            StockComponent(sku=SKU, author=build_92671A005, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
