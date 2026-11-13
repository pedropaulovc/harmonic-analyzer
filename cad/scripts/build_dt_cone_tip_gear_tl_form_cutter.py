r"""Reproduction script: the DT6-FORM1 fly-cutter bit (MHA-DT-37-TL-01).

Shop tooling, issue #2358 (``dt_cone_tip_gear_tl_form_cutter_spec`` owns every
number): 1/8 O1 drill rod, flat to centre at the tip, the T006 tooth space on
the face as its own native curves, and the two clearance prisms that relieve
every cutting edge under the face.

Bit frame: +X along the bit toward the tip, P1 (the tip centre on the face) at
the origin, the face on the Top Plane with the bit's head below it (y < 0),
the form across Z.

Features, each volume-gated against the spec's sliced form:

1. ``BitProfile`` (Front): the rod's half section, revolved to ``Bit``.
2. ``FlatProfile`` (Front): the flat to centre, its depth (``FlatDepth``)
   from a construction line on the rod's far side, cut both ways across Z.
3. ``FormReliefPlus`` / ``FormReliefMinus``: the face form (the tooth space's
   root arc, reliefs and finite flanks, closed by its shoulders and a box ahead
   of the tip) projected along each clearance direction onto the plane normal
   to it, cut both ways.  Each plane is built from read-back reference steps
   (``_straight_gash_gear._plane_through``): the Top Plane turned the front
   clearance about the Z axis, then turned about its trace on the Front Plane
   until its normal is the prism's direction.
4. Hidden reference sketches the drawing shows: the two clearance angles and
   MHA-DT-37 sheet 2's envelope (widths at P2, P12, P17).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_gear_tl_form_cutter.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _gear import equation_curve
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _straight_gash_gear import _affine_expression, _literal, _plane_through
from _visibility import blank_reference_geometry
from dt_cone_tip_gear_tl_form_cutter_spec import (
    BIT_DIA,
    BIT_DIA_PLACES,
    BIT_DIA_TOL,
    BIT_LENGTH,
    BIT_RADIUS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLANK_END_Z,
    FLAT_DEPTH,
    FACE_HEIGHT,
    FLAT_LENGTH,
    FORM_CUT_DEPTH,
    FORM_DEPTH,
    FORM_REFERENCE_SKETCH,
    FORM_WIDTH,
    FRONT_CLEARANCE_DEG,
    FRONT_CLEARANCE_SKETCH,
    INCH,
    JUNCTION_DEPTH,
    JUNCTION_WIDTH,
    REFERENCE_SKETCHES,
    ROOT_RADIUS,
    SIDE_CLEARANCE_DEG,
    SIDE_CLEARANCE_SKETCH,
    TAN_FRONT,
    TAN_SIDE,
    TIP_DEPTH,
    TIP_STOCK,
    TIP_WIDTH,
    UNIT,
    VOLUME_TOL_MM3,
    bit_volume_mm3,
    clearance_direction,
    form_segments,
    shoulder_loop_g,
)

PART_NAME = "dt-cone-tip-gear-tl-form-cutter"
MATERIAL = "Alloy Steel"  # O1 tool steel drill rod (the registry row names it)

Vector = tuple[float, float, float]

# Front-plane (u, v) = model (X, Y): the rod's half section from the shank end
# up, along the top to past the tip, down the end to the axis, back along the
# axis through P1 (the origin) to the shank end.
PROFILE_POINTS = [
    (-BIT_LENGTH, 0.0),
    (-BIT_LENGTH, BIT_RADIUS),
    (TIP_STOCK, BIT_RADIUS),
    (TIP_STOCK, 0.0),
    (0.0, 0.0),
]
# The flat: a Front-plane box over the face from the flat's start to past the
# tip, cut through the rod both ways along Z.  Its floor (the face) stands
# FLAT_DEPTH above a construction line on the rod's far side, so the depth the
# sheet prints is the thickness a micrometer reads across the flat; on the
# .001 grid it leaves the face FACE_HEIGHT above the axis.
_FLAT_FAR_X = TIP_STOCK + 1.0
_FLAT_TOP = BIT_RADIUS + 1.0
FLAT_POINTS = [
    (-FLAT_LENGTH, FACE_HEIGHT),
    (-FLAT_LENGTH, _FLAT_TOP),
    (_FLAT_FAR_X, _FLAT_TOP),
    (_FLAT_FAR_X, FACE_HEIGHT),
]
# The rod's far side at the flat's start, run to under P1.
FAR_SIDE_ENDS = ((-FLAT_LENGTH, -BIT_RADIUS), (0.0, -BIT_RADIUS))


def _unit(vector: Vector) -> Vector:
    length = math.sqrt(sum(c * c for c in vector))
    return tuple(c / length for c in vector)


def _cross(a: Vector, b: Vector) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


# The face-relief plane's trace on the Front Plane: the pivot of both prism
# planes, along the front-clearance line under the tip.
_FRONT_TRACE = (
    math.cos(math.radians(FRONT_CLEARANCE_DEG)),
    -math.sin(math.radians(FRONT_CLEARANCE_DEG)),
    0.0,
)


def _prism_plane_angle_deg() -> float:
    """The turn from the face-relief plane to a prism plane about their shared
    trace: between the face-relief plane's normal and the prism's direction."""
    normal = (
        math.sin(math.radians(FRONT_CLEARANCE_DEG)),
        math.cos(math.radians(FRONT_CLEARANCE_DEG)),
        0.0,
    )
    return math.degrees(math.acos(abs(_dot(normal, clearance_direction(1)))))


def _model_to_sketch(adapter: Any):
    """The ACTIVE sketch's model-to-sketch map, mm in, (u, v, w) mm out
    (``_straight_gash_gear._sketch_mapper``'s ``ModelToSketchTransform``)."""
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("fly-cutter bit: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: Vector) -> Vector:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    return raw


def _face_model(xg: float, yg: float) -> Vector:
    """The face point (model mm) of gear-frame tooth-space point (xg, yg)."""
    return (ROOT_RADIUS - xg, 0.0, yg)


def _projected_map(adapter: Any, direction: Vector):
    """Affine sketch map of a face point projected along ``direction`` onto
    the active (prism) sketch plane, which passes through the origin with
    ``direction`` as its normal: (origin_uv, d/dxg, d/dyg), sketch mm."""
    raw = _model_to_sketch(adapter)

    def projected(xg: float, yg: float) -> Vector:
        point = _face_model(xg, yg)
        along = _dot(point, direction)
        mapped = raw(
            tuple(p - along * d for p, d in zip(point, direction, strict=True))
        )
        if abs(mapped[2]) > 1e-6:
            raise RuntimeError(
                f"fly-cutter bit: projected face point leaves the prism plane by {mapped[2]:g} mm"
            )
        return mapped

    origin = projected(0.0, 0.0)
    along_x = tuple(a - o for a, o in zip(projected(1.0, 0.0), origin, strict=True))
    along_y = tuple(a - o for a, o in zip(projected(0.0, 1.0), origin, strict=True))
    return origin, along_x, along_y


def _line_expression(start: float, end: float) -> str:
    """A straight run over t in [0, 1], inches, fixed-point literals."""
    return f"(({_literal(start / INCH)})+({_literal((end - start) / INCH)})*t)"


async def _form_prism(
    adapter: Any, side: int, plane: str, sketch: str, feature: str
) -> None:
    """Sketch the face form projected onto ``plane`` and cut it both ways."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    direction = clearance_direction(side)
    check(f"create_sketch {sketch}", await adapter.create_sketch(plane))
    origin, along_x, along_y = _projected_map(adapter, direction)

    def mapped(x_expr: str, y_expr: str) -> tuple[str, str]:
        return tuple(
            _affine_expression(origin[k] / INCH, along_x[k], along_y[k], x_expr, y_expr)
            for k in (0, 1)
        )

    curves = []
    loop = shoulder_loop_g()
    for index, ((x0, y0), (x1, y1)) in enumerate(zip(loop, loop[1:])):
        curves.append(
            await equation_curve(
                adapter,
                f"{sketch} shoulder {index}",
                *mapped(_line_expression(x0, x1), _line_expression(y0, y1)),
            )
        )
    for segment in form_segments(unit_scale=1.0 / INCH):
        curves.append(
            await equation_curve(
                adapter, f"{sketch} {segment.name}", *mapped(segment.x, segment.y)
            )
        )
    await ensure_fully_defined(
        adapter, f"{sketch} sketch", fix_entities=curves, allow_fix_escalation=True
    )
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    check(
        f"cut {feature}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FORM_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, feature)


async def _prism_planes(adapter: Any) -> tuple[str, ...]:
    """The two prism planes, each through the origin normal to its prism's
    direction; returns every reference feature made, for blanking."""
    from solidworks_mcp.adapters.base import CreateAxisParameters

    z_axis = check(
        "create_axis bit Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    ).name
    await _plane_through(
        adapter,
        "FaceReliefPlane",
        base_plane="Top Plane",
        pivot_axis=z_axis,
        angle_deg=FRONT_CLEARANCE_DEG,
        direction=_FRONT_TRACE,
    )
    trace = check(
        "create_axis face-relief trace (FaceReliefPlane x Front)",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="two_planes", planes=["FaceReliefPlane", "Front Plane"]
            )
        ),
    ).name
    angle = _prism_plane_angle_deg()
    for side, plane in ((1, "FormReliefPlanePlus"), (-1, "FormReliefPlaneMinus")):
        await _plane_through(
            adapter,
            plane,
            base_plane="FaceReliefPlane",
            pivot_axis=trace,
            angle_deg=angle,
            direction=_unit(_cross(clearance_direction(side), _FRONT_TRACE)),
        )
    return z_axis, trace


async def _angle_reference(
    adapter: Any,
    plane: str,
    sketch: str,
    vertex: Vector,
    lean: Vector,
    angle_name: str,
    angle_deg: float,
    *,
    vertex_name: str | None,
) -> list[tuple[str, str]]:
    """A hidden reference sketch: a vertical line down from ``vertex`` (model
    mm) the rod's radius, and the clearance trace from the same vertex to
    ``vertex + lean``; the angle between them is the printed clearance."""
    dims = SketchDims()
    check(f"create_sketch {sketch}", await adapter.create_sketch(plane))
    raw = _model_to_sketch(adapter)
    top = raw(vertex)[:2]
    plumb = raw(
        tuple(v + d for v, d in zip(vertex, (0.0, -BIT_RADIUS, 0.0), strict=True))
    )[:2]
    trace = raw(tuple(v + d for v, d in zip(vertex, lean, strict=True)))[:2]
    if abs(plumb[0] - top[0]) > 1e-9:
        raise RuntimeError(f"{sketch}: model -Y is not sketch-vertical on {plane}")
    set_sketch_direct_db(adapter, True)
    (vertical,) = await add_line_chain(adapter, [top, plumb], close=False)
    (clearance,) = await add_line_chain(adapter, [top, trace], close=False)
    set_sketch_direct_db(adapter, False)
    check(
        f"{sketch} plumb vertical",
        await adapter.add_sketch_constraint(vertical, None, "vertical"),
    )
    check(
        f"{sketch} shared vertex",
        await adapter.add_sketch_constraint(
            f"{clearance}.start", f"{vertical}.start", "coincident"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{vertical}.start", top[0], top[1], f"{sketch} vertex"
    )
    if abs(top[0]) >= 1e-9:
        dims.record(vertex_name)
    if abs(top[1]) >= 1e-9:
        raise RuntimeError(f"{sketch}: the clearance vertex must lie on the face")
    await dimension_between(
        adapter,
        f"{vertical}.start",
        f"{vertical}.end",
        "vertical_distance",
        BIT_RADIUS,
        f"{sketch} plumb length",
    )
    dims.record(None)
    await dimension_between(
        adapter,
        f"{clearance}.start",
        f"{clearance}.end",
        "vertical_distance",
        BIT_RADIUS,
        f"{sketch} trace depth",
    )
    dims.record(None)
    check(
        f"{sketch} {angle_name}",
        await adapter.add_sketch_dimension(clearance, vertical, "angular", angle_deg),
    )
    dims.record(angle_name, f'"{angle_name}"')
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    return dims.apply(adapter, sketch)


async def _form_envelope(adapter: Any) -> list[tuple[str, str]]:
    """MHA-DT-37 sheet 2's widths on the face: P2-P2 (the tip), P12-P12 (the
    relief's junction with the involute) and P17-P17 (the blank OD), each a
    line across the form at its table station Y back from P1."""
    dims = SketchDims()
    check(f"create_sketch {FORM_REFERENCE_SKETCH}", await adapter.create_sketch("Top"))
    raw = _model_to_sketch(adapter)
    rows = (
        ("Tip", TIP_WIDTH, TIP_DEPTH),
        ("Junction", JUNCTION_WIDTH, JUNCTION_DEPTH),
        ("Form", FORM_WIDTH, FORM_DEPTH),
    )
    lines = []
    set_sketch_direct_db(adapter, True)
    for name, width, depth in rows:
        ends = [raw((-depth, 0.0, side * width / 2.0))[:2] for side in (1, -1)]
        if abs(ends[0][0] - ends[1][0]) > 1e-9:
            raise RuntimeError(
                f"{FORM_REFERENCE_SKETCH}: model Z is not sketch-vertical"
            )
        (line,) = await add_line_chain(adapter, ends, close=False)
        lines.append((name, line, width, ends))
    set_sketch_direct_db(adapter, False)
    for name, line, width, ends in lines:
        check(
            f"{name} width vertical",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "vertical_distance",
            width,
            f"{name} width",
        )
        dims.record(f"{name}Width")
        await anchor_point_to_origin(
            adapter, f"{line}.start", *ends[0], f"{name} station"
        )
        dims.record(f"{name}Depth")
        dims.record(f"{name}Half")
    await ensure_fully_defined(adapter, f"{FORM_REFERENCE_SKETCH} sketch")
    check(f"exit_sketch {FORM_REFERENCE_SKETCH}", await adapter.exit_sketch())
    name_last_feature(adapter, FORM_REFERENCE_SKETCH)
    return dims.apply(adapter, FORM_REFERENCE_SKETCH)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # Editable knobs: inch document, so the mm suffix is load-bearing.
    for name, value in (
        ("BitDia", f"{BIT_DIA}mm"),
        ("BitLength", f"{BIT_LENGTH}mm"),
        ("FlatLength", f"{FLAT_LENGTH}mm"),
        ("FlatDepth", f"{FLAT_DEPTH}mm"),
        ("FrontClearance", f"{FRONT_CLEARANCE_DEG}deg"),
        ("SideClearance", f"{SIDE_CLEARANCE_DEG}deg"),
    ):
        await set_global(adapter, name, value)
    drive_jobs: list[tuple[str, str]] = []

    # 1. The rod.
    profile = SketchDims()
    check("create_sketch bit profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "bit axis centerline",
        await adapter.add_centerline(-BIT_LENGTH, 0.0, TIP_STOCK, 0.0),
    )
    lines = await add_line_chain(adapter, PROFILE_POINTS)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        v0 = PROFILE_POINTS[index][1]
        v1 = PROFILE_POINTS[(index + 1) % len(PROFILE_POINTS)][1]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"bit profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    shank_end, top, tip_end, tip_axis, shank_axis = lines
    check(
        "P1 on the origin",
        await adapter.add_sketch_constraint(
            f"{shank_axis}.start", "origin", "coincident"
        ),
    )
    await dimension_between(
        adapter,
        f"{shank_axis}.end",
        f"{shank_axis}.start",
        "horizontal_distance",
        BIT_LENGTH,
        "bit length",
    )
    profile.record("BitLength", '"BitLength"')
    await dimension_between(
        adapter,
        f"{tip_axis}.start",
        f"{tip_axis}.end",
        "horizontal_distance",
        TIP_STOCK,
        "tip stock",
    )
    profile.record("TipStock")
    await add_diametric_linear_dimension(
        adapter, axis, top, (-BIT_LENGTH - 2.0, BIT_RADIUS), "BitDia"
    )
    profile.record("BitDia", '"BitDia"')
    await ensure_fully_defined(adapter, "bit profile")
    check("exit_sketch bit profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BitProfile")
    drive_jobs += profile.apply(adapter, "BitProfile")
    check("revolve bit", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Bit")
    await volume_check(adapter, "drill rod", bit_volume_mm3("revolve"), VOLUME_TOL_MM3)
    await bbox_extent_check(adapter, "bit length", "x", BIT_LENGTH + TIP_STOCK)

    # 2. The flat to centre.
    flat = SketchDims()
    check("create_sketch flat", await adapter.create_sketch("Front"))
    flat_lines = await add_line_chain(adapter, FLAT_POINTS)
    for index, line in enumerate(flat_lines):
        v0 = FLAT_POINTS[index][1]
        v1 = FLAT_POINTS[(index + 1) % len(FLAT_POINTS)][1]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"flat {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    set_sketch_direct_db(adapter, True)
    far_side = check(
        "flat far-side centerline",
        await adapter.add_centerline(*FAR_SIDE_ENDS[0], *FAR_SIDE_ENDS[1]),
    )
    set_sketch_direct_db(adapter, False)
    for ref1, ref2, relation in (
        (far_side, None, "horizontal"),
        (f"{far_side}.end", "origin", "vertical_points"),
        (f"{far_side}.start", f"{flat_lines[0]}.start", "vertical_points"),
    ):
        check(
            f"flat far side {relation}",
            await adapter.add_sketch_constraint(ref1, ref2, relation),
        )
    await dimension_between(
        adapter,
        f"{flat_lines[0]}.start",
        "origin",
        "horizontal_distance",
        FLAT_LENGTH,
        "flat start",
    )
    flat.record("FlatLength", '"FlatLength"')
    await dimension_between(
        adapter,
        f"{far_side}.end",
        "origin",
        "vertical_distance",
        BIT_RADIUS,
        "rod far side",
    )
    flat.record("RodFarSide", '"BitDia"/2')
    await dimension_between(
        adapter,
        f"{far_side}.start",
        f"{flat_lines[0]}.start",
        "vertical_distance",
        FLAT_DEPTH,
        "flat depth",
    )
    flat.record("FlatDepth", '"FlatDepth"')
    await dimension_between(
        adapter,
        f"{flat_lines[0]}.start",
        f"{flat_lines[0]}.end",
        "vertical_distance",
        _FLAT_TOP - FACE_HEIGHT,
        "flat box height",
    )
    flat.record(None)
    await dimension_between(
        adapter,
        f"{flat_lines[0]}.start",
        f"{flat_lines[2]}.end",
        "horizontal_distance",
        _FLAT_FAR_X + FLAT_LENGTH,
        "flat box length",
    )
    flat.record(None)
    await ensure_fully_defined(adapter, "flat")
    check("exit_sketch flat", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatProfile")
    drive_jobs += flat.apply(adapter, "FlatProfile")
    check(
        "cut flat to centre",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * _FLAT_TOP, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Flat")
    await volume_check(
        adapter, "flat to centre", bit_volume_mm3("flat"), VOLUME_TOL_MM3
    )

    # 3. The face form and its two clearance prisms.
    axes = await _prism_planes(adapter)
    await _form_prism(
        adapter, 1, "FormReliefPlanePlus", "FormProfilePlus", "FormReliefPlus"
    )
    await volume_check(
        adapter, "form, +Z flank relieved", bit_volume_mm3("form_plus"), VOLUME_TOL_MM3
    )
    await _form_prism(
        adapter, -1, "FormReliefPlaneMinus", "FormProfileMinus", "FormReliefMinus"
    )
    await volume_check(
        adapter, "form, both flanks relieved", bit_volume_mm3("form"), VOLUME_TOL_MM3
    )
    part = _early_bound(adapter.currentModel, "IPartDoc")
    if len(tuple(part.GetBodies2(0, False) or ())) != 1:
        raise RuntimeError("fly-cutter bit: the form cut must leave one solid body")
    blank_reference_geometry(
        adapter,
        (
            *((name, "AXIS") for name in axes),
            ("FaceReliefPlane", "PLANE"),
            ("FormReliefPlanePlus", "PLANE"),
            ("FormReliefPlaneMinus", "PLANE"),
        ),
    )

    # 4. The printed references.
    drive_jobs += await _angle_reference(
        adapter,
        "Front",
        FRONT_CLEARANCE_SKETCH,
        (0.0, 0.0, 0.0),
        (-BIT_RADIUS * TAN_FRONT, -BIT_RADIUS, 0.0),
        "FrontClearance",
        FRONT_CLEARANCE_DEG,
        vertex_name=None,
    )
    drive_jobs += await _angle_reference(
        adapter,
        "Right",
        SIDE_CLEARANCE_SKETCH,
        (0.0, 0.0, FLANK_END_Z),
        (0.0, -BIT_RADIUS, -BIT_RADIUS * TAN_SIDE),
        "SideClearance",
        SIDE_CLEARANCE_DEG,
        vertex_name="SideFlankEndZ",
    )
    drive_jobs += await _form_envelope(adapter)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven bit (equations neutral)",
        bit_volume_mm3("form"),
        VOLUME_TOL_MM3,
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The rod's ground diameter carries the supplier's band (the slip fit in
    # the bar); every other size takes the title block's rows.
    set_dimension_symmetric_tolerance(
        adapter,
        "BitProfile",
        "BitDia",
        BIT_DIA_TOL,
        places=BIT_DIA_PLACES,
        display_unit=UNIT,
    )
    # The flat's depth takes the title block's .XXX row, like every other size.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=())
    apply_drawing_properties(adapter, PART_NAME)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter, ("Number", "Material Specification", "Finish", "Quantity")
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
