r"""Reproduction script: oblique-trammel hub clamp washer (MHA-CH-06-TL-35).

The turned brass washer under the TL-VN-85 hub screw's low head
(``ch_rocker_arm_tl_oblique_hub_washer_spec``): the owner's Ø11 O.D. and a
#9 drilled bore, .06 thick.

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
thickness, so the strap-side face is the Front Plane (z = 0) and the
head-side face is at z = THICK.  ``Axis1`` is the bore axis (Top Plane x
Right Plane, the local Z axis).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_hub_washer.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_hub_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ID,
    OD,
    THICK,
)

PART_NAME = "ch-rocker-arm-tl-oblique-hub-washer"
MATERIAL = "Brass"  # C36000 free-machining brass rod

V_RING = math.pi * ((OD / 2.0) ** 2 - (ID / 2.0) ** 2) * THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "WasherOd", f"{OD}mm")
    await set_global(adapter, "WasherBore", f"{ID}mm")
    await set_global(adapter, "WasherThickness", f"{THICK}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch washer", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "washer OD",
        dims=ring,
        names=("OdCx", "OdCy", "WasherOd"),
        drives=(None, None, '"WasherOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        ID / 2.0,
        "washer bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "WasherBore"),
        drives=(None, None, '"WasherBore"'),
    )
    await ensure_fully_defined(adapter, "washer sketch")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    drive_jobs += ring.apply(adapter, "WasherProfile")
    check(
        "extrude washer",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICK)),
    )
    name_last_feature(adapter, "Washer")
    thickness = name_dimensions(adapter, "Washer", ["WasherThickness"])
    drive_jobs.append((thickness[0], '"WasherThickness"'))
    await volume_check(adapter, "washer", V_RING, 0.005 * V_RING)
    await bbox_extent_check(adapter, "washer thickness", "z", THICK)
    await bbox_extent_check(adapter, "washer O.D.", "x", OD)

    # Axis1: the bore axis, model Z (Top Plane x Right Plane).
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "washer bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"washer bore axis came back {axis!r}, not Axis1")
    blank_reference_geometry(adapter, ((axis, "AXIS"),))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven washer (equations neutral)", V_RING, 0.005 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # Every size takes the title block's rows: the O.D. .XXX, the drilled
    # bore DRILLED HOLES, the thickness .XX.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=())
    apply_drawing_properties(adapter, PART_NAME)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter, ("Number", "Material Specification", "Finish", "Quantity")
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
