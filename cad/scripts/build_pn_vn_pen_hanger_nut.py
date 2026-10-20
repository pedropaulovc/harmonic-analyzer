r"""Purchased MHA-PN-VN-54 pen-hanger nut: McMaster 90480A009.

A zinc-plated steel #8-32 hex nut (``pn_vn_pen_hanger_nut_spec``) on the
pen-hanger screw, bearing on the strap's front face; the MHA-PN-VN-55 jam nut
is jammed against it.  The stock recipe ``diagnostics/diag_build_90480A009.py``
models the hex with a plain bore at the thread major; no vendor model was
fetched, so its standalone run is catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, the solid
spanning z = 0 (the Front Plane) to z = THICKNESS.  The axis is published as
``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_vn_pen_hanger_nut.py
"""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90480A009 import build_90480A009
from pn_vn_pen_hanger_nut_spec import SKU

PART_NAME = "pn-vn-pen-hanger-nut"
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
            StockComponent(sku=SKU, author=build_90480A009, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
