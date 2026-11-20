r"""Build MHA-DT-03-TL-07, the round tooth-cutting arbor (shop tooling, #2356).

Every number is ``dt_cone_gear_tl_round_arbor_spec``'s. The model follows the
keyed arbor's recipe (``build_dt_cone_gear_tl_keyed_arbor``, MHA-DT-04's):
each turned diameter is a circle on the plane at its own end station,
extruded back to its origin, so each diameter's dimension stands on its own
step in the side view and each length is a feature depth. No keyseat and no
centre holes (owner ruling 2026-11-20, #2356: no tail centre). The overall
length, which no feature depth carries (the thread runs back only to the
relief), is the one driving dimension of a hidden reference sketch on the
Right Plane (``build_dt_crankshaft``'s StationReference).

Frame: axis +Z; z = 0 (the Front Plane) is the grip's end face;
``ShoulderPlane`` is the shoulder face the blank bears on.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_round_arbor.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
import dt_cone_gear_tl_round_arbor_spec as spec
from solidworks_mcp.adapters.com_variant import double_array

PART_NAME = "dt-cone-gear-tl-round-arbor"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring
UNIT = spec.UNIT


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units (inch here).
    for name, value in spec.GLOBALS.items():
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # The shoulder face, the blank side's datum, as a named plane: the seat's
    # sections stand on it.
    check(
        "create_plane ShoulderPlane",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=spec.SHOULDER_Z
            )
        ),
    )
    name_last_feature(adapter, spec.SHOULDER_PLANE)
    (shoulder,) = name_dimensions(adapter, spec.SHOULDER_PLANE, ["ShoulderStation"])
    drive_jobs.append((shoulder, spec.SHOULDER_EXPRESSION))

    volume = 0.0
    for section, dia, start, end in spec.SECTIONS:
        volume = _add_section(adapter, drive_jobs, section, dia, start, end)
    blank_reference_geometry(
        adapter,
        (
            (spec.SHOULDER_PLANE, "PLANE"),
            *(
                (spec.end_plane(section), "PLANE")
                for section, *_rest in spec.SECTIONS
                if section not in ("Grip", "Standoff")
            ),
        ),
    )
    if abs(volume - spec.TURNED_VOLUME) > 1e-6 * spec.TURNED_VOLUME:
        raise AssertionError("the sections' running volume is not the spec's")

    _add_overall_reference(adapter, drive_jobs)

    # The shoulder root: a full circle on the seat, picked at -X.
    check(
        "fillet shoulder root",
        adapter.add_fillet(
            spec.SHOULDER_R,
            [[-spec.SEAT_DIA / 2.0, 0.0, spec.SHOULDER_Z]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, spec.SHOULDER_FILLET)
    name_dimensions(adapter, spec.SHOULDER_FILLET, ["ShoulderR"])
    volume_check(adapter, "shoulder root", volume, 0.005 * volume)

    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven round arbor (equations neutral)", volume, 0.005 * volume
    )
    if abs(volume - spec.FINISHED_VOLUME) > 0.005 * spec.FINISHED_VOLUME:
        raise AssertionError("the built arbor's volume is not the spec's")

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    _shoulder_root_max_limit(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": spec.SHEET_NOTES,
            "Isometric View Note": spec.ISOMETRIC_VIEW_NOTE,
        },
    )
    # The reference sketch owns a printed dimension but no geometry: hide it
    # so it renders nowhere; the drawing shows it per view through
    # _drawing_hidden_sketches to import that dimension.
    blank_sketch(adapter, spec.OVERALL_SKETCH)
    return save_part_and_images(adapter, PART_NAME)


def _add_section(
    adapter: Any,
    drive_jobs: list[tuple[str, str]],
    section: str,
    dia: float,
    start: float,
    end: float,
) -> float:
    """One turned section: the grip on the Front Plane extruded +Z; every
    other on its own end plane extruded back toward the grip's end face (the
    standoff's end plane is the shoulder; the thread stops at the relief), so
    each length on the sheet is a depth from that one face. Returns the
    running volume."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    dia_name, length_name = spec.SECTION_DIMENSIONS[section]
    label = f"{section} d{dia:g}mm z {start:g}..{end:g}"
    if section == "Grip":
        plane = "Front"
        reverse = False
    elif section == "Standoff":
        plane = spec.SHOULDER_PLANE
        reverse = True
    else:
        plane = spec.end_plane(section)
        check(
            f"create_plane {plane}",
            adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Front Plane", offset=end
                )
            ),
        )
        name_last_feature(adapter, plane)
        (station,) = name_dimensions(adapter, plane, [f"{section}Station"])
        drive_jobs.append((station, spec.END_STATION_DRIVES[section]))
        reverse = True
    dims = SketchDims()
    check(f"create_sketch {label}", adapter.create_sketch(plane))
    define_circle(
        adapter,
        0.0,
        0.0,
        dia / 2.0,
        label,
        dims=dims,
        names=(f"{section}Cx", f"{section}Cy", dia_name),
        drives=(None, None, f'"{dia_name}"'),
    )
    ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    profile = spec.profile_sketch(section)
    name_last_feature(adapter, profile)
    drive_jobs += dims.apply(adapter, profile)
    check(
        f"extrude {label}",
        adapter.create_extrusion(
            ExtrusionParameters(depth=end - start, reverse_direction=reverse)
        ),
    )
    name_last_feature(adapter, section)
    (depth,) = name_dimensions(adapter, section, [length_name])
    drive_jobs.append((depth, spec.LENGTH_DRIVES[length_name]))
    # Each section runs from its end back over the larger sections before it,
    # so the running volume is the union of those built; an extrude the wrong
    # way lands off the arbor and fails it.
    names = [name for name, *_rest in spec.SECTIONS]
    expected = _union_volume(spec.SECTIONS[: names.index(section) + 1])
    volume_check(adapter, label, expected, 0.005 * expected)
    return expected


def _union_volume(sections) -> float:
    """Volume of the union of coaxial sections (name, dia, start z, end z)."""
    stations = sorted({z for _n, _d, a, b in sections for z in (a, b)})
    volume = 0.0
    for z0, z1 in zip(stations, stations[1:], strict=False):
        mid = (z0 + z1) / 2.0
        covering = [d for _n, d, a, b in sections if a <= mid <= b]
        if covering:
            volume += math.pi * (max(covering) / 2.0) ** 2 * (z1 - z0)
    return volume


def _add_overall_reference(adapter: Any, drive_jobs: list[tuple[str, str]]) -> None:
    """The overall length as a hidden reference sketch's one dimension.

    On the Right Plane (the side view's plane, so the dimension imports
    there): a centreline on the axis from the grip's end face (the origin)
    to the thread's end, its far end anchored by one distance from the
    origin driven by ``"OverallLength"``. Model points map to the sketch
    through ModelToSketchTransform (the keyed arbor's centre-hole sketch),
    which also says which sketch axis runs along the arbor.
    """
    label = "overall reference"
    check(f"create_sketch {label}", adapter.create_sketch("Right"))
    start = _sketch_xy_mm(adapter, (0.0, 0.0, 0.0))
    end = _sketch_xy_mm(adapter, (0.0, 0.0, spec.OVERALL_LENGTH))
    if (
        abs(start[0]) > 1e-6
        or abs(start[1]) > 1e-6
        or min(abs(end[0]), abs(end[1])) > 1e-6
    ):
        raise RuntimeError(f"{label}: the axis maps to sketch {start}..{end}")
    dims = SketchDims()
    set_sketch_direct_db(adapter, True)
    axis = check(f"{label} axis", adapter.add_centerline(*start, *end))
    set_sketch_direct_db(adapter, False)
    check(
        f"{label} axis at the grip end",
        adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    anchor_point_to_origin(adapter, f"{axis}.end", *end, f"{label} thread end")
    dims.record("Overall", spec.OVERALL_EXPRESSION)
    ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    name_last_feature(adapter, spec.OVERALL_SKETCH)
    drive_jobs += dims.apply(adapter, spec.OVERALL_SKETCH)


@_telemetry.traced("part.round_arbor.shoulder_root_max")
def _shoulder_root_max_limit(adapter: Any) -> None:
    """ShoulderR as the single limit "R.004 MAX": no native tolerance, " MAX"
    its suffix (build_dt_cone_gear_tl_keyed_arbor._shoulder_root_max_limit),
    since swTolMAX prints a lowercase "max."."""
    display, dimension = _named_dimension(adapter, spec.SHOULDER_FILLET, "ShoulderR")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = spec.SHOULDER_R_TOL_TYPE
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(2, spec.SHOULDER_R_SUFFIX)  # swDimensionTextSuffix
    if (
        int(tolerance.Type) != spec.SHOULDER_R_TOL_TYPE
        or str(display.GetText(2) or "") != spec.SHOULDER_R_SUFFIX
    ):
        raise RuntimeError("ShoulderR: the MAX single limit did not persist")


def _sketch_xy_mm(
    adapter: Any, point_mm: tuple[float, float, float]
) -> tuple[float, float]:
    """The active sketch's (x, y), mm, of a model point given in mm."""
    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        utility.CreatePoint(double_array([value / 1000.0 for value in point_mm])),
        "IMathPoint",
    )
    moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    data = [float(value) for value in moved.ArrayData]
    return data[0] * 1000.0, data[1] * 1000.0


if __name__ == "__main__":
    sys.exit(run_build(build))
