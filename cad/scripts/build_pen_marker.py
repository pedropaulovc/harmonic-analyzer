r"""Reproduction script: pen marker (book ch. 24, pp. 60-63).

The marking pen itself: a round barrel with a conical tip, held by the
pen rod's v-block at ~12 degrees so the tip rides the platen paper.
Modeled as a plain barrel + cone (the book pen's collar/ferrule detail
omitted -- simplification).

Layout: axis +Y from the tip at the origin; cone 12 tall, barrel to
y 60. Dimensions: cad/DIMENSIONS.md ch. 24 (M6.4, low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_marker.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
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
    BARREL_DIA,
    BARREL_TOP_Y,
    CONE_H,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    SURFACE_FINISHES,
)

PART_NAME = "pen-marker"
MATERIAL = "Brass"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): barrel diameter, the barrel top, and
    # the tip-cone height. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units (an
    # unsuffixed 60 = 60 in, blowing the part up 25.4x).
    await set_global(adapter, "BarrelDia", f"{BARREL_DIA}mm")
    await set_global(adapter, "BarrelTopY", f"{BARREL_TOP_Y}mm")
    await set_global(adapter, "ConeH", f"{CONE_H}mm")

    drive_jobs: list[tuple[str, str]] = []

    r = BARREL_DIA / 2.0
    profile_dims = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, BARREL_TOP_Y),
    )
    profile_pts = [
        (0.0, 0.0),
        (r, CONE_H),
        (r, BARREL_TOP_Y),
        (0.0, BARREL_TOP_Y),
    ]
    profile = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the tip/top profile corners at creation,
    # so the closed chain's own constraints define it too.
    # Emission order (anchor vertex 0 at origin = 0 dims; then segments 0..2,
    # segment 3 closes onto the anchor): segment 0 is general (cone flank ->
    # horizontal r then vertical ConeH), segment 1 is vertical (barrel side ->
    # BarrelTopY - ConeH), segment 2 is horizontal (barrel top -> r).
    await define_polygon_chain(
        adapter, profile, profile_pts, label="marker", dims=profile_dims,
        names=["ConeRadius", "ConeH", "BarrelLen", "BarrelRadius"],
        drives=['"BarrelDia" / 2', '"ConeH"', '"BarrelTopY" - "ConeH"', '"BarrelDia" / 2'],
    )
    await ensure_fully_defined(adapter, "marker profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "MarkerProfile")
    drive_jobs += profile_dims.apply(adapter, "MarkerProfile")
    check("revolve marker", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Marker")

    expected = math.pi * r * r * (CONE_H / 3.0 + (BARREL_TOP_Y - CONE_H))
    await volume_check(adapter, "marker", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven marker (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    # The ch24 macro shows a bright nickel/steel marker body, not brass —
    # keep the brass mass model, override the display colour.
    await apply_color(adapter, POLISHED_STEEL)
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
