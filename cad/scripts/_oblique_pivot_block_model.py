"""Native TL-22/TL-32 shoulder-screw block recipes, in the carriage frame.

Taps are represented by their drill cylinders (as native Wizard taps are),
not by helical cut threads. The model owns every size and printed tolerance.
"""
from __future__ import annotations
from typing import Any
from collections.abc import Callable
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import name_dimensions
from _document_units import apply_package_model_units
from _drawing_marks import clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _metric_vendor_dimension import set_metric_vendor_units
from _feature_tree import name_last_feature
from _fit_deviations import deviations
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

    Section B-B cuts along Y through the (+13, +13) counterbore (along X its
    arrows and letters would sit on the bore: review r5; through the -13
    column its left-pointing letters met the seat's 10.00 extension line), so
    its cutting plane is the Right plane (model YZ) carried to X = +BoltX; a
    derived view imports a reference sketch that lies in its cut
    (build_pd_platen ``CboreFloorReference``). One construction line on the
    M4 clearance hole's +Y wall, a visible section edge, from the carriage
    seat (Z = 0) up to the counterbore floor: its foot's Y from the origin
    (unprinted; the Z = 0 end sits on the sketch axis), and its rise, the
    printed floor. The off-sketch check in ``_sketch_mapper`` proves the
    plane stands at X = +13 and that the sketch opened on it, not on a
    fallback plane.
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


async def _construction(adapter, create, label: str) -> str:
    """One construction entity, drawn without inference (no snap to the
    model edges it lies on), so only the dimensions below define it.
    ``create`` is the un-awaited adapter call; it runs inside the mode."""
    set_sketch_direct_db(adapter, True)
    try:
        entity = check(label, await create)
    finally:
        set_sketch_direct_db(adapter, False)
    _as_construction(adapter, entity)
    return entity


async def _offset_point(adapter, dims, base, point, du, dv, names, label) -> None:
    """Pin sketch ``point`` at offset (du, dv) from ``base`` and record the
    dims ``anchor_point_to_point`` emits: none for a zero component."""
    await anchor_point_to_point(adapter, base, point, du, dv, label)
    for offset, name in zip((du, dv), names, strict=True):
        if abs(offset) >= 1e-9:
            dims.record(name)


async def _construction_circle(adapter, dims, base, base_uv, uv, dia, names, label) -> str:
    """A construction circle on a real hole, centred by offsets from
    ``base`` (a sketch point at ``base_uv``), then sized."""
    circle = await _construction(adapter, adapter.add_circle(uv[0], uv[1], dia / 2), label)
    await _offset_point(adapter, dims, base, f"{circle}.center",
                        abs(uv[0] - base_uv[0]), abs(uv[1] - base_uv[1]), names[:2], label)
    check(f"{label} diameter", await adapter.add_sketch_dimension(circle, None, "diameter", dia))
    dims.record(names[2])
    return circle


async def _plan_datum_reference(adapter, part) -> None:
    """The hidden top-face sketch that carries the plan's X ordinates from
    the -X edge (rule 10): a construction line ON that edge, construction
    circles ON the shoulder seat and one carriage hole per column, and on
    TL-32 a line ON the lug's -X face, which also carries the overall from the
    top (+Y) edge. Shown in the plan view, every entity overlies a real edge."""
    feature = spec.PLAN_DATUM_REFERENCE
    z = part.BLOCK_HEIGHT
    check(f"create_sketch {feature}", await adapter.create_sketch("TopFace"))
    at = _xy_mapper(adapter, z, feature)
    dims = SketchDims()
    edge_start, edge_end = at(part.BLOCK_X0, -part.BLOCK_WIDTH / 2), at(part.BLOCK_X0, part.BLOCK_WIDTH / 2)
    edge = await _construction(adapter, adapter.add_line(edge_start[0], edge_start[1], edge_end[0], edge_end[1]),
                               f"{feature} -X edge")
    check(f"{feature} -X edge vertical", await adapter.add_sketch_constraint(edge, None, "vertical"))
    await anchor_point_to_origin(adapter, f"{edge}.start", *edge_start, f"{feature} -X edge foot")
    dims.record("PlanEdgeX")
    dims.record("PlanEdgeY")
    await dimension_between(adapter, f"{edge}.start", f"{edge}.end", "vertical_distance",
                            part.BLOCK_WIDTH, f"{feature} -X edge length")
    dims.record("PlanEdgeLength")
    corner = f"{edge}.end"
    await _construction_circle(adapter, dims, corner, edge_end, at(spec.BORE_X, spec.BORE_Y), spec.BORE_DIA,
                               ("PlanBoreX", "PlanBoreY", "PlanBoreDia"), f"{feature} seat")
    for i, (x, y) in enumerate(spec.PLAN_DATUM_HOLES, 1):
        await _construction_circle(adapter, dims, corner, edge_end, at(x, y), spec.HOLE_DIA,
                                   (f"PlanHole{i}X", f"PlanHole{i}Y", f"PlanHole{i}Dia"),
                                   f"{feature} carriage hole column {i}")
    if hasattr(part, "LUG_WIDTH"):
        lug_top, lug_end = at(part.LUG_X0, part.LUG_Y1), at(part.LUG_X0, part.LUG_Y0)
        lug = await _construction(adapter, adapter.add_line(lug_top[0], lug_top[1], lug_end[0], lug_end[1]),
                                  f"{feature} lug -X face")
        check(f"{feature} lug face vertical", await adapter.add_sketch_constraint(lug, None, "vertical"))
        await _offset_point(adapter, dims, f"{edge}.start", f"{lug}.start",
                            abs(lug_top[0] - edge_start[0]), abs(lug_top[1] - edge_start[1]),
                            ("PlanLugX", "PlanLugY"), f"{feature} lug face from -X edge")
        await dimension_between(adapter, corner, f"{lug}.end", "vertical_distance",
                                part.BLOCK_WIDTH / 2 - part.LUG_Y0, f"{feature} overall from +Y edge")
        dims.record("PlanOverallY")
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


async def _nut_pattern_reference(adapter, part) -> None:
    """The hidden nut-face sketch that carries VIEW D's locations: a
    construction line ON the lug end, the nut axis (a circle ON the spigot
    recess) from that end and the bottom face, and the four taps (circles ON
    their drills) from the nut axis, so the pattern prints against the recess
    it surrounds."""
    feature = "NutPatternReference"
    check(f"create_sketch {feature}", await adapter.create_sketch("NutFace"))
    to_sketch = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=feature)

    def at(y: float, z: float) -> tuple[float, float]:
        return to_sketch((part.NUT_FACE_X, y, z))

    dims = SketchDims()
    end_start, end_end = at(part.LUG_Y0, 0.0), at(part.LUG_Y0, part.BLOCK_HEIGHT)
    end = await _construction(adapter, adapter.add_line(end_start[0], end_start[1], end_end[0], end_end[1]),
                              f"{feature} lug end")
    check(f"{feature} lug end horizontal", await adapter.add_sketch_constraint(end, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{end}.start", *end_start, f"{feature} lug end corner")
    dims.record("NutEndY")
    await dimension_between(adapter, f"{end}.start", f"{end}.end", "horizontal_distance",
                            part.BLOCK_HEIGHT, f"{feature} lug end length")
    dims.record("NutEndLength")
    axis_uv = at(part.NUT_AXIS_Y, part.NUT_AXIS_Z)
    axis = await _construction_circle(adapter, dims, f"{end}.start", end_start, axis_uv, part.NUT_SEAT_DIA,
                                      ("NutCentreZ", "NutCentreY", "NutCentreDia"), f"{feature} nut axis")
    for i, (y, z) in enumerate(part.NUT_HOLES_YZ, 1):
        await _construction_circle(adapter, dims, f"{axis}.center", axis_uv, at(y, z), part.NUT_TAP_DRILL,
                                   (f"NutTap{i}Z", f"NutTap{i}Y", f"NutTap{i}Dia"), f"{feature} tap {i}")
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


async def build_block_model(adapter, part) -> None:
    import math
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters
    check("create part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(part.PART_NAME), label=part.PART_NAME)
    # Anchored at the +X/-Y corner, where the printed BlockSideY's witness
    # starts: from the -X corner its extension line ran the whole -Y edge and,
    # on TL-32, across the lug's top face (round-5 review).
    await _rectangle(adapter,"BlockProfile",(part.BLOCK_X0,part.BLOCK_X1,-part.BLOCK_WIDTH/2,part.BLOCK_WIDTH/2),
                     ["BlockLength","BlockWidth","BlockEndX","BlockSideY"], anchor=1)
    check("block",await adapter.create_extrusion(ExtrusionParameters(depth=part.BLOCK_HEIGHT)))
    name_last_feature(adapter,"Block")
    name_dimensions(adapter,"Block",["BlockHeight"])
    expected = part.BLOCK_LENGTH * part.BLOCK_WIDTH * part.BLOCK_HEIGHT
    if hasattr(part,"LUG_WIDTH"):
        # The shared edge at Y=-20 joins the two full-height extrusions.
        await _rectangle(adapter,"LugProfile",(part.LUG_X0,part.LUG_X1,part.LUG_Y0,part.LUG_Y1),
                         ["LugWidth","LugLength","LugEndX","LugEndY"])
        check("integral lug",await adapter.create_extrusion(ExtrusionParameters(depth=part.BLOCK_HEIGHT)))
        name_last_feature(adapter,"Lug")
        expected += part.LUG_WIDTH * part.LUG_LENGTH * part.BLOCK_HEIGHT
    check("top plane",await adapter.create_plane(CreatePlaneParameters(mode="offset",base_plane="Front Plane",offset=part.BLOCK_HEIGHT)))
    name_last_feature(adapter,"TopFace")
    blank_reference_geometry(adapter,(("TopFace","PLANE"),))
    await _circles(adapter,"TopFace",part.BLOCK_HEIGHT,"TopBoreProfile",
                   [(spec.BORE_X,0,spec.BORE_DIA,("BoreX",None,"BoreDia"))])
    check("shoulder seat",await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.BORE_DEPTH)))
    name_last_feature(adapter,"TopBore")
    name_dimensions(adapter,"TopBore",["TopBoreDepth"])
    expected -= math.pi * (spec.BORE_DIA/2)**2 * spec.BORE_DEPTH
    await _circles(adapter,"TopFace",part.BLOCK_HEIGHT,"PivotTapProfile",
                   [(spec.BORE_X,0,spec.PIVOT_TAP_DRILL,("TapX",None,"TapDrillDia"))])
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
        for profile,dia,depth,feature,names in (
            ("NutSeatProfile",part.NUT_SEAT_DIA,part.NUT_RECESS_DEPTH,"NutSeat",("NutAxisZ","NutAxisY","NutSeatDia")),
            ("NutClearanceProfile",part.SCREW_CLEARANCE_DIA,part.LUG_WIDTH*2,"NutClearance",("NutClearanceZ","NutClearanceY","NutClearanceDia")),
        ):
            await _circles(adapter,"NutFace",part.NUT_FACE_X,profile,
                           [(part.NUT_AXIS_Z,part.NUT_AXIS_Y,dia,names)],side=True)
            check(feature,await adapter.create_cut_extrude(ExtrusionParameters(depth=depth,reverse_direction=True)))
            name_last_feature(adapter,feature)
            name_dimensions(adapter,feature,["NutSeatDepth" if feature=="NutSeat" else "NutClearanceDepth"])
        wizard_holes(adapter,part.NUT_TAP_SPEC,
             [[part.NUT_FACE_X,y,z] for y,z in part.NUT_HOLES_YZ],(-1.0,0.0,0.0),
             "nut flange blind taps",name="NutTaps",expect_dia_mm=part.NUT_TAP_DRILL,
             placement_dims=[((f"NutPlacement{i}U",None),(f"NutPlacement{i}V",None))
                             for i in range(1,5)])
        # Drill-to-print pattern dimensions on the physical face; no transfer spotting.
        expected -= math.pi*(part.SCREW_CLEARANCE_DIA/2)**2*part.LUG_WIDTH
        expected -= math.pi*((part.NUT_SEAT_DIA/2)**2-(part.SCREW_CLEARANCE_DIA/2)**2)*part.NUT_RECESS_DEPTH
        from _holes import blind_hole_volume_mm3
        expected -= 4*blind_hole_volume_mm3(part.NUT_TAP_DRILL,part.NUT_TAP_DRILL_DEPTH)
        await _nut_pattern_reference(adapter, part)
    await name_bore_axis(adapter,"Right Plane",spec.BORE_X,"Top Plane",0.0,"pivot axis")
    name_last_feature(adapter,spec.PIVOT_AXIS_NAME)
    await force_rebuild(adapter)
    _require_one_solid_body(adapter,label=part.PART_NAME)
    await volume_check(adapter,"finished block",expected,expected*0.002)
    set_dimension_bilateral_tolerance(adapter,"TopBoreProfile","BoreDia",*deviations(spec.BORE_BAND),
                                      places=spec.BORE_PLACES,display_unit=spec.UNIT)
    apply_drawing_precision(adapter,part.DRAWING_PRECISION)
    # TL-32's Tr8/KP08 vendor-line dimensions print exact millimetres with
    # their own bands (owner ruling 4).
    for (feature_name,dimension_name),(places,band) in getattr(part,"METRIC_DIMENSIONS",{}).items():
        set_dimension_symmetric_tolerance(adapter,feature_name,dimension_name,band,display_unit="mm")
        set_metric_vendor_units(adapter,feature_name,dimension_name,places=places)
    # Thread identity and fit/process qualifiers belong to the saved model.
    from _drawing_precision import _named_dimension
    for channel,callouts in ((2,part.CALLOUTS_SUFFIX),(3,part.CALLOUTS_ABOVE),(4,part.CALLOUTS_BELOW)):
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
