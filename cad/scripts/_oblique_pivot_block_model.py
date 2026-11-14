"""Native TL-22/TL-32 shoulder-screw block recipes, in the carriage frame.

Taps are represented by their drill cylinders (as native Wizard taps are),
not by helical cut threads. The model owns every size and printed tolerance.
"""
from __future__ import annotations
import math
from typing import Any
from collections.abc import Callable
import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _bind, _com_invoke, _early_bound
from _dimensions import name_dimensions
from _document_units import apply_package_model_units
from _drawing_marks import clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_angular_tolerance, set_dimension_symmetric_tolerance
from _metric_vendor_dimension import set_metric_vendor_units
from _feature_tree import name_last_feature
from _holes import wizard_holes
from _part_checks import volume_check, report_mass_properties
from _part_properties import part_drawing_unit
from _rebuild import force_rebuild
from _sketch import SketchDims, add_line_chain, anchor_point_to_origin, anchor_point_to_point, blank_reference_sketches, dimension_between, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
import ch_rocker_arm_tl_oblique_pivot_block_spec as spec
from ch_rocker_arm_tl_oblique_pivot_block_spec import BOLT_Y, HOLE_DIA, CBORE_FLOOR, CBORE_FLOOR_REFERENCE, CBORE_SECTION_PLANE

MATERIAL = "6061 Alloy"

def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )

def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    The pivot plate's mapper (build_ch_rocker_arm_tl_trammel_pivot_plate):
    profile points go through ``ModelToSketchTransform`` so only the
    orientation is assumed, and it is checked here.
    """
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch

def _xy_mapper(adapter: Any, z: float, label: str):
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label=label)
    origin = to_sketch((0.0, 0.0, z))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{label}: sketch origin maps to {origin}")
    return lambda x, y: to_sketch((x, y, z))

def _as_construction(adapter: Any, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (rebind to the
    base ISketchSegment, which declares ``ConstructionGeometry``;
    build_ch_rocker_arm_tl_oblique_base_bar)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")

async def _cbore_floor_reference(adapter, part) -> list[tuple[str, str]]:
    """The hidden sketch carrying the printed counterbore floor height.

    B-B cuts the -X carriage-hole column, clear of the centred feed block's
    +X lug. Its native reference sketch lies on the same Right-plane offset,
    so the section imports the actual counterbore floor from the carriage
    seat. The mapper checks the signed plane location before authoring.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane {CBORE_SECTION_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=spec.CBORE_SECTION_X
            )
        ),
    )
    name_last_feature(adapter, CBORE_SECTION_PLANE)
    # The offset prints its magnitude (build_ch_rocker_arm_tl_oblique_carrier).
    jobs = [
        (
            name_dimensions(adapter, CBORE_SECTION_PLANE, ["CboreSectionOffset"])[0],
            '"BoltX"',
        )
    ]
    blank_reference_geometry(adapter, ((CBORE_SECTION_PLANE, "PLANE"),))

    feature = CBORE_FLOOR_REFERENCE
    y_wall = BOLT_Y + HOLE_DIA / 2.0
    check(f"create_sketch {feature}", await adapter.create_sketch(CBORE_SECTION_PLANE))
    # A Right-plane sketch reads (u, v) = model (-Z, Y) (build_pd_platen).
    to_sketch = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=feature)
    origin = to_sketch((spec.CBORE_SECTION_X, 0.0, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{feature}: sketch origin maps to {origin}")
    foot = to_sketch((spec.CBORE_SECTION_X, y_wall, 0.0))
    floor = to_sketch((spec.CBORE_SECTION_X, y_wall, CBORE_FLOOR))
    set_sketch_direct_db(adapter, True)
    line = check(feature, await adapter.add_line(*foot, *floor))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    # Model Z runs along the sketch's u.
    check(
        f"{feature} along Z",
        await adapter.add_sketch_constraint(line, None, "horizontal"),
    )
    dims = SketchDims()
    await anchor_point_to_origin(
        adapter, f"{line}.start", *foot, f"{feature} foot on the hole wall"
    )
    dims.record("CboreFloorY", f'"BoltY" + {HOLE_DIA / 2.0:g}mm')
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "horizontal_distance",
        CBORE_FLOOR,
        f"{feature} floor height",
    )
    dims.record("CboreFloor", '"CboreFloor"')
    if "SectionBlockHeight" in part.DRAWING_DIMENSIONS[feature]:
        # TL-32 prints the block height on B-B. Its line stands inside the
        # cut face, midway between the counterbore wall and the +Y face.
        # TL-22's sections never imported a full-height dimension (farm
        # rounds 1 to 9), so TL-22 prints the Block extrusion's depth on a
        # standard Right view.
        y_side = (BOLT_Y + spec.CBORE_DIA / 2.0 + spec.BLOCK_WIDTH / 2.0) / 2.0
        side_foot = to_sketch((spec.CBORE_SECTION_X, y_side, 0.0))
        side_top = to_sketch((spec.CBORE_SECTION_X, y_side, spec.BLOCK_HEIGHT))
        side = await _construction(adapter, adapter.add_line(side_foot[0], side_foot[1], side_top[0], side_top[1]),
                                   f"{feature} block height")
        check(f"{feature} block height along Z", await adapter.add_sketch_constraint(side, None, "horizontal"))
        await anchor_point_to_origin(adapter, f"{side}.start", *side_foot, f"{feature} block height foot")
        dims.record("SectionSideY")
        await dimension_between(adapter, f"{side}.start", f"{side}.end", "horizontal_distance",
                                spec.BLOCK_HEIGHT, f"{feature} block height")
        dims.record("SectionBlockHeight")
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return jobs + dims.apply(adapter, feature)


async def _rectangle(adapter, name, bounds, names, *, anchor=0):
    """``anchor`` indexes the origin-anchored corner: (x0,y0), (x1,y0), (x1,y1),
    (x0,y1)."""
    check(name, await adapter.create_sketch("Front"))
    at = _xy_mapper(adapter, 0.0, name)
    x0, x1, y0, y1 = bounds
    points = [at(x0,y0),at(x1,y0),at(x1,y1),at(x0,y1)]
    dims = SketchDims()
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(adapter, lines, points, anchor=anchor, label=name, dims=dims, names=names)
    await ensure_fully_defined(adapter, name)
    check(name, await adapter.exit_sketch())
    name_last_feature(adapter, name)
    dims.apply(adapter, name)


async def _circles(adapter, plane, z, profile, circles, *, side=False):
    check(profile, await adapter.create_sketch(plane))
    at = (_sketch_mapper(adapter, u_axis=2, v_axis=1, label=profile)
          if side else _xy_mapper(adapter, z, profile))
    dims = SketchDims()
    for x,y,dia,names in circles:
        uv = at((z,y,x)) if side else at(x,y)
        await define_circle(adapter,*uv,dia/2,profile,dims=dims,names=names)
    await ensure_fully_defined(adapter, profile)
    check(profile, await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)


async def _drawn(adapter, create, label: str) -> str:
    """One sketch entity, drawn without inference (no snap to the model
    edges it lies on), so only the dimensions below define it. ``create``
    is the un-awaited adapter call; it runs inside the mode.

    A line ON a printed outline stays a plain sketch line, as the base bar's
    and end bracket's reference lines do: shown in its view, a construction
    line's dash font prints over the outline, which then reads broken by
    dashes (TL-32 machinist review, farm run 20261105T054045952Z: the plan's
    -X edge and lug -X face, VIEW D's lug end; TL-22's -X edge the same)."""
    set_sketch_direct_db(adapter, True)
    try:
        return check(label, await create)
    finally:
        set_sketch_direct_db(adapter, False)


async def _construction(adapter, create, label: str) -> str:
    """One construction entity, drawn as :func:`_drawn`."""
    entity = await _drawn(adapter, create, label)
    _as_construction(adapter, entity)
    return entity


async def _offset_point(adapter, dims, base, point, du, dv, names, label) -> None:
    """Pin sketch ``point`` at offset (du, dv) from ``base`` and record the
    dims ``anchor_point_to_point`` emits: none for a zero component."""
    await anchor_point_to_point(adapter, base, point, du, dv, label)
    for offset, name in zip((du, dv), names, strict=True):
        if abs(offset) >= 1e-9:
            dims.record(name)


async def _construction_circle(adapter, dims, x_base, y_base, uv, dia, names, label) -> str:
    """A construction circle on a real hole: its centre's X from the sketch
    point ``x_base`` and its Y from ``y_base`` (each a ``(point, uv)`` pair),
    a zero offset an alignment relation instead of a dimension; then sized.
    ``names`` are the X, Y and diameter names; only emitted dims are recorded."""
    circle = await _construction(adapter, adapter.add_circle(uv[0], uv[1], dia / 2), label)
    centre = f"{circle}.center"
    for (base, base_uv), axis, kind, align, name in (
        (x_base, 0, "horizontal_distance", "vertical_points", names[0]),
        (y_base, 1, "vertical_distance", "horizontal_points", names[1]),
    ):
        offset = abs(uv[axis] - base_uv[axis])
        if offset < 1e-9:
            check(f"{label} {align}", await adapter.add_sketch_constraint(base, centre, align))
        else:
            await dimension_between(adapter, base, centre, kind, offset, f"{label} {name}")
            dims.record(name)
    check(f"{label} diameter", await adapter.add_sketch_dimension(circle, None, "diameter", dia))
    dims.record(names[2])
    return circle


async def _plan_datum_reference(adapter, part) -> None:
    """The hidden top-face sketch that carries the plan's ordinates (rule 10):
    every X from the -X edge, every Y from one full-width edge, so the plan has
    one origin (machinist review, farm r3 20261108T014606685Z: the hole rows
    were chained .512 through the seat axis). Plain lines ON the -X edge and
    the +X end, construction circles ON the shoulder seat, one carriage hole
    per column and one per row, and on TL-32 a plain line ON the lug's -X
    face, which also carries the overall from the top (+Y) edge and the lug's
    length from the step. Shown in the plan view, every entity overlies a
    real edge. X dims leave the -X edge's +Y end, above the plan's X tiers;
    Y dims leave a +X end corner, BlockSideY's own witness point (from the -X
    corner a witness ran the whole edge and, on TL-32, across the lug's top
    face: round-5 review). TL-22 measures Y from its -Y edge (+X/-Y corner).
    TL-32 measures from its full-width +Y edge (+X/+Y corner): its -Y edge is
    only the step left of the lug, and the +X/-Y point lies on the lug's
    right edge, where no -Y edge exists (restack farm r4
    20261108T055431582Z; Main-approved 2026-11-08, dimensioning only)."""
    feed = hasattr(part, "LUG_WIDTH")
    feature = spec.PLAN_DATUM_REFERENCE
    z = part.BLOCK_HEIGHT
    check(f"create_sketch {feature}", await adapter.create_sketch("TopFace"))
    at = _xy_mapper(adapter, z, feature)
    dims = SketchDims()
    edge_start, edge_end = at(part.BLOCK_X0, -part.BLOCK_WIDTH / 2), at(part.BLOCK_X0, part.BLOCK_WIDTH / 2)
    edge = await _drawn(adapter, adapter.add_line(edge_start[0], edge_start[1], edge_end[0], edge_end[1]),
                        f"{feature} -X edge")
    check(f"{feature} -X edge vertical", await adapter.add_sketch_constraint(edge, None, "vertical"))
    await anchor_point_to_origin(adapter, f"{edge}.start", *edge_start, f"{feature} -X edge foot")
    dims.record("PlanEdgeX")
    dims.record("PlanEdgeY")
    await dimension_between(adapter, f"{edge}.start", f"{edge}.end", "vertical_distance",
                            part.BLOCK_WIDTH, f"{feature} -X edge length")
    dims.record("PlanEdgeLength")
    end_start, end_end = at(part.BLOCK_X1, -part.BLOCK_WIDTH / 2), at(part.BLOCK_X1, part.BLOCK_WIDTH / 2)
    end = await _drawn(adapter, adapter.add_line(end_start[0], end_start[1], end_end[0], end_end[1]),
                       f"{feature} +X end")
    check(f"{feature} +X end vertical", await adapter.add_sketch_constraint(end, None, "vertical"))
    await _offset_point(adapter, dims, f"{edge}.start", f"{end}.start", abs(end_start[0] - edge_start[0]), 0.0,
                        ("PlanEndX", "PlanEndY"), f"{feature} +X end from -X edge")
    await dimension_between(adapter, f"{end}.start", f"{end}.end", "vertical_distance",
                            part.BLOCK_WIDTH, f"{feature} +X end length")
    dims.record("PlanEndLength")
    x_base = (f"{edge}.end", edge_end)
    y_base = (f"{end}.end", end_end) if feed else (f"{end}.start", end_start)
    await _construction_circle(adapter, dims, x_base, y_base, at(spec.BORE_X, spec.BORE_Y), spec.BORE_DIA,
                               ("PlanBoreX", "PlanBoreY", "PlanBoreDia"), f"{feature} seat")
    columns = {}
    for i, (x, y) in enumerate(spec.PLAN_DATUM_HOLES, 1):
        columns[x] = (await _construction_circle(
            adapter, dims, x_base, y_base, at(x, y), spec.HOLE_DIA,
            (f"PlanHole{i}X", f"PlanHole{i}Y", f"PlanHole{i}Dia"), f"{feature} carriage hole column {i}",
        ), at(x, y))
    # The other row's hole stands under a column's: aligned to it, so only
    # its Y is dimensioned.
    i = len(spec.PLAN_DATUM_HOLES) + 1
    x, y = spec.PLAN_DATUM_ROW_HOLE
    above, above_uv = columns[x]
    await _construction_circle(adapter, dims, (f"{above}.center", above_uv), y_base, at(x, y), spec.HOLE_DIA,
                               (f"PlanHole{i}X", f"PlanHole{i}Y", f"PlanHole{i}Dia"),
                               f"{feature} carriage hole row")
    if feed:
        lug_top, lug_end = at(part.LUG_X0, part.LUG_Y1), at(part.LUG_X0, part.LUG_Y0)
        lug = await _drawn(adapter, adapter.add_line(lug_top[0], lug_top[1], lug_end[0], lug_end[1]),
                           f"{feature} lug -X face")
        check(f"{feature} lug face vertical", await adapter.add_sketch_constraint(lug, None, "vertical"))
        # The lug face's X from the -X edge; its top's Y is set by the lug's
        # length from its end (not aligned to the -X edge's foot, which
        # PlanLugLength would make redundant).
        await dimension_between(adapter, f"{edge}.start", f"{lug}.start", "horizontal_distance",
                                abs(lug_top[0] - edge_start[0]), f"{feature} lug face from -X edge")
        dims.record("PlanLugX")
        await dimension_between(adapter, f"{edge}.end", f"{lug}.end", "vertical_distance",
                                part.BLOCK_WIDTH / 2 - part.LUG_Y0, f"{feature} overall from +Y edge")
        dims.record("PlanOverallY")
        # The lug's length, step face to lug end: printed in the pocket left
        # of the lug, its upper arrow on the step face itself (the 1.58 has
        # no -Y end to leave on the +X side of an L).
        await dimension_between(adapter, f"{lug}.start", f"{lug}.end", "vertical_distance",
                                part.LUG_LENGTH, f"{feature} lug length from step")
        dims.record("PlanLugLength")
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


async def _driving_angle(adapter, first: str, second: str, text_mm, degrees: float, label: str) -> None:
    """A driving angular dimension between two sketch lines, its text at the
    model point ``text_mm`` (inside the wedge it measures), read back exact.
    The shared ``add_angular_reference_dimension`` makes a driven one and
    passes sketch coordinates with z = 0, which is not on the nut face's plane
    (build_ch_rocker_arm_tl_oblique_riser's note); the supplier reference
    sketches' driving angle is the pattern (_supplier_screw_reference)."""
    import math
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    try:
        _select_sketch_entities(adapter, [first, second], 0)
        display, status = _early_bound(model.Extension, "IModelDocExtension").AddSpecificDimension(
            *(c / 1000.0 for c in text_mm), 3, 0  # swDimensionType_e.swAngularDimension
        )
    finally:
        model.ClearSelection2(True)
    if display is None or status != 0:  # swAddSpecificDimension_Success
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 3:  # swAngularDimension
        raise RuntimeError(f"{label}: not a native angular dimension")
    angle = _early_bound(display.GetDimension2(0), "IDimension")
    angle.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(angle.DrivenState) != 2 or not math.isclose(
        float(angle.SystemValue), math.radians(degrees), rel_tol=0.0, abs_tol=math.radians(1e-5)
    ):
        raise RuntimeError(
            f"{label}: angle {math.degrees(float(angle.SystemValue)):.6f} deg is not a "
            f"driving {degrees:g} deg"
        )


async def _nut_pattern_reference(adapter, part) -> None:
    """The hidden nut-face sketch that carries VIEW D's locations: a plain
    line ON the lug end and the leadscrew axis (a construction circle ON the
    screw clearance) from that end and the bottom face; and the taps'
    clocking, the angle between two construction rays from the axis, along
    +Z and to one tap's centre. The feed nut's taps are located by their
    transfer callout, not here; the clocking bounds every one of them."""
    import math
    feature = "NutPatternReference"
    check(f"create_sketch {feature}", await adapter.create_sketch("NutFace"))
    to_sketch = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=feature)

    def at(y: float, z: float) -> tuple[float, float]:
        return to_sketch((part.NUT_FACE_X, y, z))

    dims = SketchDims()
    end_start, end_end = at(part.LUG_Y0, 0.0), at(part.LUG_Y0, part.BLOCK_HEIGHT)
    end = await _drawn(adapter, adapter.add_line(end_start[0], end_start[1], end_end[0], end_end[1]),
                       f"{feature} lug end")
    check(f"{feature} lug end horizontal", await adapter.add_sketch_constraint(end, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{end}.start", *end_start, f"{feature} lug end corner")
    dims.record("NutEndY")
    await dimension_between(adapter, f"{end}.start", f"{end}.end", "horizontal_distance",
                            part.BLOCK_HEIGHT, f"{feature} lug end length")
    dims.record("NutEndLength")
    axis_uv = at(part.NUT_AXIS_Y, part.NUT_AXIS_Z)
    end_corner = (f"{end}.start", end_start)
    axis = await _construction_circle(adapter, dims, end_corner, end_corner, axis_uv, part.SCREW_CLEARANCE_DIA,
                                      ("NutCentreZ", "NutCentreY", "NutCentreDia"), f"{feature} nut axis")
    centre = f"{axis}.center"
    reach = part.NUT_CLOCK_RAY
    base_end = at(part.NUT_AXIS_Y, part.NUT_AXIS_Z + reach)
    baseline = await _construction(adapter, adapter.add_line(axis_uv[0], axis_uv[1], base_end[0], base_end[1]),
                                   f"{feature} clock baseline")
    check(f"{feature} clock baseline on the axis",
          await adapter.add_sketch_constraint(f"{baseline}.start", centre, "coincident"))
    check(f"{feature} clock baseline along +Z", await adapter.add_sketch_constraint(baseline, None, "horizontal"))
    await dimension_between(adapter, f"{baseline}.start", f"{baseline}.end", "horizontal_distance",
                            reach, f"{feature} clock baseline length")
    dims.record("NutClockBaselineLength")
    tap_y, tap_z = part.NUT_HOLES_YZ[part.NUT_CLOCK_TAP]
    tap_uv = at(tap_y, tap_z)
    ray = await _construction(adapter, adapter.add_line(axis_uv[0], axis_uv[1], tap_uv[0], tap_uv[1]),
                              f"{feature} clock ray")
    check(f"{feature} clock ray on the axis",
          await adapter.add_sketch_constraint(f"{ray}.start", centre, "coincident"))
    await dimension_between(adapter, f"{ray}.start", f"{ray}.end", "distance",
                            math.hypot(tap_y - part.NUT_AXIS_Y, tap_z - part.NUT_AXIS_Z),
                            f"{feature} clock ray length")
    dims.record("NutClockRayLength")
    # The text on the wedge's bisector, inside the wedge, so it reads the
    # angle itself, not its supplement.
    bisector = math.atan2(tap_y - part.NUT_AXIS_Y, tap_z - part.NUT_AXIS_Z) / 2.0
    await _driving_angle(
        adapter, baseline, ray,
        (part.NUT_FACE_X, part.NUT_AXIS_Y + 0.6 * reach * math.sin(bisector),
         part.NUT_AXIS_Z + 0.6 * reach * math.cos(bisector)),
        part.NUT_CLOCK_DEG, f"{feature} tap clocking",
    )
    dims.record(part.NUT_CLOCK_DIMENSION)
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


def _native_nut_tap_diameter(adapter, part) -> float:
    """Use the committed Wizard drill, not the rounded catalogue volume value."""
    from _feature_tree import _feature_by_name

    feature = _feature_by_name(adapter, "NutTaps")
    # GetDefinition is VT_DISPATCH. Bind the raw InvokeTypes return before
    # reading its property; _early_bound alone passes bare PyIDispatch through.
    definition = _bind(_com_invoke(feature, "IFeature", "GetDefinition"), "IWizardHoleFeatureData2")
    if feature.GetTypeName2() != "HoleWzd" or definition is None:
        raise RuntimeError(f"{part.PART_NAME}: NutTaps has no native Hole Wizard definition")
    diameter = float(definition.ThruTapDrillDiameter) * 1000.0
    # TAP_DRILL_MM pins this table entry to three decimal mm; the Wizard
    # retains the exact native value. This tests that representation, not a
    # manufacturing allowance. Solid-cylinder matching below stays at 1e-6 mm.
    if not math.isfinite(diameter) or diameter <= 0.0 or round(diameter, 3) != part.NUT_TAP_DRILL:
        raise RuntimeError(
            f"{part.PART_NAME}: NutTaps.ThruTapDrillDiameter={diameter!r} mm "
            f"does not represent catalogue drill {part.NUT_TAP_DRILL!r} mm"
        )
    _telemetry.info(
        f"{part.PART_NAME}: native NutTaps through-tap drill {diameter!r} mm; "
        f"catalogue three-decimal value {part.NUT_TAP_DRILL!r} mm"
    )
    return diameter


@_telemetry.traced("part.readback.flush_lug_end")
def _require_flush_lug_end(body, part) -> dict[str, list[float]]:
    """TL-32's +X end is ONE planar face from the lug end to the +Y edge,
    full height (owner ruling 2026-11-07): the lug's +X side and the block's
    end merged, with no step and no seam between the two extrusions.

    Exact reads only; ``IFace2.GetBox`` is not a tight box. Members (both
    tlbs SOLIDWORKS 3DEXPERIENCE R2026x, audited 2026-11-07), lengths in
    metres:
    ``IBody2.GetFaces() -> VARIANT`` (faces); ``face_geometry`` reads
    ``IFace2.GetSurface() -> IDispatch``, ``ISurface.Identity() -> I4``
    (swSurfaceTypes_e PLANE_TYPE = 4001), ``ISurface.PlaneParams`` (get,
    ``VARIANT`` [normal xyz, root point xyz]) and
    ``IFace2.FaceInSurfaceSense() -> BOOL`` (the outward normal);
    ``IFace2.GetEdges() -> VARIANT`` (edges);
    ``IEdge.GetStartVertex()/GetEndVertex() -> IDispatch`` (None on a closed
    edge: the face's tap and clearance circles); ``IVertex.GetPoint() ->
    VARIANT`` [x, y, z]."""
    from _gtol_face import SURFACE_PLANE
    from _gtol_face_read import face_geometry
    ends = []
    for face in _com_invoke(body, "IBody2", "GetFaces") or ():
        geometry = face_geometry(face, identities=frozenset({SURFACE_PLANE}))
        if geometry is None or geometry.identity != SURFACE_PLANE:
            continue
        normal, plane_x = geometry.outward_normal, geometry.parameters[3] * 1000.0
        if abs(normal[0] - 1.0) < 1e-9 and abs(plane_x - part.BLOCK_X1) < 1e-6:
            ends.append(face)
    if len(ends) != 1:
        raise RuntimeError(f"{part.PART_NAME}: {len(ends)} planar +X faces at X {part.BLOCK_X1} mm, "
                           "expected the one merged lug and block end")
    corners = []
    for edge in _com_invoke(ends[0], "IFace2", "GetEdges") or ():
        for end in ("GetStartVertex", "GetEndVertex"):
            vertex = _com_invoke(edge, "IEdge", end)
            if vertex is not None:
                corners.append([float(c) * 1000.0 for c in _com_invoke(vertex, "IVertex", "GetPoint")])
    span = {
        "x": [min(c[0] for c in corners), max(c[0] for c in corners)] if corners else [],
        "y": [min(c[1] for c in corners), max(c[1] for c in corners)] if corners else [],
        "z": [min(c[2] for c in corners), max(c[2] for c in corners)] if corners else [],
    }
    want = {"x": (part.BLOCK_X1, part.BLOCK_X1), "y": (part.LUG_Y0, part.BLOCK_WIDTH / 2),
            "z": (0.0, part.BLOCK_HEIGHT)}
    if not corners or not all(
        math.isclose(got, wanted, rel_tol=0.0, abs_tol=1e-6)
        for axis, limits in want.items() for got, wanted in zip(span[axis], limits, strict=True)
    ):
        raise RuntimeError(
            f"{part.PART_NAME}: the +X end face's vertices span {span!r} mm, "
            f"expected {want!r}: the lug end does not run flush with the block end"
        )
    return span


@_telemetry.traced("part.readback.oblique_block_geometry")
def require_block_geometry(adapter, part) -> None:
    """Read physical bore axes and model dimensions; never certify a nominal box."""
    from _drawing_precision import _named_dimensions
    from _gtol_face import SURFACE_CYLINDER
    from _gtol_face_read import face_geometry

    bodies = tuple(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"{part.PART_NAME}: expected one native solid for readback")
    cylinders = []
    for face in _early_bound(bodies[0], "IBody2").GetFaces() or ():
        geometry = face_geometry(face, identities=frozenset({SURFACE_CYLINDER}))
        if geometry is not None and geometry.identity == SURFACE_CYLINDER:
            cylinders.append(geometry.parameters)
    observations = [
        {"origin_mm": [v * 1000.0 for v in parameters[:3]],
         "axis": list(parameters[3:6]), "diameter_mm": parameters[6] * 2000.0}
        for parameters in cylinders if len(parameters) == 7
    ]
    expected = [
        ("pivot seat", 2, (spec.BORE_X, spec.BORE_Y, 0.0), spec.BORE_DIA),
        ("pivot tap", 2, (spec.BORE_X, spec.BORE_Y, 0.0), spec.PIVOT_TAP_DRILL),
        *[
            (f"M4 {index} {label}", 2, (x, y, 0.0), diameter)
            for index, (x, y) in enumerate(spec.BOLT_POINTS, 1)
            for label, diameter in (("clearance", spec.HOLE_DIA), ("counterbore", spec.CBORE_DIA))
        ],
    ]
    if hasattr(part, "NUT_FACE_X"):
        nut_tap_diameter = _native_nut_tap_diameter(adapter, part)
        expected += [
            ("leadscrew clearance", 0, (0.0, part.NUT_AXIS_Y, part.NUT_AXIS_Z), part.SCREW_CLEARANCE_DIA),
            *[(f"nut tap {index}", 0, (0.0, y, z), nut_tap_diameter)
              for index, (y, z) in enumerate(part.NUT_HOLES_YZ, 1)],
        ]
    measured = {}
    for label, axis, centre, diameter in expected:
        matches = [
            parameters for parameters in cylinders
            if len(parameters) == 7
            and abs(abs(parameters[axis + 3]) - 1.0) < 1e-9
            and all(abs(parameters[i] * 1000.0 - centre[i]) < 1e-6
                    for i in range(3) if i != axis)
            and abs(parameters[6] * 2000.0 - diameter) < 1e-6
        ]
        if not matches:
            raise RuntimeError(
                f"{part.PART_NAME}: no native {label} at {centre}, "
                f"axis index {axis}, diameter {diameter!r} mm; "
                f"observed solid cylinders: {observations!r}"
            )
        measured[label] = [list(parameters) for parameters in matches]
    if hasattr(part, "LUG_WIDTH"):
        measured["flush +X end span"] = _require_flush_lug_end(bodies[0], part)
    dimensions = {}
    for feature, names in part.DRAWING_DIMENSIONS.items():
        wanted = set(names) & part.DRAWING_VALUES.keys()
        for name, (_display, dimension) in _named_dimensions(adapter, feature, wanted).items():
            value = float(dimension.SystemValue) * 1000.0
            if not math.isclose(value, part.DRAWING_VALUES[name], rel_tol=0.0, abs_tol=1e-6):
                raise RuntimeError(f"{name}@{feature}: native {value}, expected {part.DRAWING_VALUES[name]}")
            dimensions[f"{name}@{feature}"] = value
    _telemetry.info("centred block native dimensional readback", part=part.PART_NAME,
                    cylinders=measured, dimensions_mm=dimensions)


async def build_block_model(adapter, part) -> None:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters
    check("create part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(part.PART_NAME), label=part.PART_NAME)
    # BlockSideY's witness leaves the anchor corner. TL-22 anchors at +X/-Y
    # (from the -X corner its extension line ran the whole -Y edge: round-5
    # review). TL-32 anchors at +X/+Y: its -Y edge is only the step left of
    # the lug, so a +X/-Y witness left the lug's right edge where no -Y edge
    # exists (restack farm r4 20261108T055431582Z; Main-approved 2026-11-08).
    await _rectangle(adapter,"BlockProfile",(part.BLOCK_X0,part.BLOCK_X1,-part.BLOCK_WIDTH/2,part.BLOCK_WIDTH/2),
                     ["BlockLength","BlockWidth","BlockEndX","BlockSideY"],
                     anchor=2 if hasattr(part,"LUG_WIDTH") else 1)
    check("block",await adapter.create_extrusion(ExtrusionParameters(depth=part.BLOCK_HEIGHT)))
    name_last_feature(adapter,"Block")
    name_dimensions(adapter,"Block",["BlockHeight"])
    expected = part.BLOCK_LENGTH * part.BLOCK_WIDTH * part.BLOCK_HEIGHT
    if hasattr(part,"LUG_WIDTH"):
        # Owner ruling 2026-11-07: the lug's +X side is the block's +X end.
        # Anchored on BlockProfile's +X/-Y corner, the lug's +X edge lies on
        # the block's, and the union leaves one face (readback,
        # _require_flush_lug_end); the shared edge at Y=-20 joins the two
        # full-height extrusions.
        await _rectangle(adapter,"LugProfile",(part.LUG_X0,part.LUG_X1,part.LUG_Y0,part.LUG_Y1),
                         ["LugWidth","LugLength","LugCornerX","LugCornerY"], anchor=2)
        check("integral lug",await adapter.create_extrusion(ExtrusionParameters(depth=part.BLOCK_HEIGHT)))
        name_last_feature(adapter,"Lug")
        expected += part.LUG_WIDTH * part.LUG_LENGTH * part.BLOCK_HEIGHT
    check("top plane",await adapter.create_plane(CreatePlaneParameters(mode="offset",base_plane="Front Plane",offset=part.BLOCK_HEIGHT)))
    name_last_feature(adapter,"TopFace")
    blank_reference_geometry(adapter,(("TopFace","PLANE"),))
    await _circles(adapter,"TopFace",part.BLOCK_HEIGHT,"TopBoreProfile",
                   [(spec.BORE_X,0,spec.BORE_DIA,(None,None,"BoreDia"))])
    check("shoulder seat",await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.BORE_DEPTH)))
    name_last_feature(adapter,"TopBore")
    name_dimensions(adapter,"TopBore",["TopBoreDepth"])
    expected -= math.pi * (spec.BORE_DIA/2)**2 * spec.BORE_DEPTH
    await _circles(adapter,"TopFace",part.BLOCK_HEIGHT,"PivotTapProfile",
                   [(spec.BORE_X,0,spec.PIVOT_TAP_DRILL,(None,None,"TapDrillDia"))])
    check("pivot tap drill thru",await adapter.create_cut_extrude(ExtrusionParameters(depth=part.BLOCK_HEIGHT*2)))
    name_last_feature(adapter,"PivotTap")
    expected -= math.pi*(spec.PIVOT_TAP_DRILL/2)**2 * (part.BLOCK_HEIGHT-spec.BORE_DEPTH)
    for profile,diameter,depth,feature in (
        ("CarriageDrillProfile",spec.HOLE_DIA,part.BLOCK_HEIGHT*2,"CarriageDrills"),
        ("CarriageCboreProfile",spec.CBORE_DIA,spec.CBORE_DEPTH,"CarriageCounterbores"),
    ):
        circles = [(x,y,diameter,(f"{feature}{i}X",f"{feature}{i}Y",f"{feature}{i}Dia"))
                   for i,(x,y) in enumerate(spec.BOLT_POINTS,1)]
        await _circles(adapter,"TopFace",part.BLOCK_HEIGHT,profile,circles)
        check(feature,await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)))
        name_last_feature(adapter,feature)
    expected -= 4*math.pi*((spec.HOLE_DIA/2)**2*spec.CBORE_FLOOR+(spec.CBORE_DIA/2)**2*spec.CBORE_DEPTH)
    # Preserve the native carriage-floor reference on the actual section plane.
    await _cbore_floor_reference(adapter, part)
    await _plan_datum_reference(adapter, part)
    if hasattr(part,"NUT_FACE_X"):
        check("nut face plane",await adapter.create_plane(CreatePlaneParameters(mode="offset",base_plane="Right Plane",offset=part.NUT_FACE_X)))
        name_last_feature(adapter,"NutFace")
        blank_reference_geometry(adapter,(("NutFace","PLANE"),))
        await _circles(adapter,"NutFace",part.NUT_FACE_X,"NutClearanceProfile",
                       [(part.NUT_AXIS_Z,part.NUT_AXIS_Y,part.SCREW_CLEARANCE_DIA,
                         ("NutClearanceZ","NutClearanceY","NutClearanceDia"))],side=True)
        check("NutClearance",await adapter.create_cut_extrude(ExtrusionParameters(depth=part.LUG_WIDTH*2)))
        name_last_feature(adapter,"NutClearance")
        name_dimensions(adapter,"NutClearance",["NutClearanceDepth"])
        nut_taps = wizard_holes(adapter,part.NUT_TAP_SPEC,
             [[part.NUT_FACE_X,y,z] for y,z in part.NUT_HOLES_YZ],(1.0,0.0,0.0),
             "feed nut screw taps (#4-40 through)",name="NutTaps",expect_dia_mm=part.NUT_TAP_DRILL,
             placement_dims=[((f"NutPlacement{i}U",None),(f"NutPlacement{i}V",None))
                             for i in range(1,len(part.NUT_HOLES_YZ)+1)])
        # The taps are transferred through the TL-VN-84 FeedNut at assembly:
        # modelled where the nominal nut puts them.
        expected -= math.pi*(part.SCREW_CLEARANCE_DIA/2)**2*part.LUG_WIDTH
        expected -= len(part.NUT_HOLES_YZ)*math.pi*(nut_taps.hole_dia_mm/2)**2*part.LUG_WIDTH
        await _nut_pattern_reference(adapter, part)
    await name_bore_axis(adapter,"Right Plane",spec.BORE_X,"Top Plane",0.0,"pivot axis")
    name_last_feature(adapter,spec.PIVOT_AXIS_NAME)
    await force_rebuild(adapter)
    _require_one_solid_body(adapter,label=part.PART_NAME)
    require_block_geometry(adapter, part)
    await volume_check(adapter,"finished block",expected,expected*0.002)
    apply_drawing_precision(adapter,part.DRAWING_PRECISION)
    # TL-32's Tr8/KP08 vendor-line dimensions print exact millimetres with
    # their own bands (owner ruling 4).
    for (feature_name,dimension_name),(places,band) in getattr(part,"METRIC_DIMENSIONS",{}).items():
        set_dimension_symmetric_tolerance(adapter,feature_name,dimension_name,band,display_unit="mm")
        set_metric_vendor_units(adapter,feature_name,dimension_name,places=places)
    # TL-32's Ø.351 clearance station in Y, ±.002 (owner ruling 2026-11-08
    # (Pedro), A2 option (i)); its Z is the millimetre band above.
    for (feature_name,dimension_name),(places,band) in getattr(part,"INCH_TOLERANCED_DIMENSIONS",{}).items():
        set_dimension_symmetric_tolerance(adapter,feature_name,dimension_name,band,places=places,display_unit="in")
    # TL-32's tap clocking band, every tap (TL-00 F1B sets all four holes in it).
    if hasattr(part,"NUT_CLOCK_DIMENSION"):
        set_dimension_symmetric_angular_tolerance(adapter,"NutPatternReference",part.NUT_CLOCK_DIMENSION,
                                                  part.NUT_CLOCK_TOL_DEG)
    # Thread identity and fit/process qualifiers belong to the saved model.
    from _drawing_precision import _named_dimension
    for channel,callouts in ((1,getattr(part,"CALLOUTS_PREFIX",{})),(2,part.CALLOUTS_SUFFIX),
                             (3,part.CALLOUTS_ABOVE),(4,part.CALLOUTS_BELOW)):
        for name,text in callouts.items():
            owners = [feature for feature,names in part.DRAWING_DIMENSIONS.items() if name in names]
            if len(owners) != 1:
                raise RuntimeError(f"{name}: expected one native callout owner")
            display,_ = _named_dimension(adapter,owners[0],name)
            display.SetText(channel,text)
            if str(display.GetText(channel) or "") != text:
                raise RuntimeError(f"{name}: model callout did not persist")
    clear_dimensions_for_drawing(adapter)
    for feature,names in part.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter,feature,names)
    blank_reference_sketches(adapter,part.REFERENCE_SKETCHES)
    await apply_material(adapter,MATERIAL)
    await report_mass_properties(adapter)
