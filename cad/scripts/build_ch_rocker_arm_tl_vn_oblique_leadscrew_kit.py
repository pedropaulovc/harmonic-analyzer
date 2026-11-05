r"""Configured ReliaBot T8 kit, Amazon B085DDHJTW (MHA-CH-06-TL-VN-84).

Owner ruling 2026-11-04 (#2187): one purchased SKU, one native model, with the
``LeadScrew`` and ``FeedNut`` members as configurations on the clamping kit's
pattern (``_purchased_part_variants``). It replaces TL-VN-54 (the screw) and
the unreleased TL-VN-82 (the nut). Both members keep their +Y axis at the
origin as one shared ``ScrewAxis`` (Front ∩ Right). Member-owned features are
suppressed in the other configuration; each member carries its own installed
quantity, notes, library material, colour and native BOM grouping key under
the kit's one Number.

``LeadScrew`` is the screw as installed: a plain Ø8 cylinder at the thread's
major diameter (the thread is not modelled), shop-cut to C4's
``SCREW_LENGTH``, each end broken 0.25 x 45° (``ScrewProfile`` ->
``Screw``), then milled with a set-screw flat under each set screw that locks
it: one at clock 0 (+X) at each KP08 and the handwheel (``FlatProfile`` ->
``Flats``), and each KP08's second at 120° from it (``<Station>ClockProfile``
-> ``<Station>ClockFlat``, sketched on the offset plane
``<Station>ClockPlane``). Its controls are named driving dimensions (the
member spec's ``DIMENSION_CONTROLS``) under the title block's general band:
the profile's axis edge ``CutLength``; the flats' ``FlatLength``, ``FlatAF``
and ``<Station>FlatStation``; each clock flat's ``<Station>ClockAF`` and
``<Station>ClockAngle``. Every cut is proved by its own volume step and its
own planar faces. y = 0 is the near (spindle-side) end.

``FeedNut`` is the brass flange nut as fitted: the flange and body revolved
round the Ø6.0 thread-minor bore (``NutProfile`` -> ``Nut``), the four plain
Ø3.5 flange holes (``FlangeHoleSketch`` -> ``FlangeHoles``), and each hole's
82° countersink revolve-cut about the hole's own axis, on Front for the two
holes on X and on Right for the two on Z (``Countersink1`` ..
``Countersink4``, not patterned: circular patterns of cuts fail on stepped
revolved bodies, ``_features.py``). Its rework controls (Codjiflo P2) are
native and authored only here: ``FlangeThick`` (seat face to head face at
the rim) with a LIMIT band, ``CskDia`` with a symmetric band and a "4X"
prefix, the 82° held by the driving ``CskApexDepth``. y = 0 is the faced seat
face. The listing's nominal sizes are hidden supplier references.

Datasheet-built: no vendor CAD obtained. Saving, reopening and per-member
export ownership are delegated to ``save_member_part``; its readback callback
never repairs native state.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_leadscrew_kit.py
"""

from __future__ import annotations

import math
import sys

import _config
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec as leadscrew
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bought_revolve import publish_screw_axis, stock_properties
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import _set_tolerance_precision, set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_bodies,
    require_member_colour,
    require_member_configurations,
    save_member_part,
    select_member_features,
    set_member_suppression,
)
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
from _sketch_circle import define_circle
from _supplier_screw_reference import add_supplier_reference_sketch
from _visibility import assert_reference_geometry_hidden, blank_reference_geometry
from ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec import (
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
    PRINTED_FLAT,
    PROFILE,
    VOLUME_MM3,
    control_si,
)
from solidworks_mcp.adapters.com_variant import double_array

PART_NAME = "ch-rocker-arm-tl-vn-oblique-leadscrew-kit"
LEAD_SCREW_CONFIGURATION = leadscrew.CONFIGURATION
FEED_NUT_CONFIGURATION = feed_nut.CONFIGURATION
CONFIGURATIONS = (LEAD_SCREW_CONFIGURATION, FEED_NUT_CONFIGURATION)
MEMBER_SPECS = {
    LEAD_SCREW_CONFIGURATION: leadscrew,
    FEED_NUT_CONFIGURATION: feed_nut,
}
# Each member's SOLIDWORKS library material and display colour, set in its own
# configuration: SUS304 stainless as rolled, and brass.
MATERIALS = {name: spec.MATERIAL for name, spec in MEMBER_SPECS.items()}
COLOURS = {
    LEAD_SCREW_CONFIGURATION: POLISHED_STEEL,
    FEED_NUT_CONFIGURATION: _config.palette("brass_bright"),
}
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = stock_properties(_PART)
CLOCK_PLANES = tuple(f"{name}ClockPlane" for name in CLOCKED_FLATS)
# Parents precede their dependents; ScrewAxis is shared, not owned by either
# member, and is never part of the suppression matrix.
MEMBER_FEATURES = {
    LEAD_SCREW_CONFIGURATION: (
        "ScrewProfile",
        "Screw",
        "FlatProfile",
        "Flats",
        *(
            feature
            for name in CLOCKED_FLATS
            for feature in (
                f"{name}ClockPlane",
                f"{name}ClockProfile",
                f"{name}ClockFlat",
            )
        ),
    ),
    FEED_NUT_CONFIGURATION: (
        "NutProfile",
        "Nut",
        "FlangeHoleSketch",
        "FlangeHoles",
        *(
            feature
            for index in range(1, len(feed_nut.COUNTERSINK_AXES) + 1)
            for feature in (f"Countersink{index}Profile", f"Countersink{index}")
        ),
        "SupplierReference",
        "SupplierTopReference",
    ),
}
MEMBER_DESCRIPTIONS = {
    name: spec.BOM_DESCRIPTION for name, spec in MEMBER_SPECS.items()
}
MEMBER_PROPERTIES = {
    configuration: {
        **STOCK_PROPERTIES,
        "Material Specification": str(_PART["material_specification"]),
        "Finish": str(_PART["finish"]),
        "Manufacturing Notes": spec.DRAWING_NOTES,
    }
    for configuration, spec in MEMBER_SPECS.items()
}
# File-level, so each member's notes read the same whatever view feeds a
# title block (the clamping kit's convention).
MEMBER_NOTE_PROPERTIES = {
    f"{configuration} Manufacturing Notes": spec.DRAWING_NOTES
    for configuration, spec in MEMBER_SPECS.items()
}
SAVED_DRAWING_PROPERTIES = (
    "Number", "Material Specification", "Finish", "Quantity",
    *STOCK_PROPERTIES, *MEMBER_NOTE_PROPERTIES,
)

# --- LeadScrew ------------------------------------------------------------------

# The sketch dimensions in define_polygon_chain's emission order for
# ``screw_profile_points()``: the anchor at the origin emits none, the segment
# closing on it (the near end face) is skipped, then each segment in line
# order -- one dimension on an axis-parallel segment, radial then axial on
# a chamfer. The axis edge comes first, so the cut length is a driving
# dimension of its own rather than the closure's remainder.
SCREW_PROFILE_DIMENSIONS = (
    "CutLength",
    "FarEndRadius",
    "FarChamferRadial",
    "FarChamferAxial",
    "ShankLength",
    "NearChamferRadial",
    "NearChamferAxial",
)


def screw_profile_points() -> list[tuple[float, float]]:
    """``PROFILE`` as Front-plane sketch points (x = radius, y = station), up
    the axis first: the origin vertex, then the far end, back down the
    outline to the near end face, which closes on the origin."""
    return [PROFILE[0], *reversed(PROFILE[1:])]


async def define_screw_profile(adapter, lines: list[str]) -> SketchDims:
    """Fully define the profile chain; return its named dimensions."""
    dims = SketchDims()
    await define_polygon_chain(
        adapter,
        lines,
        screw_profile_points(),
        label="screw",
        dims=dims,
        names=list(SCREW_PROFILE_DIMENSIONS),
    )
    return dims


async def _revolve_screw(adapter) -> None:
    """Sketch the profile on Front and revolve it 360° about its axis edge.

    The ``revolve_profile`` recipe, with the profile's dimensions named: the
    centerline lies over the axis edge (points 0 -> 1) and merges into its
    corners, the vertex at the origin anchors the chain.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    points = screw_profile_points()
    check("create_sketch screw", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check("screw axis", await adapter.add_centerline(*points[0], *points[1]))
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    dims = await define_screw_profile(adapter, lines)
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


def _lead_screw_controls(adapter) -> None:
    """Mark the member spec's controls for the drawing, each at its places
    under the title block's band for them. Unmarks every earlier mark first:
    LeadScrew is authored first, so the FeedNut's marks follow it."""
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


def _assert_lead_screw_controls(adapter) -> None:
    """Read every LeadScrew control back: driving, at its nominal, under the
    title block's general band."""
    for feature, names in DRAWING_DIMENSIONS.items():
        for name in sorted(names):
            nominal, band = control_si(name)
            _, dimension = _named_dimension(adapter, feature, name)
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            if (
                int(dimension.DrivenState) != 2
                or not math.isclose(
                    abs(float(dimension.SystemValue)), nominal, abs_tol=1e-8
                )
                or int(tolerance.Type) != DIMENSION_TOLERANCE_TYPES[name]
                or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
                or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
            ):
                raise RuntimeError(f"{name}@{feature}: saved LeadScrew control changed")


async def _author_lead_screw(adapter) -> None:
    """The cut screw and its five flats, only in the LeadScrew configuration."""
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
    for name in CLOCKED_FLATS:
        await _clock_flat(adapter, name)
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
    _lead_screw_controls(adapter)
    blank_reference_geometry(adapter, tuple((plane, "PLANE") for plane in CLOCK_PLANES))


# --- FeedNut ---------------------------------------------------------------------


def nut_profile_points() -> list[tuple[float, float]]:
    """``PROFILE`` as Front-plane sketch points: x = radius, y = station."""
    return list(feed_nut.PROFILE)


def hole_sketch_points() -> list[tuple[float, float]]:
    """The flange-hole centres on the Top plane (y = 0, the seat face). The
    Top sketch reads model (x, -z)."""
    return [(x, -z) for x, z in feed_nut.HOLE_CENTRES]


async def _revolve_nut(adapter) -> None:
    """``revolve_profile``'s free-axis recipe with the profile's dimensions
    named: a centerline up the sketch's v-axis from the origin, pinned
    vertical and to its length; the chain anchored at its first vertex. The
    flange's rim edge carries ``FlangeThick``."""
    from solidworks_mcp.adapters.base import RevolveParameters

    points = nut_profile_points()
    dims = SketchDims()
    check("create_sketch nut", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "nut axis", await adapter.add_centerline(0.0, 0.0, 0.0, feed_nut.LENGTH)
    )
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    check(
        "nut axis vertical",
        await adapter.add_sketch_constraint(centerline, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{centerline}.start", 0.0, 0.0, "nut axis")
    check(
        "nut axis length",
        await adapter.add_sketch_dimension(centerline, None, "linear", feed_nut.LENGTH),
    )
    dims.record(feed_nut.NUT_PROFILE_DIMENSIONS[0])
    await define_polygon_chain(
        adapter,
        lines,
        points,
        label="nut",
        dims=dims,
        names=list(feed_nut.NUT_PROFILE_DIMENSIONS[1:]),
    )
    await ensure_fully_defined(adapter, "nut profile")
    check("exit_sketch nut", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    dims.apply(adapter, "NutProfile")
    check("revolve nut", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Nut")


async def _countersink(adapter, index: int, plane: str, u: float) -> None:
    """One 82° countersink revolve-cut about its hole's axis
    (build_pd_transgear_arm_plate's countersinks): the cone from the apex to
    the mouth on the head face, a vertical wall CSK_OVERRUN above it, the top
    and back down the axis; a centerline above the axis top is the revolve
    axis. Drivers: the hole's station, the mouth on the head face, the
    diameter (centerline to the wall, doubled) and the apex depth below the
    mouth, which holds the 82° (an angular sketch dimension reads its
    supplement and flips the cone)."""
    from solidworks_mcp.adapters.base import RevolveParameters

    label = f"countersink {index}"
    names = feed_nut.countersink_dimensions(index)
    profile = feed_nut.countersink_points(u)
    side = 1.0 if u > 0.0 else -1.0
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{label} axis",
        await adapter.add_centerline(
            *profile[3], profile[3][0], feed_nut.CSK_TOP_Y + feed_nut.CSK_OVERRUN
        ),
    )
    cone, wall, top, axis_side = await add_line_chain(adapter, profile)
    set_sketch_direct_db(adapter, False)
    for line, relation in zip(
        (wall, top, axis_side), ("vertical", "horizontal", "vertical"), strict=True
    ):
        check(
            f"{label} {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        f"{label} axis vertical",
        await adapter.add_sketch_constraint(axis, None, "vertical"),
    )
    check(
        f"{label} axis on the profile",
        await adapter.add_sketch_constraint(
            f"{axis}.start", f"{axis_side}.start", "coincident"
        ),
    )
    check(
        f"{label} axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", feed_nut.CSK_OVERRUN),
    )
    dims.record(names[0])
    await dimension_between(
        adapter,
        "origin",
        f"{axis_side}.start",
        "horizontal_distance",
        abs(u),
        f"{label} station",
    )
    dims.record(names[1])
    await dimension_between(
        adapter,
        "origin",
        f"{wall}.start",
        "vertical_distance",
        feed_nut.FLANGE_THICK,
        f"{label} on the head face",
    )
    dims.record(names[2])
    await add_diametric_linear_dimension(
        adapter,
        axis,
        wall,
        (profile[2][0] + side * 3.0, profile[2][1]),
        f"{label} diameter",
    )
    dims.record(names[3])
    await dimension_between(
        adapter,
        f"{cone}.start",
        f"{wall}.start",
        "vertical_distance",
        feed_nut.CSK_APEX_DEPTH,
        f"{label} apex depth",
    )
    dims.record(names[4])
    await dimension_between(
        adapter,
        f"{wall}.start",
        f"{wall}.end",
        "vertical_distance",
        feed_nut.CSK_OVERRUN,
        f"{label} overrun",
    )
    dims.record(names[5])
    await ensure_fully_defined(adapter, f"{label} profile")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, f"Countersink{index}Profile")
    dims.apply(adapter, f"Countersink{index}Profile")
    check(
        f"revolve-cut {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, f"Countersink{index}")


def _author_flange_limits(adapter) -> None:
    """FlangeThick's band as native LIMITs (build_pd_platen_guide._depth_limits):
    3.7/3.3, the flange after the facing pass, seat face to head face."""
    nominal, lower, upper, places = feed_nut.REWORK_CONTROLS["FlangeThick"]
    label = "FlangeThick@NutProfile"
    display, dimension = _named_dimension(adapter, "NutProfile", "FlangeThick")
    if int(dimension.DrivenState) != 2 or not math.isclose(
        float(dimension.SystemValue), nominal / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(f"{label}: not the driving flange thickness")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = feed_nut.TOL_LIMIT
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: LIMIT deviations were rejected")
    if (
        int(tolerance.Type) != feed_nut.TOL_LIMIT
        or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-12
        or abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-12
    ):
        raise RuntimeError(f"{label}: LIMIT tolerance readback changed")
    _set_tolerance_precision(
        display, (lower, upper), display_unit="mm", label=label, places=places
    )


def _feed_nut_rework(adapter) -> None:
    """The FeedNut's native rework controls (Codjiflo P2), authored while it
    is the active member on its own features: the flange LIMIT, the
    countersink's ± and its "4X Ø" prefix, both at the band's one place, then
    marked for the REWORK sheet."""
    _author_flange_limits(adapter)
    _, lower, upper, places = feed_nut.REWORK_CONTROLS["CskDia"]
    set_dimension_symmetric_tolerance(
        adapter, "Countersink1Profile", "CskDia", feed_nut.CSK_DIA_BAND, places=places
    )
    set_dimension_prefix(adapter, "Countersink1Profile", "CskDia", feed_nut.CSK_PREFIX)
    apply_drawing_precision(adapter, feed_nut.DRAWING_PRECISION)
    for feature, names in feed_nut.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    _assert_feed_nut_rework(adapter)


def _assert_feed_nut_rework(adapter) -> None:
    """Read the rework controls back: driving at nominal, their native band
    type and deviations, the prefix, and the apex depth that holds the 82°."""
    for name, (nominal, lower, upper, _places) in feed_nut.REWORK_CONTROLS.items():
        feature = next(
            feature
            for feature, names in feed_nut.DRAWING_DIMENSIONS.items()
            if name in names
        )
        _, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if (
            int(dimension.DrivenState) != 2
            or not math.isclose(float(dimension.SystemValue), nominal / 1000.0, abs_tol=1e-9)
            or int(tolerance.Type) != feed_nut.DIMENSION_TOLERANCE_TYPES[name]
            or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-9
            or abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-9
        ):
            raise RuntimeError(f"{name}@{feature}: FeedNut rework control changed")
    display, _ = _named_dimension(adapter, "Countersink1Profile", "CskDia")
    if str(_early_bound(display, "IDisplayDimension").GetText(1) or "") != (
        feed_nut.CSK_PREFIX
    ):
        raise RuntimeError("CskDia@Countersink1Profile: prefix changed")
    _, depth = _named_dimension(adapter, "Countersink1Profile", "CskApexDepth")
    if int(depth.DrivenState) != 2 or not math.isclose(
        float(depth.SystemValue), feed_nut.CSK_APEX_DEPTH / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("CskApexDepth@Countersink1Profile: the 82° driver changed")


async def _author_feed_nut(adapter) -> None:
    """The fitted nut and its rework controls, only in the FeedNut configuration."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    await _revolve_nut(adapter)
    expected = feed_nut.BODY_VOLUME_MM3
    await volume_check(adapter, "nut body", expected, 0.002 * expected)

    # Four plain flange holes, cut mid-plane from the seat face: 2 x
    # FLANGE_THICK deep reaches through the flange on +Y and meets only air
    # on -Y (the spigot is faced off).
    check("create_sketch flange holes", await adapter.create_sketch("Top"))
    for index, (u, v) in enumerate(hole_sketch_points(), start=1):
        await define_circle(adapter, u, v, feed_nut.HOLE_DIA / 2.0, f"flange hole {index}")
    await ensure_fully_defined(adapter, "flange hole sketch")
    check("exit_sketch flange holes", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeHoleSketch")
    check(
        "cut flange holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * feed_nut.FLANGE_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FlangeHoles")
    expected -= len(feed_nut.HOLE_CENTRES) * feed_nut.HOLE_VOLUME_MM3
    await volume_check(adapter, "flange holes", expected, 0.002 * expected)

    # A cut on the wrong side of the head face would meet only air, and the
    # volume check would refuse it.
    for index, (plane, u) in enumerate(feed_nut.COUNTERSINK_AXES, start=1):
        await _countersink(adapter, index, plane, u)
        expected -= feed_nut.CSK_VOLUME_MM3
        await volume_check(
            adapter, f"Countersink{index}", expected, 0.03 * feed_nut.CSK_VOLUME_MM3
        )
    await volume_check(
        adapter, "fitted nut", feed_nut.VOLUME_MM3, 0.002 * feed_nut.VOLUME_MM3
    )
    _feed_nut_rework(adapter)
    await add_supplier_reference_sketch(
        adapter,
        feed_nut.SUPPLIER_REFERENCE_DIMENSIONS,
        starts=feed_nut.SUPPLIER_REFERENCE_STARTS,
        planes=feed_nut.SUPPLIER_REFERENCE_PLANES,
    )


# --- The kit -----------------------------------------------------------------------


def _member_references(configuration: str) -> tuple[tuple[str, str], ...]:
    """The reference geometry each member hides in its own configuration."""
    planes = CLOCK_PLANES if configuration == LEAD_SCREW_CONFIGURATION else ()
    return (("ScrewAxis", "AXIS"), *((plane, "PLANE") for plane in planes))


async def _readback(adapter, configuration: str) -> None:
    """Assert the selected member without authoring, repairing or saving it."""
    assert_member_suppression(adapter, configuration, MEMBER_FEATURES)
    require_member_bodies(adapter, configuration, 1, ("ScrewAxis",))
    spec = MEMBER_SPECS[configuration]
    await volume_check(
        adapter,
        f"{configuration} saved volume",
        spec.VOLUME_MM3,
        0.002 * spec.VOLUME_MM3,
    )
    if configuration == LEAD_SCREW_CONFIGURATION:
        await bbox_extent_check(adapter, "screw length", "y", leadscrew.LENGTH)
        await bbox_extent_check(adapter, "screw diameter", "z", leadscrew.MAJOR_DIA)
        _assert_lead_screw_controls(adapter)
    else:
        await bbox_extent_check(adapter, "nut length", "y", feed_nut.LENGTH)
        await bbox_extent_check(adapter, "flange diameter", "x", feed_nut.FLANGE_DIA)
        _assert_feed_nut_rework(adapter)
    assert_member_properties(
        adapter,
        PART_NAME,
        configuration,
        MEMBER_DESCRIPTIONS[configuration],
        MEMBER_PROPERTIES[configuration],
    )
    require_member_colour(adapter, configuration, COLOURS[configuration])
    assert_reference_geometry_hidden(adapter, f"{PART_NAME} [{configuration}]")


async def build(adapter) -> dict[str, str]:
    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)
    # The bought-parts mate contract, shared by both members.
    await publish_screw_axis(adapter)

    authored = []
    for configuration, author in (
        (LEAD_SCREW_CONFIGURATION, _author_lead_screw),
        (FEED_NUT_CONFIGURATION, _author_feed_nut),
    ):
        await activate_member(adapter, configuration)
        # Foreign solids must be absent during authoring: otherwise a revolve
        # or cut can merge with, or cut into, the other member.
        for previous in reversed(authored):
            set_member_suppression(adapter, MEMBER_FEATURES[previous], suppressed=True)
        await author(adapter)
        authored.append(configuration)

    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, MEMBER_NOTE_PROPERTIES)
    for configuration in CONFIGURATIONS:
        await select_member_features(adapter, configuration, MEMBER_FEATURES)
        set_member_suppression(adapter, ("ScrewAxis",), suppressed=False)
        blank_reference_geometry(adapter, _member_references(configuration))
        await apply_material(adapter, MATERIALS[configuration])
        await apply_color(adapter, COLOURS[configuration])
        apply_member_properties(
            adapter,
            PART_NAME,
            configuration,
            MEMBER_DESCRIPTIONS[configuration],
            MEMBER_PROPERTIES[configuration],
        )
        await report_mass_properties(adapter)

    artefacts = await save_member_part(
        adapter, PART_NAME, CONFIGURATIONS, material=MATERIALS, readback=_readback
    )
    require_saved_drawing_properties(adapter, SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
