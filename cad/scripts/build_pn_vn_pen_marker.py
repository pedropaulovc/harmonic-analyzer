r"""Purchased pen marker: Sharpie permanent marker, fine point (MHA-PN-VN-56).

The stock marker that writes the curve (engineerguy 4/4 video 9:15-10:34
used the Mini; this build takes the regular Fine Point, the format Brazil's
markers share), modelled uncapped as it is used: one solid
of revolution through the ``pn_vn_pen_marker_spec.PROFILE`` stations (nib,
nose cone, the cap-seat grip that lies in the v-block groove, the tapered
silver body and its domed back end). The spec records which stations are
sourced, photo-scaled or estimated.

Frame: the origin is at the nib tip and +Y runs along the axis to the back
end (the profile is sketched on the Front plane and revolved about Y).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_vn_pen_marker.py
"""

from __future__ import annotations

import sys

import _config
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import apply_drawing_properties
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import add_line_chain, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_polygon_chain
from pn_vn_pen_marker_spec import (
    DRAWING_NOTES,
    MATERIAL,
    OVERALL_LENGTH,
    PROFILE,
    VOLUME_MM3,
)

PART_NAME = "pn-vn-pen-marker"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


def profile_points() -> list[tuple[float, float]]:
    """``PROFILE`` as Front-plane sketch points: x = radius, y = axial station."""
    return [(r, y) for y, r in PROFILE]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, OVERALL_LENGTH),
    )
    points = profile_points()
    profile = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    # The chain starts at the nib tip on the origin and closes along the axis
    # from the back end, so the centerline merges into its two axis corners.
    await define_polygon_chain(adapter, profile, points, label="marker")
    await ensure_fully_defined(adapter, "marker profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "MarkerProfile")
    check(
        "revolve marker", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Marker")
    await volume_check(adapter, "marker", VOLUME_MM3, 0.005 * VOLUME_MM3)

    await apply_material(adapter, MATERIAL)
    # The silver barrel; the ink-coloured grip and nose are not split out.
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
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
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
