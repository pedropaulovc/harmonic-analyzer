r"""Purchased 14 mm T-nut, 1/2-13, PM 52PCCK kit (MHA-CH-006-TL-39).

The datasheet-built envelope of ``ch_rocker_arm_tl_oblique_t_nut_spec`` (no
vendor CAD obtained):

1. the stepped foot-and-neck section, sketched on the Right Plane (sketch
   (u, v) = model (-Z, Y); the section is symmetric across the slot, so the
   sign of u does not matter) and extruded mid-plane along X, the slot
   direction;
2. the 1/2-13 thread, a through-all Hole Wizard tapped hole placed on the
   foot's bottom face at the origin, running up +Y.

The thread axis is published as ``ScrewAxis`` (Front Plane x Right Plane).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_t_nut.py
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
from _sketch_chains import define_rectilinear_chain
from ch_rocker_arm_tl_oblique_t_nut_spec import (
    BLOCK_VOLUME,
    DRAWING_NOTES,
    FOOT_WIDTH,
    HEIGHT,
    LENGTH,
    MATERIAL,
    PROFILE,
    TAP_DRILL_DIA,
    TAP_SPEC,
    VOLUME_MM3,
)

PART_NAME = "ch-rocker-arm-tl-oblique-t-nut"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}


def profile_points() -> list[tuple[float, float]]:
    """``PROFILE`` as Right Plane sketch points: u = across the slot, v = +Y."""
    return list(PROFILE)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # --- 1. Foot and neck --------------------------------------------------------
    check("create_sketch section", await adapter.create_sketch("Right"))
    points = profile_points()
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(adapter, lines, points, label="T-nut section")
    await ensure_fully_defined(adapter, "T-nut section")
    check("exit_sketch section", await adapter.exit_sketch())
    name_last_feature(adapter, "SectionProfile")
    check(
        "extrude T-nut",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Body")
    await volume_check(adapter, "T-nut block", BLOCK_VOLUME, 0.005 * BLOCK_VOLUME)
    await bbox_extent_check(adapter, "length along the slot", "x", LENGTH)
    await bbox_extent_check(adapter, "height", "y", HEIGHT)
    await bbox_extent_check(adapter, "foot width", "z", FOOT_WIDTH)

    # --- 2. Thread: tapped through from the foot's bottom face ----------------------
    wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"T-nut thread ({TAP_SPEC.size} through)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    await volume_check(adapter, "tapped T-nut", VOLUME_MM3, 0.005 * VOLUME_MM3)

    # --- Mate reference: the thread axis -------------------------------------------
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "thread axis")
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
