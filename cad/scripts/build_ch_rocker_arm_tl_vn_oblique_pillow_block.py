r"""Purchased KP08 pillow block, AMPEC (MHA-CH-06-TL-VN-56).

The datasheet-built envelope of ``ch_rocker_arm_tl_vn_oblique_pillow_block_spec``
(no vendor CAD obtained): one solid of the full unverified axial width, the
insert bearing included. Built on the Top Plane (the axial mid-plane), whose
sketch (u, v) is model (X, -Z), each section extruded mid-plane by the width:

1. the foot and the pedestal under the boss (one rectilinear outline);
2. the boss, a disc on the bore axis whose crown is the overall height;
3. the Ø8 bore, cut through along +/-Y;
4. the two bolt holes, cut on the Front Plane (the foot's bottom face).

The bore axis is published as ``ScrewAxis`` (Front Plane + ``AXIS_HEIGHT``
intersected with the Right Plane).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_pillow_block.py
"""

from __future__ import annotations

import sys

import _config
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _supplier_screw_reference import add_supplier_reference_sketch
import ch_rocker_arm_tl_vn_oblique_pillow_block_spec as supplier
from ch_rocker_arm_tl_vn_oblique_pillow_block_spec import (
    AXIS_HEIGHT,
    BASE_AREA,
    BASE_OUTLINE,
    BOSS_RADIUS,
    BOSS_UPPER_AREA,
    BORE_DIA,
    DRAWING_NOTES,
    FOOT_THICK,
    HEIGHT,
    HOLE_DIA,
    HOLE_X,
    LENGTH,
    MATERIAL,
    VOLUME_MM3,
    WIDTH,
)

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pillow-block"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


def top_plane_point(x: float, z: float) -> tuple[float, float]:
    """Model (x, z) on the Top Plane as its sketch (u, v) = (X, -Z)."""
    return (x, -z)


def base_profile_points() -> list[tuple[float, float]]:
    """``BASE_OUTLINE`` as Top Plane sketch points."""
    return [top_plane_point(x, z) for x, z in BASE_OUTLINE]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # --- 1. Foot and pedestal ----------------------------------------------------
    check("create_sketch base", await adapter.create_sketch("Top"))
    points = base_profile_points()
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(adapter, lines, points, label="foot and pedestal")
    await ensure_fully_defined(adapter, "foot and pedestal")
    check("exit_sketch base", await adapter.exit_sketch())
    name_last_feature(adapter, "BaseProfile")
    check(
        "extrude base",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Base")
    base_volume = WIDTH * BASE_AREA
    await volume_check(adapter, "foot and pedestal", base_volume, 0.005 * base_volume)

    # --- 2. Boss on the bore axis --------------------------------------------------
    boss_volume = WIDTH * (BASE_AREA + BOSS_UPPER_AREA)
    check("create_sketch boss", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, *top_plane_point(0.0, AXIS_HEIGHT), BOSS_RADIUS, "boss"
    )
    await ensure_fully_defined(adapter, "boss")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    check(
        "extrude boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Boss")
    await volume_check(adapter, "housing", boss_volume, 0.005 * boss_volume)
    await bbox_extent_check(adapter, "overall height", "z", HEIGHT)

    # --- 3. Bore (the insert bearing's inner ring) -------------------------------
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, *top_plane_point(0.0, AXIS_HEIGHT), BORE_DIA / 2.0, "bore"
    )
    await ensure_fully_defined(adapter, "bore")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    # Mid-plane, past both faces of the WIDTH envelope.
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=WIDTH + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")

    # --- 4. Bolt holes through the foot ------------------------------------------
    # Front Plane sketch (u, v) = model (X, Y). Mid-plane about the foot's bottom
    # face, deeper than the foot: only the foot stands at x = +/- BOLT_SPACING/2.
    check("create_sketch bolt holes", await adapter.create_sketch("Front"))
    for x in HOLE_X:
        await define_circle(adapter, x, 0.0, HOLE_DIA / 2.0, f"bolt hole x {x:g}")
    await ensure_fully_defined(adapter, "bolt holes")
    check("exit_sketch bolt holes", await adapter.exit_sketch())
    name_last_feature(adapter, "BoltHoleProfile")
    check(
        "cut bolt holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (FOOT_THICK + 1.0), both_directions=True)
        ),
    )
    name_last_feature(adapter, "BoltHoles")
    await volume_check(adapter, "pillow block", VOLUME_MM3, 0.005 * VOLUME_MM3)
    await bbox_extent_check(adapter, "overall length", "x", LENGTH)
    await bbox_extent_check(adapter, "axial width envelope", "y", WIDTH)

    # --- Mate reference: the bore axis ---------------------------------------------
    await name_bore_axis(
        adapter, "Front Plane", AXIS_HEIGHT, "Right Plane", 0.0, "KP08 bore axis"
    )
    name_last_feature(adapter, "ScrewAxis")

    await apply_material(adapter, MATERIAL)
    # The zinc-alloy housing's bright cast finish.
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    # The plan view's reference sizes: hidden construction chords whose
    # dimensions the purchased sheet imports.
    await add_supplier_reference_sketch(
        adapter,
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
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
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
