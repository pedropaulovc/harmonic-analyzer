r"""Reproduction script: regular Fine Point pen marker (book ch. 24).

The marker is an independently authored, sparse revolved silhouette: a narrow
writing end and holder neck, a tapered shoulder, a gently flared barrel, and a
rounded/tapered closed rear.  Its 123.11 mm by 12.24 mm product envelope is a
dimensional fact only; no third-party mesh or mesh topology is used.

Layout: axis +Y from the paper-contact writing point at the origin.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_marker.py
"""

from __future__ import annotations

import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from pen_marker_spec import (
    BARREL_FLARE_Y,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    MAX_DIAMETER,
    OVERALL_LENGTH,
    PROFILE_STATIONS,
    REAR_ROUND_DIAMETER,
    REAR_ROUND_Y,
    REAR_TAPER_DIAMETER,
    REAR_TAPER_Y,
    SHOULDER_DIAMETER,
    SHOULDER_Y,
    SURFACE_FINISHES,
    TIP_POINT_DIAMETER,
    TIP_POINT_Y,
    TIP_NECK_DIAMETER,
    TIP_NECK_Y,
    revolved_profile_volume_mm3,
)

PART_NAME = "pen-marker"
MATERIAL = "Brass"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Every silhouette station is editable in Tools > Equations.  Explicit mm
    # suffixes are load-bearing because the template document uses inches.
    await set_global(adapter, "OverallLength", f"{OVERALL_LENGTH}mm")
    await set_global(adapter, "MaxDiameter", f"{MAX_DIAMETER}mm")
    await set_global(adapter, "TipPointY", f"{TIP_POINT_Y}mm")
    await set_global(adapter, "TipPointDia", f"{TIP_POINT_DIAMETER}mm")
    await set_global(adapter, "TipNeckY", f"{TIP_NECK_Y}mm")
    await set_global(adapter, "TipNeckDia", f"{TIP_NECK_DIAMETER}mm")
    await set_global(adapter, "ShoulderY", f"{SHOULDER_Y}mm")
    await set_global(adapter, "ShoulderDia", f"{SHOULDER_DIAMETER}mm")
    await set_global(adapter, "BarrelFlareY", f"{BARREL_FLARE_Y}mm")
    await set_global(adapter, "RearTaperY", f"{REAR_TAPER_Y}mm")
    await set_global(adapter, "RearTaperDia", f"{REAR_TAPER_DIAMETER}mm")
    await set_global(adapter, "RearRoundY", f"{REAR_ROUND_Y}mm")
    await set_global(adapter, "RearRoundDia", f"{REAR_ROUND_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile_dims = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, OVERALL_LENGTH),
    )
    profile_pts = [(radius, axial_y) for axial_y, radius in PROFILE_STATIONS]
    profile = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # Vertex 0 is the writing point at the origin.  Each sloped flank emits
    # radial then axial distance; the centerline closure emits no duplicate
    # dimension.  The drives below therefore expose every authored station
    # while keeping the sketch fully constrained and equation-neutral.
    await define_polygon_chain(
        adapter,
        profile,
        profile_pts,
        label="marker",
        dims=profile_dims,
        names=[
            "TipPointRadius",
            "TipPointY",
            "TipNeckRadialRise",
            "TipNeckRun",
            "ShoulderRadialRise",
            "ShoulderRun",
            "FlareRadialRise",
            "FlareRun",
            "RearTaperRadialDrop",
            "RearTaperRun",
            "RearRoundRadialDrop",
            "RearRoundRun",
            "RearClosureRadius",
            "RearClosureRun",
        ],
        drives=[
            '"TipPointDia" / 2',
            '"TipPointY"',
            '("TipNeckDia" - "TipPointDia") / 2',
            '"TipNeckY" - "TipPointY"',
            '("ShoulderDia" - "TipNeckDia") / 2',
            '"ShoulderY" - "TipNeckY"',
            '("MaxDiameter" - "ShoulderDia") / 2',
            '"BarrelFlareY" - "ShoulderY"',
            '("MaxDiameter" - "RearTaperDia") / 2',
            '"RearTaperY" - "BarrelFlareY"',
            '("RearTaperDia" - "RearRoundDia") / 2',
            '"RearRoundY" - "RearTaperY"',
            '"RearRoundDia" / 2',
            '"OverallLength" - "RearRoundY"',
        ],
    )
    await ensure_fully_defined(adapter, "marker profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "MarkerProfile")
    drive_jobs += profile_dims.apply(adapter, "MarkerProfile")
    check("revolve marker", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Marker")

    expected = revolved_profile_volume_mm3()
    await volume_check(adapter, "marker", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven marker (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    # A regular Fine Point marker reads as a dark molded body in the assembly;
    # retain the configured mass material while overriding only its appearance.
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
