r"""Build the rocker arm hub filing stud (MHA-CH-006-TL-05; shop fixture).

A headed 4140 stud turned in one chucking: the lapped body locates in the
rocker arm's reamed pivot bore and carries the two filing buttons, the
head's seat takes the lower button, the thread takes the clamping nut and the
tail goes in the bench vise (``ch_rocker_arm_tl_filing_stud_spec``).

Layout: four Right-plane circles, each extruded from the seat face (X0) to
its step: body and thread toward +X, head and tail reversed toward -X, so
every axial size measures from the seat.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_filing_stud.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    anchor_point_to_origin,
    apply_material,
    blank_sketch,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
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
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_filing_stud_spec import (
    BODY_BAND,
    BODY_DIA,
    BODY_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HEAD_DIA,
    HEAD_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    TAIL_DIA,
    TAIL_END,
    THREAD_END,
    THREAD_MODEL_DIA,
)

PART_NAME = "ch-rocker-arm-tl-filing-stud"
MATERIAL = "Alloy Steel"  # the registry row names the 4140 HT rod
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)


def _area(dia: float) -> float:
    return math.pi * (dia / 2.0) ** 2


V_TOTAL = (
    _area(BODY_DIA) * BODY_LENGTH
    + _area(THREAD_MODEL_DIA) * (THREAD_END - BODY_LENGTH)
    + _area(HEAD_DIA) * HEAD_LENGTH
    + _area(TAIL_DIA) * (TAIL_END - HEAD_LENGTH)
)

# (profile, feature, diameter knob, length knob, dia, length, reversed);
# larger diameters first on each side so each step is the next one's stock.
_STEPS = (
    ("BodyProfile", "Body", "BodyDia", "BodyLength", BODY_DIA, BODY_LENGTH, False),
    ("ThreadProfile", "Thread", "ThreadDia", "ThreadEnd", THREAD_MODEL_DIA, THREAD_END, False),
    ("HeadProfile", "Head", "HeadDia", "HeadLength", HEAD_DIA, HEAD_LENGTH, True),
    ("TailProfile", "Tail", "TailDia", "TailEnd", TAIL_DIA, TAIL_END, True),
)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for _profile, _feature, dia_knob, length_knob, dia, length, _rev in _STEPS:
        await set_global(adapter, dia_knob, f"{dia}mm")
        await set_global(adapter, length_knob, f"{length}mm")

    drive_jobs: list[tuple[str, str]] = []
    for profile, feature, dia_knob, length_knob, dia, length, reverse in _STEPS:
        dims = SketchDims()
        check(f"create_sketch {feature}", await adapter.create_sketch("Right"))
        await define_circle(
            adapter,
            0.0,
            0.0,
            dia / 2.0,
            feature,
            dims=dims,
            names=(f"{feature}Cx", f"{feature}Cy", dia_knob),
            drives=(None, None, f'"{dia_knob}"'),
        )
        await ensure_fully_defined(adapter, f"{feature} sketch")
        check(f"exit_sketch {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, profile)
        drive_jobs += dims.apply(adapter, profile)
        check(
            f"extrude {feature}",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=length, reverse_direction=reverse)
            ),
        )
        name_last_feature(adapter, feature)
        drive_jobs.append(
            (name_dimensions(adapter, feature, [length_knob])[0], f'"{length_knob}"')
        )
    await volume_check(adapter, "stud", V_TOTAL, 0.005 * V_TOTAL)
    _require_one_solid_body(adapter, label="stud")

    # Drawing-only reference: the overall length for stock cut-off, one
    # construction line on the axis in the Front plane (the profile view's
    # plane), driven by the two end stations so no geometry moves. The part
    # saves it hidden; the drawing shows it per view to import the overall.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    overall_line = check(
        "overall reference line",
        await adapter.add_line(-TAIL_END, 0.0, THREAD_END, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[overall_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("overall reference line did not take construction flag")
    check(
        "overall reference horizontal",
        await adapter.add_sketch_constraint(overall_line, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{overall_line}.start", -TAIL_END, 0.0, "overall reference vise end"
    )
    stations.record("OverallStartX", '"TailEnd"')
    await dimension_between(
        adapter,
        f"{overall_line}.start",
        f"{overall_line}.end",
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length reference",
    )
    stations.record("OverallLength", '"TailEnd" + "ThreadEnd"')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven stud (equations neutral)", V_TOTAL, 0.005 * V_TOTAL)
    _require_one_solid_body(adapter, label="driven stud")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "BodyDia", *deviations(BODY_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_sketch(adapter, "StationReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
