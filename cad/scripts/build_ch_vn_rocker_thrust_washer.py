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

from functools import wraps
import math
import sys

from _fastener_catalog import fastener
from _part_properties import part_drawing_unit
from _session import run_build
from _sketch import blank_reference_sketches
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_washer_model import author_supplier_washer_references
from diagnostics.diag_build_3088A429 import build_3088A429
from ch_vn_rocker_thrust_washer_spec import REFERENCE_SKETCHES, SKU
import ch_vn_rocker_thrust_washer_spec as part

PART_NAME = "ch-vn-rocker-thrust-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the recipe's y = 0 face
# stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


@wraps(build_3088A429)
async def _build_with_supplier_references(adapter, truth=None):
    await build_3088A429(adapter, truth)
    await author_supplier_washer_references(
        adapter, axis="z", bore_mm=part.ID, outer_mm=part.OD,
        thickness_mm=part.THICKNESS, units=part.SUPPLIER_UNITS,
        sheet_units=part_drawing_unit(PART_NAME),
        precision=part.DRAWING_REFERENCE_PRECISION, bands=part.SUPPLIER_TOLERANCES,
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
