r"""Reproduction script: magnifying-lever vertical rod (book ch. 20, pp. 46-49).

The smaller vertical brass rod that slides along the magnifying lever in
the clamp block; the output fixture rides on it and the wire to the
magnifying wheel hooks below. Plain rod with domed ends, like the lever.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — Ø5 x ~150, photo-scaled
against the lever rod (low).

Layout: rod axis along +X from the origin, revolved about a centerline
(orient vertically at assembly).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_vertical_rod.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
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
from magnifying_vertical_rod_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    ISO_VIEW_NOTE,
    ROD_DIA,
    ROD_LENGTH,
)

PART_NAME = "magnifying-vertical-rod"
MATERIAL = "Brass"  # see _common.apply_material docstring

R = ROD_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): rod length + diameter. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 150 = 150 in).
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, ROD_LENGTH, 0.0),
    )
    top = check(
        "add_line top",
        await adapter.add_line(R, R, ROD_LENGTH - R, R),
    )
    cap_right = check(
        "add_arc right dome",
        await adapter.add_arc(ROD_LENGTH - R, 0.0, ROD_LENGTH, 0.0, ROD_LENGTH - R, R),
    )
    axis_line = check(
        "add_line axis",
        await adapter.add_line(ROD_LENGTH, 0.0, 0.0, 0.0),
    )
    cap_left = check(
        "add_arc left dome",
        await adapter.add_arc(R, 0.0, R, R, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    # Same scheme as build_magnifying_lever: origin corner + dome centres
    # anchored, one radial dim (the left dome's radius is forced by its
    # anchored centre + the anchored origin end), top edge horizontal and
    # aligned over the left centre; merged centerline unconstrained.
    check(
        "anchor origin corner",
        await adapter.add_sketch_constraint(
            f"{axis_line}.end", "origin", "coincident"
        ),
    )
    check(
        "axis line horizontal",
        await adapter.add_sketch_constraint(axis_line, None, "horizontal"),
    )
    # Record each manual dim into SketchDims as it is emitted (creation order):
    # the two on-axis dome-centre X distances (one dim each -- y is 0, a relation),
    # then the right dome's radius. Three display dims; the left dome's radius is
    # forced by its anchored centre + the anchored origin end, so it is not a dim.
    await anchor_point_to_origin(
        adapter, f"{cap_left}.center", R, 0.0, "left dome centre"
    )
    profile.record("LeftDomeCentre", '"RodDia" / 2')
    await anchor_point_to_origin(
        adapter, f"{cap_right}.center", ROD_LENGTH - R, 0.0, "right dome centre"
    )
    profile.record("RightDomeCentre", '"RodLength" - "RodDia" / 2')
    check(
        "right dome radius",
        await adapter.add_sketch_dimension(cap_right, None, "radial", R),
    )
    profile.record("DomeRadius", '"RodDia" / 2')
    check(
        "top horizontal",
        await adapter.add_sketch_constraint(top, None, "horizontal"),
    )
    check(
        "top start over left centre",
        await adapter.add_sketch_constraint(
            f"{top}.start", f"{cap_left}.center", "vertical_points"
        ),
    )
    await ensure_fully_defined(adapter, "rod profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += profile.apply(adapter, "RodProfile")

    check(
        "revolve rod",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Rod")

    # Capsule volume: cylinder body (length L - 2R) + a full sphere of radius R
    # from the two hemispherical domes.
    v_rod = math.pi * R**2 * (ROD_LENGTH - 2.0 * R) + (4.0 / 3.0) * math.pi * R**3
    await volume_check(adapter, "rod", v_rod, 0.005 * v_rod)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven rod (equations neutral)", v_rod, 0.005 * v_rod)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
