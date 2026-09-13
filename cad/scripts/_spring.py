"""Production builder for McMaster-Carr 9432K31 channel springs.

The native supplier recipe owns the wire, coil, transition, and machine-hook
geometry.  This module only supplies the production lifecycle shared by the
canonical installed part and the assembly's no-render length variants.
``length_mm`` is the catalogue inside-hook length in the vendor +X frame.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import _config
from _common import (
    POLISHED_STEEL,
    apply_color,
    apply_custom_properties,
    apply_material,
    check,
    force_rebuild,
    report_mass_properties,
    save_part_and_images,
)
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _stock_fastener import _blank_recipe_references
from diagnostics.diag_build_9432K31 import build_9432K31


_PART = _config.parts("channel-spring-installed")
MATERIAL = str(_PART["material"])
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


async def build_spring(
    adapter: Any,
    part_name: str,
    length_mm: float,
    *,
    views: Iterable[str] | None = None,
    drawing_properties: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build and save one 9432K31 at a catalogue inside-hook length.

    ``views=[]`` preserves the assembly variant fast path: the SLDPRT and STL
    are saved but no per-part PNG views are rendered.  The canonical wrapper
    passes ``drawing_properties`` so its purchased-reference-sheet properties
    are applied before the single save/export operation.
    """
    check("create_part", await adapter.create_part())
    try:
        await build_9432K31(adapter, None, length_mm=length_mm)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")

    _blank_recipe_references(adapter)
    await force_rebuild(adapter)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)

    if drawing_properties is not None:
        clear_dimensions_for_drawing(adapter)
        apply_drawing_properties(adapter, part_name, drawing_properties)

    await report_mass_properties(adapter)
    if views is None:
        return await save_part_and_images(adapter, part_name)
    return await save_part_and_images(adapter, part_name, views)
