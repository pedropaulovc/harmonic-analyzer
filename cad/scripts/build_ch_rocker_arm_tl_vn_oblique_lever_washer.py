r"""Purchased MHA-CH-06-TL-VN-71 oblique-trammel feed lever screw lock washer: McMaster 91812A230.

The 5/16 wedge-lock washer pair (``ch_rocker_arm_tl_vn_oblique_lever_washer_spec``)
under the head of each TL-VN-69 feed lever screw, on the TL-26 lever's top face.
The stock recipe ``diagnostics/diag_build_91812A230.py`` builds the pair's
catalogue envelope, a plain annulus; its standalone run is catalog-only (no
vendor model, so no replica gate).

Frame: axis +Y, the bottom face (on the lever's top face) at y = 0, the top
face (under the screw head) at y = THICKNESS.  The axis is published as
``ScrewAxis`` (Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_lever_washer.py
"""

from __future__ import annotations

from functools import wraps
import sys

from _fastener_catalog import fastener
from _session import run_build
from _sketch import blank_reference_sketches
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_washer_model import author_supplier_washer_references
from ch_rocker_arm_tl_vn_oblique_lever_washer_spec import REFERENCE_SKETCHES, SKU
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as part
from diagnostics.diag_build_91812A230 import build_91812A230

PART_NAME = "ch-rocker-arm-tl-vn-oblique-lever-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_91812A230)
async def _build_with_supplier_references(adapter, truth=None):
    await build_91812A230(adapter, truth)
    # These witnesses match the plain catalogue envelope, not physical cams
    # or a split pair. The existing maximum stack and material stay unchanged.
    await author_supplier_washer_references(
        adapter, axis="y", bore_mm=part.ID, outer_mm=part.OD,
        thickness_mm=part.THICKNESS, units=part.SUPPLIER_UNITS,
        precision=part.DRAWING_REFERENCE_PRECISION, bands=part.SUPPLIER_TOLERANCES,
        bore_callout=part.SUPPLIER_BORE_CALLOUT,
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_build_with_supplier_references),),
        material=MATERIAL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
