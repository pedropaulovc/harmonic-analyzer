r"""Reproduction script: channel anchor jam nut (MHA-CH-14; 20 used).

A turned brass round nut, #6-32 tapped through, one on each MHA-CH-VN-51
channel anchor, jammed against the MHA-SM-03 plate underside
(``ch_anchor_jam_nut_spec``).  One saw cut across the driven face gives the
two drive notches, the bore between them.

Layout: Front-plane disc at the origin (O.D.) extruded +Z by the thickness,
so the bearing face is the Front Plane (z = 0) and the driven face is at
z = THICKNESS.  The Hole Wizard tap runs through all from the bearing face.
The drive cut is a rectangle on ``DrivenFace`` (a Front Plane offset to the
driven face), running along X past the O.D. on both sides and SLOT_WIDTH wide
in Y, cut SLOT_DEPTH toward z = 0.  ``Axis1`` is the thread axis (Top Plane x
Right Plane, the local Z axis).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_anchor_jam_nut.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _holes import wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _visibility import blank_reference_geometry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _part_pmi import author_part_pmi
from ch_anchor_jam_nut_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    OD,
    OD_BAND,
    SLOT_DEPTH,
    SLOT_SPAN,
    SLOT_WIDTH,
    SURFACE_FINISHES,
    TAP_DRILL_DIA,
    TAP_SPEC,
    THICKNESS,
    UNIT,
)

PART_NAME = "ch-anchor-jam-nut"
MATERIAL = "Brass"  # C36000 free-machining brass round bar


def _strip_area(radius: float, half_width: float) -> float:
    """Area of a circle of ``radius`` lying within ``|y| <= half_width``."""
    h = min(half_width, radius)
    return 2.0 * (h * math.sqrt(radius**2 - h**2) + radius**2 * math.asin(h / radius))


V_DISC = math.pi * (OD / 2.0) ** 2 * THICKNESS
V_THREAD = math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * THICKNESS
# The cut removes the disc's strip under it, net of the already-void tap drill.
V_SLOT = SLOT_DEPTH * (
    _strip_area(OD / 2.0, SLOT_WIDTH / 2.0)
    - _strip_area(TAP_DRILL_DIA / 2.0, SLOT_WIDTH / 2.0)
)
V_TOTAL = V_DISC - V_THREAD - V_SLOT


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "NutOd", f"{OD}mm")
    await set_global(adapter, "NutThickness", f"{THICKNESS}mm")
    await set_global(adapter, "SlotWidth", f"{SLOT_WIDTH}mm")
    await set_global(adapter, "SlotDepth", f"{SLOT_DEPTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Disc: Front-plane O.D. circle extruded +Z ---------------------------
    disc = SketchDims()
    check("create_sketch nut", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "nut OD",
        dims=disc,
        names=("OdCx", "OdCy", "NutOd"),
        drives=(None, None, '"NutOd"'),
    )
    await ensure_fully_defined(adapter, "nut sketch")
    check("exit_sketch nut", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    drive_jobs += disc.apply(adapter, "NutProfile")
    check(
        "extrude nut",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Nut")
    nut_depth = name_dimensions(adapter, "Nut", ["NutThickness"])
    drive_jobs.append((nut_depth[0], '"NutThickness"'))
    volume = await volume_check(adapter, "nut disc", V_DISC, 0.005 * V_DISC)
    await bbox_extent_check(adapter, "nut thickness", "z", THICKNESS)
    await bbox_extent_check(adapter, "nut O.D.", "x", OD)

    # --- #6-32 UNC-2B through, from the bearing face --------------------------
    # Drilled while both faces are still whole, so the removed volume is the
    # plain tap-drill cylinder.
    thread = wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, 0.0, -1.0),
        f"jam nut thread ({TAP_SPEC.size} through)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += thread.placement_drive_jobs
    volume = await volume_check(
        adapter, "tapped through", volume - V_THREAD, 0.02 * V_THREAD
    )

    # --- Drive cut across the driven face ------------------------------------
    check(
        "create_plane DrivenFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=THICKNESS
            )
        ),
    )
    name_last_feature(adapter, "DrivenFace")
    slot = SketchDims()
    check("create_sketch drive slot", await adapter.create_sketch("DrivenFace"))
    await define_centered_rectangle(
        adapter,
        SLOT_SPAN / 2.0,
        SLOT_WIDTH / 2.0,
        "drive slot",
        dims=slot,
        name_width="SlotSpan",
        drive_width=None,
        name_depth="SlotWidth",
        drive_depth='"SlotWidth"',
    )
    await ensure_fully_defined(adapter, "drive slot sketch")
    check("exit_sketch drive slot", await adapter.exit_sketch())
    name_last_feature(adapter, "DriveSlotProfile")
    drive_jobs += slot.apply(adapter, "DriveSlotProfile")
    # Default cut direction runs opposite the plane normal: down into the nut.
    check(
        "cut drive slot",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SLOT_DEPTH)),
    )
    name_last_feature(adapter, "DriveSlot")
    blank_reference_geometry(adapter, (("DrivenFace", "PLANE"),))
    slot_depth = name_dimensions(adapter, "DriveSlot", ["SlotDepth"])
    drive_jobs.append((slot_depth[0], '"SlotDepth"'))
    await volume_check(adapter, "drive slot", volume - V_SLOT, 0.02 * V_SLOT)
    await bbox_extent_check(adapter, "nut thickness after cut", "z", THICKNESS)

    # Axis1: the thread axis, model Z (Top Plane x Right Plane).
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "jam nut thread axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"jam nut thread axis came back {axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven jam nut (equations neutral)", V_TOTAL, 0.01 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The O.D. carries its explicit band natively (its window is the wall
    # floor and the neighbouring nut); every other size takes the title
    # block's row for its places.
    set_dimension_symmetric_tolerance(
        adapter, "NutProfile", "NutOd", OD_BAND, display_unit=UNIT
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
