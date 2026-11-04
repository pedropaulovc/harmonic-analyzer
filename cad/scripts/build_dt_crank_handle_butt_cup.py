r"""Build MHA-DT-35, the plain steel cup at the butt of the crank handle.

User ruling 2026-09-29 (ch11 p.14/p.15 photographs): the butt of the ebonized
grip carries a bright steel cup with the pivot screw's slotted head recessed
inside it.  The body is epoxied into the MHA-DT-08 counterbore, face flush, and
MHA-DT-32's head bears on the floor; user rulings 2026-09-30 (concept v4) made it
a plain cup with a flat face; the handle's end round is turned on the oak only.
Dimensions live in ``dt_crank_handle_butt_cup_spec``.
Owner ruling B on #1375 enlarges only the body and its stock; the unchanged
head pocket now retains the wall floor without a shortfall note or property.

Layout: one revolve about local +X.  The cup's outer face is the origin
plane (x=0); the body and floor run toward -X, into the handle, so in
the handle's frame the cup sits at the basic overall length with the handle's
own orientation.  ``Axis1`` is the cup axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_handle_butt_cup.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _fit_deviations import deviations
from dt_crank_handle_butt_cup_notes import ISOMETRIC_VIEW_NOTE
from dt_crank_handle_butt_cup_spec import (
    BODY_CHAMFER,
    BODY_CHAMFER_TOL,
    BODY_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLOOR_HOLE_DIA,
    OVERALL_LENGTH,
    POCKET_DEPTH,
    POCKET_DIA,
    POCKET_FLOOR_CORNER_R_BAND,
    POCKET_FLOOR_CORNER_R_MAX,
    POCKET_FLOOR_CORNER_R_TOL_TYPE,
    UNIT,
)

PART_NAME = "dt-crank-handle-butt-cup"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

BODY_R = BODY_DIA / 2.0
POCKET_R = POCKET_DIA / 2.0
FLOOR_HOLE_R = FLOOR_HOLE_DIA / 2.0
# The concave pocket corner fills the square outside a quarter disk.  Pappus:
# its area is r²(1-pi/4), and its first radial moment about R-r is r³/6.
V_POCKET_FLOOR_CORNER = 2.0 * math.pi * (
    (POCKET_R - POCKET_FLOOR_CORNER_R_MAX)
    * POCKET_FLOOR_CORNER_R_MAX**2
    * (1.0 - math.pi / 4.0)
    + POCKET_FLOOR_CORNER_R_MAX**3 / 6.0
)
V_CUP = math.pi * (
    BODY_R**2 * OVERALL_LENGTH
    - POCKET_R**2 * POCKET_DEPTH
    - FLOOR_HOLE_R**2 * (OVERALL_LENGTH - POCKET_DEPTH)
) - math.pi * BODY_CHAMFER**2 * (BODY_R - BODY_CHAMFER / 3.0) + V_POCKET_FLOOR_CORNER


def _pocket_floor_max_limit(adapter) -> None:
    """Model the corner at its upper limit and print a native radial MAX."""
    lower, upper = deviations(POCKET_FLOOR_CORNER_R_BAND)
    _, dimension = _named_dimension(adapter, "CupProfile", "PocketFloorRadius")
    label = "PocketFloorRadius@CupProfile"
    if not math.isclose(
        float(dimension.SystemValue),
        POCKET_FLOOR_CORNER_R_MAX / 1000.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(f"{label}: nominal is not the pocket corner's maximum")
    # Equation-owned dimensions can read DrivenState 1; IsReference is the
    # native controlling/reference distinction (draw_pd_platen_rack).
    if bool(dimension.IsReference()):
        raise RuntimeError(f"{label}: radius is a reference model dimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = POCKET_FLOOR_CORNER_R_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: MAX-limit tolerance values rejected")
    if (
        int(tolerance.Type) != POCKET_FLOOR_CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_dt_crankshaft).
    for name, value in (
        ("BodyDia", BODY_DIA),
        ("OverallLength", OVERALL_LENGTH),
        ("PocketDia", POCKET_DIA),
        ("PocketDepth", POCKET_DEPTH),
        ("FloorHoleDia", FLOOR_HOLE_DIA),
        ("BodyChamfer", BODY_CHAMFER),
        ("PocketFloorRadius", POCKET_FLOOR_CORNER_R_MAX),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped section on the Front plane, revolved about the X axis: pocket
    # mouth -> face -> body OD -> bottom chamfer -> bottom -> floor hole ->
    # flat floor -> tangent quarter arc -> pocket wall.  The round adds
    # material inside the pocket, within the head's minimum radial clearance.
    profile = SketchDims()
    check("create_sketch cup profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "cup axis centerline",
        await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0),
    )
    corner_r = POCKET_FLOOR_CORNER_R_MAX
    floor_round_center = (-POCKET_DEPTH + corner_r, POCKET_R - corner_r)
    floor_round_start = (-POCKET_DEPTH + corner_r, POCKET_R)
    floor_round_end = (-POCKET_DEPTH, POCKET_R - corner_r)
    points = [
        (0.0, POCKET_R),
        (0.0, BODY_R),
        (-(OVERALL_LENGTH - BODY_CHAMFER), BODY_R),
        (-OVERALL_LENGTH, BODY_R - BODY_CHAMFER),
        (-OVERALL_LENGTH, FLOOR_HOLE_R),
        (-POCKET_DEPTH, FLOOR_HOLE_R),
        floor_round_end,
    ]
    lines = await add_line_chain(adapter, points, close=False)
    # add_arc is CCW: wall -> floor is the 90-degree arc, not the 270-degree
    # complement.  Its traversal is opposite the surrounding line chain.
    floor_round = check(
        "pocket floor round",
        await adapter.add_arc(
            *floor_round_center, *floor_round_start, *floor_round_end
        ),
    )
    (pocket_wall,) = await add_line_chain(
        adapter, [floor_round_start, points[0]], close=False
    )
    set_sketch_direct_db(adapter, False)
    face, body_od, chamfer, bottom, floor_hole, floor_top = lines
    check("axis horizontal", await adapter.add_sketch_constraint(axis, None, "horizontal"))
    for line, (u0, v0), (u1, v1) in (
        *zip(lines, points, points[1:], strict=False),
        (pocket_wall, floor_round_start, points[0]),
    ):
        if u0 != u1 and v0 != v1:
            continue  # the 45-degree bottom chamfer; its two legs define it
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
    await dimension_between(
        adapter,
        f"{body_od}.start",
        f"{bottom}.start",
        "horizontal_distance",
        OVERALL_LENGTH,
        "cup overall length",
    )
    profile.record("OverallLength", '"OverallLength"')
    # Face to FLAT floor, not the wall segment: the tangent round shortens
    # that line by its radius without changing the head's recess.
    await dimension_between(
        adapter,
        f"{face}.start",
        f"{floor_top}.start",
        "horizontal_distance",
        POCKET_DEPTH,
        "cup pocket depth to the floor",
    )
    profile.record("PocketDepth", '"PocketDepth"')
    # The bottom chamfer's axial leg, and its radial leg equal to it by
    # equation: 45 degrees.
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "horizontal_distance",
        BODY_CHAMFER,
        "cup bottom chamfer",
    )
    profile.record("BodyChamfer", '"BodyChamfer"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "vertical_distance",
        BODY_CHAMFER,
        "cup bottom chamfer rise",
    )
    profile.record("BodyChamferRise", '"BodyChamfer"')
    for name, line, u_mid, radius in (
        ("BodyDia", body_od, -(OVERALL_LENGTH - BODY_CHAMFER) / 2.0, BODY_R),
        ("PocketDia", pocket_wall, -POCKET_DEPTH / 2.0, POCKET_R),
        ("FloorHoleDia", floor_hole, -(POCKET_DEPTH + OVERALL_LENGTH) / 2.0, FLOOR_HOLE_R),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 3.0), name
        )
        profile.record(name, f'"{name}"')
    check(
        "pocket floor radius",
        await adapter.add_sketch_dimension(
            floor_round, None, "radial", POCKET_FLOOR_CORNER_R_MAX
        ),
    )
    profile.record("PocketFloorRadius", '"PocketFloorRadius"')
    for first, second, label in (
        (floor_top, floor_round, "pocket floor"),
        (floor_round, pocket_wall, "pocket wall"),
    ):
        check(
            f"floor round tangent to {label}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
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

    # The model-owned band (drawing-simplicity-policy.md `How the repository
    # implements the guidelines`): the bottom chamfer that clears the
    # MHA-DT-08 floor corner.  The body diameter that holds the pocket wall and
    # the pocket depth that keeps the MHA-DT-32 head below the face print at
    # .XXX under the title block's band; the pocket is bored to suit the head.
    set_dimension_symmetric_tolerance(
        adapter, "CupProfile", "BodyChamfer", BODY_CHAMFER_TOL, display_unit=UNIT
    )
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _pocket_floor_max_limit(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Isometric View Note": ISOMETRIC_VIEW_NOTE},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
