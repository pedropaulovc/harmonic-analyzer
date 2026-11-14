r"""Purchased MHA-CH-06-TL-VN-85 oblique-trammel hub washer: McMaster 90231A116.

The brass #8 SAE flat washer (``ch_rocker_arm_tl_vn_oblique_hub_washer_spec``)
under the head of the common #8-32 x 3/4 SHCS HUB clamp, on the strap over
its reamed hub hole (owner ruling 2026-11-13, #2448).  The stock recipe
``diagnostics/diag_build_90231A116.py`` models the ID x OD annulus at Table
11's basic thickness; its standalone run is catalog-only.

Frame: the recipe is built about +Y and turned so its axis is +Z, the
strap-side face on z = 0 (the Front Plane) and the head-side face at
z = THICKNESS.  The axis is published as ``ScrewAxis`` (Top ∩ Right), the
stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_hub_washer.py
"""

from __future__ import annotations

from functools import wraps
import math
import sys

from _fastener_catalog import fastener
from _part_properties import part_drawing_unit
from _session import run_build
from _sketch import blank_reference_sketches
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_washer_model import author_supplier_washer_references
from ch_rocker_arm_tl_vn_oblique_hub_washer_spec import REFERENCE_SKETCHES, SKU
import ch_rocker_arm_tl_vn_oblique_hub_washer_spec as part
from diagnostics.diag_build_90231A116 import build_90231A116

PART_NAME = "ch-rocker-arm-tl-vn-oblique-hub-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the recipe's y = 0 face
# stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


@wraps(build_90231A116)
async def _build_with_supplier_references(adapter, truth=None):
    await build_90231A116(adapter, truth)
    await author_supplier_washer_references(
        adapter, axis="z", bore_mm=part.ID, outer_mm=part.OD,
        thickness_mm=part.THICKNESS, units=part.SUPPLIER_UNITS,
        sheet_units=part_drawing_unit(PART_NAME),
        precision=part.DRAWING_REFERENCE_PRECISION, references=part.SUPPLIER_MODEL_REFERENCES,
        bore_callout=part.SUPPLIER_BORE_CALLOUT,
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=_build_with_supplier_references, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
