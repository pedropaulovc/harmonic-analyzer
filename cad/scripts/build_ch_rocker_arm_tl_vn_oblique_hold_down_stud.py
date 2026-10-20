r"""Purchased 1/2-13 x 3 in hold-down stud, PM 52PCCK kit (MHA-CH-06-TL-VN-58).

The datasheet-built envelope of ``ch_rocker_arm_tl_vn_oblique_hold_down_stud_spec``
(no vendor CAD obtained): the stud's Front-plane half profile revolved about
+Y, a plain cylinder at the thread's major diameter with a 45 deg chamfer at
each end. y = 0 is the T-nut end. The axis is published as ``ScrewAxis``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_hold_down_stud.py
"""

from __future__ import annotations

import sys

import _config
from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import add_line_chain, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_polygon_chain
from ch_rocker_arm_tl_vn_oblique_hold_down_stud_spec import (
    DRAWING_NOTES,
    LENGTH,
    MAJOR_DIA,
    MATERIAL,
    PROFILE,
    VOLUME_MM3,
)

PART_NAME = "ch-rocker-arm-tl-vn-oblique-hold-down-stud"
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

    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check("axis centerline", await adapter.add_centerline(0.0, 0.0, 0.0, LENGTH))
    points = profile_points()
    profile = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    # The chain starts on the origin at the T-nut end and closes along the axis
    # from the nut end, so the centerline merges into its two axis corners.
    await define_polygon_chain(adapter, profile, points, label="stud")
    await ensure_fully_defined(adapter, "stud profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    check("revolve stud", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stud")
    await volume_check(adapter, "stud", VOLUME_MM3, 0.005 * VOLUME_MM3)
    await bbox_extent_check(adapter, "stud length", "y", LENGTH)
    await bbox_extent_check(adapter, "stud major diameter", "x", MAJOR_DIA)

    # --- Mate reference: the stud axis (Front Plane x Right Plane) -----------------
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "stud axis")
    name_last_feature(adapter, "ScrewAxis")

    await apply_material(adapter, MATERIAL)
    # The kit's black-oxide finish.
    await apply_color(adapter, PANEL_BLACK)
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
