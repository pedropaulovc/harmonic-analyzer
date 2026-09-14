"""Build the installed McMaster-Carr 1330K524 counter spring.

The supplier-native recipe remains in its vendor frame (spring axis +X, origin
at mid-length, double-loop axes +Z) and intentionally preserves the vendor's
two touching solid bodies.  Assembly placement owns the vendor-to-machine
transform.  ``INSTALLED_LENGTH_MM`` is the actual reference mount pose's
catalogue inside-loop length.

Run with SolidWorks open::

    uv run python cad\\scripts\\build_counter_spring.py
"""

from __future__ import annotations

import sys

import _config
from _common import (
    SPRING_BLACK,
    apply_color,
    apply_custom_properties,
    apply_material,
    check,
    force_rebuild,
    report_mass_properties,
    run_build,
    save_part_and_images,
)
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _saved_part_guard import require_saved_drawing_properties
from _stock_fastener import _blank_recipe_references
from counter_spring_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE
from counter_spring_spec import INSTALLED_LENGTH_MM
from diagnostics.diag_build_1330K524 import build_1330K524


PART_NAME = "counter-spring"
_PART = _config.parts(PART_NAME)
MATERIAL = str(_PART["material"])
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    try:
        await build_1330K524(adapter, None, length_mm=INSTALLED_LENGTH_MM)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")

    _blank_recipe_references(adapter)
    await force_rebuild(adapter)
    await apply_material(adapter, MATERIAL)
    # The uncoated music wire is dark as supplied; this is an appearance, not
    # an additional finish or coating requirement.
    await apply_color(adapter, SPRING_BLACK)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    clear_dimensions_for_drawing(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
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
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
