r"""Reproduction script: transgear knob cup (MHA-PD-016; ch. 23; 1 used).

The brass ring pinned on the knob shaft's rear journal by the MHA-VN-048 spring
pin, pressed through a Ø1.6 hole match-drilled through cup and journal at
assembly (not modelled); its front face runs behind the arm plate's rear
boss, the rear stop of the knob's end float (``transgear_knob_cup_spec``).

Layout: one turned half-profile on the Front plane, revolved about local +Y:
the O.D. and the length are its driving dimensions.  The front face is the
Top Plane (y = 0), the rear face y = LENGTH.  The reamed Ø8.5 bore is cut
through the full length from a Top-plane circle.  ``Axis1`` is the cup axis
(Front Plane ∩ Right Plane).  The paper-drive assembly mates ``Axis1`` to the
knob shaft's axis and the Top Plane to the shaft's cup-face station.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_knob_cup.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
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
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from pd_transgear_knob_cup_spec import (
    BORE_BAND,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    LENGTH,
    OD,
    SURFACE_FINISHES,
)

PART_NAME = "pd-transgear-knob-cup"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

CUP_R = OD / 2.0
BORE_R = BORE_DIA / 2.0
V_BODY = math.pi * CUP_R**2 * LENGTH
V_BORE = math.pi * BORE_R**2 * LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("CupDia", OD),
        ("CupLength", LENGTH),
        ("BoreDia", BORE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Turned half-profile about local +Y: front face, O.D., rear face, back
    # down the axis.
    profile = SketchDims()
    check("create_sketch cup profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("cup axis", await adapter.add_centerline(0.0, 0.0, 0.0, LENGTH))
    points = [
        (0.0, 0.0),
        (CUP_R, 0.0),
        (CUP_R, LENGTH),
        (0.0, LENGTH),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        p0 = points[index]
        p1 = points[(index + 1) % len(points)]
        relation = "horizontal" if p0[1] == p1[1] else "vertical"
        check(
            f"cup profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "cup axis vertical", await adapter.add_sketch_constraint(axis, None, "vertical")
    )
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", 0.0, 0.0, "cup origin")
    await add_diametric_linear_dimension(
        adapter, axis, lines[1], (CUP_R + 4.0, LENGTH / 2.0), "CupDia"
    )
    profile.record("CupDia", '"CupDia"')
    check(
        "cup length",
        await adapter.add_sketch_dimension(lines[1], None, "linear", LENGTH),
    )
    profile.record("CupLength", '"CupLength"')
    await ensure_fully_defined(adapter, "cup profile")
    check("exit_sketch cup profile", await adapter.exit_sketch())
    name_last_feature(adapter, "CupProfile")
    drive_jobs += profile.apply(adapter, "CupProfile")
    check("revolve cup", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "CupBody")
    await volume_check(adapter, "turned cup body", V_BODY, 0.005 * V_BODY)
    await bbox_extent_check(adapter, "cup length", "y", LENGTH)
    await bbox_extent_check(adapter, "cup O.D.", "x", OD)

    # Reamed through bore on the cup axis: the slide on the journal.
    bore = SketchDims()
    check("create_sketch cup bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "cup reamed bore",
        dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "cup bore sketch")
    check("exit_sketch cup bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut cup bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "ThroughBore")
    await volume_check(adapter, "cup through bore", V_BODY - V_BORE, 0.01 * V_BORE)

    # The mate axis: the first reference axis, so it is Axis1.
    cup_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "cup axis"
    )
    if cup_axis != "Axis1":
        raise RuntimeError(f"cup axis came back {cup_axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cup (equations neutral)", V_BODY - V_BORE, 0.01 * V_BORE
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_BAND)
    )
    # Every other printed dimension is governed by its places (the spec's
    # DRAWING_PRECISION): no model band.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The front face: the running face on the plate's rear boss.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
