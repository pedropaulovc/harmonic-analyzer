"""Build purchased MHA-VN-060: #10 SAE 18-8 flat washer, bottom Y=0."""

from __future__ import annotations

from functools import wraps
import sys

from _fastener_catalog import fastener
from _session import run_build
from _sketch import blank_reference_sketches
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_washer_model import author_supplier_washer_references
from diagnostics.diag_build_96659A104 import build_96659A104
from vn_knife_hanger_washer_spec import REFERENCE_SKETCHES, SKU
import vn_knife_hanger_washer_spec as part

PART_NAME = "vn-knife-hanger-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


@wraps(build_96659A104)
async def _build_with_supplier_references(adapter, truth=None):
    await build_96659A104(adapter, truth)
    await author_supplier_washer_references(
        adapter,
        axis="y",
        bore_mm=part.ID,
        outer_mm=part.OD,
        thickness_mm=part.THICKNESS,
        units=part.SUPPLIER_UNITS,
        precision=part.DRAWING_REFERENCE_PRECISION,
        bands=part.SUPPLIER_TOLERANCES,
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
