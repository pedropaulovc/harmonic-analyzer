r"""Reproduction script: pen v-block (MHA-PN-05), re-derived per
``pn_pen_v_block_spec``.

The bright brass block that hangs on the pen rod and carries the marker, a
"simplified E" in plan: a neck at the paper end that the stirrup straddles,
with a 90 degree V-groove under it that seats the marker's grip; then a body
wider by BODY_SIDE_STEP each side, with a flat-roofed relief slot that passes
the marker's body; the rod's reamed pivot bore from the top face down into the
relief; and a #4-40 set-screw tap from the body's front face into that bore.

Part frame (the assembly places the part by its origin and Front/Top/Right
planes, so this is a contract): X 0..BLOCK_LENGTH along the marker, x 0 the
PAPER end face; Y 0..BLOCK_HEIGHT up, y 0 the bottom face; Z across the depth,
z 0 the neck's FRONT face (away from the paper), the neck z 0..NECK_DEPTH and
the body BODY_Z0..BODY_Z1. The origin is the bottom/paper-end/front corner of
the neck.  The print's depth datum is the body's front face (z BODY_Z0): every
station across the depth is a baseline from it, so each sketch that prints one
carries a construction foot on that face.

Features, in tree order:

* ``OutlineProfile`` (Top plane, sketch (u, v) = model (X, -Z)) -> ``Block``:
  the plan outline, neck and body, extruded +Y by the height.
* ``VGrooveProfile`` (Right plane, sketch (u, v) = model (-Z, Y)) ->
  ``VGroove``: the V, each flank's angle to the bottom face, both mouth edges
  (each from the body's front face) and its apex flat's width driving and the
  flat's height a driven reference,
  cut +X from the paper end to ``V_CUT_LENGTH``, one corner radius past the
  relief's step.
* ``VApexFillets``: the rounds where the apex flat meets the flanks, at the
  ``V_APEX_FILLET_R`` limit; the sheet prints it "2X R.020 MAX".
* ``ReliefProfile`` (Top plane) -> ``Relief``: the slot from ``RELIEF_X0`` to
  the free end, its two step corners the end mill's ``RELIEF_CORNER_R`` arcs,
  cut +Y to the roof.
* ``PivotBoreProfile`` (Top plane) -> ``PivotBore``: the reamed bore, a
  sketched through cut; it removes brass only between the top face and the
  relief roof.  Its diameter carries the H7 band.
* ``PivotBoreChamfer``: 45 deg on the bore's top edge (it clears the rod's
  shoulder-root fillet); ``PivotReference`` prints its size, a single MIN limit.
* ``SetScrewHole``: Hole Wizard #4-40 tap from the body's front face, up to
  the pivot bore (``through_next``); built after the bore so it stops there.
* ``SectionAPlane``: parallel to the Right plane through the pivot-bore axis,
  section A-A's cutting plane (hidden).
* ``ReliefReference`` / ``PivotReference`` (on ``SectionAPlane``), hidden:
  construction chords on edges the sheet shows, owning each feature's station
  across the depth from the body's front face and the relief height from the
  bottom face to the roof (``pn_pen_v_block_spec`` contract).  Both lie IN
  the section's cutting plane (the bond cradle's recipe): the drawing cuts the
  section while the part shows them, which is how a section imports a hidden
  sketch's dims.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_v_block.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import _feature_by_name, name_last_feature
from _fit_deviations import deviations
from _holes import TAP_DRILL_MM, cross_hole_volume_mm3, wizard_holes
from _part_checks import report_mass_properties, volume_check
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
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
import _telemetry
from pn_pen_v_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BODY_DEPTH,
    BODY_SIDE_STEP,
    BODY_Z0,
    BODY_Z1,
    DEPTH_MID_Z,
    DIMENSION_PREFIXES,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    NECK_DEPTH,
    PIVOT_BORE_DIA,
    PIVOT_BORE_TOP_CHAMFER,
    PIVOT_BORE_X,
    PIVOT_CHAMFER_BAND,
    PIVOT_CHAMFER_TOL_TYPE,
    REFERENCE_DIMENSIONS,
    REFERENCE_SKETCHES,
    RELIEF_CORNER_R,
    RELIEF_HEIGHT,
    RELIEF_WIDTH,
    RELIEF_X0,
    RELIEF_Z0,
    RELIEF_Z1,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
    UNIT,
    V_FLANK_ANGLE_DEG,
    V_APEX_FILLET_AREA,
    V_APEX_FILLET_BAND,
    V_APEX_FILLET_R,
    V_APEX_FILLET_TOL_TYPE,
    V_CUT_LENGTH,
    V_FLAT_WIDTH,
    V_FLAT_Y,
    V_GROOVE_AREA,
    V_GROOVE_SECTION,
    V_MOUTH_Z0,
    V_MOUTH_Z1,
    depth_station,
)

PART_NAME = "pn-pen-v-block"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed
TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size]
_Z_MID = DEPTH_MID_Z
# The body's front face in the Right plane's and the section's sketch (u =
# -Z): the depth datum's foot, where each depth-wise sketch anchors a stub.
_DATUM_U = BODY_SIDE_STEP
# Section A-A's cutting plane (the drawing cuts at x = PIVOT_BORE_X): the
# section's reference sketches lie in it.
SECTION_PLANE = "SectionAPlane"
# Length of the datum stubs and the pivot reference's axis chord; unprinted,
# short enough to stay on the front face clear of the set-screw tap.
_STUB = 1.0

# Analytic volumes (mm^3) of each feature, checked after it is built.
V_BLOCK = (
    RELIEF_X0 * NECK_DEPTH + (BLOCK_LENGTH - RELIEF_X0) * BODY_DEPTH
) * BLOCK_HEIGHT
V_GROOVE = V_GROOVE_AREA * V_CUT_LENGTH
# The apex rounds give back their corners along the whole cut.
V_APEX_FILLETS = V_APEX_FILLET_AREA * V_CUT_LENGTH
# Each step corner leaves its R x R square less the quarter disc standing.
V_RELIEF_CORNERS = 2.0 * (1.0 - math.pi / 4.0) * RELIEF_CORNER_R**2 * RELIEF_HEIGHT
# The V's run past the step lies inside the slot (the corner arcs stand
# outside its mouth), already void when the relief is cut.
V_GROOVE_PAST_STEP = V_GROOVE_SECTION * (V_CUT_LENGTH - RELIEF_X0)
V_RELIEF = (
    RELIEF_WIDTH * RELIEF_HEIGHT * (BLOCK_LENGTH - RELIEF_X0)
    - V_RELIEF_CORNERS
    - V_GROOVE_PAST_STEP
)
# The vertical bore removes brass only from the relief roof to the top face.
V_PIVOT_BORE = math.pi * (PIVOT_BORE_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - RELIEF_HEIGHT)
# A 45 deg chamfer of leg c round a bore of radius r: the c x c / 2 triangle
# swept about the axis at its centroid's radius r + c / 3.
V_PIVOT_CHAMFER = (
    math.pi
    * PIVOT_BORE_TOP_CHAMFER**2
    * (PIVOT_BORE_DIA / 2.0 + PIVOT_BORE_TOP_CHAMFER / 3.0)
)
# The tap runs from the body's front face to where its whole profile is inside
# the bore: the drill cylinder to the bore axis less its near half of the
# drill-through-bore intersection (already void).
V_SET_SCREW_TAP = (
    math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * (_Z_MID - BODY_Z0)
    - cross_hole_volume_mm3(TAP_DRILL_DIA, PIVOT_BORE_DIA) / 2.0
)
V_TOTAL = (
    V_BLOCK
    - V_GROOVE
    + V_APEX_FILLETS
    - V_RELIEF
    - V_PIVOT_BORE
    - V_PIVOT_CHAMFER
    - V_SET_SCREW_TAP
)


async def _outline(adapter, dims: SketchDims) -> None:
    """The plan outline on the Top plane, sketch (u, v) = model (X, -Z).

    Lines L0..L7 run from the origin round the neck and the body: (0,0) ->
    (X0,0) -> (X0,s) -> (L,s) -> (L,-Z1) -> (X0,-Z1) -> (X0,-N) -> (0,-N),
    with X0 the step (RELIEF_X0), s the body's side step, Z1 its back face and
    N the neck's depth.  Relations: L0 starts on the origin; the even lines
    horizontal, the odd vertical.  Dims: the step's station on both neck faces
    (unprinted, the "ReliefX0" global: the print states it once, on the slot's
    step, in line with these), the overall length along the back (printed in
    the bottom view under it, the outermost of the paper end's baseline row:
    its extension lines drop from the paper end's and the free end's back
    corners into the air behind the block, so the air in front of it is free
    for the relief corner's radius), and the depth-wise faces as baselines
    from the body's front face at the step (L2's start): the neck's front face
    and its back face (NeckZ0 / NeckZ1) and the body's back face at the step
    (Depth), one row printed in the bottom view right of the paper end, where
    the neck's step is an outline change on both long edges and the overall
    depth closes the row (blind review final9: without it the neck's back face
    read as the overall) -- 16 point DOF less 2 + 8 relations + 6 dims = 0.
    """
    step, side = RELIEF_X0, BODY_SIDE_STEP
    points = [
        (0.0, 0.0),
        (step, 0.0),
        (step, side),
        (BLOCK_LENGTH, side),
        (BLOCK_LENGTH, -BODY_Z1),
        (step, -BODY_Z1),
        (step, -NECK_DEPTH),
        (0.0, -NECK_DEPTH),
    ]
    lines = await add_line_chain(adapter, points)
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "outline origin corner"
    )
    for index, line in enumerate(lines):
        relation = "vertical" if index % 2 else "horizontal"
        check(
            f"outline L{index} {relation}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    paper_front, step_front = f"{lines[0]}.start", f"{lines[0]}.end"
    datum = f"{lines[2]}.start"  # the body's front face, at the step
    paper_back = f"{lines[6]}.end"
    free_back, body_back = f"{lines[3]}.end", f"{lines[4]}.end"
    step_back = f"{lines[6]}.start"
    for first, second, kind, value, name, drive, label in (
        (
            paper_front,
            step_front,
            "horizontal_distance",
            step,
            "NeckLength",
            '"ReliefX0"',
            "neck front face length",
        ),
        (
            paper_back,
            step_back,
            "horizontal_distance",
            step,
            "NeckBackLength",
            '"ReliefX0"',
            "neck back face length",
        ),
        (
            paper_back,
            free_back,
            "horizontal_distance",
            BLOCK_LENGTH,
            "Length",
            '"BlockLength"',
            "block length",
        ),
        (
            datum,
            paper_front,
            "vertical_distance",
            side,
            "NeckZ0",
            '"NeckFrontZ"',
            "neck front face from the body's front face",
        ),
        (
            datum,
            paper_back,
            "vertical_distance",
            depth_station(NECK_DEPTH),
            "NeckZ1",
            '"NeckBackZ"',
            "neck back face from the body's front face",
        ),
        (
            datum,
            body_back,
            "vertical_distance",
            BODY_DEPTH,
            "Depth",
            '"BlockDepth"',
            "body back face from the body's front face",
        ),
    ):
        await dimension_between(adapter, first, second, kind, value, label)
        dims.record(name, drive)


# Sketch (u, v) of each flank's angle text point, front then back: it picks
# the wedge that flank's angle to the bottom face is measured in
# (AddSpecificDimension takes the region holding its text point).  The front
# one stands in the groove just over its mouth corner (unprinted).  The
# printed back one stands in the vertically opposite wedge, under the bottom
# face and beyond the back mouth corner, between the flank's and the bottom
# face's continuations past the corner: the same 45 deg, so the drawing keeps
# the angle's arc out of the view, short, at the corner (blind review final9:
# in the groove the arc struck its own text).
def _flank_angle_text_points() -> tuple[tuple[float, float], tuple[float, float]]:
    return ((-(V_MOUTH_Z0 + 1.5), 0.5), (-(V_MOUTH_Z1 + 1.5), -0.6))


def _add_driving_flank_angle(
    adapter, flank: str, mouth: str, text_point: tuple[float, float], label: str
) -> None:
    """One flank's angle to the mouth line (the bottom face), as a DRIVING
    dimension.

    ``build_dt_cone_pivot_post._add_driving_plan_incline``'s recipe: both
    lines selected as segments (the adapter's "angular" route selects one
    segment and its vertex and left the farm's first native run, c0b95549c,
    over-defined), the text point inside the wedge, passed as sketch (u, v)
    in the x / y slots and as the model point (Z = -u) in the z slot, so it
    lands in the wedge whichever space SOLIDWORKS reads it in (the Right
    plane's normal, model X, projects away).  The measured value is checked
    before the dimension is made driving.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    u, v = (value / 1000.0 for value in text_point)
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [flank, mouth], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        u,
        v,
        -u,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_rad = abs(float(dimension.SystemValue))
    if abs(actual_rad - math.radians(V_FLANK_ANGLE_DEG)) > 1e-8:
        raise RuntimeError(
            f"{label}: measured {math.degrees(actual_rad):.6f} deg, "
            f"expected {V_FLANK_ANGLE_DEG:.6f} deg"
        )
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(dimension.DrivenState) != 2:
        raise RuntimeError(f"{label}: angular dimension did not become driving")
    _telemetry.success(f"driving {label}: {V_FLANK_ANGLE_DEG:g} deg")


def _make_driven(adapter, dimension_id: str, label: str) -> None:
    """Turn a just-made sketch dimension into a DRIVEN (reference) one."""
    display = _early_bound(adapter._sketch_entities[dimension_id], "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{label}: dimension did not become driven")


async def _v_groove(adapter, dims: SketchDims) -> None:
    """The V on the Right plane, sketch (u, v) = model (-Z, Y).

    A construction stub stands on the body's front face (the depth datum,
    beyond the neck in the paper-end view) from its foot on the bottom face:
    its foot from the origin and its length, unprinted.  The neck's faces and
    the depth print in the bottom view, from the outline.  The V is a
    trapezoid: LA runs front mouth -> the flat's front end, LF along the apex
    flat, LB the flat's back end -> back mouth, LC back mouth -> front mouth
    along the bottom face.  Relations: the stub's foot on the origin's level
    and the stub vertical, LC and LF horizontal, the front mouth on the
    origin's level.  Driving dims: both mouth edges from the datum's foot
    (real edges on the bottom face, baselines from the face the print locates
    everything from, so neither is chained from the other and the V is not
    placed by the depth's symmetry), the flat's width and each flank's angle
    to LC (the bottom face), so each flank is fixed on its own -- 1 x 4 + 8
    DOF less 5 relations + 7 dims = 0.  The flat's height is what they leave:
    a DRIVEN dimension the print shows as a reference.  It is made driven
    before the angles exist, so the sketch is never over-defined.  The stub
    is construction geometry: the cut takes only the trapezoid.
    """
    datum = await _construction_chord(
        adapter, "VGrooveProfile", (_DATUM_U, 0.0), (_DATUM_U, _STUB)
    )
    await anchor_point_to_origin(
        adapter, f"{datum}.start", _DATUM_U, 0.0, "V datum foot on the front face"
    )
    dims.record("VDatumZ", '"NeckFrontZ"')
    check(
        "V datum stub vertical",
        await adapter.add_sketch_constraint(datum, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{datum}.start",
        f"{datum}.end",
        "vertical_distance",
        _STUB,
        "V datum stub",
    )
    dims.record("VDatumStub")
    flat_half = V_FLAT_WIDTH / 2.0
    points = [
        (-V_MOUTH_Z0, 0.0),
        (-(_Z_MID - flat_half), V_FLAT_Y),
        (-(_Z_MID + flat_half), V_FLAT_Y),
        (-V_MOUTH_Z1, 0.0),
    ]
    flank_a, flat, flank_b, mouth = await add_line_chain(adapter, points)
    check(
        "V mouth horizontal",
        await adapter.add_sketch_constraint(mouth, None, "horizontal"),
    )
    check(
        "V apex flat horizontal",
        await adapter.add_sketch_constraint(flat, None, "horizontal"),
    )
    check(
        "V mouth on the bottom face",
        await adapter.add_sketch_constraint(
            f"{flank_a}.start", "origin", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{datum}.start",
        f"{flank_a}.start",
        "horizontal_distance",
        depth_station(V_MOUTH_Z0),
        "V front mouth edge from the front face",
    )
    dims.record("VMouthZ0", '"VMouthFrontZ"')
    flat_height = await dimension_between(
        adapter,
        f"{flat}.end",
        "origin",
        "vertical_distance",
        V_FLAT_Y,
        "V apex flat height",
    )
    _make_driven(adapter, flat_height, "V apex flat height")
    dims.record("VFlatY")
    await dimension_between(
        adapter,
        f"{datum}.start",
        f"{flank_b}.end",
        "horizontal_distance",
        depth_station(V_MOUTH_Z1),
        "V back mouth edge from the front face",
    )
    dims.record("VMouthZ1", '"VMouthBackZ"')
    await dimension_between(
        adapter,
        f"{flat}.start",
        f"{flat}.end",
        "horizontal_distance",
        V_FLAT_WIDTH,
        "V apex flat width",
    )
    dims.record("VFlatWidth", '"VFlatWidth"')
    front_text, back_text = _flank_angle_text_points()
    _add_driving_flank_angle(
        adapter, flank_a, mouth, front_text, "V front flank to the bottom face"
    )
    dims.record("OtherVFlankAngle", '"VFlankAngle"')
    _add_driving_flank_angle(
        adapter, flank_b, mouth, back_text, "V back flank to the bottom face"
    )
    dims.record("VFlankAngle", '"VFlankAngle"')


async def _construction_chord(
    adapter, feature: str, start: tuple[float, float], end: tuple[float, float]
) -> str:
    """One construction line, placed with inference off (ms_stop_geom recipe)."""
    set_sketch_direct_db(adapter, True)
    line = check(feature, await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError(f"{feature}: construction flag rejected")
    return line


def _plane_frame(adapter, name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(rotation, origin mm) of a reference plane, read back from
    ``IRefPlane::Transform`` (diag_build_1330K524._plane_frame's layout:
    nine rotation doubles, then the translation in metres)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return tuple(data[0:9]), tuple(v * 1000.0 for v in data[9:12])


async def _section_plane(adapter) -> None:
    """Section A-A's cutting plane: the Right plane carried +X to the pivot-bore
    axis.  Read back against the Right plane: the same rotation (so a sketch on
    it keeps the Right plane's (u, v) = model (-Z, Y)) and an origin shifted by
    exactly PIVOT_BORE_X along +X; anything else raises before a chord is laid.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create plane {SECTION_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=PIVOT_BORE_X
            )
        ),
    )
    name_last_feature(adapter, SECTION_PLANE)
    right_rotation, right_origin = _plane_frame(adapter, "Right Plane")
    rotation, origin = _plane_frame(adapter, SECTION_PLANE)
    shift = tuple(o - r for o, r in zip(origin, right_origin))
    if any(abs(a - b) > 1e-9 for a, b in zip(rotation, right_rotation)) or any(
        abs(s - e) > 1e-6 for s, e in zip(shift, (PIVOT_BORE_X, 0.0, 0.0))
    ):
        raise RuntimeError(
            f"{SECTION_PLANE}: rotation {rotation} / origin shift {shift} mm, "
            f"expected the Right plane's {right_rotation} shifted "
            f"({PIVOT_BORE_X}, 0, 0)"
        )


def _require_on_section_plane(adapter, sketch: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select; the sketch's parents must name SECTION_PLANE."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if SECTION_PLANE not in parents:
        raise RuntimeError(f"{sketch} is not on {SECTION_PLANE}: parents {parents}")


async def _relief_reference(adapter) -> list[tuple[str, str]]:
    """The relief's depth-wise walls and height in section A-A.

    On SECTION_PLANE, sketch (u, v) = model (-Z, Y), construction only and
    hidden.  The relief is cut from a Top-plane profile whose stations across
    the depth project edge-on in the section, and its cut depth is a vector
    that ends in air.  A shown reference sketch prints, so its chords lie only
    on the section's own edges, never across the open mouth: a _STUB up the
    body's front face from its foot (the depth datum; the origin, the neck's
    front face, lies inside the near wall here), its foot from the origin;
    the near wall from its foot to the roof, its foot ReliefZ0 from the front
    face's foot; and the far wall, whose foot is ReliefZ1 from the same foot
    (a baseline, not chained from the near wall) and whose height is the
    printed ReliefHeight (the section draws the far wall on its right, outside
    the stations under it).  3 x 4 DOF less the three feet's level, the three
    chords vertical (6) and 6 dims = 0.
    """
    feature = "ReliefReference"
    z0, z1 = RELIEF_Z0, RELIEF_Z1
    check(f"create sketch {feature}", await adapter.create_sketch(SECTION_PLANE))
    front = await _construction_chord(
        adapter, feature, (_DATUM_U, 0.0), (_DATUM_U, _STUB)
    )
    await anchor_point_to_origin(
        adapter, f"{front}.start", _DATUM_U, 0.0, f"{feature} front face foot"
    )
    check(feature, await adapter.add_sketch_constraint(front, None, "vertical"))
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{front}.end",
        "vertical_distance",
        _STUB,
        f"{feature} front stub",
    )
    near = await _construction_chord(adapter, feature, (-z0, 0.0), (-z0, RELIEF_HEIGHT))
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{near}.start", f"{front}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{near}.start",
        "horizontal_distance",
        depth_station(z0),
        f"{feature} near wall from the front face",
    )
    check(feature, await adapter.add_sketch_constraint(near, None, "vertical"))
    await dimension_between(
        adapter,
        f"{near}.start",
        f"{near}.end",
        "vertical_distance",
        RELIEF_HEIGHT,
        f"{feature} height",
    )
    far = await _construction_chord(adapter, feature, (-z1, 0.0), (-z1, RELIEF_HEIGHT))
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{far}.start", f"{front}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{far}.start",
        "horizontal_distance",
        depth_station(z1),
        f"{feature} far wall from the front face",
    )
    check(feature, await adapter.add_sketch_constraint(far, None, "vertical"))
    await dimension_between(
        adapter,
        f"{far}.start",
        f"{far}.end",
        "vertical_distance",
        RELIEF_HEIGHT,
        f"{feature} far wall",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    _require_on_section_plane(adapter, feature)
    # The stub's length is fixed: nothing in the part sets it.
    front_face, _, z0_name, near_wall, z1_name, height = name_dimensions(
        adapter,
        feature,
        [
            "ReliefFrontFace",
            "ReliefFrontStub",
            "ReliefZ0",
            "ReliefNearWall",
            "ReliefZ1",
            "ReliefHeight",
        ],
    )
    return [
        (front_face, '"NeckFrontZ"'),
        (z0_name, '"ReliefFrontZ"'),
        (near_wall, '"ReliefHeight"'),
        (z1_name, '"ReliefBackZ"'),
        (height, '"ReliefHeight"'),
    ]


async def _pivot_reference(adapter) -> list[tuple[str, str]]:
    """The pivot bore's depth-wise station and top chamfer, in section A-A.

    On SECTION_PLANE, sketch (u, v) = model (-Z, Y), construction only and
    hidden.  The bore's own Top-plane station projects edge-on in the section.
    A shown reference sketch prints, so no chord crosses the bore's open
    mouth: a _STUB chord down the body's front face (the depth datum) from its
    top edge, another down the bore axis (the section's centreline) from the
    top face, PivotZ between their tops; and the chamfer's face on the bore's
    FAR side, from its rim on the top face to its foot on the bore wall, whose
    run is the printed chamfer size (its extension lines rise from the
    chamfer's own vertices, clear of PivotZ's span).  3 x 4 DOF less: both
    stubs vertical, the axis top and the rim level with the front top (4); and
    8 dims (the front top's two from the origin, two stub lengths, PivotZ, the
    foot's offset from the axis, run, drop) = 0.
    """
    feature = "PivotReference"
    radius = PIVOT_BORE_DIA / 2.0
    chamfer = PIVOT_BORE_TOP_CHAMFER
    top = BLOCK_HEIGHT
    check(f"create sketch {feature}", await adapter.create_sketch(SECTION_PLANE))
    front = await _construction_chord(
        adapter, feature, (_DATUM_U, top), (_DATUM_U, top - _STUB)
    )
    await anchor_point_to_origin(
        adapter, f"{front}.start", _DATUM_U, top, f"{feature} front face top edge"
    )
    check(feature, await adapter.add_sketch_constraint(front, None, "vertical"))
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{front}.end",
        "vertical_distance",
        _STUB,
        f"{feature} front stub",
    )
    axis = await _construction_chord(
        adapter, feature, (-_Z_MID, top), (-_Z_MID, top - _STUB)
    )
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{axis}.start", f"{front}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{front}.start",
        f"{axis}.start",
        "horizontal_distance",
        depth_station(_Z_MID),
        f"{feature} bore axis from the front face",
    )
    check(feature, await adapter.add_sketch_constraint(axis, None, "vertical"))
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "vertical_distance",
        _STUB,
        f"{feature} axis stub",
    )
    leg = await _construction_chord(
        adapter,
        feature,
        (-(_Z_MID + radius + chamfer), top),
        (-(_Z_MID + radius), top - chamfer),
    )
    check(
        feature,
        await adapter.add_sketch_constraint(
            f"{leg}.start", f"{front}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{leg}.end",
        f"{axis}.start",
        "horizontal_distance",
        radius,
        f"{feature} chamfer foot on the bore wall",
    )
    await dimension_between(
        adapter,
        f"{leg}.start",
        f"{leg}.end",
        "horizontal_distance",
        chamfer,
        f"{feature} chamfer run",
    )
    await dimension_between(
        adapter,
        f"{leg}.start",
        f"{leg}.end",
        "vertical_distance",
        chamfer,
        f"{feature} chamfer drop",
    )
    await ensure_fully_defined(adapter, feature)
    check(f"exit sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    _require_on_section_plane(adapter, feature)
    # The stubs' lengths are fixed: nothing in the part sets them.
    front_face, station, _, pivot_z, _, bore_r, run, drop = name_dimensions(
        adapter,
        feature,
        [
            "PivotFrontFace",
            "PivotStation",
            "PivotFrontStub",
            "PivotZ",
            "PivotAxisStub",
            "PivotChamferBoreR",
            "PivotChamferSize",
            "PivotChamferDrop",
        ],
    )
    return [
        (front_face, '"NeckFrontZ"'),
        (station, '"BlockHeight"'),
        (pivot_z, '"BlockDepth" / 2'),
        (bore_r, '"PivotBoreDia" / 2'),
        (run, '"PivotChamfer"'),
        (drop, '"PivotChamfer"'),
    ]


# (feature, dimension, the limit the model carries, its native band,
# swTolType_e, the word it prints): the pivot bore's chamfer has a floor, the
# V's apex rounds a ceiling.
_SINGLE_LIMITS = (
    (
        "PivotReference",
        "PivotChamferSize",
        PIVOT_BORE_TOP_CHAMFER,
        PIVOT_CHAMFER_BAND,
        PIVOT_CHAMFER_TOL_TYPE,
        "MIN",
    ),
    (
        "VApexFillets",
        "VApexFilletR",
        V_APEX_FILLET_R,
        V_APEX_FILLET_BAND,
        V_APEX_FILLET_TOL_TYPE,
        "MAX",
    ),
)


def _single_limits(adapter) -> None:
    """Each ``_SINGLE_LIMITS`` dimension as a single limit carrying its band's
    deviations (build_pn_pen_rod._shoulder_fillet_max_limit's recipe): the
    native type prints the nominal, so the nominal is the limit."""
    for (
        feature_name,
        dimension_name,
        limit,
        limit_band,
        tol_type,
        word,
    ) in _SINGLE_LIMITS:
        lower, upper = deviations(limit_band)
        _, dimension = _named_dimension(adapter, feature_name, dimension_name)
        label = f"{dimension_name}@{feature_name}"
        value = float(dimension.SystemValue)
        if not math.isclose(value, limit / 1000.0, abs_tol=1e-9):
            raise RuntimeError(
                f"{label}: nominal {value * 1000.0:.7f} is not the band's "
                f"{word.lower()} {limit}"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = tol_type
        if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
            raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
        if (
            int(tolerance.Type) != tol_type
            or not math.isclose(
                float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
            )
            or not math.isclose(
                float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
            )
        ):
            raise RuntimeError(f"{label}: {word}-limit tolerance readback changed")
        _telemetry.success(f"{label}: single limit {limit:g} {word}")


def _author_reference_dimensions(adapter) -> None:
    """Show each driven dimension as a reference: no tolerance, "(.20)"
    (build_ms_stop_block._author_plate_location_references' recipe)."""
    for feature_name, dimension_name in REFERENCE_DIMENSIONS:
        display, dimension = _named_dimension(adapter, feature_name, dimension_name)
        label = f"{dimension_name}@{feature_name}"
        if int(dimension.DrivenState) != 1:
            raise RuntimeError(f"{label}: a reference dimension must be driven")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 0  # swTolType_e.swTolNONE; property put, no success retval
        # The native prefix/suffix channel around the live model value, not
        # ShowParenthesis (which brackets above-line text).
        display.SetText(1, "(")
        display.SetText(2, ")")
        if (
            int(tolerance.Type) != 0
            or (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
            != ("(", ")")
            or not bool(display.ShowDimensionValue)
        ):
            raise RuntimeError(f"{label}: reference display did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 36 = 36 in).
    for name, value in (
        ("BlockLength", BLOCK_LENGTH),
        ("BlockHeight", BLOCK_HEIGHT),
        # Stations across the depth from the body's front face (the datum).
        ("BlockDepth", BODY_DEPTH),
        ("NeckFrontZ", depth_station(0.0)),
        ("NeckBackZ", depth_station(NECK_DEPTH)),
        ("VMouthFrontZ", depth_station(V_MOUTH_Z0)),
        ("VMouthBackZ", depth_station(V_MOUTH_Z1)),
        ("VFlatWidth", V_FLAT_WIDTH),
        ("ReliefX0", RELIEF_X0),
        ("ReliefFrontZ", depth_station(RELIEF_Z0)),
        ("ReliefBackZ", depth_station(RELIEF_Z1)),
        ("ReliefHeight", RELIEF_HEIGHT),
        ("ReliefCornerR", RELIEF_CORNER_R),
        ("PivotBoreX", PIVOT_BORE_X),
        ("PivotBoreDia", PIVOT_BORE_DIA),
        ("PivotChamfer", PIVOT_BORE_TOP_CHAMFER),
        ("VApexFilletR", V_APEX_FILLET_R),
        ("SetScrewY", SET_SCREW_Y),
    ):
        await set_global(adapter, name, f"{value}mm")
    # Both flanks' angle to the bottom face drives its sketch (degrees, not mm).
    await set_global(adapter, "VFlankAngle", f"{V_FLANK_ANGLE_DEG}deg")

    # Each sketch records its dim names + drive equations in emission order;
    # the equations are applied in one deferred batch once the model exists.
    drive_jobs: list[tuple[str, str]] = []

    # 1. The plan outline, neck and body, extruded +Y (the Top plane's normal)
    # by the height.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Top"))
    await _outline(adapter, outline)
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "OutlineProfile")
    drive_jobs += outline.apply(adapter, "OutlineProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    drive_jobs += [(name_dimensions(adapter, "Block", ["Height"])[0], '"BlockHeight"')]
    volume = await volume_check(adapter, "block", V_BLOCK, 0.001 * V_BLOCK)

    # 2. The grip's V-groove, cut +X (the Right plane's normal) from the paper
    # end face one corner radius past the relief's start, so the step face
    # never ends in a sliver under a flank (review final2's mouth triangles).
    groove = SketchDims()
    check("create_sketch V-groove", await adapter.create_sketch("Right"))
    await _v_groove(adapter, groove)
    await ensure_fully_defined(adapter, "V-groove sketch")
    check("exit_sketch V-groove", await adapter.exit_sketch())
    name_last_feature(adapter, "VGrooveProfile")
    drive_jobs += groove.apply(adapter, "VGrooveProfile")
    check(
        "cut V-groove",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=V_CUT_LENGTH)),
    )
    name_last_feature(adapter, "VGroove")
    drive_jobs += [
        (
            name_dimensions(adapter, "VGroove", ["VLength"])[0],
            '"ReliefX0" + "ReliefCornerR"',
        )
    ]
    volume = await volume_check(adapter, "V-groove", volume - V_GROOVE, 0.01 * V_GROOVE)

    # 2b. The rounds where the apex flat meets the flanks, at the radius the
    # print allows (R MAX): each edge picked mid-neck on its flat end, the
    # only edge through that point.  They add ~0.1 mm^3, under the mass
    # properties' resolution: the check proves the round ate nothing else.
    check(
        "fillet V apex flat corners",
        await adapter.add_fillet(
            V_APEX_FILLET_R,
            [
                [RELIEF_X0 / 2.0, V_FLAT_Y, _Z_MID - V_FLAT_WIDTH / 2.0],
                [RELIEF_X0 / 2.0, V_FLAT_Y, _Z_MID + V_FLAT_WIDTH / 2.0],
            ],
        ),
    )
    name_last_feature(adapter, "VApexFillets")
    fillet_dim = name_dimensions(adapter, "VApexFillets", ["VApexFilletR"])
    drive_jobs += [(fillet_dim[0], '"VApexFilletR"')]
    volume = await volume_check(
        adapter, "V apex fillets", volume + V_APEX_FILLETS, 0.01 * V_GROOVE
    )

    # 3. The body's relief slot, cut +Y (the Top plane's normal) up to its roof.
    # Sketch (u, v) = model (X, -Z).  Drawn counter-clockwise (add_arc runs
    # counter-clockwise start -> end) from the back wall's tangent point: back
    # wall to the free end, the free end, the front wall back to the step,
    # then the step between the two end-mill corner arcs, whose centres stand
    # one radius into the slot.  Exact-coordinate endpoints merge in the
    # sketch DB (inference off).  The front-face corner's radius is the one
    # the sheet prints ("2X"); the back one is driven by the same global.  The
    # walls' unprinted stations run from the origin (the neck's front face);
    # the print's, from the body's front face, are ReliefReference's.
    relief = SketchDims()
    check("create_sketch relief", await adapter.create_sketch("Top"))
    z0, z1 = RELIEF_Z0, RELIEF_Z1
    corner_r = RELIEF_CORNER_R
    x1 = RELIEF_X0 + corner_r
    set_sketch_direct_db(adapter, True)
    back = check("relief back wall", await adapter.add_line(x1, -z1, BLOCK_LENGTH, -z1))
    free_end = check(
        "relief free end",
        await adapter.add_line(BLOCK_LENGTH, -z1, BLOCK_LENGTH, -z0),
    )
    front = check(
        "relief front wall", await adapter.add_line(BLOCK_LENGTH, -z0, x1, -z0)
    )
    front_corner = check(
        "relief front corner",
        await adapter.add_arc(
            x1, -(z0 + corner_r), x1, -z0, RELIEF_X0, -(z0 + corner_r)
        ),
    )
    step = check(
        "relief step",
        await adapter.add_line(
            RELIEF_X0, -(z0 + corner_r), RELIEF_X0, -(z1 - corner_r)
        ),
    )
    back_corner = check(
        "relief back corner",
        await adapter.add_arc(
            x1, -(z1 - corner_r), RELIEF_X0, -(z1 - corner_r), x1, -z1
        ),
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("relief back wall horizontal", back, None, "horizontal"),
        ("relief front wall horizontal", front, None, "horizontal"),
        ("relief free end vertical", free_end, None, "vertical"),
        ("relief step vertical", step, None, "vertical"),
        ("relief front corner tangent wall", front_corner, front, "tangent"),
        ("relief front corner tangent step", front_corner, step, "tangent"),
        ("relief back corner tangent step", back_corner, step, "tangent"),
        ("relief back corner tangent wall", back_corner, back, "tangent"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    await dimension_between(
        adapter,
        f"{step}.start",
        f"{free_end}.start",
        "horizontal_distance",
        BLOCK_LENGTH - RELIEF_X0,
        "relief length",
    )
    relief.record("ReliefLength", '"BlockLength" - "ReliefX0"')
    await dimension_between(
        adapter,
        f"{back}.start",
        "origin",
        "vertical_distance",
        z1,
        "relief back wall from the origin",
    )
    relief.record("ReliefZ1", '"ReliefBackZ" - "NeckFrontZ"')
    # The station runs from the paper end to the step's far (z 16) end, so
    # its extension line leaves the step's own edge, not the corner arc.
    await dimension_between(
        adapter,
        f"{step}.end",
        "origin",
        "horizontal_distance",
        RELIEF_X0,
        "relief start station",
    )
    relief.record("ReliefX0", '"ReliefX0"')
    await dimension_between(
        adapter,
        f"{front}.start",
        "origin",
        "vertical_distance",
        z0,
        "relief front wall from the origin",
    )
    relief.record("ReliefZ0", '"ReliefFrontZ" - "NeckFrontZ"')
    for name, arc in (
        ("ReliefCornerR", front_corner),
        ("OtherReliefCornerR", back_corner),
    ):
        check(
            f"{name} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", corner_r),
        )
        relief.record(name, '"ReliefCornerR"')
    await ensure_fully_defined(adapter, "relief sketch")
    check("exit_sketch relief", await adapter.exit_sketch())
    name_last_feature(adapter, "ReliefProfile")
    drive_jobs += relief.apply(adapter, "ReliefProfile")
    check(
        "cut relief",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=RELIEF_HEIGHT)),
    )
    name_last_feature(adapter, "Relief")
    drive_jobs += [
        (name_dimensions(adapter, "Relief", ["ReliefHeight"])[0], '"ReliefHeight"')
    ]
    volume = await volume_check(
        adapter, "relief slot", volume - V_RELIEF, 0.01 * V_RELIEF
    )

    # 4. The rod's reamed pivot bore: a Top-plane circle cut mid-plane through
    # everything; below the roof it crosses only the relief's void.
    pivot = SketchDims()
    check("create_sketch pivot bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        PIVOT_BORE_X,
        -_Z_MID,
        PIVOT_BORE_DIA / 2.0,
        "pivot bore",
        dims=pivot,
        names=("PivotX", "PivotZ", "PivotDia"),
        drives=('"PivotBoreX"', '"BlockDepth" / 2 - "NeckFrontZ"', '"PivotBoreDia"'),
    )
    await ensure_fully_defined(adapter, "pivot bore sketch")
    check("exit_sketch pivot bore", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotBoreProfile")
    drive_jobs += pivot.apply(adapter, "PivotBoreProfile")
    check(
        "cut pivot bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotBore")
    volume = await volume_check(
        adapter, "pivot bore", volume - V_PIVOT_BORE, 0.01 * V_PIVOT_BORE
    )

    # 4b. The bore's top-edge chamfer, where the rod's square shoulder seats:
    # it clears the rod's shoulder-root fillet.  Picked on the bore's top
    # circular edge at +X, the only edge through that point.
    check(
        "chamfer pivot bore top edge",
        await adapter.add_chamfer(
            PIVOT_BORE_TOP_CHAMFER,
            [[PIVOT_BORE_X + PIVOT_BORE_DIA / 2.0, BLOCK_HEIGHT, _Z_MID]],
        ),
    )
    name_last_feature(adapter, "PivotBoreChamfer")
    chamfer_dims = name_dimensions(
        adapter, "PivotBoreChamfer", ["PivotChamferDistance", "PivotChamferAngle"]
    )
    drive_jobs.append((chamfer_dims[0], '"PivotChamfer"'))
    volume = await volume_check(
        adapter,
        "pivot-bore chamfer",
        volume - V_PIVOT_CHAMFER,
        0.1 * V_PIVOT_CHAMFER + 0.05,
    )

    # 5. The rod set-screw tap: the body's front face (outward normal -Z) up
    # to the pivot bore it locks the rod's pivot in.  Placement sketch on that
    # face, z BODY_Z0.
    tap = wizard_holes(
        adapter,
        SET_SCREW_TAP_SPEC,
        [[PIVOT_BORE_X, SET_SCREW_Y, BODY_Z0]],
        (0.0, 0.0, -1.0),
        f"rod set-screw tap ({SET_SCREW_TAP_SPEC.size} into the pivot bore)",
        name="SetScrewHole",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[(("SetScrewX", '"PivotBoreX"'), ("SetScrewY", '"SetScrewY"'))],
    )
    drive_jobs += tap.placement_drive_jobs
    await volume_check(
        adapter, "set-screw tap", volume - V_SET_SCREW_TAP, 0.03 * V_SET_SCREW_TAP
    )

    # 6. The hidden depth-wise references the sheet prints (no solid change).
    await _section_plane(adapter)
    drive_jobs += await _relief_reference(adapter)
    drive_jobs += await _pivot_reference(adapter)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pen v-block (equations neutral)", V_TOTAL, 0.002 * V_TOTAL
    )

    # Bright brass in every photo: no colour override, the material appearance
    # is the finish.
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: the pivot band, the authored places, and
    # exactly the print's dimensions marked (the drawing must find every one).
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band), display_unit=UNIT
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _single_limits(adapter)
    _author_reference_dimensions(adapter)
    for (feature_name, dimension_name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Saved hidden: the drawing shows them per view (_drawing_hidden_sketches).
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
