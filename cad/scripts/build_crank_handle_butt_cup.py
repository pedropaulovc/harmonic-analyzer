r"""Build MHA-153, the plain steel cup at the butt of the crank handle.

User ruling 2026-09-29 (ch11 p.14/p.15 photographs): the butt of the ebonized
grip carries a bright steel cup with the pivot screw's slotted head recessed
inside it.  The body is epoxied into the MHA-022 counterbore, face flush, and
MHA-139's head bears on the floor; user rulings 2026-09-30 (concept v4) made it
a plain cup, the handle's end round turned across oak and cup together.
Dimensions live in ``crank_handle_butt_cup_spec``.

Layout: one revolve about local +X.  The cup's outer face is the origin
plane (x=0); the body and floor run toward -X, into the handle, so in
the handle's frame the cup sits at the basic overall length with the handle's
own orientation.  ``Axis1`` is the cup axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_handle_butt_cup.py
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
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from crank_handle_butt_cup_spec import (
    BODY_DIA,
    BODY_DIA_TOL,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLOOR_HOLE_DIA,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    POCKET_DEPTH,
    POCKET_DEPTH_TOL,
    POCKET_DIA,
)

PART_NAME = "crank-handle-butt-cup"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

BODY_R = BODY_DIA / 2.0
POCKET_R = POCKET_DIA / 2.0
FLOOR_HOLE_R = FLOOR_HOLE_DIA / 2.0
V_CUP = math.pi * (
    BODY_R**2 * OVERALL_LENGTH
    - POCKET_R**2 * POCKET_DEPTH
    - FLOOR_HOLE_R**2 * (OVERALL_LENGTH - POCKET_DEPTH)
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_crankshaft).
    for name, value in (
        ("BodyDia", BODY_DIA),
        ("OverallLength", OVERALL_LENGTH),
        ("PocketDia", POCKET_DIA),
        ("PocketDepth", POCKET_DEPTH),
        ("FloorHoleDia", FLOOR_HOLE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped section on the Front plane, revolved about the X axis: pocket
    # mouth -> face -> body OD -> bottom -> floor hole -> floor top -> pocket
    # wall.  Nothing touches the axis: the
    # floor hole passes the screw shoulder.
    profile = SketchDims()
    check("create_sketch cup profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "cup axis centerline",
        await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0),
    )
    points = [
        (0.0, POCKET_R),
        (0.0, BODY_R),
        (-OVERALL_LENGTH, BODY_R),
        (-OVERALL_LENGTH, FLOOR_HOLE_R),
        (-POCKET_DEPTH, FLOOR_HOLE_R),
        (-POCKET_DEPTH, POCKET_R),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    face, body_od, bottom, floor_hole, floor_top, pocket_wall = lines
    check("axis horizontal", await adapter.add_sketch_constraint(axis, None, "horizontal"))
    for index, line in enumerate(lines):
        (u0, v0), (u1, v1) = points[index], points[(index + 1) % len(points)]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"cup profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "axis starts at the origin",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "face on the origin plane",
        await adapter.add_sketch_constraint(f"{face}.start", "origin", "vertical_points"),
    )
    # Dimensions in creation order.
    check(
        "axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", OVERALL_LENGTH),
    )
    profile.record("AxisLength", '"OverallLength"')
    check(
        "cup overall length",
        await adapter.add_sketch_dimension(body_od, None, "linear", OVERALL_LENGTH),
    )
    profile.record("OverallLength", '"OverallLength"')
    # Every axial size reads from the face (MHA-153 re-review); the
    # floor is what the overall leaves.
    check(
        "pocket depth",
        await adapter.add_sketch_dimension(pocket_wall, None, "linear", POCKET_DEPTH),
    )
    profile.record("PocketDepth", '"PocketDepth"')
    for name, line, u_mid, radius in (
        ("BodyDia", body_od, -OVERALL_LENGTH / 2.0, BODY_R),
        ("PocketDia", pocket_wall, -POCKET_DEPTH / 2.0, POCKET_R),
        ("FloorHoleDia", floor_hole, -(POCKET_DEPTH + OVERALL_LENGTH) / 2.0, FLOOR_HOLE_R),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 3.0), name
        )
        profile.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "cup profile sketch")
    check("exit_sketch cup profile", await adapter.exit_sketch())
    name_last_feature(adapter, "CupProfile")
    drive_jobs += profile.apply(adapter, "CupProfile")
    check("revolve cup", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Cup")
    await volume_check(adapter, "butt cup", V_CUP, 0.005 * V_CUP)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "cup axis")

    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven butt cup (equations neutral)", V_CUP, 0.005 * V_CUP
    )

    # The model-owned bands (policy rule 2): the body diameter that holds the
    # pocket wall, and the pocket depth that keeps the MHA-139 head below the
    # face.  Every other size is routine (.X); the pocket is bored to suit
    # the head's diameter.
    set_dimension_symmetric_tolerance(adapter, "CupProfile", "BodyDia", BODY_DIA_TOL)
    set_dimension_symmetric_tolerance(
        adapter, "CupProfile", "PocketDepth", POCKET_DEPTH_TOL
    )
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
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
