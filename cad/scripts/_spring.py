"""Production authoring for McMaster-Carr 9432K31 channel springs.

The native supplier recipe owns the wire, coil, transition, and machine-hook
geometry.  This module supplies the lifecycle shared by the canonical
installed part (one configuration per installed length,
``build_ch_vn_channel_spring_installed``) and the native seat calibration's
single-length fixture springs (``diagnostics/calibrate_spring_seats``).
``length_mm`` is the catalogue inside-hook length in the vendor +X frame.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import _config
import _telemetry
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _custom_properties import apply_custom_properties
from _part_checks import report_mass_properties
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _stock_fastener import _blank_recipe_references
from diagnostics.diag_build_9432K31 import build_9432K31


_PART = _config.parts("ch-vn-channel-spring-installed")
MATERIAL = str(_PART["material"])
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


@_telemetry.traced("spring.author_length", label_param="suffix")
def author_spring(adapter: Any, length_mm: float, *, suffix: str = "") -> None:
    """Author one 9432K31 body at ``length_mm`` into the active configuration.

    The configuration must hold no live solid. ``suffix`` names this length's
    recipe features (``diag_build_9432K31.feature_names``); its construction
    references are hidden at once, while they are live in this configuration.
    """
    try:
        build_9432K31(adapter, None, length_mm=length_mm, suffix=suffix)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")
    _blank_recipe_references(adapter)


def finish_spring(adapter: Any) -> None:
    """Material and display colour of the active configuration's spring."""
    apply_material(adapter, MATERIAL)
    apply_color(adapter, POLISHED_STEEL)


@_telemetry.traced("spring.build_fixture", label_param="part_name")
def build_spring(
    adapter: Any,
    part_name: str,
    length_mm: float,
    *,
    views: Iterable[str] = (),
) -> dict[str, str]:
    """Build and save one single-configuration 9432K31 at ``length_mm``.

    The calibration fixture path: the SLDPRT and STL are saved and, with the
    default ``views=()``, no per-part PNG view is rendered.
    """
    check("create_part", adapter.create_part())
    author_spring(adapter, length_mm)
    force_rebuild(adapter)
    finish_spring(adapter)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    report_mass_properties(adapter)
    return save_part_and_images(adapter, part_name, views)
