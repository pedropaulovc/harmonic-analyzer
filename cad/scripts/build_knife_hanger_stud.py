"""Build the knife-hanger bolt from McMaster 91247A720."""

from __future__ import annotations

from functools import wraps
import sys

from _common import run_build
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _fastener_catalog import fastener
from _saved_part_guard import require_saved_drawing_properties
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91247A720 import (
    GB_HH,
    GB_HW,
    GB_LEN,
    GB_MAJOR_R,
    GB_UNDERSIDE,
    GB_WASHER_T,
    build_91247A720,
)

PART_NAME = "knife-hanger-stud"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

HEAD_AF = GB_HW
HEAD_H = GB_HH
SHANK_DIA = 2.0 * GB_MAJOR_R
SHANK_LEN = GB_LEN
UNDERHEAD_LEN = GB_LEN - GB_WASHER_T


@wraps(build_91247A720)
async def _prepared_stud(adapter, truth=None, **parameters):
    """Stamp only identity properties; the purchased sheet has no PMI."""
    receipt = await build_91247A720(adapter, truth, **parameters)
    clear_dimensions_for_drawing(adapter)
    apply_drawing_properties(adapter, PART_NAME)
    return receipt


async def build(adapter) -> dict[str, str]:
    artefacts = await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "91247A720",
                _prepared_stud,
                RigidTransform(translation_mm=(0.0, GB_LEN - GB_UNDERSIDE, 0.0)),
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
