r"""Purchased 1/2-13 flange nut, PM 52PCCK kit (MHA-CH-06-TL-VN-60).

The datasheet-built envelope of ``ch_rocker_arm_tl_vn_oblique_flange_nut_spec``
(no vendor CAD obtained). Both sections are sketched on the Top Plane (the
flange's bearing face; sketch (u, v) = model (X, -Z)), and a Top Plane boss
runs +Y:

1. the round flange, extruded ``FLANGE_THICK``;
2. the hex, extruded the nut's full ``HEIGHT`` through the flange;
3. the 1/2-13 thread, a through-all Hole Wizard tapped hole placed on the
   bearing face at the origin, running up +Y.

The nut axis is published as ``ScrewAxis`` (Front Plane x Right Plane).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_flange_nut.py
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
from _holes import wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import add_line_chain, ensure_fully_defined
from _sketch_chains import define_polygon_chain
from _sketch_circle import define_circle
from ch_rocker_arm_tl_vn_oblique_flange_nut_spec import (
    DRAWING_NOTES,
    FLANGE_DIA,
    FLANGE_THICK,
    FLANGE_VOLUME,
    HEIGHT,
    HEX_OUTLINE,
    MATERIAL,
    SOLID_VOLUME,
    TAP_DRILL_DIA,
    TAP_SPEC,
    VOLUME_MM3,
)

PART_NAME = "ch-rocker-arm-tl-vn-oblique-flange-nut"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


def hex_points() -> list[tuple[float, float]]:
    """``HEX_OUTLINE`` (x, z) as Top Plane sketch points (u, v) = (X, -Z)."""
    return [(x, -z) for x, z in HEX_OUTLINE]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # --- 1. Flange -----------------------------------------------------------------
    check("create_sketch flange", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, FLANGE_DIA / 2.0, "flange")
    await ensure_fully_defined(adapter, "flange")
    check("exit_sketch flange", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeProfile")
    check(
        "extrude flange",
        await adapter.create_extrusion(ExtrusionParameters(depth=FLANGE_THICK)),
    )
    name_last_feature(adapter, "Flange")
    await volume_check(adapter, "flange", FLANGE_VOLUME, 0.005 * FLANGE_VOLUME)

    # --- 2. Hex ----------------------------------------------------------------------
    check("create_sketch hex", await adapter.create_sketch("Top"))
    points = hex_points()
    lines = await add_line_chain(adapter, points)
    await define_polygon_chain(adapter, lines, points, label="hex")
    await ensure_fully_defined(adapter, "hex")
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    check(
        "extrude hex",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEIGHT)),
    )
    name_last_feature(adapter, "Hex")
    await volume_check(adapter, "flange and hex", SOLID_VOLUME, 0.005 * SOLID_VOLUME)
    await bbox_extent_check(adapter, "nut height", "y", HEIGHT)
    await bbox_extent_check(adapter, "flange diameter", "x", FLANGE_DIA)

    # --- 3. Thread: tapped through from the bearing face ------------------------------
    wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"flange nut thread ({TAP_SPEC.size} through)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    await volume_check(adapter, "tapped flange nut", VOLUME_MM3, 0.005 * VOLUME_MM3)

    # --- Mate reference: the nut axis -------------------------------------------------
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "nut axis")
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
