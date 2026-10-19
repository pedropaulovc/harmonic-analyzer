r"""Build purchased MHA-CH-VN-56: McMaster 3088A429 ring shim, axis +Z, z 0..T.

The stock recipe ``diagnostics/diag_build_3088A429.py`` models the annulus
about +Y at the catalogue's nominal thickness; it is turned so the axis is
+Z, one face on z = 0 (the Front Plane) and the other at z = THICKNESS, the
frame ``build_ch_channel_assembly`` places both washers in.  The axis is
published as ``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_vn_rocker_thrust_washer.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_3088A429 import build_3088A429
from ch_vn_rocker_thrust_washer_spec import SKU

PART_NAME = "ch-vn-rocker-thrust-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the recipe's y = 0 face
# stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_3088A429, transform=TRANSFORM),),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
