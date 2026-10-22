r"""Purchased MHA-PD-VN-63 transgear pivot spring: McMaster 9715K43.

A curved disc spring for a 0.190 shaft (``pd_vn_transgear_pivot_spring_spec``); on
the MHA-PD-VN-57 pivot screw's shoulder, between its head and the MHA-PD-18 arm's
spot-face floor, it preloads the arm onto the MHA-PD-20 spacer.  The stock
recipe ``diagnostics/diag_build_9715K43.py`` models the catalogue sizes; no
vendor model was fetched, so its standalone run is catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, the OD
rim's bearing face on z = 0 (the Front Plane) and the ID rim's at
z = MODEL_HEIGHT, the installed height.  The axis is published as
``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_transgear_pivot_spring.py
"""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_9715K43 import build_9715K43
from pd_vn_transgear_pivot_spring_spec import SKU
import pd_vn_transgear_pivot_spring_spec as supplier_spec
from _part_save import save_part_and_images
from vn_disc_spring_supplier_stock import add_supplier_disc_diagram

PART_NAME = "pd-vn-transgear-pivot-spring"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the OD rim's bearing face
# (recipe y = 0) stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


async def _save_supplier_reference_part(adapter, part_name: str) -> dict[str, str]:
    await add_supplier_disc_diagram(adapter, spec=supplier_spec)
    return await save_part_and_images(adapter, part_name)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_9715K43, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
        save_unthreaded_part=_save_supplier_reference_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
