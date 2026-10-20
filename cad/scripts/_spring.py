"""Production builder for McMaster-Carr 9432K31 channel springs.

The native supplier recipe owns the wire, coil, transition, and machine-hook
geometry.  This module only supplies the production lifecycle shared by the
canonical installed part and the assembly's no-render length variants.
``length_mm`` is the catalogue inside-hook length in the vendor +X frame.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any

import _config
import _telemetry
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _custom_properties import apply_custom_properties
from _part_checks import report_mass_properties
from _part_save import save_part_and_images
from _rebuild import active_configuration_name, force_rebuild
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _stock_fastener import _blank_recipe_references
from diagnostics.diag_build_9432K31 import build_9432K31


_PART = _config.parts("vn-channel-spring-installed")
MATERIAL = str(_PART["material"])
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


async def run_before_save(
    adapter: Any,
    part_name: str,
    before_save: Callable[[Any], Awaitable[None]],
) -> None:
    """Run a reference hook only when it preserves the installed active state.

    Both spring lifecycles must reject missing or changed configuration
    identities before their save/export pipeline can begin.
    """
    installed_configuration = active_configuration_name(adapter)
    if not installed_configuration:
        raise RuntimeError(
            f"{part_name}: installed configuration identity is unavailable"
        )
    await before_save(adapter)
    if active_configuration_name(adapter) != installed_configuration:
        raise RuntimeError(
            f"{part_name}: before_save changed the installed active configuration"
        )


@_telemetry.traced("spring.build_variant", label_param="part_name")
async def build_spring(
    adapter: Any,
    part_name: str,
    length_mm: float,
    *,
    views: Iterable[str] | None = None,
    drawing_properties: Mapping[str, str] | None = None,
    before_save: Callable[[Any], Awaitable[None]] | None = None,
) -> dict[str, str]:
    """Build and save one 9432K31 at a catalogue inside-hook length.

    ``views=[]`` preserves the assembly variant fast path: the SLDPRT and STL
    are saved but no per-part PNG views are rendered.  The canonical wrapper
    passes ``drawing_properties`` so its purchased-reference-sheet properties
    are applied before the single save/export operation.
    ``before_save`` adds canonical reference-only configurations after all
    installed geometry/property work; assembly length variants leave it unset.
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
    if before_save is not None:
        await run_before_save(adapter, part_name, before_save)

    if views is None:
        return await save_part_and_images(adapter, part_name)
    return await save_part_and_images(adapter, part_name, views)
