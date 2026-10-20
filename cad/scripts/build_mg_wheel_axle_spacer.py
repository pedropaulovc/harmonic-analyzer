r"""Reproduction script: wheel-axle spacer (MHA-MG-11; ch. 21; 1 used).

The turned brass sleeve on the mg-wheel-axle between the mg-wheel-bar's front
face and the MHA-MG-VN-54 back washer (``mg_wheel_axle_spacer_spec``).  Its
length carries the magnifying wheel off the bar onto the pen-rod line, so it
is derived from ``paper_drive_geom.PEN_Z_MID``; it sets the wheel's station on
the pin's thread stack, so it carries an explicit band.  The bore is a drilled
clearance on the pin.

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
length, so the bar-side face is the Front Plane (z = 0) and the washer face is
at z = LENGTH.  ``Axis1`` is the bore axis (Top Plane x Right Plane, the local
Z axis).  The magnifier assembly places it like the washers and locks its
Front Plane to the axle's.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_wheel_axle_spacer.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _part_pmi import author_part_pmi
from mg_wheel_axle_spacer_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    LENGTH,
    LENGTH_BAND,
    OD,
    SURFACE_FINISHES,
)

PART_NAME = "mg-wheel-axle-spacer"
MATERIAL = "Brass"  # C36000 free-machining brass bar

V_RING = math.pi * ((OD / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "SpacerOd", f"{OD}mm")
    await set_global(adapter, "SpacerBore", f"{BORE_DIA}mm")
    await set_global(adapter, "SpacerLength", f"{LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "spacer OD",
        dims=ring,
        names=("OdCx", "OdCy", "SpacerOd"),
        drives=(None, None, '"SpacerOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "spacer bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "SpacerBore"),
        drives=(None, None, '"SpacerBore"'),
    )
    await ensure_fully_defined(adapter, "spacer sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude spacer",
        await adapter.create_extrusion(ExtrusionParameters(depth=LENGTH)),
    )
    name_last_feature(adapter, "Spacer")
    spacer_depth = name_dimensions(adapter, "Spacer", ["SpacerLength"])
    drive_jobs.append((spacer_depth[0], '"SpacerLength"'))
    await volume_check(adapter, "spacer", V_RING, 0.005 * V_RING)
    await bbox_extent_check(adapter, "spacer length", "z", LENGTH)
    await bbox_extent_check(adapter, "spacer O.D.", "x", OD)

    # Axis1: the bore axis, model Z (Top Plane x Right Plane).
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "spacer bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"spacer bore axis came back {axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven spacer (equations neutral)", V_RING, 0.005 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The length sets the wheel's station on the pin: its explicit band.  The
    # O.D. and the drilled bore take the title block's rows.
    set_dimension_symmetric_tolerance(adapter, "Spacer", "SpacerLength", LENGTH_BAND)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
