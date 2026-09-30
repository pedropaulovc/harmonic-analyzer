r"""Build MHA-152, the brass ferrule at the crank end of the handle.

User ruling 2026-09-29 (ch11 p.14/p.15 photographs): the bright ring between
the crank arm and the ebonized grip is a separate brass ferrule, epoxied on
the MHA-022 tenon and seated on its shoulder; its outer end face runs against
the arm.  Dimensions live in ``crank_handle_ferrule_spec``.

Layout: one revolve about local +X, in the handle's own frame -- the
arm-bearing face at x=0, the seat face at x=LENGTH -- so the drive train
places it with the handle's transform.  ``Axis1`` is the ferrule axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_handle_ferrule.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
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
from crank_handle_ferrule_spec import (
    BORE_DIA,
    BORE_DIA_TOL,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    OUTER_DIA,
)

PART_NAME = "crank-handle-ferrule"
MATERIAL = "Brass"  # the gears' gold; see _common.apply_material docstring

OUTER_R = OUTER_DIA / 2.0
BORE_R = BORE_DIA / 2.0
V_FERRULE = math.pi * (OUTER_R**2 - BORE_R**2) * LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_crankshaft).
    for name, value in (
        ("OuterDia", OUTER_DIA),
        ("BoreDia", BORE_DIA),
        ("Length", LENGTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rectangular section on the Front plane, revolved about the X axis:
    # arm face -> OD -> seat face -> bore.
    profile = SketchDims()
    check("create_sketch ferrule profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "ferrule axis centerline",
        await adapter.add_centerline(0.0, 0.0, LENGTH, 0.0),
    )
    arm_face, outer, seat_face, bore = await add_line_chain(
        adapter,
        [(0.0, BORE_R), (0.0, OUTER_R), (LENGTH, OUTER_R), (LENGTH, BORE_R)],
    )
    set_sketch_direct_db(adapter, False)
    check("axis horizontal", await adapter.add_sketch_constraint(axis, None, "horizontal"))
    for label, entity, relation in (
        ("arm face", arm_face, "vertical"),
        ("OD", outer, "horizontal"),
        ("seat face", seat_face, "vertical"),
        ("bore", bore, "horizontal"),
    ):
        check(
            f"ferrule {label} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "axis starts at the origin",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "arm face on the origin plane",
        await adapter.add_sketch_constraint(f"{arm_face}.start", "origin", "vertical_points"),
    )
    # Dimensions in creation order.
    check(
        "axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", LENGTH),
    )
    profile.record("AxisLength", '"Length"')
    check(
        "ferrule length",
        await adapter.add_sketch_dimension(outer, None, "linear", LENGTH),
    )
    profile.record("Length", '"Length"')
    await add_diametric_linear_dimension(
        adapter, axis, outer, (LENGTH / 2.0, OUTER_R + 4.0), "OuterDia"
    )
    profile.record("OuterDia", '"OuterDia"')
    await add_diametric_linear_dimension(
        adapter, axis, bore, (LENGTH / 2.0, BORE_R - 2.0), "BoreDia"
    )
    profile.record("BoreDia", '"BoreDia"')
    await ensure_fully_defined(adapter, "ferrule profile sketch")
    check("exit_sketch ferrule profile", await adapter.exit_sketch())
    name_last_feature(adapter, "FerruleProfile")
    drive_jobs += profile.apply(adapter, "FerruleProfile")
    check("revolve ferrule", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Ferrule")
    await volume_check(adapter, "brass ferrule", V_FERRULE, 0.005 * V_FERRULE)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "ferrule axis")

    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven brass ferrule (equations neutral)", V_FERRULE, 0.005 * V_FERRULE
    )

    # The one model-owned band (policy rule 2): the bore, which the oak tenon
    # is turned to suit, holds both the MHA-022 seat and the oak round the
    # pivot bore.  Every other size is routine (.X); the handle's end play is
    # fitted on the MHA-139 shoulder.
    set_dimension_symmetric_tolerance(adapter, "FerruleProfile", "BoreDia", BORE_DIA_TOL)
    await apply_material(adapter, MATERIAL)
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
