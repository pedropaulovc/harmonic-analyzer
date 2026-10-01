r"""Reproduction script: transgear stud shim (MHA-178; 1 used).

The turned steel washer under the MHA-082 stud's collar, on the MHA-164
arm's front face (``transgear_stud_shim_spec``).  It is faced to fit at
assembly, and the model is the shim as fitted to parts at their nominals.

Layout: Front-plane annulus at the origin (OD, bore) extruded +Z by the
thickness, so the collar face is the Front Plane (z = 0) and the arm face is
the ``ArmFace`` plane (z = THICKNESS).  ``Axis1`` is the bore axis (Top
Plane ∩ Right Plane).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_stud_shim.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from transgear_stud_shim_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ID,
    ID_BAND,
    OD,
    SURFACE_FINISHES,
    THICKNESS,
)

PART_NAME = "transgear-stud-shim"
MATERIAL = "Plain Carbon Steel"  # 12L14 / 1215 bar (the registry row names it)

DISC_DIA = OD
DISC_THICK = THICKNESS
BORE_DIA = ID

V_DISC = math.pi * ((DISC_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * DISC_THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "DiscDia", f"{DISC_DIA}mm")
    await set_global(adapter, "DiscThick", f"{DISC_THICK}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: OD + bore in ONE Front-plane sketch (both on-axis circles ->
    # only the two diameter dims emit), extruded once along +Z.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        DISC_DIA / 2.0,
        "shim OD",
        dims=ring,
        names=("OdCx", "OdCy", "DiscDia"),
        drives=(None, None, '"DiscDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "shim bore",
        dims=ring,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=DISC_THICK)),
    )
    name_last_feature(adapter, "Disc")
    disc_depth = name_dimensions(adapter, "Disc", ["DiscThick"])
    drive_jobs.append((disc_depth[0], '"DiscThick"'))
    await volume_check(adapter, "disc", V_DISC, 0.005 * V_DISC)
    await bbox_extent_check(adapter, "shim thickness", "z", DISC_THICK)
    await bbox_extent_check(adapter, "shim O.D.", "x", DISC_DIA)

    # The mate datums: the bore axis first, so it is Axis1; then the arm face,
    # driven by the thickness so it tracks a thickness edit.
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shim bore axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"shim bore axis came back {axis!r}, not Axis1")
    check(
        "create_plane ArmFace (Front Plane + DiscThick)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=DISC_THICK
            )
        ),
    )
    name_last_feature(adapter, "ArmFace")
    blank_reference_geometry(adapter, (("ArmFace", "PLANE"),))
    arm_offset = name_dimensions(adapter, "ArmFace", ["ArmFaceOffset"])
    drive_jobs.append((arm_offset[0], '"DiscThick"'))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shim (equations neutral)", V_DISC, 0.005 * V_DISC
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "BoreDia", *deviations(ID_BAND)
    )
    # The thickness is faced to fit at assembly: no band on the model; the
    # sheet prints it as a reference under its callout.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Both bearing faces, resolved by outward normal and offset: a shim
    # extruded -Z would have no +Z face at z = THICKNESS and refuse here.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
