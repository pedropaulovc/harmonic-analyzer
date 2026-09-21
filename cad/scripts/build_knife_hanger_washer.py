r"""Purchased knife-hanger washer: McMaster 90126A211."""

from __future__ import annotations

from functools import wraps
import sys

from _common import run_build
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _fastener_catalog import fastener
from _saved_part_guard import require_saved_drawing_properties
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90126A211 import W_ID, W_OD, W_T, build_90126A211

PART_NAME = "knife-hanger-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

OUTER_DIA = W_OD
INNER_DIA = W_ID
THICKNESS = W_T


@wraps(build_90126A211)
async def _prepared_washer(adapter, truth=None, **parameters):
    """Stamp only identity properties; the purchased sheet has no PMI."""
    receipt = await build_90126A211(adapter, truth, **parameters)
    clear_dimensions_for_drawing(adapter)
    apply_drawing_properties(adapter, PART_NAME)
    return receipt


async def build(adapter) -> dict[str, str]:
    artefacts = await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="90126A211",
                author=_prepared_washer,
                transform=RigidTransform(),
            ),
        ),
        material=MATERIAL,
    )
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
