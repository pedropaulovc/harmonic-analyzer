r"""Reproduction script: the DT6-FORM1 fly-cutter bar (MHA-DT-37-TL-02).

Shop tooling, issue #2358 (``dt_cone_tip_gear_tl_cutter_bar_spec`` owns every
number): 3/8 cold-finished round, the reamed cross hole for the
MHA-DT-37-TL-01 bit square to its axis, and the #4-40 tap up the axis from
the cutting end to the cross hole for the MHA-SH-VN-54 set screw.

Part frame: bar axis +Y, the cutting end face on the Top Plane (y = 0).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_gear_tl_cutter_bar.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _holes import DIAMETER_TOLERANCE_MM, cross_hole_volume_mm3, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from dt_cone_tip_gear_tl_cutter_bar_spec import (
    BAR_DIA,
    BAR_LENGTH,
    BAR_RADIUS,
    CROSS_HOLE_BAND,
    CROSS_HOLE_DIA,
    CROSS_HOLE_PLACES,
    CROSS_HOLE_STATION,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    SET_SCREW_HOLE_SPEC,
    TAP_DRILL_DIA,
    UNIT,
    tap_drill_volume_mm3,
)

PART_NAME = "dt-cone-tip-gear-tl-cutter-bar"
MATERIAL = "Plain Carbon Steel"  # 1018 cold-finished round (the registry row names it)

# Front-plane (u, v) = model (X, Y): the cutting end face from the axis out,
# up the O.D. to the collet end, back to the axis, down the axis.
PROFILE_POINTS = [
    (0.0, 0.0),
    (BAR_RADIUS, 0.0),
    (BAR_RADIUS, BAR_LENGTH),
    (0.0, BAR_LENGTH),
]
V_BAR = math.pi * BAR_RADIUS**2 * BAR_LENGTH
V_CROSS_HOLE = cross_hole_volume_mm3(CROSS_HOLE_DIA, BAR_DIA)
V_TAP = tap_drill_volume_mm3()
V_FINISHED = V_BAR - V_CROSS_HOLE - V_TAP


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # Editable knobs: inch document, so the mm suffix is load-bearing.
    for name, value in (
        ("BarDia", BAR_DIA),
        ("BarLength", BAR_LENGTH),
        ("CrossHoleDia", CROSS_HOLE_DIA),
        ("CrossHoleStation", CROSS_HOLE_STATION),
    ):
        await set_global(adapter, name, f"{value}mm")
    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch bar profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "bar axis centerline", await adapter.add_centerline(0.0, 0.0, 0.0, BAR_LENGTH)
    )
    lines = await add_line_chain(adapter, PROFILE_POINTS)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        u0 = PROFILE_POINTS[index][0]
        u1 = PROFILE_POINTS[(index + 1) % len(PROFILE_POINTS)][0]
        relation = "vertical" if u0 == u1 else "horizontal"
        check(
            f"bar profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    end_face, outside, collet_end, _axis_line = lines
    check(
        "cutting end centre on the origin",
        await adapter.add_sketch_constraint(
            f"{end_face}.start", "origin", "coincident"
        ),
    )
    await dimension_between(
        adapter,
        f"{outside}.start",
        f"{outside}.end",
        "vertical_distance",
        BAR_LENGTH,
        "bar length",
    )
    profile.record("BarLength", '"BarLength"')
    await add_diametric_linear_dimension(
        adapter, axis, outside, (BAR_RADIUS + 3.0, BAR_LENGTH / 2.0), "BarDia"
    )
    profile.record("BarDia", '"BarDia"')
    await ensure_fully_defined(adapter, "bar profile")
    check("exit_sketch bar profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += profile.apply(adapter, "BarProfile")
    check("revolve bar", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Bar")
    await volume_check(adapter, "bar", V_BAR, 0.002 * V_BAR)
    await bbox_extent_check(adapter, "bar length", "y", BAR_LENGTH)
    await bbox_extent_check(adapter, "bar O.D.", "x", BAR_DIA)

    # The cross hole: a Right-plane circle, (u, v) = model (-Z, Y), on the axis
    # at its station, cut both ways along X.
    hole = SketchDims()
    check("create_sketch cross hole", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        CROSS_HOLE_STATION,
        CROSS_HOLE_DIA / 2.0,
        "cross hole",
        dims=hole,
        names=(None, "CrossHoleStation", "CrossHoleDia"),
        drives=(None, '"CrossHoleStation"', '"CrossHoleDia"'),
    )
    await ensure_fully_defined(adapter, "cross hole sketch")
    check("exit_sketch cross hole", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossHoleProfile")
    drive_jobs += hole.apply(adapter, "CrossHoleProfile")
    check(
        "cut cross hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHole")
    await volume_check(adapter, "cross hole", V_BAR - V_CROSS_HOLE, 0.01 * V_CROSS_HOLE)

    # The set-screw tap: ONE native blind #4-40 hole up the axis from the
    # cutting end, its drill to the cross hole's axis and its full thread
    # short of the hole (SET_SCREW_HOLE_SPEC); the drill beyond the hole's
    # wall cuts only air, so V_TAP is unchanged.
    tap = wizard_holes(
        adapter,
        SET_SCREW_HOLE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        "set-screw tap (#4-40)",
        name="SetScrewTap",
        placement_dims=[((None, None), (None, None))],
    )
    if abs(tap.hole_dia_mm - TAP_DRILL_DIA) > DIAMETER_TOLERANCE_MM:
        raise RuntimeError(
            f"set-screw tap drill Ø{tap.hole_dia_mm:.4f} != Ø{TAP_DRILL_DIA:.4f}"
        )
    drive_jobs += tap.placement_drive_jobs
    await volume_check(adapter, "set-screw tap", V_FINISHED, 0.03 * V_TAP)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven bar (equations neutral)", V_FINISHED, 0.03 * V_TAP
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The reamed hole carries the reamer's row; every other size takes the
    # title block's.
    set_dimension_bilateral_tolerance(
        adapter,
        "CrossHoleProfile",
        "CrossHoleDia",
        *deviations(CROSS_HOLE_BAND),
        places=CROSS_HOLE_PLACES,
        display_unit=UNIT,
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
