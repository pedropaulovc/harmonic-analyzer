r"""Build MHA-DT-03-TL-03, the keyed tooth-cutting arbor (shop tooling, #2465).

Every number is ``dt_cone_gear_tl_keyed_arbor_spec``'s. The model follows
MHA-DT-04's recipe (``build_dt_cone_gear_shaft``): each turned diameter is a
circle on the plane at its own end station, extruded back to its origin, so
each diameter's dimension stands on its own step in the side view and each
length is a feature depth. The keyseat and its end-mill closed end are that
builder's cuts on this seat; the two 60° centre holes are one revolve cut
(``build_pd_transgear_thumbnut``'s countersink recipe).

Frame: axis +Z; z = 0 (the Front Plane) is the grip's end face;
``ShoulderPlane`` is the shoulder face the blank bears on; the keyseat is
centred on +X.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_keyed_arbor.py
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
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
import dt_cone_gear_tl_keyed_arbor_spec as spec
from solidworks_mcp.adapters.com_variant import double_array

PART_NAME = "dt-cone-gear-tl-keyed-arbor"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring
UNIT = spec.UNIT


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units (inch here).
    for name, value in spec.GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # The shoulder face, the blank side's datum, as a named plane: the kit
    # (MHA-DT-03-TL-05) and the seat's sections stand on it.
    check(
        "create_plane ShoulderPlane",
        await adapter.create_plane(
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
        volume = await _add_section(adapter, drive_jobs, section, dia, start, end)
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

    removed = await _cut_centres(adapter, drive_jobs)
    volume -= removed
    await volume_check(adapter, "centre holes", volume, 0.05 * removed)
    removed = await _cut_keyseat(adapter, drive_jobs)
    volume -= removed
    await volume_check(adapter, "keyseat", volume, 0.1 * removed)
    removed = await _cut_keyseat_end(adapter, drive_jobs)
    volume -= removed
    # The end's own volume, about 1 mm^3, sets its gate: a plunge on the
    # wrong side removes a whole fresh disc.
    await volume_check(adapter, "keyseat end", volume, 0.25 * removed)

    # The shoulder root: a full circle on the seat (the keyseat's end radius
    # stops short of it), picked at -X, opposite the keyseat.
    check(
        "fillet shoulder root",
        await adapter.add_fillet(
            spec.SHOULDER_R,
            [[-spec.SEAT_DIA / 2.0, 0.0, spec.SHOULDER_Z]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, spec.SHOULDER_FILLET)
    name_dimensions(adapter, spec.SHOULDER_FILLET, ["ShoulderR"])
    await volume_check(adapter, "shoulder root", volume, 0.005 * volume)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keyed arbor (equations neutral)", volume, 0.005 * volume
    )
    if abs(volume - spec.FINISHED_VOLUME) > 0.005 * spec.FINISHED_VOLUME:
        raise AssertionError("the built arbor's volume is not the spec's")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The seat and keyseat carry their bands on the model dimension.
    for (feature, name), band in spec.MODEL_BANDS_MM.items():
        set_dimension_bilateral_tolerance(
            adapter,
            feature,
            name,
            *deviations(band),
            places=spec.DRAWING_PRECISION_BY_NAME[name],
            display_unit=UNIT,
        )
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
    return await save_part_and_images(adapter, PART_NAME)


async def _add_section(
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
            await adapter.create_plane(
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
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await define_circle(
        adapter,
        0.0,
        0.0,
        dia / 2.0,
        label,
        dims=dims,
        names=(f"{section}Cx", f"{section}Cy", dia_name),
        drives=(None, None, f'"{dia_name}"'),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    profile = spec.profile_sketch(section)
    name_last_feature(adapter, profile)
    drive_jobs += dims.apply(adapter, profile)
    check(
        f"extrude {label}",
        await adapter.create_extrusion(
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
    await volume_check(adapter, label, expected, 0.005 * expected)
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


async def _cut_centres(adapter: Any, drive_jobs: list[tuple[str, str]]) -> float:
    """Both 60° centre holes in one revolve cut and return the volume removed.

    ``build_pd_transgear_thumbnut``'s countersink layout on the Right Plane
    (model Y, Z): a centreline on the axis from the grip end to the thread end,
    and per end a triangle -- the cone line, the end-face line from the mouth to
    the axis, the axis line back to the apex -- sized by its mouth diameter
    (diametric from the centreline) and its cone depth along the axis, driven
    as mouth/2 / tan(30°). The grip end's axis point is the origin; the thread
    end's stands the arbor's length along the axis. Model points map to the
    sketch through ModelToSketchTransform, which also says which sketch axis
    runs along the arbor.

    No angular dimension: ``add_sketch_dimension(..., "angular")`` hands
    ``AddDimension`` a text point in SKETCH coordinates, and SolidWorks picks
    the measured angle region from that point read in model space (the index
    plate's ``_add_flank_reference`` note). On the Front Plane the two agree;
    on this Right Plane (sketch u = -Z) the point lands outside the 30° wedge,
    so the dimension can take the 150° side and, driven to 30°, solve each
    apex across its end face into air, leaving the revolve no material to cut
    (farm run 20261112T203156536Z: "Failed to create revolve feature" with a
    fully defined sketch). An axial distance keeps the side the apex was
    drawn on.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    label = "centre holes"
    length = spec.OVERALL_LENGTH
    check(f"create_sketch {label}", await adapter.create_sketch("Right"))

    def point(radius: float, z: float) -> tuple[float, float]:
        return _sketch_xy_mm(adapter, (0.0, radius, z))

    start, end = point(0.0, 0.0), point(0.0, length)
    along_x = abs(end[0]) > abs(end[1])
    along = 0 if along_x else 1
    if abs(start[0]) > 1e-6 or abs(start[1]) > 1e-6 or abs(end[1 - along]) > 1e-6:
        raise RuntimeError(f"{label}: the axis maps to sketch {start}..{end}")
    axis_relation, face_relation = (
        ("horizontal", "vertical") if along_x else ("vertical", "horizontal")
    )
    head_dia, tail_dia = spec.HEAD_CENTRE_DIA, spec.TAIL_CENTRE_DIA
    profiles = (
        (
            "head",
            [
                point(0.0, spec.centre_depth_mm(head_dia)),
                point(head_dia / 2.0, 0.0),
                point(0.0, 0.0),
            ],
            0.0,
            "HeadCentreDia",
            "HeadCentreDepth",
            head_dia,
        ),
        (
            "tail",
            [
                point(0.0, length - spec.centre_depth_mm(tail_dia)),
                point(tail_dia / 2.0, length),
                point(0.0, length),
            ],
            length,
            "TailCentreDia",
            "TailCentreDepth",
            tail_dia,
        ),
    )
    dims = SketchDims()
    set_sketch_direct_db(adapter, True)
    axis = check(f"{label} axis", await adapter.add_centerline(*start, *end))
    chains = [
        (profile, await add_line_chain(adapter, profile[1])) for profile in profiles
    ]
    set_sketch_direct_db(adapter, False)
    for relation_label, first, second, relation in (
        (f"{label} axis along the arbor", axis, None, axis_relation),
        (f"{label} axis at the grip end", f"{axis}.start", "origin", "coincident"),
        (
            f"{label} axis at the thread end",
            f"{axis}.end",
            f"{chains[1][1][1]}.end",
            "coincident",
        ),
    ):
        check(
            relation_label, await adapter.add_sketch_constraint(first, second, relation)
        )
    for (end_label, _points, z, dia_name, depth_name, dia), lines in chains:
        _cone, face, centre = lines
        for i in range(3):
            check(
                f"{end_label} centre junction {i}",
                await adapter.add_sketch_constraint(
                    f"{lines[i]}.end", f"{lines[(i + 1) % 3]}.start", "coincident"
                ),
            )
        check(
            f"{end_label} centre face",
            await adapter.add_sketch_constraint(face, None, face_relation),
        )
        check(
            f"{end_label} centre axis",
            await adapter.add_sketch_constraint(centre, None, axis_relation),
        )
        if z == 0.0:
            check(
                f"{end_label} centre at the origin",
                await adapter.add_sketch_constraint(
                    f"{face}.end", "origin", "coincident"
                ),
            )
        else:
            await anchor_point_to_origin(
                adapter, f"{face}.end", *point(0.0, z), f"{end_label} centre station"
            )
            dims.record("CentreOverall", spec.OVERALL_EXPRESSION)
        text = point(dia / 2.0 + 1.0, z)
        await add_diametric_linear_dimension(
            adapter,
            axis,
            f"{face}.start",
            text_xy=text,
            label=f"{end_label} centre diameter",
        )
        dims.record(dia_name, f'"{dia_name}"')
        depth_kind = "horizontal_distance" if along_x else "vertical_distance"
        await dimension_between(
            adapter,
            f"{centre}.start",
            f"{centre}.end",
            depth_kind,
            spec.centre_depth_mm(dia),
            f"{end_label} centre depth",
        )
        dims.record(
            depth_name,
            f'"{dia_name}" / 2 / tan({spec.CENTRE_HALF_ANGLE_DEG:g})',
        )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, spec.CENTRE_SKETCH)
    drive_jobs += dims.apply(adapter, spec.CENTRE_SKETCH)
    check(
        f"revolve {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, spec.CENTRE_FEATURE)
    return spec.CENTRE_VOLUME


async def _cut_keyseat(adapter: Any, drive_jobs: list[tuple[str, str]]) -> float:
    """Cut the seat's keyseat and return the volume removed
    (``build_dt_cone_gear_shaft._cut_keyseat`` on this seat).

    Sketched on SeatEndPlane, where its sizes lie in the plane a section view
    shows: a rectangle whose inner edge is the keyseat floor, ``KeyseatWidth``
    long and centred on the sketch's x axis, its outer edge 1 mm clear of the
    seat; a construction line along the x axis from the seat's far side
    (``SeatDia``/2 from the axis) to the floor's midpoint, whose length IS
    ``KeyseatS`` (ANSI B17.1 S). The cut runs back toward the shoulder by the
    seat's length less the end radius's set; beyond SeatEndPlane the pilot
    lies inside the floor, so the rectangle meets no material there.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    label = "keyseat"
    radius = spec.SEAT_DIA / 2.0
    floor_offset = spec.KEYSEAT_FLOOR_OFFSET
    half = spec.KEYSEAT_WIDTH / 2.0
    reach = radius + 1.0
    dims = SketchDims()
    check(
        f"create_sketch {label}",
        await adapter.create_sketch(spec.end_plane("Seat")),
    )
    sign = _sketch_x_per_model_x(adapter)
    bottom, outer, top, floor = await add_line_chain(
        adapter,
        [
            (sign * floor_offset, -half),
            (sign * reach, -half),
            (sign * reach, half),
            (sign * floor_offset, half),
        ],
    )
    for edge, direction in (
        (bottom, "horizontal"),
        (outer, "vertical"),
        (top, "horizontal"),
        (floor, "vertical"),
    ):
        check(
            f"{label} {direction} {edge}",
            await adapter.add_sketch_constraint(edge, None, direction),
        )
    await dimension_between(
        adapter,
        f"{bottom}.start",
        f"{bottom}.end",
        "horizontal_distance",
        reach - floor_offset,
        f"{label} reach",
    )
    dims.record("KeyseatReach")
    await dimension_between(
        adapter,
        f"{floor}.start",
        f"{floor}.end",
        "vertical_distance",
        2.0 * half,
        f"{label} width",
    )
    dims.record("KeyseatWidth", '"KeyseatW"')
    (across,) = await add_line_chain(
        adapter, [(-sign * radius, 0.0), (sign * floor_offset, 0.0)], close=False
    )
    _as_construction(adapter, across)
    check(
        f"{label} S line horizontal",
        await adapter.add_sketch_constraint(across, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{across}.start", -sign * radius, 0.0, f"{label} far side"
    )
    dims.record("KeyseatFarSide", '"SeatDia" / 2')
    check(
        f"{label} S line meets the floor",
        await adapter.add_sketch_constraint(f"{across}.end", floor, "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{across}.start",
        f"{across}.end",
        "horizontal_distance",
        spec.KEYSEAT_S,
        f"{label} S",
    )
    dims.record("KeyseatS", '"KeyseatS"')
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, spec.KEYSEAT_SKETCH)
    drive_jobs += dims.apply(adapter, spec.KEYSEAT_SKETCH)
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=spec.KEYSEAT_CUT_LENGTH)
        ),
    )
    name_last_feature(adapter, spec.KEYSEAT_FEATURE)
    (length,) = name_dimensions(adapter, spec.KEYSEAT_FEATURE, ["KeyseatLength"])
    drive_jobs.append((length, spec.KEYSEAT_LENGTH_EXPRESSION))
    return spec.KEYSEAT_VOLUME


async def _cut_keyseat_end(adapter: Any, drive_jobs: list[tuple[str, str]]) -> float:
    """Close the keyseat's shoulder end with the end mill's semicircle and
    return the volume removed (``build_dt_cone_gear_shaft._cut_keyseat_end``).

    A Ø``KeyseatW`` circle centred on the keyseat's centreline at KEY_END_Z,
    sketched on a plane parallel to the Right Plane one millimetre outside the
    seat on the keyseat's +X side, cut mid-plane deep enough to reach the
    floor. The sketch locates the centre FROM THE SHOULDER, as the sheet
    does: a construction line standing on the shoulder face from the axis to
    the seat's round on -Y (``KeyseatShoulderFace`` from the origin, driven by
    the shoulder's station; ``KeyseatShoulderRise`` = ``SeatDia``/2), and
    the centre ``KeyseatEndSet`` along the arbor from the line's outer end.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    label = "keyseat end"
    radius = spec.SEAT_DIA / 2.0
    reach = radius + 1.0
    floor_offset = spec.KEYSEAT_FLOOR_OFFSET
    half = spec.KEYSEAT_WIDTH / 2.0
    check(
        f"create_plane {spec.KEYSEAT_END_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Right Plane", offset=reach)
        ),
    )
    name_last_feature(adapter, spec.KEYSEAT_END_PLANE)
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(spec.KEYSEAT_END_PLANE))
    centre = _sketch_xy_mm(adapter, (reach, 0.0, spec.KEY_END_Z))
    face = _sketch_xy_mm(adapter, (reach, 0.0, spec.SHOULDER_Z))
    corner = _sketch_xy_mm(adapter, (reach, -radius, spec.SHOULDER_Z))
    along_x = abs(centre[0]) > abs(centre[1])
    along, across = (0, 1) if along_x else (1, 0)
    for point, station in ((centre, spec.KEY_END_Z), (face, spec.SHOULDER_Z)):
        if abs(point[across]) > 1e-6 or abs(abs(point[along]) - station) > 1e-6:
            raise RuntimeError(
                f"{label}: station {station} maps to sketch {point}, not onto one axis"
            )
    if (
        abs(corner[along] - face[along]) > 1e-6
        or abs(abs(corner[across]) - radius) > 1e-6
    ):
        raise RuntimeError(f"{label}: the shoulder corner maps to sketch {corner}")
    along_distance, across_distance = (
        ("horizontal_distance", "vertical_distance")
        if along_x
        else ("vertical_distance", "horizontal_distance")
    )
    (shoulder_line,) = await add_line_chain(adapter, [face, corner], close=False)
    _as_construction(adapter, shoulder_line)
    check(
        f"{label} shoulder line square to the axis",
        await adapter.add_sketch_constraint(
            shoulder_line, None, "vertical" if along_x else "horizontal"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{shoulder_line}.start", face[0], face[1], f"{label} shoulder face"
    )
    dims.record("KeyseatShoulderFace", spec.SHOULDER_EXPRESSION)
    await dimension_between(
        adapter,
        f"{shoulder_line}.start",
        f"{shoulder_line}.end",
        across_distance,
        radius,
        f"{label} shoulder rise",
    )
    dims.record("KeyseatShoulderRise", '"SeatDia" / 2')
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = await adapter.add_circle(centre[0], centre[1], half)
        check(f"add_circle {label}", circle)
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    check(
        f"{label} centre on the axis",
        await adapter.add_sketch_constraint(
            f"{circle.data}.center",
            "origin",
            "horizontal_points" if along_x else "vertical_points",
        ),
    )
    await dimension_between(
        adapter,
        f"{shoulder_line}.end",
        f"{circle.data}.center",
        along_distance,
        spec.KEY_END_SET,
        f"{label} set",
    )
    dims.record("KeyseatEndSet", '"KeyseatEndSet"')
    check(
        f"dimension {label} diameter",
        await adapter.add_sketch_dimension(circle.data, None, "diameter", 2.0 * half),
    )
    dims.record("KeyseatEndDia", '"KeyseatW"')
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, spec.KEYSEAT_END_SKETCH)
    drive_jobs += dims.apply(adapter, spec.KEYSEAT_END_SKETCH)
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * (reach - floor_offset), both_directions=True
            )
        ),
    )
    name_last_feature(adapter, spec.KEYSEAT_END_FEATURE)
    blank_reference_geometry(adapter, ((spec.KEYSEAT_END_PLANE, "PLANE"),))
    return spec.KEYSEAT_END_VOLUME


@_telemetry.traced("part.keyed_arbor.shoulder_root_max")
def _shoulder_root_max_limit(adapter: Any) -> None:
    """ShoulderR as the single limit "R.004 MAX": no native tolerance, " MAX"
    its suffix (build_pd_transgear_thumbnut._countersink_max_limit), since
    swTolMAX prints a lowercase "max."."""
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


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _sketch_x_per_model_x(adapter: Any) -> float:
    """+1 or -1: the active sketch's x per model +X (the keyseat's side)."""
    origin = _sketch_xy_mm(adapter, (0.0, 0.0, 0.0))
    moved = _sketch_xy_mm(adapter, (1.0, 0.0, 0.0))
    dx, dy = moved[0] - origin[0], moved[1] - origin[1]
    if abs(abs(dx) - 1.0) > 1e-6 or abs(dy) > 1e-6:
        raise RuntimeError(f"sketch x is not along model X: {origin} -> {moved}")
    return math.copysign(1.0, dx)


if __name__ == "__main__":
    sys.exit(run_build(build))
