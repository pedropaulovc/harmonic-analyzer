r"""Build the rocker arm hub filing stud (MHA-CH-006-TL-05; shop fixture).

A headed 4140 stud turned in one chucking: the lapped body locates in the
rocker arm's reamed pivot bore and carries the two filing buttons, the
head's seat takes the lower button, the thread takes the clamping nut and the
tail goes in the bench vise (``ch_rocker_arm_tl_filing_stud_spec``).

Layout: four Right-plane circles, each extruded from the seat face (X0) to
its step: body and thread toward +X, head and tail reversed toward -X. A
thread-relief annulus is then cut from a plane at the body shoulder. A
hidden station sketch carries the print's axial baseline from the faced tip.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_filing_stud.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_filing_stud_spec import (
    BODY_DIA,
    BODY_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HEAD_DIA,
    HEAD_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    RELIEF_DIA,
    RELIEF_WIDTH,
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


V_RELIEF = (_area(THREAD_MODEL_DIA) - _area(RELIEF_DIA)) * RELIEF_WIDTH
V_TOTAL = (
    _area(BODY_DIA) * BODY_LENGTH
    + _area(THREAD_MODEL_DIA) * (THREAD_END - BODY_LENGTH)
    + _area(HEAD_DIA) * HEAD_LENGTH
    + _area(TAIL_DIA) * (TAIL_END - HEAD_LENGTH)
    - V_RELIEF
)

# (profile, feature, diameter knob, length knob, dia, length, reversed);
# larger diameters first on each side so each step is the next one's stock.
_STEPS = (
    ("BodyProfile", "Body", "BodyDia", "BodyLength", BODY_DIA, BODY_LENGTH, False),
    (
        "ThreadProfile",
        "Thread",
        "ThreadDia",
        "ThreadEnd",
        THREAD_MODEL_DIA,
        THREAD_END,
        False,
    ),
    ("HeadProfile", "Head", "HeadDia", "HeadLength", HEAD_DIA, HEAD_LENGTH, True),
    ("TailProfile", "Tail", "TailDia", "TailEnd", TAIL_DIA, TAIL_END, True),
)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for _profile, _feature, dia_knob, length_knob, dia, length, _rev in _STEPS:
        await set_global(adapter, dia_knob, f"{dia}mm")
        await set_global(adapter, length_knob, f"{length}mm")
    await set_global(adapter, "ReliefDia", f"{RELIEF_DIA}mm")
    await set_global(adapter, "ReliefWidth", f"{RELIEF_WIDTH}mm")

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

    # Thread relief: the thread annulus down to the relief floor, from a plane
    # at the body shoulder toward the tip (build_dt_crankshaft's
    # _cut_annulus_inboard: running away from the base plane takes
    # reverse_direction; the volume gate fails loud on the wrong side).
    check(
        "create_plane ReliefStartPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=BODY_LENGTH
            )
        ),
    )
    name_last_feature(adapter, "ReliefStartPlane")
    relief_start = name_dimensions(adapter, "ReliefStartPlane", ["ReliefStart"])[0]
    drive_jobs.append((relief_start, '"BodyLength"'))
    relief = SketchDims()
    check("create_sketch Relief", await adapter.create_sketch("ReliefStartPlane"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        RELIEF_DIA / 2.0,
        "relief floor circle",
        dims=relief,
        names=("ReliefCx", "ReliefCy", "ReliefDia"),
        drives=(None, None, '"ReliefDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        THREAD_MODEL_DIA / 2.0 + 1.0,
        "relief clearance circle",
        dims=relief,
        names=("ReliefOuterCx", "ReliefOuterCy", "ReliefOuterDia"),
    )
    await ensure_fully_defined(adapter, "Relief sketch")
    check("exit_sketch Relief", await adapter.exit_sketch())
    name_last_feature(adapter, "ReliefProfile")
    drive_jobs += relief.apply(adapter, "ReliefProfile")
    check(
        "cut Relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=RELIEF_WIDTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Relief")
    relief_width = name_dimensions(adapter, "Relief", ["ReliefWidth"])[0]
    drive_jobs.append((relief_width, '"ReliefWidth"'))
    await volume_check(adapter, "stud", V_TOTAL, 0.005 * V_TOTAL)
    _require_one_solid_body(adapter, label="stud")

    # Drawing-only stations: the print's one baseline from the faced tip.
    # Construction lines on the axis in the Front plane (the profile view's
    # plane), each from the tip to one station and driven by the extrude
    # knobs so no geometry moves. The part saves the sketch hidden; the
    # drawing shows it per view to import the stations.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Front"))
    # (label, station X, dimension name, drive) in creation order; the seat
    # line comes first and anchors the tip for the rest.
    rows = (
        ("head seat", 0.0, "SeatStation", '"ThreadEnd"'),
        (
            "relief end",
            BODY_LENGTH + RELIEF_WIDTH,
            "ReliefEndStation",
            '"ThreadEnd" - "BodyLength" - "ReliefWidth"',
        ),
        (
            "body shoulder",
            BODY_LENGTH,
            "ShoulderStation",
            '"ThreadEnd" - "BodyLength"',
        ),
        (
            "head back face",
            -HEAD_LENGTH,
            "HeadBackStation",
            '"ThreadEnd" + "HeadLength"',
        ),
        ("vise end", -TAIL_END, "TailEndStation", '"ThreadEnd" + "TailEnd"'),
    )
    set_sketch_direct_db(adapter, True)
    lines = [
        check(
            f"{label} station line",
            await adapter.add_line(THREAD_END, 0.0, station_x, 0.0),
        )
        for label, station_x, _name, _drive in rows
    ]
    set_sketch_direct_db(adapter, False)
    for line, (label, *_rest) in zip(lines, rows, strict=True):
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{label} station line did not take construction flag")
        check(
            f"{label} station horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    check(
        "head seat station ends at the seat",
        await adapter.add_sketch_constraint(f"{lines[0]}.end", "origin", "coincident"),
    )
    for line, (label, *_rest) in zip(lines[1:], rows[1:], strict=True):
        check(
            f"{label} station starts at the tip",
            await adapter.add_sketch_constraint(
                f"{line}.start", f"{lines[0]}.start", "coincident"
            ),
        )
    for line, (label, station_x, name, drive) in zip(lines, rows, strict=True):
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "horizontal_distance",
            THREAD_END - station_x,
            f"tip to {label}",
        )
        stations.record(name, drive)
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven stud (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _require_one_solid_body(adapter, label="driven stud")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
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
    blank_reference_geometry(adapter, (("ReliefStartPlane", "PLANE"),))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
