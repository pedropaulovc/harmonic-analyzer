r"""Bought Tr8x2 leadscrew: ZYLtech HW-SC-T8x2-600 cut to length (MHA-CH-06-TL-VN-54).

The oblique trammel jig's feed screw as installed: a plain Ø8 cylinder at
the thread's major diameter (the thread is not modelled), shop-cut to C4's
``SCREW_LENGTH``, each end broken 0.25 x 45° (``ScrewProfile`` -> ``Screw``),
then milled with a set-screw flat under each set screw that locks it: one at
clock 0 (+X) at each KP08 and the handwheel (``FlatProfile`` -> ``Flats``),
and each KP08's second at 120° from it (``<Station>ClockProfile`` ->
``<Station>ClockFlat``, sketched on the offset plane ``<Station>ClockPlane``).
Built from ``ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec``, which records
each value's source. Datasheet-built: no vendor CAD obtained.

The drawing's controls are named driving dimensions (the spec's
``DIMENSION_CONTROLS``): the profile's axis edge ``CutLength``; the flats'
``FlatLength``, ``FlatAF`` and ``<Station>FlatStation`` (FlatProfile, on
Front, so they print on the main view); each clock flat's
``<Station>ClockAF`` and ``<Station>ClockAngle`` (its station's sketch, so
they print on that station's section). Every cut is proved by its own
volume step and its own planar faces.

Frame: the axis is +Y and is published as ``ScrewAxis`` (Front ∩ Right).
y = 0 is the near (spindle-side) end.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_leadscrew.py
"""

from __future__ import annotations

import math
import sys

import _config
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bought_revolve import SAVED_PROPERTIES, publish_screw_axis, stock_properties
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec import (
    BLANK_VOLUME_MM3,
    CLOCKED_FLATS,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLAT_AF,
    FLAT_CHORD,
    FLAT_DEPTH,
    FLAT_LENGTH,
    FLAT_STARTS,
    FLAT_STATIONS,
    FLAT_VOLUME_MM3,
    KP08_SET_SCREW_SPACING_DEG,
    MAJOR_DIA,
    MATERIAL,
    PRINTED_FLAT,
    PROFILE,
    VOLUME_MM3,
    control_si,
)
from solidworks_mcp.adapters.com_variant import double_array

PART_NAME = "ch-rocker-arm-tl-vn-oblique-leadscrew"
STOCK_PROPERTIES = stock_properties(_config.parts(PART_NAME))
# No method note (rule 7): the cut length and the flats' native dimensions
# define the part, so it saves the bought parts' contract less the note.
SAVED_PROPERTIES_NO_NOTE = tuple(
    name for name in SAVED_PROPERTIES if name != "Manufacturing Notes"
)

# The sketch dimensions in define_polygon_chain's emission order for
# ``profile_points()``: the anchor at the origin emits none, the segment
# closing on it (the near end face) is skipped, then each segment in line
# order -- one dimension on an axis-parallel segment, radial then axial on
# a chamfer. The axis edge comes first, so the cut length is a driving
# dimension of its own rather than the closure's remainder.
PROFILE_DIMENSIONS = (
    "CutLength",
    "FarEndRadius",
    "FarChamferRadial",
    "FarChamferAxial",
    "ShankLength",
    "NearChamferRadial",
    "NearChamferAxial",
)


def profile_points() -> list[tuple[float, float]]:
    """``PROFILE`` as Front-plane sketch points (x = radius, y = station), up
    the axis first: the origin vertex, then the far end, back down the
    outline to the near end face, which closes on the origin."""
    return [PROFILE[0], *reversed(PROFILE[1:])]


async def define_profile(adapter, lines: list[str]) -> SketchDims:
    """Fully define the profile chain; return its named dimensions."""
    dims = SketchDims()
    await define_polygon_chain(
        adapter,
        lines,
        profile_points(),
        label="screw",
        dims=dims,
        names=list(PROFILE_DIMENSIONS),
    )
    return dims


async def _revolve_screw(adapter) -> None:
    """Sketch the profile on Front and revolve it 360° about its axis edge.

    The ``revolve_profile`` recipe, with the profile's dimensions named: the
    centerline lies over the axis edge (points 0 -> 1) and merges into its
    corners, the vertex at the origin anchors the chain.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    points = profile_points()
    check("create_sketch screw", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check("screw axis", await adapter.add_centerline(*points[0], *points[1]))
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    dims = await define_profile(adapter, lines)
    await ensure_fully_defined(adapter, "screw profile")
    check("exit_sketch screw", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    dims.apply(adapter, "ScrewProfile")
    check("revolve screw", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Screw")


def _as_construction(adapter, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag
    (build_ch_pivot_shaft)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _flats(adapter) -> None:
    """The clock-0 set-screw flats: ONE cut from a rectangle per station on
    Front (build_ch_pivot_shaft._flats, turned to this part's +Y axis). Each
    rectangle's inner edge is its flat, at x = R - FLAT_DEPTH (the flat faces
    model +X), its other three edges 1 mm clear of the screw; a construction
    line from the screw's far side (x = -R) square to the flat's midpoint has
    the across-flat as its length, and the flat's near end's height over the
    origin is its station: the review's rule 10 dimensions the flat's edge,
    not its unmarked middle. ``PRINTED_FLAT``'s rectangle carries
    the printed ``FlatLength`` and ``FlatAF``; every station's ``FlatStation``
    prints. A mid-plane cut 1 mm past the screw each side of Front takes the
    whole segment."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    radius = MAJOR_DIA / 2.0
    offset = radius - FLAT_DEPTH
    reach = radius + 1.0
    dims = SketchDims()
    check("create_sketch flats", await adapter.create_sketch("Front"))
    drawn = []
    for name, station in FLAT_STATIONS.items():
        v0, v1 = station - FLAT_LENGTH / 2.0, station + FLAT_LENGTH / 2.0
        flat, end, outer, start = await add_line_chain(
            adapter, [(offset, v0), (offset, v1), (reach, v1), (reach, v0)]
        )
        for edge, direction in (
            (flat, "vertical"),
            (end, "horizontal"),
            (outer, "vertical"),
            (start, "horizontal"),
        ):
            check(
                f"{name} flat {direction} {edge}",
                await adapter.add_sketch_constraint(edge, None, direction),
            )
        (across,) = await add_line_chain(
            adapter, [(-radius, station), (offset, station)], close=False
        )
        _as_construction(adapter, across)
        check(
            f"{name} flat across-flat horizontal",
            await adapter.add_sketch_constraint(across, None, "horizontal"),
        )
        check(
            f"{name} flat across-flat meets the flat",
            await adapter.add_sketch_constraint(f"{across}.end", flat, "midpoint"),
        )
        drawn.append((name, flat, end, across))
    for name, flat, end, across in drawn:
        printed = name == PRINTED_FLAT
        await dimension_between(
            adapter,
            f"{flat}.start",
            f"{flat}.end",
            "vertical_distance",
            FLAT_LENGTH,
            f"{name} flat length",
        )
        dims.record("FlatLength" if printed else f"{name}FlatLength")
        await dimension_between(
            adapter,
            f"{end}.start",
            f"{end}.end",
            "horizontal_distance",
            reach - offset,
            f"{name} flat reach",
        )
        dims.record(f"{name}FlatReach")
        await dimension_between(
            adapter,
            f"{across}.start",
            "origin",
            "horizontal_distance",
            radius,
            f"{name} flat far side",
        )
        dims.record(f"{name}FarSide")
        await dimension_between(
            adapter,
            f"{across}.start",
            f"{across}.end",
            "horizontal_distance",
            FLAT_AF,
            f"{name} flat across flat",
        )
        dims.record("FlatAF" if printed else f"{name}FlatAF")
        await dimension_between(
            adapter,
            f"{flat}.start",
            "origin",
            "vertical_distance",
            FLAT_STARTS[name],
            f"{name} flat station",
        )
        dims.record(f"{name}FlatStation")
    await ensure_fully_defined(adapter, "flats sketch")
    check("exit_sketch flats", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatProfile")
    dims.apply(adapter, "FlatProfile")
    check(
        "cut flats",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * reach, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Flats")


def _sketch_z_per_model_z(adapter) -> float:
    """+1 or -1: the active sketch's y per model +Z, its x along model +X.

    build_dt_cone_gear_shaft._sketch_x_per_model_x taken to both in-plane
    axes: a station plane offset from Top is expected to share Top's frame
    (x = +X, y = -Z), but which way its axes run is the sketch's to state
    (ModelToSketchTransform), not ours to assume. Its x must run +X: the
    angle's text point is passed in the model frame too (see
    ``_clock_angle``).
    """
    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    mapped = []
    for xyz in ((0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.0, 0.001)):
        point = _early_bound(utility.CreatePoint(double_array(list(xyz))), "IMathPoint")
        if any(
            abs(float(a) - b) > 1e-12 for a, b in zip(point.ArrayData, xyz, strict=True)
        ):
            raise RuntimeError(f"CreatePoint did not echo {xyz}: {point.ArrayData}")
        moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        mapped.append(tuple(float(value) for value in moved.ArrayData))
    origin, along_x, along_z = mapped
    if abs(origin[0]) > 1e-9 or abs(origin[1]) > 1e-9:
        raise RuntimeError(
            f"the screw axis is off the station sketch's origin: {mapped}"
        )
    if abs(along_x[0] - origin[0] - 0.001) > 1e-9 or abs(along_x[1] - origin[1]) > 1e-9:
        raise RuntimeError(f"station sketch x is not along model +X: {mapped}")
    dy = along_z[1] - origin[1]
    if abs(along_z[0] - origin[0]) > 1e-9 or abs(abs(dy) - 0.001) > 1e-9:
        raise RuntimeError(f"station sketch y is not along model Z: {mapped}")
    return math.copysign(1.0, dy)


def _clock_angle(adapter, name: str, ref: str, radial: str, z_sign: float) -> None:
    """Author the clock flat's angle from clock 0 as a DRIVING dimension
    between the two origin-rooted construction rays (``ref`` along +X,
    ``radial`` out to the flat): both selected as segments and placed with
    ``AddSpecificDimension`` (build_dt_cone_pivot_post._add_driving_plan_incline),
    a supplement turned by ``SupplementaryAngle`` (build_sm_vn_knife_hanger_stud).
    The text point sits on the rays' bisector, passed with sketch y in the y
    slot and as model Z (``z_sign``) in the z slot, so it lands in the wedge
    whether SOLIDWORKS reads it in sketch or in model space (the off-plane
    component projects away)."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    nominal = math.radians(KP08_SET_SCREW_SPACING_DEG)
    text_radius_m = (MAJOR_DIA / 2.0 + 2.0) / 1000.0
    text_x = text_radius_m * math.cos(nominal / 2.0)
    text_y = z_sign * text_radius_m * math.sin(nominal / 2.0)
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [ref, radial], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_x,
        text_y,
        z_sign * text_y,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(
            f"{name} clock angle: AddSpecificDimension failed ({status})"
        )
    display = _early_bound(display, "IDisplayDimension")
    angle = _early_bound(display.GetDimension2(0), "IDimension")
    actual = abs(float(angle.SystemValue))
    if not math.isclose(actual, nominal, abs_tol=1e-8):
        if (
            not math.isclose(math.pi - actual, nominal, abs_tol=1e-8)
            or not display.SupplementaryAngle()
        ):
            raise RuntimeError(
                f"{name} clock angle measured {math.degrees(actual):.6f} deg, "
                f"expected {KP08_SET_SCREW_SPACING_DEG:g}"
            )
    angle.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(angle.DrivenState) != 2 or not math.isclose(
        abs(float(angle.SystemValue)), nominal, abs_tol=1e-8
    ):
        raise RuntimeError(
            f"{name} clock angle is not a driving {nominal!r} rad control"
        )


async def _clock_flat(adapter, name: str) -> str:
    """A KP08 station's second flat, KP08_SET_SCREW_SPACING_DEG round from
    clock 0 toward +Z: a rectangle on the station's own plane (offset from
    Top, the build_dt_crankshaft station-plane idiom), cut FLAT_LENGTH
    mid-plane. Construction: ``ref`` from the origin along +X (clock 0) and
    ``radial`` from the origin to the flat's midpoint, one chain sharing the
    origin vertex; ``across`` from the screw's far side to that midpoint,
    parallel to ``radial``, carries the printed ``<name>ClockAF`` and the
    far side's radius; the driving ``<name>ClockAngle`` between ``ref`` and
    ``radial`` is authored last, the sketch's one remaining freedom. The
    rectangle is square to ``radial`` on its midpoint, 2R wide and 1 mm past
    the screw. Returns the plane's name."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    station = FLAT_STATIONS[name]
    plane = f"{name}ClockPlane"
    check(
        f"create_plane {plane}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=station)
        ),
    )
    name_last_feature(adapter, plane)
    check(f"create_sketch {name} clock flat", await adapter.create_sketch(plane))
    z_sign = _sketch_z_per_model_z(adapter)
    radius = MAJOR_DIA / 2.0
    offset = radius - FLAT_DEPTH
    reach = radius + 1.0
    clock = math.radians(KP08_SET_SCREW_SPACING_DEG)
    normal = (math.cos(clock), z_sign * math.sin(clock))  # sketch axes
    tangent = (-normal[1], normal[0])

    def at(along: float, across_: float) -> tuple[float, float]:
        return (
            along * normal[0] + across_ * tangent[0],
            along * normal[1] + across_ * tangent[1],
        )

    dims = SketchDims()
    ref, radial = await add_line_chain(
        adapter, [(reach, 0.0), (0.0, 0.0), at(offset, 0.0)], close=False
    )
    (across,) = await add_line_chain(
        adapter, [at(-radius, 0.0), at(offset, 0.0)], close=False
    )
    for line in (ref, radial, across):
        _as_construction(adapter, line)
    flat, end, outer, start = await add_line_chain(
        adapter,
        [
            at(offset, -radius),
            at(offset, radius),
            at(reach, radius),
            at(reach, -radius),
        ],
    )
    label = f"{name} clock flat"
    await anchor_point_to_origin(adapter, f"{ref}.end", 0.0, 0.0, f"{label} centre")
    await anchor_point_to_origin(
        adapter, f"{ref}.start", reach, 0.0, f"{label} clock 0"
    )
    dims.record(f"{name}ClockRef")
    for first, second, relation in (
        (across, radial, "parallel"),
        (flat, radial, "perpendicular"),
        (end, flat, "perpendicular"),
        (start, flat, "perpendicular"),
        (outer, flat, "parallel"),
    ):
        check(
            f"{label} {first} {relation} {second}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    check(
        f"{label} on the radial's end",
        await adapter.add_sketch_constraint(f"{radial}.end", flat, "midpoint"),
    )
    await dimension_between(
        adapter, f"{across}.start", "origin", "distance", radius, f"{label} far side"
    )
    dims.record(f"{name}ClockFarSide")
    await dimension_between(
        adapter, f"{across}.start", f"{across}.end", "distance", FLAT_AF, f"{label} AF"
    )
    dims.record(f"{name}ClockAF")
    await dimension_between(
        adapter,
        f"{flat}.start",
        f"{flat}.end",
        "distance",
        2.0 * radius,
        f"{label} width",
    )
    dims.record(f"{name}ClockWidth")
    await dimension_between(
        adapter,
        f"{end}.start",
        f"{end}.end",
        "distance",
        reach - offset,
        f"{label} reach",
    )
    dims.record(f"{name}ClockReach")
    _clock_angle(adapter, name, ref, radial, z_sign)
    dims.record(f"{name}ClockAngle")
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}ClockProfile")
    dims.apply(adapter, f"{name}ClockProfile")
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FLAT_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, f"{name}ClockFlat")
    return plane


_FLAT_PLANE_TOL_MM = 1e-4


def _flat_faces_readback(
    adapter, feature_name: str, clock_deg: float, stations: tuple[float, ...]
) -> None:
    """Prove a flats cut by its own planar faces (the
    build_dt_cylinder_gear._notch_kerf_readback idiom): per station, one flat
    square to the clock's radial, FLAT_DEPTH under the crest, FLAT_CHORD by
    FLAT_LENGTH, between two end walls square to the axis at the station
    -+ FLAT_LENGTH / 2. Any other face, or a missing one, fails the build."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    raw = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
    if raw is None:
        raise RuntimeError(f"flats: {feature_name} feature is missing")
    feature = _early_bound(raw, "IFeature")
    error = feature.GetErrorCode2()
    if not isinstance(error, (list, tuple)) or len(error) < 2 or int(error[0] or 0):
        raise RuntimeError(f"flats: {feature_name} error state {error!r}")
    clock = math.radians(clock_deg)
    radial = (math.cos(clock), 0.0, math.sin(clock))
    offset = MAJOR_DIA / 2.0 - FLAT_DEPTH
    flat_area, flat_count, walls = 0.0, 0, []
    for raw_face in feature.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None or not surface.IsPlane():
            raise RuntimeError(f"flats: {feature_name} has a non-planar face")
        values = tuple(float(value) for value in surface.PlaneParams)
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise RuntimeError(
                f"flats: invalid {feature_name} plane parameters {values}"
            )
        normal, root = values[:3], [value * 1000.0 for value in values[3:]]
        along = sum(a * b for a, b in zip(normal, radial, strict=True))
        height = abs(sum(a * b for a, b in zip(normal, root, strict=True)))
        if abs(abs(along) - 1.0) < 1e-9 and abs(height - offset) < _FLAT_PLANE_TOL_MM:
            flat_count += 1
            flat_area += float(face.GetArea()) * 1e6
        elif abs(abs(normal[1]) - 1.0) < 1e-9:
            walls.append(root[1])
        else:
            raise RuntimeError(f"flats: unexpected {feature_name} plane {values}")
    expected_walls = sorted(
        station + side * FLAT_LENGTH / 2.0
        for station in stations
        for side in (-1.0, 1.0)
    )
    expected_area = len(stations) * FLAT_CHORD * FLAT_LENGTH
    if (
        flat_count != len(stations)
        or not math.isclose(flat_area, expected_area, rel_tol=1e-4)
        or len(walls) != len(expected_walls)
        or any(
            abs(found - wanted) > _FLAT_PLANE_TOL_MM
            for found, wanted in zip(sorted(walls), expected_walls, strict=True)
        )
    ):
        raise RuntimeError(
            f"flats: {feature_name} has {flat_count} flats of {flat_area:.4f} mm^2 "
            f"(expected {len(stations)}, {expected_area:.4f}) and end walls at "
            f"{sorted(walls)} (expected {expected_walls})"
        )


def _manufacturing_controls(adapter) -> None:
    """Mark the spec's controls for the drawing, each at its places under the
    title block's band for them."""
    clear_dimensions_for_drawing(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # swTolGeneral prints no band and leaves the title block's row in force;
    # the values record that row so the drawing can verify it.
    for feature, names in DRAWING_DIMENSIONS.items():
        for name in sorted(names):
            _, band = control_si(name)
            tolerance_type = DIMENSION_TOLERANCE_TYPES[name]
            _, dimension = _named_dimension(adapter, feature, name)
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            tolerance.Type = tolerance_type
            if (
                not tolerance.SetValues(-band, band)
                or int(tolerance.Type) != tolerance_type
                or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
                or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
            ):
                raise RuntimeError(f"{name}@{feature}: cannot retain general tolerance")
    for feature_name, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, names)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await _revolve_screw(adapter)
    volume = await volume_check(
        adapter, "leadscrew blank", BLANK_VOLUME_MM3, 0.002 * BLANK_VOLUME_MM3
    )
    # Each flat takes FLAT_VOLUME_MM3 (17.9 mm^3): each cut must take its own
    # count of them, and its faces must be the flats and walls it was drawn as.
    await _flats(adapter)
    _flat_faces_readback(adapter, "Flats", 0.0, tuple(FLAT_STATIONS.values()))
    volume = await volume_check(
        adapter,
        "leadscrew clock-0 flats",
        volume - len(FLAT_STATIONS) * FLAT_VOLUME_MM3,
        0.25 * FLAT_VOLUME_MM3,
    )
    planes = []
    for name in CLOCKED_FLATS:
        planes.append(await _clock_flat(adapter, name))
        _flat_faces_readback(
            adapter,
            f"{name}ClockFlat",
            KP08_SET_SCREW_SPACING_DEG,
            (FLAT_STATIONS[name],),
        )
        volume = await volume_check(
            adapter,
            f"leadscrew {name} clock flat",
            volume - FLAT_VOLUME_MM3,
            0.25 * FLAT_VOLUME_MM3,
        )
    await volume_check(adapter, "leadscrew", VOLUME_MM3, 0.002 * VOLUME_MM3)

    await publish_screw_axis(adapter)
    _manufacturing_controls(adapter)
    blank_reference_geometry(adapter, tuple((plane, "PLANE") for plane in planes))

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)  # 304 stainless, as rolled
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME)
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, SAVED_PROPERTIES_NO_NOTE)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
