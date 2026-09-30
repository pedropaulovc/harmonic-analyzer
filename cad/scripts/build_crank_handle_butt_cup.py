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

import _config
from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    active_configuration_name,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    assert_saved_configurations_regenerate,
    check,
    dimension_between,
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
from _configuration_material import require_material_in_every_configuration
from _grouped_bom_properties import apply_grouped_bom_properties
from solidworks_mcp.adapters.com_variant import bstr_array
from crank_handle_butt_cup_spec import (
    BODY_DIA,
    BODY_DIA_TOL,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLOOR_HOLE_DIA,
    INSTALLED_CONFIG,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    POCKET_DEPTH,
    POCKET_DEPTH_TOL,
    POCKET_DIA,
)

from crank_handle_spec import END_ROUND_CENTER, END_ROUND_R, HANDLE_LENGTH  # noqa: E402

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
# The handle's end round in this part's frame (face at x=0 = the handle's
# basic length), and the steel it turns off the cup's outer corner.
END_ROUND_CX_LOCAL = END_ROUND_CENTER[0] - HANDLE_LENGTH
_CUT_MARGIN = 0.2


def _crown_volume(steps: int = 4000) -> float:
    """Steel outside the end round between its crest radius and the body OD
    (midpoint rule on 2*pi*r*axial-depth)."""
    cy = END_ROUND_CENTER[1]
    r0, r1 = cy, BODY_R
    h = (r1 - r0) / steps
    total = 0.0
    for i in range(steps):
        r = r0 + (i + 0.5) * h
        x = END_ROUND_CX_LOCAL + math.sqrt(END_ROUND_R**2 - (r - cy) ** 2)
        total += 2.0 * math.pi * r * max(0.0, -x) * h
    return total


V_CROWN = _crown_volume()
V_INSTALLED = V_CUP - V_CROWN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        RevolveParameters,
    )

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
    # Every model edit precedes the INSTALLED split, so the split copies a
    # finished default (the MHA-135 lesson: an edit after it touches the
    # active configuration only and leaves the other stale).
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    default_config = active_configuration_name(adapter)
    check(
        f"create_configuration {INSTALLED_CONFIG}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=INSTALLED_CONFIG,
                comment="bonded; the handle's end round turned across the face",
            )
        ),
    )
    check(
        f"activate {INSTALLED_CONFIG}",
        await adapter.set_active_configuration(INSTALLED_CONFIG),
    )
    await _cut_end_round(adapter)
    end_round = _early_bound(
        _early_bound(adapter.currentModel, "IPartDoc").FeatureByName("EndRound"), "IFeature"
    )
    # swSuppressFeature / swUnSuppressFeature, swSpecifyConfiguration.
    if not bool(end_round.SetSuppression2(0, 3, bstr_array([default_config]))):
        raise RuntimeError(f"EndRound would not suppress in {default_config}")
    if not bool(end_round.SetSuppression2(1, 3, bstr_array([INSTALLED_CONFIG]))):
        raise RuntimeError(f"EndRound would not unsuppress in {INSTALLED_CONFIG}")
    await force_rebuild(adapter)
    await volume_check(
        adapter, "installed cup (end round turned)", V_INSTALLED, 0.1 * V_CROWN
    )
    check(
        f"re-activate {default_config}",
        await adapter.set_active_configuration(default_config),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "as-turned cup (default)", V_CUP, 0.1 * V_CROWN)
    # The configuration description wins over the drive-train BOM's written
    # cell, so it is the text that BOM prints (the MHA-135 precedent).
    grouped_spec = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        [default_config, INSTALLED_CONFIG],
        part_number=str(grouped_spec["number"]),
        description=str(grouped_spec["description"]),
    )
    await report_mass_properties(adapter)
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (default_config, INSTALLED_CONFIG)
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    # The drive train places INSTALLED while the part saves on its default, so
    # INSTALLED's saved cache is what it rebuilds.  Reopen and prove it the way
    # the assembly loads it (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check(f"reopen saved {PART_NAME}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


async def _cut_end_round(adapter) -> None:
    """Revolve-cut the handle's end round across the cup face (INSTALLED).

    The circle is MHA-022's own end round, carried into this part's frame
    (face at x=0), so the two cannot drift apart.  The cut region is outside
    that circle between its crest radius and a little past the body OD.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    cx, cy = END_ROUND_CX_LOCAL, END_ROUND_CENTER[1]
    crest = (cx + END_ROUND_R, cy)
    top_r = BODY_R + _CUT_MARGIN
    top_on_circle = (cx + math.sqrt(END_ROUND_R**2 - (top_r - cy) ** 2), top_r)
    right_x = crest[0] + _CUT_MARGIN + 0.25
    check("create_sketch end round", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "end round axis", await adapter.add_centerline(-1.0, 0.0, 1.0, 0.0)
    )
    arc = check(
        "end round arc", await adapter.add_arc(cx, cy, *crest, *top_on_circle)
    )
    bottom, right, top = await add_line_chain(
        adapter,
        [crest, (right_x, cy), (right_x, top_r), top_on_circle],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    for entity, relation in (
        (axis, "horizontal"),
        (bottom, "horizontal"),
        (right, "vertical"),
        (top, "horizontal"),
    ):
        check(
            f"end round {relation} {entity}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    await anchor_point_to_origin(adapter, f"{axis}.start", -1.0, 0.0, "end round axis start")
    check("end round axis length", await adapter.add_sketch_dimension(axis, None, "linear", 2.0))
    await anchor_point_to_origin(adapter, f"{arc}.center", cx, cy, "end round centre")
    check(
        "end round radius",
        await adapter.add_sketch_dimension(arc, None, "radial", END_ROUND_R),
    )
    await anchor_point_to_origin(adapter, f"{bottom}.end", right_x, cy, "end round corner")
    await dimension_between(
        adapter, f"{right}.start", f"{right}.end", "vertical_distance", top_r - cy,
        "end round cut height",
    )
    await ensure_fully_defined(adapter, "end round sketch")
    check("exit_sketch end round", await adapter.exit_sketch())
    name_last_feature(adapter, "EndRoundProfile")
    check(
        "revolve-cut end round",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "EndRound")


if __name__ == "__main__":
    sys.exit(run_build(build))
