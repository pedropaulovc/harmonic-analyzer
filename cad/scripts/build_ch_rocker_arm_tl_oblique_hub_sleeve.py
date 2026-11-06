r"""Reproduction script: oblique-trammel hub sleeve (MHA-CH-06-TL-34).

The loose turned steel sleeve on the TL-33 stud's shank inside the TL-24
riser's HUB clearance (``ch_rocker_arm_tl_oblique_hub_sleeve_spec``): a .580
O.D., a .4000 reamed bore and a length matched to the actual riser.

Layout: Front-plane annulus at the origin (O.D., bore) extruded +Z by the
length, so the carrier-side face is the Front Plane (z = 0) and the
strap-side face is at z = LENGTH.  ``Axis1`` is the bore axis (Top Plane x
Right Plane, the local Z axis).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_hub_sleeve.py
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
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
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
from ch_rocker_arm_tl_oblique_hub_sleeve_spec import (
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ID,
    LENGTH,
    OD,
    STEM,
    UNIT,
)

PART_NAME = STEM
MATERIAL = "Plain Carbon Steel"  # 1018 bar; see _appearance.apply_material

V_RING = math.pi * ((OD / 2.0) ** 2 - (ID / 2.0) ** 2) * LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "SleeveOd", f"{OD}mm")
    await set_global(adapter, "SleeveBore", f"{ID}mm")
    await set_global(adapter, "SleeveLength", f"{LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: O.D. + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch sleeve", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        OD / 2.0,
        "sleeve OD",
        dims=ring,
        names=("OdCx", "OdCy", "SleeveOd"),
        drives=(None, None, '"SleeveOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        ID / 2.0,
        "sleeve bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "SleeveBore"),
        drives=(None, None, '"SleeveBore"'),
    )
    await ensure_fully_defined(adapter, "sleeve sketch")
    check("exit_sketch sleeve", await adapter.exit_sketch())
    name_last_feature(adapter, "SleeveProfile")
    drive_jobs += ring.apply(adapter, "SleeveProfile")
    check(
        "extrude sleeve",
        await adapter.create_extrusion(ExtrusionParameters(depth=LENGTH)),
    )
    name_last_feature(adapter, "Sleeve")
    length = name_dimensions(adapter, "Sleeve", ["SleeveLength"])
    drive_jobs.append((length[0], '"SleeveLength"'))
    await volume_check(adapter, "sleeve", V_RING, 0.005 * V_RING)
    await bbox_extent_check(adapter, "sleeve length", "z", LENGTH)
    await bbox_extent_check(adapter, "sleeve O.D.", "x", OD)

    # Axis1: the bore axis, model Z (Top Plane x Right Plane).
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "sleeve bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"sleeve bore axis came back {axis!r}, not Axis1")
    blank_reference_geometry(adapter, ((axis, "AXIS"),))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven sleeve (equations neutral)", V_RING, 0.005 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The reamed bore carries its fit band; the O.D. and the matched length
    # take the title block's rows (the length's acceptance is its callout).
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band), display_unit=UNIT
        )
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
