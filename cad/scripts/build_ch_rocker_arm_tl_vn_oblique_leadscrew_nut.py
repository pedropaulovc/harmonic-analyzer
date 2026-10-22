r"""Bought Tr8x2 brass flange nut: ZYLtech regular nut (MHA-CH-06-TL-VN-55).

The nut that drives the oblique trammel jig's carriage 1 from the leadscrew.
It is one solid, built from ``ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec``,
which records each value's source. The build:

- revolves the spigot, flange and long body round the Ø6.0 thread-minor
  bore (``NutProfile`` -> ``Nut``);
- cuts the four plain Ø3.5 flange holes on the PCD 16 (``FlangeHoleSketch``
  -> ``FlangeHoles``).

The thread is not modelled. Datasheet-built: no vendor CAD obtained.

Frame: the axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the flange's bracket-side face, the spigot is below it, and the long
body points toward +Y.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_leadscrew_nut.py
"""

from __future__ import annotations

import sys

import _config
from _appearance import apply_material
from _bought_revolve import (
    SAVED_PROPERTIES,
    publish_screw_axis,
    revolve_profile,
    stock_properties,
)
from _check import check
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import ensure_fully_defined
from _sketch_circle import define_circle
from _supplier_screw_reference import add_supplier_reference_sketch
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as supplier
from ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec import (
    BODY_VOLUME_MM3,
    DRAWING_NOTES,
    FAR_END_Y,
    FLANGE_THICK,
    HOLE_CENTRES,
    HOLE_DIA,
    MATERIAL,
    PROFILE,
    VOLUME_MM3,
)

PART_NAME = "ch-rocker-arm-tl-vn-oblique-leadscrew-nut"
STOCK_PROPERTIES = stock_properties(_config.parts(PART_NAME))


def profile_points() -> list[tuple[float, float]]:
    """``PROFILE`` as Front-plane sketch points: x = radius, y = station."""
    return list(PROFILE)


def hole_sketch_points() -> list[tuple[float, float]]:
    """The flange-hole centres on the Top plane (y = 0, the flange's bracket
    face). The Top sketch reads model (x, -z); the 45° square pattern is
    symmetric about both axes, so the sign is moot."""
    return [(x, -z) for x, z in HOLE_CENTRES]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    await revolve_profile(
        adapter,
        "Front",
        "nut",
        profile_points(),
        ("NutProfile", "Nut"),
        free_axis_length=FAR_END_Y,
    )
    await volume_check(adapter, "nut body", BODY_VOLUME_MM3, 0.002 * BODY_VOLUME_MM3)

    # Four plain flange holes, cut mid-plane from the flange's bracket face:
    # 2 x FLANGE_THICK deep reaches through the flange on +Y, and on -Y it
    # meets only air (the spigot is inside the hole circle).
    check("create_sketch flange holes", await adapter.create_sketch("Top"))
    for index, (u, v) in enumerate(hole_sketch_points(), start=1):
        await define_circle(adapter, u, v, HOLE_DIA / 2.0, f"flange hole {index}")
    await ensure_fully_defined(adapter, "flange hole sketch")
    check("exit_sketch flange holes", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeHoleSketch")
    check(
        "cut flange holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * FLANGE_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FlangeHoles")
    await volume_check(adapter, "flange nut", VOLUME_MM3, 0.002 * VOLUME_MM3)

    await publish_screw_axis(adapter)

    # Brass carries its own appearance (the build_dt_crank_pin_ring idiom).
    await apply_material(adapter, MATERIAL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    await add_supplier_reference_sketch(
        adapter,
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
    )
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, SAVED_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
