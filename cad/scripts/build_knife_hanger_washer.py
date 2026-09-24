r"""Purchased knife-hanger washer: McMaster 90126A211."""

from __future__ import annotations

from functools import wraps
import sys

from _common import _read_member, name_dimensions, run_build
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _fastener_catalog import fastener
from _saved_part_guard import require_saved_drawing_properties
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90126A211 import W_ID, W_OD, W_T, build_90126A211
from knife_hanger_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    INNER_DIAMETER_DIM,
    OUTER_DIAMETER_DIM,
    THICKNESS_DIM,
)

PART_NAME = "knife-hanger-washer"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

OUTER_DIA = W_OD
INNER_DIA = W_ID
THICKNESS = W_T

_REFERENCE_DIMENSION_ORDER = (
    ("AnnulusProfile", (OUTER_DIAMETER_DIM, INNER_DIAMETER_DIM)),
    ("WasherBody", (THICKNESS_DIM,)),
)
_REFERENCE_DIMENSION_VALUES_MM = {
    OUTER_DIAMETER_DIM: OUTER_DIA,
    INNER_DIAMETER_DIM: INNER_DIA,
    THICKNESS_DIM: THICKNESS,
}


def _author_reference_dimensions(adapter) -> None:
    """Name, precision, mark, and read back the supplier-model dimensions."""
    clear_dimensions_for_drawing(adapter)
    for feature_name, ordered_names in _REFERENCE_DIMENSION_ORDER:
        name_dimensions(adapter, feature_name, list(ordered_names))
    for feature_name, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature_name, ordered_names in _REFERENCE_DIMENSION_ORDER:
        for name in ordered_names:
            parameter = adapter.currentModel.Parameter(f"{name}@{feature_name}")
            if parameter is None:
                raise RuntimeError(
                    f"native washer dimension missing after naming: "
                    f"{name}@{feature_name}"
                )
            actual_mm = float(_read_member(parameter, "SystemValue")) * 1000.0
            expected_mm = _REFERENCE_DIMENSION_VALUES_MM[name]
            if abs(actual_mm - expected_mm) > 1e-6:
                raise RuntimeError(
                    f"{name}@{feature_name} native readback {actual_mm:g} mm "
                    f"!= authored {expected_mm:g} mm"
                )


@wraps(build_90126A211)
async def _prepared_washer(adapter, truth=None, **parameters):
    """Stamp identity and the three receiving-reference model dimensions."""
    receipt = await build_90126A211(adapter, truth, **parameters)
    _author_reference_dimensions(adapter)
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
