r"""Build the oblique-trammel jig's pivot block (MHA-CH-06-TL-22; shop tooling).

A 6061 block bolted on each HGH15CA carriage, carrying the pivot pin in two
pressed 6200-2RS bearings (``ch_rocker_arm_tl_oblique_pivot_block_spec``).

Layout (the spec's frame, +Z up): the block is a Front-plane rectangle
(sketch u = X, v = Y) extruded +Z by the block height. The top bearing seat
is a circle on the TopFace plane cut blind down; its sketch also carries
the construction points every printed X/Y station dimensions to, from the
-X end and -Y side (``_top_seat_sketch``). The bottom seat is the same
circle on the Front plane cut blind up (reversed), and the Ø25 shoulder hole
a Front-plane circle cut through, both centred from the origin (unprinted).
One fillet rounds both seat-wall/shoulder corners. The four carriage-screw
counterbores are one native Hole Wizard feature drilled from the top face.
The printed counterbore floor height lives in the hidden
``CboreFloorReference`` sketch on ``CboreSectionPlane`` (Right plane carried
to X = -13), which section B-B cuts (``_cbore_floor_reference``).
The two nut-bracket screw counterbores (PR C4) are a second, drilled along Y
from the +Y face; their printed stations, from the -X end and the bottom
face, live on the hidden Top-plane sketch ``SideScrewReference``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_pivot_block.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _holes import SharedCoordinate, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_pivot_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BLOCK_WIDTH,
    BLOCK_X0,
    BLOCK_X1,
    BOLT_POINTS,
    BOLT_X,
    BOLT_Y,
    BORE_BAND,
    BORE_DEPTH,
    BORE_DIA,
    BORE_X,
    CBORE_FLOOR,
    CBORE_FLOOR_REFERENCE,
    CBORE_SECTION_PLANE,
    DATUM_X,
    DATUM_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_VALUES,
    HOLE_DIA,
    ISOMETRIC_VIEW_NOTE,
    MODEL_KNOBS,
    RADIUS_TOL_TYPE,
    REFERENCE_SKETCHES,
    SCREW_HOLE_SPEC,
    SEAT_FILLET_RADIUS,
    SHOULDER,
    SHOULDER_HOLE_DIA,
    SIDE_HOLE_DIA,
    SIDE_SCREW_HOLE_SPEC,
    SIDE_SCREW_HOLES,
    SIDE_SCREW_REFERENCE,
)

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-block"
MATERIAL = "6061 Alloy"  # the registry row names the 6061-T6 flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

THROUGH_CUT_DEPTH = 2.0 * BLOCK_HEIGHT

_R_BORE = BORE_DIA / 2.0
_R_SHOULDER = SHOULDER_HOLE_DIA / 2.0

V_BLOCK = (BLOCK_X1 - BLOCK_X0) * BLOCK_WIDTH * BLOCK_HEIGHT
V_BORE = math.pi * _R_BORE**2 * BORE_DEPTH
V_SHOULDER_HOLE = math.pi * _R_SHOULDER**2 * SHOULDER
# A concave corner fillet ADDS its (1 - pi/4) r^2 section, swept (Pappus) at
# its centroid, (10 - 3 pi) / (12 - 3 pi) r inside the seat wall; two corners.
_FILLET_AREA = (1.0 - math.pi / 4.0) * SEAT_FILLET_RADIUS**2
_FILLET_INSET = (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi) * SEAT_FILLET_RADIUS
V_SEAT_FILLETS = 2.0 * 2.0 * math.pi * (_R_BORE - _FILLET_INSET) * _FILLET_AREA


def _max_limit(adapter: Any, feature: str, dimension_name: str) -> None:
    """A corner radius as a single MAX limit: the print shows the model value
    (build_ch_rocker_arm_tl_oblique_pivot_pin)."""
    _, dimension = _named_dimension(adapter, feature, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = RADIUS_TOL_TYPE
    if int(tolerance.Type) != RADIUS_TOL_TYPE:
        raise RuntimeError(
            f"{dimension_name}@{feature}: MAX tolerance type did not persist"
        )


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


# The printed stations, each driven from the origin-relative knobs so it
# stays on its feature (spec MODEL_KNOBS).
_STATION_DRIVES = {
    "BoreStationX": '"BlockEndX" - "BoreX"',
    "BoreStationY": '"BlockSideY"',
    "HoleColumn1X": '"BlockEndX" - "BoltX"',
    "HoleColumn2X": '"BlockEndX" + "BoltX"',
    "HoleRow1Y": '"BlockSideY" - "BoltY"',
    "HoleRow2Y": '"BlockSideY" + "BoltY"',
    "SideScrew1X": '"BlockEndX" - "SideScrewX"',
    "SideScrew2X": '"BlockEndX" + "SideScrewX"',
    "SideScrewRowZ": '"SideScrewZ"',
}


def _add_reference_point(adapter: Any, uv: tuple[float, float], label: str) -> str:
    """One sketch point straight into the sketch DB (no inference snap),
    registered for the adapter's dimension refs (the TL-29 builder's)."""
    sketch_manager = _early_bound(adapter.currentSketchManager, "ISketchManager")
    previous = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        point = sketch_manager.CreatePoint(uv[0] / 1000.0, uv[1] / 1000.0, 0.0)
    finally:
        sketch_manager.AddToDB = previous
    if point is None:
        raise RuntimeError(f"cannot create the {label} reference point")
    return adapter._register_sketch_entity("Point", point)


async def _side_screw_reference(adapter: Any) -> SketchDims:
    """The side screws' printed stations, from the -X end and the bottom face.

    The wizard dimensions its placement points from the origin (the carriage
    centre, mid-air on the +Y face), so the printed stations live here, on
    the Top plane (Y = 0, normal +Y, the side view's direction). Three
    points, no lines: the -X end's bottom corner anchors to the origin
    (unprinted), both X stations and the hole row's Z dimension from it, and
    a horizontal relation holds the second hole on the first's Z. The side
    view shows this sketch to import its dimensions, and a construction line
    from the corner to the hole printed there as a stray diagonal (review
    c4r3).
    """
    label = "side screw reference"
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Top"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=2, label=label)
    corner = to_top((DATUM_X, 0.0, 0.0))
    corner_ref = _add_reference_point(adapter, corner, f"{label} corner")
    near, far = (
        _add_reference_point(adapter, to_top((x, 0.0, z)), f"{label} hole {i}")
        for i, (x, z) in enumerate(SIDE_SCREW_HOLES, start=1)
    )
    await anchor_point_to_origin(adapter, corner_ref, *corner, f"{label} corner")
    dims.record("SideRefEndX", '"BlockEndX"')
    check(
        f"horizontal_points {label} row",
        await adapter.add_sketch_constraint(near, far, "horizontal_points"),
    )
    for ref, kind, name in (
        (near, "horizontal_distance", "SideScrew1X"),
        (far, "horizontal_distance", "SideScrew2X"),
        (near, "vertical_distance", "SideScrewRowZ"),
    ):
        await dimension_between(
            adapter, corner_ref, ref, kind, DRAWING_VALUES[name], f"{label} {name}"
        )
        dims.record(name, _STATION_DRIVES[name])
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    return dims


async def _bore_sketch(
    adapter: Any, plane: str, z: float, names: tuple[str, str], label: str
) -> SketchDims:
    """One bearing-seat circle at the bore axis; returns its sketch dims."""
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    at = _xy_mapper(adapter, z, label)
    await define_circle(
        adapter,
        *at(BORE_X, 0.0),
        _R_BORE,
        label,
        dims=dims,
        names=(names[0], None, names[1]),
        drives=('"BoreX"', None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    return dims


async def _top_seat_sketch(adapter: Any) -> SketchDims:
    """The top seat's circle, located from the block's faces, plus the
    construction points every printed station dimensions to (rule 10).

    Three construction lines the cut ignores and the drawing never shows (a
    consumed profile's geometry stays hidden; its dimensions import):

    * ``datum`` runs along the top face's -Y edge from the -X end (its start,
      the X datum) to the +X end (its end, the Y datum);
    * ``row`` joins the -Y row's two holes: the X stations print on it, their
      witness lines running down to the stack under the plan, and the -Y
      row's Y on its +X end;
    * ``upper`` is the +Y row: its +X end carries that row's Y, so every Y
      witness line runs right to the stack beside the plan.

    Each line end takes its other coordinate by a points relation to the
    row it shares, so no dimension prints twice. The lines share no end
    point (exactly coincident ends merge under AddToDB). Emission order:
    the datum's x/y from the origin and its length, the bore centre's
    stations and diameter, then the hole stations.
    """
    label = "top seat"
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("TopFace"))
    at = _xy_mapper(adapter, BLOCK_HEIGHT, label)
    x_datum, y_datum = at(DATUM_X, DATUM_Y), at(BLOCK_X1, DATUM_Y)
    set_sketch_direct_db(adapter, True)
    try:
        datum = check(f"{label} datum line", await adapter.add_line(*x_datum, *y_datum))
        row = check(
            f"{label} -Y row line",
            await adapter.add_line(*at(-BOLT_X, -BOLT_Y), *at(BOLT_X, -BOLT_Y)),
        )
        upper = check(
            f"{label} +Y row line",
            await adapter.add_line(*at(BOLT_X, BOLT_Y), *at(-BOLT_X, BOLT_Y)),
        )
        circle = check(
            f"add_circle {label}", await adapter.add_circle(*at(BORE_X, 0.0), _R_BORE)
        )
    finally:
        set_sketch_direct_db(adapter, False)
    for line in (datum, row, upper):
        _as_construction(adapter, line)

    x_ref, y_ref = f"{datum}.start", f"{datum}.end"
    await anchor_point_to_origin(adapter, x_ref, *x_datum, f"{label} datum")
    dims.record("SeatDatumX", '"BlockEndX"')
    dims.record("SeatDatumY", '"BlockSideY"')
    await anchor_point_to_point(
        adapter, x_ref, y_ref, BLOCK_LENGTH, 0.0, f"{label} datum length"
    )
    dims.record("SeatDatumLength", '"BlockLength"')

    async def station(ref: str, kind: str, name: str) -> None:
        datum_ref = x_ref if kind == "horizontal_distance" else y_ref
        value = DRAWING_VALUES[name]
        await dimension_between(adapter, datum_ref, ref, kind, value, f"{label} {name}")
        dims.record(name, _STATION_DRIVES[name])

    centre = f"{circle}.center"
    await station(centre, "horizontal_distance", "BoreStationX")
    await station(centre, "vertical_distance", "BoreStationY")
    check(
        f"dimension {label} diameter",
        await adapter.add_sketch_dimension(circle, None, "diameter", BORE_DIA),
    )
    dims.record("BoreDia", '"BoreDia"')

    for a, b, relation in (
        (f"{row}.start", f"{row}.end", "horizontal_points"),
        (f"{row}.end", f"{upper}.start", "vertical_points"),
        (f"{upper}.start", f"{upper}.end", "horizontal_points"),
        (f"{row}.start", f"{upper}.end", "vertical_points"),
    ):
        check(
            f"{relation} {label} {a} {b}",
            await adapter.add_sketch_constraint(a, b, relation),
        )
    await station(f"{row}.start", "horizontal_distance", "HoleColumn1X")
    await station(f"{row}.end", "horizontal_distance", "HoleColumn2X")
    await station(f"{row}.end", "vertical_distance", "HoleRow1Y")
    await station(f"{upper}.start", "vertical_distance", "HoleRow2Y")
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    return dims


async def _cbore_floor_reference(adapter) -> list[tuple[str, str]]:
    """The hidden sketch carrying the printed counterbore floor height.

    Section B-B cuts along Y through the (-13, +13) counterbore (along X its
    arrows and letters would sit on the bore: review r5), so its cutting
    plane is the Right plane (model YZ) carried to X = -BoltX; a derived view
    imports a reference sketch that lies in its cut (build_pd_platen
    ``CboreFloorReference``). One construction line on the Ø4.5 hole's +Y
    wall, a visible section edge, from the carriage seat (Z = 0) up to the
    counterbore floor: its foot's Y from the origin (unprinted; the Z = 0
    end sits on the sketch axis), and its rise, the printed floor. The
    off-sketch check in ``_sketch_mapper`` proves the plane stands at
    X = -13 and that the sketch opened on it, not on a fallback plane.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane {CBORE_SECTION_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=-BOLT_X
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
    origin = to_sketch((-BOLT_X, 0.0, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{feature}: sketch origin maps to {origin}")
    foot = to_sketch((-BOLT_X, y_wall, 0.0))
    floor = to_sketch((-BOLT_X, y_wall, CBORE_FLOOR))
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
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return jobs + dims.apply(adapter, feature)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units. The printed stations are driven from the knobs
    # (_STATION_DRIVES), so they take no globals of their own.
    for name, value in {**DRAWING_VALUES, **MODEL_KNOBS}.items():
        if name not in _STATION_DRIVES:
            await set_global(adapter, name, f"{value}mm")

    # --- Block: Front-plane rectangle, extruded +Z ----------------------------
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    to_front = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="block profile")
    half = BLOCK_WIDTH / 2.0
    points = [
        to_front((BLOCK_X0, -half, 0.0)),
        to_front((BLOCK_X1, -half, 0.0)),
        to_front((BLOCK_X1, half, 0.0)),
        to_front((BLOCK_X0, half, 0.0)),
    ]
    lines = await add_line_chain(adapter, points)
    # Emission order: the two spans, then the anchor's x and y from the origin.
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="block profile",
        dims=block,
        names=["BlockLength", "BlockWidth", "BlockEndX", "BlockSideY"],
        drives=['"BlockLength"', '"BlockWidth"', '"BlockEndX"', '"BlockSideY"'],
    )
    await ensure_fully_defined(adapter, "block profile")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs = block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    drive_jobs.append(
        (name_dimensions(adapter, "Block", ["BlockHeight"])[0], '"BlockHeight"')
    )
    volume = await volume_check(adapter, "block", V_BLOCK, 0.002 * V_BLOCK)

    # --- The top face plane ----------------------------------------------------
    check(
        "create_plane TopFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=BLOCK_HEIGHT
            )
        ),
    )
    name_last_feature(adapter, "TopFace")
    drive_jobs.append(
        (name_dimensions(adapter, "TopFace", ["TopFaceOffset"])[0], '"BlockHeight"')
    )
    blank_reference_geometry(adapter, (("TopFace", "PLANE"),))

    # --- Bearing seats: from the top, then the same from the bottom -----------
    # A cut on a plane runs against its normal by default: down from TopFace.
    top = await _top_seat_sketch(adapter)
    name_last_feature(adapter, "TopBoreProfile")
    drive_jobs += top.apply(adapter, "TopBoreProfile")
    check(
        "cut top seat",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=BORE_DEPTH)),
    )
    name_last_feature(adapter, "TopBore")
    drive_jobs.append(
        (name_dimensions(adapter, "TopBore", ["TopBoreDepth"])[0], '"TopBoreDepth"')
    )
    volume = await volume_check(adapter, "top seat", volume - V_BORE, 0.01 * V_BORE)

    bottom = await _bore_sketch(
        adapter, "Front", 0.0, ("BottomBoreX", "BoreDia2"), "bottom seat"
    )
    name_last_feature(adapter, "BottomBoreProfile")
    drive_jobs += bottom.apply(adapter, "BottomBoreProfile")
    # Reversed: up into the block from the carriage seat.
    check(
        "cut bottom seat",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "BottomBore")
    drive_jobs.append(
        (
            name_dimensions(adapter, "BottomBore", ["BottomBoreDepth"])[0],
            '"BottomBoreDepth"',
        )
    )
    volume = await volume_check(adapter, "bottom seat", volume - V_BORE, 0.01 * V_BORE)

    # --- The shoulder's Ø25 hole (the puller cavity), through ---------------
    shoulder = SketchDims()
    check("create_sketch shoulder hole", await adapter.create_sketch("Front"))
    at = _xy_mapper(adapter, 0.0, "shoulder hole")
    await define_circle(
        adapter,
        *at(BORE_X, 0.0),
        _R_SHOULDER,
        "shoulder hole",
        dims=shoulder,
        names=("ShoulderHoleX", None, "ShoulderHoleDia"),
        drives=('"BoreX"', None, '"ShoulderHoleDia"'),
    )
    await ensure_fully_defined(adapter, "shoulder hole")
    check("exit_sketch shoulder hole", await adapter.exit_sketch())
    name_last_feature(adapter, "ShoulderHoleProfile")
    drive_jobs += shoulder.apply(adapter, "ShoulderHoleProfile")
    check(
        "cut shoulder hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShoulderHole")
    volume = await volume_check(
        adapter, "shoulder hole", volume - V_SHOULDER_HOLE, 0.01 * V_SHOULDER_HOLE
    )

    # --- Seat corners (rule 16): one fillet on both wall-shoulder corners ----
    # Each pick lies on its corner circle (model Y = seat radius, Z = the
    # shoulder face); the Ø25 hole's edges stand 2.49 inside it.
    check(
        "fillet seat corners",
        await adapter.add_fillet(
            SEAT_FILLET_RADIUS,
            [
                [BORE_X, _R_BORE, BLOCK_HEIGHT - BORE_DEPTH],
                [BORE_X, _R_BORE, BORE_DEPTH],
            ],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "SeatFillets")
    drive_jobs.append(
        (name_dimensions(adapter, "SeatFillets", ["SeatFilletR"])[0], '"SeatFilletR"')
    )
    volume = await volume_check(
        adapter, "seat corners", volume + V_SEAT_FILLETS, 0.25 * V_SEAT_FILLETS
    )

    # --- Carriage screws: ONE native Hole Wizard counterbore feature ---------
    # Drilled from the top face; the placement sketch's origin dimensions
    # are unprinted (the stations print from the faces, _top_seat_sketch).
    holes = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[x, y, BLOCK_HEIGHT] for x, y in BOLT_POINTS],
        (0.0, 0.0, 1.0),
        "carriage screw counterbores (M4 clearance)",
        name="ScrewHoles",
        expect_dia_mm=HOLE_DIA,
        placement_dims=[
            ((f"ScrewHole{index}X", '"BoltX"'), (f"ScrewHole{index}Y", '"BoltY"'))
            for index in range(1, len(BOLT_POINTS) + 1)
        ],
    )
    drive_jobs += holes.placement_drive_jobs
    v_hole = math.pi * (holes.cbore_dia_mm / 2.0) ** 2 * holes.cbore_depth_mm + (
        math.pi * (holes.hole_dia_mm / 2.0) ** 2 * (BLOCK_HEIGHT - holes.cbore_depth_mm)
    )
    volume = await volume_check(
        adapter,
        "carriage screw counterbores",
        volume - len(BOLT_POINTS) * v_hole,
        0.01 * len(BOLT_POINTS) * v_hole,
    )

    # --- Nut-bracket screws (PR C4): ONE native counterbore feature along Y --
    # Drilled from the +Y face (placement sketch u = model X, v = model Z, the
    # feed lever's +Y-face precedent); the origin dimensions are unprinted
    # and the second hole's Z repeats the first's. The printed stations live
    # on SideScrewReference.
    side = wizard_holes(
        adapter,
        SIDE_SCREW_HOLE_SPEC,
        [[x, BLOCK_WIDTH / 2.0, z] for x, z in SIDE_SCREW_HOLES],
        (0.0, 1.0, 0.0),
        "nut-bracket screw counterbores (#8 normal clearance, from +Y)",
        name="SideScrewHoles",
        expect_dia_mm=SIDE_HOLE_DIA,
        placement_dims=[
            (("SideScrewHole1X", '"SideScrewX"'), ("SideScrewHole1Z", '"SideScrewZ"')),
            (("SideScrewHole2X", '"SideScrewX"'), SharedCoordinate(0)),
        ],
    )
    drive_jobs += side.placement_drive_jobs
    v_side = math.pi * (side.cbore_dia_mm / 2.0) ** 2 * side.cbore_depth_mm + (
        math.pi * (side.hole_dia_mm / 2.0) ** 2 * (BLOCK_WIDTH - side.cbore_depth_mm)
    )
    volume = await volume_check(
        adapter,
        "nut-bracket screw counterbores",
        volume - len(SIDE_SCREW_HOLES) * v_side,
        0.01 * len(SIDE_SCREW_HOLES) * v_side,
    )
    _require_one_solid_body(adapter, label="pivot block")
    drive_jobs += await _cbore_floor_reference(adapter)
    reference = await _side_screw_reference(adapter)
    name_last_feature(adapter, SIDE_SCREW_REFERENCE)
    drive_jobs += reference.apply(adapter, SIDE_SCREW_REFERENCE)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pivot block (equations neutral)", volume, 0.002 * V_BLOCK
    )
    _require_one_solid_body(adapter, label="driven pivot block")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The bearing seat is the one model band: the N6 matched fit on the
    # 6200-2RS outer race (spec BORE_BAND). The holes print DRILL, so the
    # title block's DRILLED HOLES row governs them; the seat corners print
    # their single MAX limit.
    set_dimension_bilateral_tolerance(
        adapter, "TopBoreProfile", "BoreDia", *deviations(BORE_BAND)
    )
    _max_limit(adapter, "SeatFillets", "SeatFilletR")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
