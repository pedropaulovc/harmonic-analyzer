r"""Build the rocker arm profile fixture (MHA-CH-006-TL-02; shop fixture).

A milled steel plate carrying twelve bonded strap pads, a bonded hub stand and
four bonded rail rests for the S3/S4 rocker-arm profile setups
(``ch_rocker_arm_tl_profile_fixture_spec``). One is made.

Layout (rocker frame A, the spec's frame): the pads, the stand and the plate
are sketched on the hidden ``PadTop`` plane -- the pad reference -- and built
down from it, so the plate's and the stand's start offsets ARE the printed
drops below the pad tops. The rail rests, which seat on their pocket floors,
are sketched on the hidden ``PlateTop`` plane and built down from a start
offset above it, so that offset is the printed rest-top height and the depth
the rest's scheduled height. Every cut is sketched on
``PlateTop`` and cut into the plate. The bonded parts are separate bodies,
built after every cut and hole so no cut ever reaches them.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_profile_fixture.py
"""

from __future__ import annotations

import math
import re
import sys

from _common import (
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    ensure_fully_defined,
    extrude_at_offset,
    feature_name_by_type,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)
from _drawing_marks import (
    _named_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _holes import blind_hole_volume_mm3, wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_profile_fixture_spec import (
    CLAMP_STUD_POINTS,
    CLAMP_STUD_SPEC,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    EXPLICIT_SYMMETRIC_TOLERANCES_MM,
    FEATURE_SCHEDULE,
    FEATURE_SCHEDULE_HEADER,
    HOLD_DOWN_CBORE_DEPTH,
    HOLD_DOWN_CBORE_DIA,
    HOLD_DOWN_CLEARANCE_DIA,
    HOLD_DOWN_HOLE_SPEC,
    HOLD_DOWN_POINTS,
    ISOMETRIC_VIEW_NOTE,
    LOCATING_BORE_BAND,
    LOCATING_BORE_DEPTH,
    LOCATING_BORE_DIA,
    LOCATING_BORE_FLOOR_Z,
    PAD_HEIGHT,
    PAD_POCKET_DEPTH,
    PAD_POCKETS,
    PAD_TOP_Z,
    PADS,
    PART_SCHEDULE,
    PART_SCHEDULE_HEADER,
    PIVOT_TAP_DRILL_DIA,
    PIVOT_TAP_SPEC,
    PLATE_DROP,
    PLATE_LENGTH,
    PLATE_SOUTH_Y,
    PLATE_THICK,
    PLATE_TOP_Z,
    PLATE_WEST_X,
    PLATE_WIDTH,
    REST_HEIGHT,
    REST_POCKET_DEPTH,
    REST_POCKETS,
    REST_TOP_HEIGHT,
    REST_TOP_Z,
    RESTS,
    ROD_PIN_HOLE_BAND,
    ROD_PIN_HOLE_DEPTH,
    ROD_PIN_HOLE_DIA,
    ROD_PIN_HOLE_XY,
    SCHEDULE_CELL_DIMENSIONS,
    STAND_BORE,
    STAND_DROP,
    STAND_HEIGHT,
    STAND_OD,
    STAND_POCKET_DEPTH,
    STAND_POCKET_DIA,
    STAND_TOP_Z,
    part_dimension_names,
    pocket_dimension_names,
)

PART_NAME = "ch-rocker-arm-tl-profile-fixture"
MATERIAL = "Plain Carbon Steel"  # the plate; the bonded parts are a few grams
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)
PAD_PLANE = "PadTop"
PLATE_PLANE = "PlateTop"
# plate + 12 pads + hub stand + 4 rail rests
BODY_COUNT = 1 + len(PADS) + 1 + len(RESTS)


def _circle_area(dia: float) -> float:
    return math.pi * dia * dia / 4.0


def _require_bodies(adapter, count: int, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != count:
        raise RuntimeError(f"{label}: expected {count} solid bodies, found {len(bodies)}")


def _rect_points(cx: float, cy: float, length: float, width: float) -> list[tuple[float, float]]:
    x0, x1 = cx - length / 2.0, cx + length / 2.0
    y0, y1 = cy - width / 2.0, cy + width / 2.0
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


async def _construction_line(adapter, start: tuple[float, float], end: tuple[float, float], label: str) -> str:
    """A construction line placed without inference: an end on an existing
    vertex merges with it, as ``add_line_chain`` closes its loop."""
    sketch_mgr = adapter.currentSketchManager
    previous_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        line_id = check(f"add construction line {label}", await adapter.add_line(*start, *end))
        # ConstructionGeometry is declared on ISketchSegment, not ISketchLine.
        _early_bound(adapter._sketch_entities[line_id], "ISketchSegment").ConstructionGeometry = True
    finally:
        sketch_mgr.AddToDB = previous_add_to_db
    return line_id


async def _centred_rect(
    adapter, cx: float, cy: float, length: float, width: float, *, label: str, dims: SketchDims,
    names: tuple[str, str, str, str],
) -> None:
    """An axis-parallel rectangle driven by exactly what its schedule row
    prints: length, width and centre (``names`` in that order: centre X,
    centre Y, length, width). A construction diagonal carries the centre as
    the midpoint of a construction half-diagonal's start, and the centre is
    dimensioned from the origin (the locating-bore axis)."""
    if abs(cx) < 1e-9 or abs(cy) < 1e-9:
        raise ValueError(f"{label}: a scheduled centre on an axis has one anchor dimension")
    x_name, y_name, length_name, width_name = names
    points = _rect_points(cx, cy, length, width)
    lines = await add_line_chain(adapter, points)
    for line, direction in zip(lines, ("horizontal", "vertical") * 2, strict=True):
        check(
            f"{label} {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    await dimension_between(
        adapter, f"{lines[0]}.start", f"{lines[0]}.end", "horizontal_distance", length, f"{label} length"
    )
    await dimension_between(
        adapter, f"{lines[1]}.start", f"{lines[1]}.end", "vertical_distance", width, f"{label} width"
    )
    diagonal = await _construction_line(adapter, points[0], points[2], f"{label} diagonal")
    centre = await _construction_line(adapter, (cx, cy), points[1], f"{label} centre")
    check(
        f"{label} centre at the diagonal's midpoint",
        await adapter.add_sketch_constraint(f"{centre}.start", diagonal, "midpoint"),
    )
    await anchor_point_to_origin(adapter, f"{centre}.start", cx, cy, f"{label} centre")
    for name in (length_name, width_name, x_name, y_name):
        dims.record(name)


async def _pocket_sketch(adapter, rects, *, label: str, profile: str) -> None:
    """One sketch of scheduled pockets, each driven by its schedule row."""
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(PLATE_PLANE))
    for tag, cx, cy, length, width in rects:
        await _centred_rect(
            adapter, cx, cy, length, width, label=f"{label} {tag}", dims=dims,
            names=pocket_dimension_names(tag),
        )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)


async def _part_sketch(adapter, plane: str, parts, *, label: str, profile: str, part: str) -> None:
    """One sketch of bonded parts, each anchored at its south-west corner (an
    unprinted location: each part is centred in its pocket) and driven by the
    length and width the part schedule prints."""
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    for tag, cx, cy, length, width in parts:
        points = _rect_points(cx, cy, length, width)
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(
            adapter, lines, points, label=f"{label} {tag}", dims=dims,
            names=list(part_dimension_names(tag, part)),
        )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)


async def _circle_sketch(adapter, plane: str, x: float, y: float, dia: float, *, profile: str, names) -> None:
    dims = SketchDims()
    check(f"create_sketch {profile}", await adapter.create_sketch(plane))
    await define_circle(adapter, x, y, dia / 2.0, profile, dims=dims, names=names)
    await ensure_fully_defined(adapter, f"{profile} sketch")
    check(f"exit_sketch {profile}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)


def _extrude_down_from_offset(adapter, height: float, top: float) -> str:
    """Boss-extrude the last exited sketch as new bodies that start ``top``
    above its plane (a start offset along the normal) and run ``height`` back
    down through it: a part seated in a pocket of the sketch plane's face, its
    own dimensions its height and its top above that face. Raw
    ``FeatureExtrusion3``, as ``_common.extrude_at_offset``, whose single flip
    turns the offset and the direction together."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    if not sketch_name:
        raise RuntimeError("_extrude_down_from_offset: no sketch found to consume")
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"_extrude_down_from_offset: cannot select sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureExtrusion3(
        True,  # Sd: single direction
        False,  # Flip side to cut
        True,  # Dir: against the plane normal (down)
        0,  # T1: swEndCondBlind
        0,  # T2
        height / 1000.0,  # D1
        0.0,  # D2
        False,
        False,  # Dchk1/2
        False,
        False,  # Ddir1/2
        0.0,
        0.0,  # Dang1/2
        False,
        False,  # OffsetReverse1/2
        False,
        False,  # TranslateSurface1/2
        False,  # Merge: separate bonded bodies
        False,  # UseFeatScope
        True,  # UseAutoSelect
        3,  # T0: swStartOffset
        top / 1000.0,  # StartOffset
        False,  # FlipStartOffset: along the plane normal (up)
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("_extrude_down_from_offset: FeatureExtrusion3 returned None")
    return str(_read_member(feature, "Name"))


def _require_dimension(adapter, full_name: str, mm: float) -> None:
    """The named dimension reads ``mm``: the names follow creation order."""
    dimension = adapter.currentModel.Parameter(full_name)
    if dimension is None:
        raise RuntimeError(f"no dimension {full_name}")
    actual = float(_read_member(dimension, "SystemValue")) * 1000.0
    if abs(actual - mm) > 1e-6:
        raise RuntimeError(f"{full_name} reads {actual:.4f} mm, not {mm:.4f}")


def _require_rest_tops(adapter) -> None:
    """Each rail rest spans its pocket floor to REST_TOP_Z: the start offset
    must run along the plate top's outward normal and the depth back down. The
    body box is approximate (IBody2.GetBodyBox), so 0.25 mm; flipped, the rest
    would end well off at both faces."""
    boxes = [
        tuple(float(value) * 1000.0 for value in _early_bound(body, "IBody2").GetBodyBox())
        for body in _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    ]
    floor = PLATE_TOP_Z - REST_POCKET_DEPTH
    for tag, cx, cy, _length, _width in RESTS:
        over = [box for box in boxes if box[0] < cx < box[3] and box[1] < cy < box[4]]
        found = [
            box for box in over
            if abs(box[5] - REST_TOP_Z) < 0.25 and abs(box[2] - floor) < 0.25
        ]
        if len(found) != 1:
            raise RuntimeError(
                f"rest {tag}: expected one body from Z{floor:g} to Z{REST_TOP_Z:g}; "
                f"bodies over it {over}"
            )


# The schedules print sizes the model has to carry: every printed value is
# read back from the built faces, so neither table can publish a number the
# CAD does not hold (codex review of PR 1252: schedule cells were only
# formatted spec values). Every value comes from exact B-rep geometry: plane
# heights from ISurface.PlaneParams, flat-face extents from their straight
# edges' vertices and whole circles' CircleParams, hole axes from
# ISurface.CylinderParams (cross-vendor review of PR 1252: IFace2.GetBox is an
# approximate, possibly loose box). The schedules round to three places, so
# the model may differ from a cell by half the finest printed place.
_SCHEDULE_READBACK_TOL_MM = 0.0005


def _flat_face_extent(face) -> tuple[float, ...] | None:
    """A horizontal planar face's exact (x min, y min, z, x max, y max, z) in
    mm, or None for any other face. Its edges must be straight lines (their
    end vertices bound it) or circles (each bounds it by centre +/- radius:
    exact for the whole circles of these bores, stands and counterbores; an arc
    would overstate the face, so it then matches no schedule row and fails)."""
    surface = _early_bound(face.GetSurface(), "ISurface")
    if not surface.IsPlane():
        return None
    *normal, _root_x, _root_y, root_z = (float(value) for value in surface.PlaneParams)
    if abs(abs(normal[2]) - 1.0) > 1e-9:
        return None
    xs, ys = [], []
    for raw_edge in face.GetEdges() or ():
        edge = _early_bound(raw_edge, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve.IsLine():
            for vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
                x, y, _z = (float(value) for value in _early_bound(vertex, "IVertex").GetPoint())
                xs.append(x)
                ys.append(y)
        elif curve.IsCircle():
            cx, cy, _cz, *_axis, radius = (float(value) for value in curve.CircleParams)
            xs += [cx - radius, cx + radius]
            ys += [cy - radius, cy + radius]
        else:
            return None
    if not xs:
        return None
    z = root_z * 1000.0
    return (min(xs) * 1000.0, min(ys) * 1000.0, z, max(xs) * 1000.0, max(ys) * 1000.0, z)


def _schedule_faces(adapter) -> tuple[list[tuple[float, ...]], list[tuple[float, float, float]]]:
    """The model's horizontal flat-face extents and its vertical cylinders
    (axis x, axis y, radius), all in mm."""
    extents, cylinders = [], []
    for body in _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ():
        for raw_face in _early_bound(body, "IBody2").GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface.IsCylinder():
                params = tuple(float(value) for value in surface.CylinderParams)
                if abs(abs(params[5]) - 1.0) < 1e-9:
                    cylinders.append((params[0] * 1000.0, params[1] * 1000.0, params[6] * 1000.0))
                continue
            extent = _flat_face_extent(face)
            if extent is not None:
                extents.append(extent)
    return extents, cylinders


def _require_face(extents, label: str, z: float, cx: float, cy: float, length: float, width: float) -> None:
    want = (cx - length / 2.0, cy - width / 2.0, z, cx + length / 2.0, cy + width / 2.0, z)
    if not any(
        all(abs(a - b) <= _SCHEDULE_READBACK_TOL_MM for a, b in zip(extent, want, strict=True))
        for extent in extents
    ):
        raise RuntimeError(f"{label}: no flat face {want} in the model, as the schedule prints")


def _require_hole(cylinders, label: str, cx: float, cy: float, dia: float) -> None:
    want = (cx, cy, dia / 2.0)
    if not any(
        all(abs(a - b) <= _SCHEDULE_READBACK_TOL_MM for a, b in zip(cylinder, want, strict=True))
        for cylinder in cylinders
    ):
        raise RuntimeError(f"{label}: no vertical bore {want} in the model, as the schedule prints")


def _model_cell(adapter, feature_name: str, dimension_name: str) -> str:
    """A scheduled dimension as the model owns it: its value at its authored
    places and, for a natively banded one, its symmetric tolerance at the
    tolerance places. A sketch distance holds no sign; the cell's sign is the
    side the face readback proves."""
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(display, "IDisplayDimension")
    value = abs(float(_read_member(dimension, "SystemValue")) * 1000.0)
    text = f"{value:.{int(display.GetPrimaryPrecision2())}f}"
    if (feature_name, dimension_name) not in EXPLICIT_SYMMETRIC_TOLERANCES_MM:
        return text
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    label = f"{dimension_name}@{feature_name}"
    if int(tolerance.Type) != 4:  # swTolType_e.swTolSYMMETRIC
        raise RuntimeError(f"{label}: carries no symmetric model tolerance")
    plus = float(tolerance.GetMaxValue()) * 1000.0
    if abs(float(tolerance.GetMinValue()) * 1000.0 + plus) > 1e-9:
        raise RuntimeError(f"{label}: model tolerance is not symmetric")
    return f"{text} \u00b1{plus:.{int(display.GetPrimaryTolPrecision2())}f}"


def _cell_number(cell: str) -> str:
    """A cell's number as the model states it: no sign, no "OD "/"DRILL Ø"."""
    return re.sub(r"^\D+", "", cell)


def _require_schedules(adapter, hole_dias: dict[str, float]) -> None:
    """Every number in the printed schedules is a model dimension's own value,
    places and native band (policy rule 2), and every row is geometry of the
    built model: pocket floors (centre, length, width, depth), hole axes
    (centre, at the cut diameter ``hole_dias`` gives per feature), bonded-part
    tops and undersides (length, width, height, centred in their pockets) and
    the hub stand's drilled bore."""
    cells = {
        (schedule, row[0], column): text
        for schedule, header, rows in (
            ("FEATURE", FEATURE_SCHEDULE_HEADER, FEATURE_SCHEDULE),
            ("PART", PART_SCHEDULE_HEADER, PART_SCHEDULE),
        )
        for row in rows
        for column, text in zip(header, row, strict=True)
    }
    for key, owners in SCHEDULE_CELL_DIMENSIONS.items():
        for feature_name, dimension_name in owners:
            model = _model_cell(adapter, feature_name, dimension_name)
            if model != _cell_number(cells[key]):
                raise RuntimeError(
                    f"{' '.join(key)} prints {cells[key]!r}; "
                    f"{dimension_name}@{feature_name} owns {model!r}"
                )
    extents, cylinders = _schedule_faces(adapter)
    pockets = {}
    for tag, feature, x, y, length, width, depth in FEATURE_SCHEDULE:
        # Bore L is the origin; a banded coordinate locates at its nominal.
        cx, cy = (0.0 if value == "-" else float(value.split()[0]) for value in (x, y))
        if not feature.endswith("POCKET"):
            _require_hole(cylinders, f"{tag} {feature.lower()}", cx, cy, hole_dias[feature])
            continue
        pockets[tag] = (cx, cy)
        floor = PLATE_TOP_Z - float(depth)
        _require_face(extents, f"{tag} pocket floor", floor, cx, cy, float(length), float(width))
    for tags, part, _stock, length, width, height in PART_SCHEDULE:
        if part == "HUB STAND":
            od = float(_cell_number(length))
            for z, end in ((STAND_TOP_Z, "top"), (STAND_TOP_Z - float(height), "foot")):
                _require_face(extents, f"hub stand {end}", z, 0.0, 0.0, od, od)
            _require_hole(cylinders, "hub stand bore", 0.0, 0.0, float(_cell_number(width)))
            continue
        top = PAD_TOP_Z if part == "PAD" else REST_TOP_Z
        for tag in tags.split(", "):
            for z, end in ((top, "top"), (top - float(height), "underside")):
                _require_face(
                    extents, f"{part.lower()} {tag} {end}", z, *pockets[tag], float(length), float(width)
                )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    for plane, offset in ((PAD_PLANE, PAD_TOP_Z), (PLATE_PLANE, PLATE_TOP_Z)):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
            ),
        )
        name_last_feature(adapter, plane)

    # Plate: its outline from the locating bore axis, built down from the pad
    # reference by PlateDrop (the gauge stack) and its own 1 in thickness.
    plate_dims = SketchDims()
    check("create_sketch plate", await adapter.create_sketch(PAD_PLANE))
    outline = _rect_points(
        PLATE_WEST_X + PLATE_LENGTH / 2.0,
        PLATE_SOUTH_Y + PLATE_WIDTH / 2.0,
        PLATE_LENGTH,
        PLATE_WIDTH,
    )
    outline_lines = await add_line_chain(adapter, outline)
    await define_rectilinear_chain(
        adapter,
        outline_lines,
        outline,
        label="plate outline",
        dims=plate_dims,
        names=["PlateLength", "PlateWidth", "PlateWestX", "PlateSouthY"],
    )
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    plate_dims.apply(adapter, "PlateProfile")
    extrude_at_offset(adapter, PLATE_THICK, PLATE_DROP, True)
    name_last_feature(adapter, "Plate")
    # Offset bosses expose depth first and start offset second.
    name_dimensions(adapter, "Plate", ["PlateThick", "PlateDrop"])
    volume = PLATE_LENGTH * PLATE_WIDTH * PLATE_THICK
    await volume_check(adapter, "plate", volume, 0.001 * volume)

    # Pockets for the bonded parts.
    for rects, depth, label, profile, feature in (
        (PAD_POCKETS, PAD_POCKET_DEPTH, "pad pockets", "PadPocketProfile", "PadPockets"),
        (REST_POCKETS, REST_POCKET_DEPTH, "rest pockets", "RestPocketProfile", "RestPockets"),
    ):
        await _pocket_sketch(adapter, rects, label=label, profile=profile)
        check(
            f"cut {label}",
            await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)),
        )
        name_last_feature(adapter, feature)
        name_dimensions(adapter, feature, [f"{feature.removesuffix('s')}Depth"])
        removed = sum(length * width * depth for _t, _x, _y, length, width in rects)
        volume = await volume_check(adapter, label, volume - removed, 0.01 * removed)

    # Hub stand counterbore, then the reamed locating bore below it.
    for profile, feature, dia, depth, dia_name, depth_name, removed_depth in (
        (
            "StandPocketProfile",
            "StandPocket",
            STAND_POCKET_DIA,
            STAND_POCKET_DEPTH,
            "StandPocketDia",
            "StandPocketDepth",
            STAND_POCKET_DEPTH,
        ),
        (
            "LocatingBoreProfile",
            "LocatingBore",
            LOCATING_BORE_DIA,
            LOCATING_BORE_DEPTH,
            "LocatingBoreDia",
            "LocatingBoreDepth",
            LOCATING_BORE_DEPTH - STAND_POCKET_DEPTH,
        ),
    ):
        await _circle_sketch(
            adapter,
            PLATE_PLANE,
            0.0,
            0.0,
            dia,
            profile=profile,
            names=(None, None, dia_name),
        )
        check(f"cut {feature}", await adapter.create_cut_extrude(ExtrusionParameters(depth=depth)))
        name_last_feature(adapter, feature)
        name_dimensions(adapter, feature, [depth_name])
        removed = _circle_area(dia) * removed_depth
        volume = await volume_check(adapter, feature, volume - removed, 0.01 * removed)

    await _circle_sketch(
        adapter,
        PLATE_PLANE,
        *ROD_PIN_HOLE_XY,
        ROD_PIN_HOLE_DIA,
        profile="RodPinHoleProfile",
        names=("RodPinHoleX", "RodPinHoleY", "RodPinHoleDia"),
    )
    check(
        "cut rod pin hole",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=ROD_PIN_HOLE_DEPTH)),
    )
    name_last_feature(adapter, "RodPinHole")
    name_dimensions(adapter, "RodPinHole", ["RodPinHoleDepth"])
    removed = _circle_area(ROD_PIN_HOLE_DIA) * ROD_PIN_HOLE_DEPTH
    volume = await volume_check(adapter, "rod pin hole", volume - removed, 0.01 * removed)

    # Native Hole Wizard holes, all cut before any bonded body exists. Every
    # placement point is dimensioned to the origin (the scheduled centres), so
    # the saved CAD carries them as driving dimensions (codex review of PR
    # 1252); the pivot tap sits on the origin by a coincident relation.
    hold_down = wizard_holes(
        adapter,
        HOLD_DOWN_HOLE_SPEC,
        [[x, y, PLATE_TOP_Z] for x, y in HOLD_DOWN_POINTS],
        (0.0, 0.0, 1.0),
        "hold-down counterbores (1/2 socket head)",
        name="HoldDownHoles",
        expect_dia_mm=HOLD_DOWN_CLEARANCE_DIA,
        placement_dims=[
            ((f"HoldDown{index}X", None), (f"HoldDown{index}Y", None))
            for index in range(1, len(HOLD_DOWN_POINTS) + 1)
        ],
    )
    removed = len(HOLD_DOWN_POINTS) * (
        _circle_area(hold_down.cbore_dia_mm or HOLD_DOWN_CBORE_DIA) * HOLD_DOWN_CBORE_DEPTH
        + _circle_area(hold_down.hole_dia_mm) * (PLATE_THICK - HOLD_DOWN_CBORE_DEPTH)
    )
    volume = await volume_check(adapter, "hold-down holes", volume - removed, 0.01 * removed)

    studs = wizard_holes(
        adapter,
        CLAMP_STUD_SPEC,
        [[x, y, PLATE_TOP_Z] for x, y in CLAMP_STUD_POINTS],
        (0.0, 0.0, 1.0),
        "strap-clamp stud taps (3/8-16)",
        name="ClampStudTaps",
        placement_dims=[
            ((f"ClampStud{index}X", None), (f"ClampStud{index}Y", None))
            for index in range(1, len(CLAMP_STUD_POINTS) + 1)
        ],
    )
    removed = len(CLAMP_STUD_POINTS) * blind_hole_volume_mm3(
        studs.hole_dia_mm, CLAMP_STUD_SPEC.depth_mm
    )
    volume = await volume_check(adapter, "clamp stud taps", volume - removed, 0.03 * removed)

    pivot_tap = wizard_holes(
        adapter,
        PIVOT_TAP_SPEC,
        [[0.0, 0.0, LOCATING_BORE_FLOOR_Z]],
        (0.0, 0.0, 1.0),
        "pivot screw tap (#10-24)",
        name="PivotScrewTap",
        expect_dia_mm=PIVOT_TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    removed = blind_hole_volume_mm3(pivot_tap.hole_dia_mm, PIVOT_TAP_SPEC.depth_mm)
    volume = await volume_check(adapter, "pivot screw tap", volume - removed, 0.03 * removed)
    plate_volume = volume
    _require_bodies(adapter, 1, label="machined plate")

    # Bonded parts: separate bodies, each top on its reference.
    await _part_sketch(adapter, PAD_PLANE, PADS, label="pads", profile="PadProfile", part="Pad")
    check(
        "extrude pads",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PAD_HEIGHT, reverse_direction=True, merge_result=False)
        ),
    )
    name_last_feature(adapter, "Pads")
    name_dimensions(adapter, "Pads", ["PadHeight"])
    added = sum(length * width * PAD_HEIGHT for _t, _x, _y, length, width in PADS)
    volume = await volume_check(adapter, "pads", volume + added, 0.005 * added)

    stand_dims = SketchDims()
    check("create_sketch stand", await adapter.create_sketch(PAD_PLANE))
    await define_circle(
        adapter, 0.0, 0.0, STAND_OD / 2.0, "stand OD", dims=stand_dims, names=(None, None, "StandOD")
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        STAND_BORE / 2.0,
        "stand bore",
        dims=stand_dims,
        names=(None, None, "StandBore"),
    )
    await ensure_fully_defined(adapter, "stand sketch")
    check("exit_sketch stand", await adapter.exit_sketch())
    name_last_feature(adapter, "StandProfile")
    stand_dims.apply(adapter, "StandProfile")
    extrude_at_offset(adapter, STAND_HEIGHT, STAND_DROP, True, merge_result=False)
    name_last_feature(adapter, "Stand")
    name_dimensions(adapter, "Stand", ["StandHeight", "StandDrop"])
    added = (_circle_area(STAND_OD) - _circle_area(STAND_BORE)) * STAND_HEIGHT
    volume = await volume_check(adapter, "hub stand", volume + added, 0.005 * added)

    # Rail rests seat on their pocket floors: sketched on the plate top, each
    # stands RestTopHeight above it and runs its pocket depth down to the floor.
    await _part_sketch(adapter, PLATE_PLANE, RESTS, label="rests", profile="RestProfile", part="Rest")
    _extrude_down_from_offset(adapter, REST_HEIGHT, REST_TOP_HEIGHT)
    name_last_feature(adapter, "Rests")
    # Offset bosses expose depth first and start offset second.
    name_dimensions(adapter, "Rests", ["RestHeight", "RestTopHeight"])
    _require_dimension(adapter, "RestHeight@Rests", REST_HEIGHT)
    _require_dimension(adapter, "RestTopHeight@Rests", REST_TOP_HEIGHT)
    added = sum(length * width * REST_HEIGHT for _t, _x, _y, length, width in RESTS)
    volume = await volume_check(adapter, "rail rests", volume + added, 0.005 * added)
    _require_bodies(adapter, BODY_COUNT, label="built-up fixture")
    _require_rest_tops(adapter)

    blank_reference_geometry(adapter, ((PAD_PLANE, "PLANE"), (PLATE_PLANE, "PLANE")))
    await force_rebuild(adapter)
    await volume_check(adapter, "rebuilt fixture", volume, 0.001 * plate_volume)
    _require_bodies(adapter, BODY_COUNT, label="rebuilt fixture")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "LocatingBoreProfile", "LocatingBoreDia", *deviations(LOCATING_BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "RodPinHoleProfile", "RodPinHoleDia", *deviations(ROD_PIN_HOLE_BAND)
    )
    # The schedule's banded cells are model tolerances (policy rule 2).
    for (feature_name, dimension_name), plus in EXPLICIT_SYMMETRIC_TOLERANCES_MM.items():
        set_dimension_symmetric_tolerance(adapter, feature_name, dimension_name, plus)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _require_schedules(
        adapter,
        {
            "LOCATING BORE": LOCATING_BORE_DIA,
            "ROD PIN HOLE": ROD_PIN_HOLE_DIA,
            "HOLD-DOWN": hold_down.hole_dia_mm,
            "STUD TAP": studs.hole_dia_mm,
        },
    )
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
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
