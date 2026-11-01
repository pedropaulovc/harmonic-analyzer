r"""Create the curated machinist drawing for the summing lever.

The SLDPRT remains authoritative.  This recipe supplies only the summing-lever
views, dimension layout, hole callouts, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

A large green cast-iron first-class lever hung on hex knife-edge trunnions (no
bore): a coefficients plate on the +X arm carrying the 20 channel-spring anchor
taps, a solid pivot cylinder (6.00 long, along Z), and a summation arm
reaching to the tapped counter-spring anchor boss on the -X arm.  Both spring
anchors are purchased eyebolts that thread straight into those taps, so the
print controls thread identity and position, never a seat bore. Sheet 1
shows the 1:2 end profile and top plan and a 1:4 shaded isometric.
Sheet 2 shows VIEW F at 1:1, a complete 10:1 knife detail D cut from that
view, and a shaded underside isometric. VIEW F carries the blind bracket
receivers, the uniform coefficient plate's visible free-end thickness and
the receiver row's centreline below the unchanged hex centre.
The ordinary views and native receiver drill/thread-depth callout retain
the manufacturing definition without auxiliary sections.  The sheet prints
decimal inch (the part's ``drawing_unit: in``); the model keeps its
millimetre nominals.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_summing_lever.py sm-summing-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Callable, Iterable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_basic_dimension,
    set_dimension_callouts,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_dimensions,
    part_sketches_shown,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_precision import set_dimension_display_precision
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import dimension_segments, set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _part_properties import part_drawing_unit
from _printed_tolerance import printed_band_mm
from _named_views import octant_view_name
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from magnifying_bracket_joint_layout import (
    DRILL_DEPTH,
    DRILL_DEPTH_BAND,
    LEVER_HOLE_POINTS,
    RECEIVER_HOLE_PLACES,
    RECEIVER_ROW_Y,
    TAP_DRILL_DIA,
    THREAD_DEPTH,
)
from sm_summing_lever_notes import (
    BACK_VIEW_LETTER,
    BASIC_PLACES,
    BOSS_Z_CALLOUT,
    BRACKET_TAP_CALLOUT_PROCESS,
    BRACKET_TAP_PRECISION,
    COUNTER_TAP_PRECISION,
    CYLINDER_REFERENCE_Z,
    DIMENSION_CALLOUTS_ABOVE,
    DIMENSION_CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    FRONT_VIEW_LETTER,
    SPRING_TAP_CALLOUT_PROCESS,
    SPRING_TAP_PRECISION,
    RECEIVER_ISOMETRIC_OCTANT,
)
from sm_summing_lever_spec import (
    ANCHOR_H,
    ANCHOR_R,
    CHANNEL_PITCH,
    COEFFICIENT_BOTTOM_Y,
    COEFFICIENT_T,
    COEFFICIENT_TOP_Y,
    COUNTER_HOLE_SPEC,
    COUNTER_WEB_T,
    DRAWING_PRECISION,
    GEOMETRIC_TOLERANCES_IN,
    HEX_DEPTH,
    HEX_H,
    HOLE_COUNT,
    HOLE_END_OFFSET_LAST,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_FIRST,
    HOLE_Z_LAST,
    KNIFE_RIDGE_R,
    KNIFE_RIDGE_R_TOL_TYPE,
    KNIFE_RIDGE_TANGENT_XY,
    PLATE_L,
    PLATE_W,
    RIB_REACH,
    RIDGE_ANGLE_DEG,
    SURFACE_FINISHES,
    TIP_X,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
# Tap-drill diameter of the boss's counter-anchor tap; the rim points below
# pick its circular edge, and the native callout prints the thread itself.
COUNTER_R = blind_cut_dia_mm(COUNTER_HOLE_SPEC) / 2.0

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front (down -Z) and top (down -Y) share the same X extent: anchor eye
# (TIP_X - ANCHOR_R) on the left to the plate right edge (PLATE_W).
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FRONT_CENTER = (0.225, 0.235)
TOP_CENTER = (0.225, 0.130)  # aligned plan below the front profile
ISO_CENTER = (0.350, 0.225)
# R7's receiver callout entered the title block (top Y66 mm), while its
# left-hand stations entered D. Translate the complete 1:1 field +35/+50 mm:
# the native view outline becomes X264.3..405.7, Y129.2..170.8 mm.
BACK_CENTER = (0.335, 0.150)
SHEET_NAMES = ("Lever Geometry", "Bracket Receiver")

# One complete 10:1 knife detail in sheet 2's open left field. A 6 mm model
# fence holds the entire envelope and ridge round without the pivot rib.
# It is cut from VIEW F so no extra parent view or cross-sheet move is needed.
DETAIL_LETTER = "D"
DETAIL_CENTER = (0.115, 0.150)
DETAIL_SCALE = (10.0, 1.0)
DETAIL_RADIUS_MM = 6.0
DETAIL_LABEL_XY = (0.115, 0.071)
# R11's left-facing D shoulder crossed ReceiverX0 at (365,180) mm.
# Target (400,170), right of its text and below its Y173 mm underline,
# keeping the shoulder-to-circle route below that dimension.
# SetLabelPosition leaves the source circle and datum A unchanged.
DETAIL_LETTER_OFFSET = (0.085, 0.020)
KNIFE_SKETCHES = ("KnifeEnvelopeReference",)
_COSMETIC_THREAD_ANNOTATION = 1  # swAnnotationType_e.swCosmeticThread

# Match the builder's native nominal checks (1e-6 mm), not manufacturing
# deviations or settled-state equality. Equation-driven SI readbacks need not
# equal the requested decimal after SolidWorks' document-unit round trip.
_NATIVE_NOMINAL_TOL_M = 1e-9

# The receiver stations come from the builder's hidden coordinate sketch,
# outside the marked-dimension contract. One native 3X rib-thickness dimension
# sizes both end ribs and the middle rib.
DIMENSIONS_BY_FEATURE: dict[str, set[str]] = {
    **DRAWING_DIMENSIONS,
    "ReceiverCoordinates": {"ReceiverX0", "ReceiverX1", "ReceiverY0"},
}


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the top plan view (1:2)."""
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] + mz * _S / 1000.0,
    )


def _end_face_edge(edges: ViewEdges, *, x_mm: float) -> ViewEdge:
    """The one visible line of the +Z end face crossing model ``x_mm``.

    The plan shows the common positive rib's outer top edge up to its
    tangent blend into the coefficient plate. Beyond the blend the actual
    plate-top edge is visible. Inboard flange and underside edges cannot
    substitute for this outer end face.
    """
    z_mm = PLATE_L / 2.0
    matches = [
        item
        for item in edges.lines
        if all(abs(point[2] - z_mm) < 1e-6 and point[1] > -1e-6 for point in item.line)
        and min(point[0] for point in item.line) - 1e-6 <= x_mm
        and x_mm <= max(point[0] for point in item.line) + 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"summing lever +Z end face: expected one visible line at z={z_mm:g} "
            f"spanning x={x_mm:g} in the {edges.label!r} scan, found "
            f"{[item.line for item in matches]}"
        )
    return matches[0]


def _boss_face_location_check(adapter: Any, front: Any) -> Callable[[], None]:
    """Locate the boss from two actual Y faces, not the plate midplane.

    The +Y boss rim is edge-on in VIEW G; its native circle still identifies
    the real end face Y=ANCHOR_H/2. The other pick is the coefficient top's
    straight +Z end edge, beyond the rib reach, at Y=COEFFICIENT_TOP_Y.
    The builder independently proves the counterweb's actual top is flush
    with that plate top. Together with the imported boss height and web
    thickness, this closes the face graph without a construction datum.
    """
    label = "boss upper face above coefficient top"
    edges = scan_view_edges(front, label="VIEW G face locations")
    boss = edges.circle_at(
        (TIP_X, ANCHOR_H / 2.0, 0.0), ANCHOR_R,
        axis=(0.0, 1.0, 0.0), label="boss upper-face rim",
    )
    plate_point = (
        (RIB_REACH + PLATE_W) / 2.0, COEFFICIENT_TOP_Y, PLATE_L / 2.0,
    )
    plate = edges.exact_line_through(plate_point, label="coefficient top end edge")
    points_mm = (
        (TIP_X, ANCHOR_H / 2.0, ANCHOR_R),
        plate_point,
    )
    expected_mm = ANCHOR_H / 2.0 - COEFFICIENT_TOP_Y
    if expected_mm <= 0.0 or not math.isclose(
        COUNTER_WEB_T / 2.0, COEFFICIENT_TOP_Y, abs_tol=1e-9,
    ):
        raise RuntimeError(f"{label}: source face graph is not upper/flush")

    def project_faces() -> list[tuple[float, float]]:
        points = model_points_in_view(
            adapter, front,
            [tuple(value / 1000.0 for value in point) for point in points_mm],
            label=label,
        )
        scale = tuple(_early_bound(front, "IView").ScaleRatio)
        if len(scale) != 2 or any(
            type(value) not in (int, float) or not math.isfinite(value) or value <= 0.0
            for value in scale
        ):
            raise RuntimeError(f"{label}: invalid native view scale {scale!r}")
        projected_rise = points[0][1] - points[1][1]
        if not math.isclose(
            projected_rise, expected_mm / 1000.0 * scale[0] / scale[1],
            rel_tol=0.0, abs_tol=1e-8,
        ):
            raise RuntimeError(
                f"{label}: VIEW G does not project the actual boss top above the plate top"
            )
        return points

    boss_xy, plate_xy = project_faces()
    dimension = add_edge_dimension(
        adapter, front, p0=boss_xy, p1=plate_xy,
        text_xy=BOSS_FACE_LOCATION_XY, label=label, orientation="vertical",
        entities=(boss.edge, plate.edge),
    )

    def check_faces() -> None:
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        if drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
            raise RuntimeError(f"{label}: cannot activate its native owner sheet")
        project_faces()
        measured = assert_dimension_measures(
            adapter, dimension, expected_mm=expected_mm, label=label,
            entities=(boss.edge, plate.edge),
        )
        display = _early_bound(dimension, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        places = display.GetPrimaryPrecision2()
        if places == -2:  # swPrecisionFollowsDocumentSetting
            extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
            # Same linear-document precision readback as draw_ch_pivot_bracket.
            places = extension.GetUserPreferenceInteger(24, 206)
        if places != 2 or tolerance.Type != 0:  # ordinary .XX, no explicit band
            raise RuntimeError(f"{label}: lost ordinary two-place title-block control")
        _telemetry.success(f"{label}: native face-attached {measured:.6f} mm at .XX")

    check_faces()
    return check_faces


def _theoretical_knife_vertex_in_view(
    adapter: Any, view: Any,
) -> tuple[Any, tuple[float, float, float]]:
    """Map the existing height.end used by Detail D's two ridge dimensions.

    The round removed the solid sharp. Do not substitute its crest, circle
    centre or a new drawing point for this native model-reference endpoint.
    """
    label = "theoretical knife vertex"
    view = _early_bound(view, "IView")
    model = view.ReferencedDocument
    if model is None:
        raise RuntimeError(f"{label}: VIEW F has no source part")
    raw = _early_bound(model, "IPartDoc").FeatureByName("KnifeEnvelopeReference")
    if raw is None:
        raise RuntimeError(f"{label}: missing native KnifeEnvelopeReference")
    sketch = _early_bound(_early_bound(raw, "IFeature").GetSpecificFeature2(), "ISketch")
    expected = (_metres((0.0, -HEX_H / 2.0, 0.0)), _metres((0.0, HEX_H / 2.0, 0.0)))
    matches = []
    for raw_segment in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw_segment, "ISketchSegment")
        if segment.GetType() != 0 or segment.ConstructionGeometry is not True:
            continue
        line = _early_bound(segment, "ISketchLine")
        points = (line.GetStartPoint2(), line.GetEndPoint2())
        if any(point is None for point in points):
            raise RuntimeError(f"{label}: native construction line has a null endpoint")
        bound = tuple(_early_bound(point, "ISketchPoint") for point in points)
        coordinates = tuple(tuple(float(getattr(point, axis)) for axis in "XYZ") for point in bound)
        if all(
            all(math.isfinite(value) for value in actual)
            and math.dist(actual, wanted) <= 1e-10
            for actual, wanted in zip(coordinates, expected)
        ):
            matches.append(bound[1])
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one native height.end, found {len(matches)}")
    vertex = matches[0]
    if adapter.swApp.IsSame(vertex.GetSketch(), sketch) != 1:
        raise RuntimeError(f"{label}: endpoint does not belong to its source sketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    local = tuple(float(getattr(vertex, axis)) for axis in "XYZ")
    point = _early_bound(utility.CreatePoint(double_array(local)), "IMathPoint")
    model_point = _early_bound(point.MultiplyTransform(inverse), "IMathPoint")
    xyz = tuple(float(value) for value in model_point.ArrayData)
    if (
        len(xyz) != 3 or not all(math.isfinite(value) for value in xyz)
        or math.dist(xyz, expected[1]) > 1e-10
    ):
        raise RuntimeError(f"{label}: source height.end is not the model-space sharp {xyz!r}")
    mapped = view.GetCorresponding(vertex)
    if mapped is None:
        raise RuntimeError(f"{label}: native height.end has no VIEW F correspondence")
    return _early_bound(mapped, "ISketchPoint"), xyz


@_telemetry.traced("drawing.knife_height_location")
def _knife_height_location_check(adapter: Any, back: Any) -> Callable[[], None]:
    """One ordinary native VIEW F location from the theoretical ridge to plate top."""
    _telemetry.annotate(dimensions=1, references=2)
    label = "coefficient top below theoretical knife vertex"
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(back, "IView")
    expected_mm = HEX_H / 2.0 - COEFFICIENT_TOP_Y
    plate_point = ((RIB_REACH + PLATE_W) / 2.0, COEFFICIENT_TOP_Y, -PLATE_L / 2.0)

    def references() -> tuple[Any, Any]:
        vertex, xyz = _theoretical_knife_vertex_in_view(adapter, view)
        plate = scan_view_edges(view, label=label).exact_line_through(
            plate_point, label="VIEW F coefficient top end edge",
        )
        projected = model_points_in_view(
            adapter, view, (xyz, _metres(plate_point)), label=label,
        )
        if tuple(view.ScaleRatio) != (1.0, 1.0) or not math.isclose(
            projected[0][1] - projected[1][1], expected_mm / 1000.0,
            rel_tol=0.0, abs_tol=1e-8,
        ):
            raise RuntimeError(f"{label}: VIEW F does not project the actual sharp above plate top")
        return vertex, plate.edge

    vertex, plate = references()
    if drawing.ActivateView(view_name(adapter, view)) is not True:
        raise RuntimeError(f"{label}: cannot activate VIEW F")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection = _early_bound(manager.CreateSelectData(), "ISelectData")
    selection.View = view
    try:
        for index, (entity, interface) in enumerate(((vertex, "ISketchPoint"), (plate, "IEntity"))):
            if (
                _early_bound(entity, interface).Select4(index > 0, selection) is not True
                or manager.GetSelectedObjectCount2(-1) != index + 1
            ):
                raise RuntimeError(f"{label}: native {interface} selection failed")
        raw_dimension = draw.AddVerticalDimension2(*KNIFE_HEIGHT_LOCATION_XY, 0.0)
    finally:
        draw.ClearSelection2(True)
    if raw_dimension is None:
        raise RuntimeError(f"{label}: native vertical dimension was not created")
    display = _early_bound(raw_dimension, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")

    def check_height() -> None:
        if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
            raise RuntimeError(f"{label}: cannot activate its native owner sheet")
        vertex, plate = references()
        measured = assert_dimension_measures(
            adapter, display, expected_mm=expected_mm, label=label,
            entities=(vertex, plate), entity_types=("SKETCHPOINT", "EDGE"),
        )
        count = view.GetAnnotationCount()
        owned = view.GetAnnotations()
        if (
            type(count) is not int or not isinstance(owned, (tuple, list)) or len(owned) != count
            or sum(adapter.swApp.IsSame(item, annotation) == 1 for item in owned) != 1
            or annotation.OwnerType != 0 or annotation.Visible != 1
            or adapter.swApp.IsSame(_early_bound(annotation.Owner, "IView"), view) != 1
        ):
            raise RuntimeError(f"{label}: native dimension is not visible and owned by VIEW F")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        places = display.GetPrimaryPrecision2()
        if places == -2:
            extension = _early_bound(draw.Extension, "IModelDocExtension")
            places = extension.GetUserPreferenceInteger(24, 206)
        if places != 2 or tolerance.Type != 0:
            raise RuntimeError(f"{label}: lost ordinary two-place title-block control")
        _telemetry.success(f"{label}: native sharp/face-attached {measured:.6f} mm at .XX")

    check_height()
    return check_height


def _knife_detail(adapter: Any, back: Any) -> Any:
    """The complete native 10:1 knife envelope and ridge-round detail."""
    return _detail_view(
        adapter,
        back,
        centre_mm=(0.0, 0.0, -PLATE_L / 2.0 - HEX_DEPTH),
        radius_m=DETAIL_RADIUS_MM / 1000.0,
        at_xy=DETAIL_CENTER,
        scale=DETAIL_SCALE,
        letter=DETAIL_LETTER,
        label_xy=DETAIL_LABEL_XY,
        letter_offset=DETAIL_LETTER_OFFSET,
        label="knife detail",
    )


def _detail_view(
    adapter: Any,
    parent_view: Any,
    *,
    centre_mm: tuple[float, float, float],
    radius_m: float,
    at_xy: tuple[float, float],
    scale: tuple[float, float],
    letter: str,
    label_xy: tuple[float, float],
    letter_offset: tuple[float, float],
    label: str,
) -> Any:
    """A native detail of ``parent_view``: its fence, ``radius_m`` on the
    sheet, round model point ``centre_mm``; the view centred on ``at_xy``,
    its label at ``label_xy``, the parent circle's letter ``letter_offset``
    from the fence centre, each position read back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError(f"failed to activate the {label}'s parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter, parent_view, _metres(centre_mm), label=f"{label} centre"
    )
    # The fence is drawn in sheet space on the parent.
    radius = radius_m
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    # Direct to the database: inferred, the centre snapped onto the
    # hexagon's left flat and the rim point onto its right flat (farm r4
    # 2026-10-16: a fence of radius HEX_W centred 3.8 model mm off the axis,
    # clipping the hexagon's right shoulders).
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError(f"failed to create the {label} fence")
    arc = _early_bound(fence, "ISketchArc")
    fence_centre = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    placed_centre = (float(fence_centre.X), float(fence_centre.Y))
    if (
        math.dist(placed_centre, points[0][:2]) > 1e-9
        or abs(float(arc.GetRadius()) - math.dist(points[0][:2], points[1][:2])) > 1e-9
    ):
        raise RuntimeError(
            f"{label} fence moved off its authored circle: {placed_centre}"
        )
    draw.ClearSelection2(True)
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection.CreateSelectData()
    selection_data.View = parent_view
    if not _early_bound(fence, "ISketchSegment").Select4(False, selection_data):
        raise RuntimeError(f"failed to select the {label} fence")
    if int(selection.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError(f"{label} fence is not the only selection")
    detail = drawing.CreateDetailViewAt4(
        *at_xy,
        0.0,
        2,  # swDetViewLEADER: a leader joins the letter to the fence
        *scale,
        letter,
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError(f"failed to create the {label}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in scale])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError(f"{label} has invalid bounds: {outline!r}")
    target = [
        position[axis] + at_xy[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to position the {label}")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label} label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*label_xy, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError(f"failed to position the {label} label")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one {label} circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    letter_xy = tuple(center[i] + letter_offset[i] for i in range(2))
    circle.SetLabelPosition(*letter_xy)  # VT_VOID: the read-back is the proof
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"{label} label position did not persist: {actual}")
    placed = tuple(float(value) for value in circle.GetLabelPosition())
    if len(placed) != 2 or math.dist(placed, letter_xy) > 1e-8:
        raise RuntimeError(f"{label} letter position did not persist: {placed}")
    return detail


def _attach_radial_leaders(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str], *, label: str
) -> None:
    """Stop each radial leader at its own arc.

    ``ArcExtensionLineOrOppositeSide`` defaults to True, which sweeps the
    R138.8 summation arc through the top view and trails the R15.24 rib leader
    across the front view; ``SolidLeader`` defaults to True on this template
    and rules the leader on to the arc centre, off the view for R138.8 (both
    seen on the 2026-10 summing-lever renders).  Both are bool properties, so
    each assignment is proven only by reading it back.
    """
    wanted = set(names)
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArcExtensionLineOrOppositeSide = False
        if bool(display.ArcExtensionLineOrOppositeSide):
            raise RuntimeError(f"{label}: {name} leader still rides the arc extension")
        display.SolidLeader = False
        if bool(display.SolidLeader):
            raise RuntimeError(f"{label}: {name} leader still runs to the arc centre")
        seen.add(name)
    missing = sorted(wanted - seen)
    if missing:
        raise RuntimeError(f"{label}: radial dimensions missing: {missing}")


def _shorten_radii(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str], *, label: str
) -> None:
    """Foreshorten each named radius: ``IDisplayDimension::ShortenedRadius``
    draws the jogged radius, its line stopping short of a centre beyond the
    view, so no bare line runs from the arc centre to the text (machinist
    review r8: the R138.85's line read as a loose line in the plan).  A bool
    put SolidWorks ignores still returns, so each flag is read back
    (draw_pd_latch_hook._shorten_radii)."""
    wanted = set(names)
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = True
        if not bool(display.ShortenedRadius):
            raise RuntimeError(f"{label}: {name} did not keep its shortened radius")
        seen.add(name)
    missing = sorted(wanted - seen)
    if missing:
        raise RuntimeError(f"{label}: radii to shorten missing: {missing}")


def _apply_callouts(adapter: Any, annotations: list[Any], *, label: str) -> None:
    """Write the notes module's callout text onto the dimensions this sheet
    kept, above or below the value."""
    present = {dimension_name(adapter, annotation) for annotation in annotations}
    for location, callouts in (
        ("above", DIMENSION_CALLOUTS_ABOVE),
        ("below", DIMENSION_CALLOUTS_BELOW),
    ):
        wanted = {name: text for name, text in callouts.items() if name in present}
        set_dimension_callouts(adapter, annotations, wanted, location=location)
    _telemetry.info(f"{label}: callouts on {sorted(present)}")


def _add_view_arrow(
    adapter: Any,
    top: Any,
    letter: str,
    arrow: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    """A letter arrow on the plan that names a removed view: square onto the
    end face it looks at."""
    text_xy, tip_xy = arrow
    label = f"view {letter} viewing arrow"
    note = add_leader_note(
        adapter,
        letter,
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=top,
        label=label,
    )
    # add_note leaves text at the document height; size the letter here and
    # prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {label} letter")
    rebuild_drawing(adapter, label=f"{label} letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError(f"{label} tip moved when its letter was sized")
    # The leader leaves the letter's nearer side, whose x is the glyph's
    # width: slide the letter by any miss so the arrow stands square.
    miss = tip_xy[0] - points[0]
    if abs(miss) > VIEW_ARROW_SQUARE_TOL:
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x + miss, y, z):
            raise RuntimeError(f"failed to square the {label}")
        rebuild_drawing(adapter, label=f"square {label}")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if (
            len(points) < 6
            or math.dist((points[-3], points[-2]), tip_xy) > 0.001
            or abs(tip_xy[0] - points[0]) > VIEW_ARROW_SQUARE_TOL
        ):
            raise RuntimeError(f"{label} did not square: leader {points}")
    _telemetry.info(
        f"{label}: leader {points[0]:.5f},{points[1]:.5f} -> "
        f"{points[-3]:.5f},{points[-2]:.5f} (square when the x agree)"
    )


def _assert_knife_ridge_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove Detail D's KnifeRidgeRadius prints the part's R MAX: radial,
    measuring KNIFE_RIDGE_R, the native swTolMAX the part set
    (draw_ch_pivot_bracket._dress_corner_radius's readback)."""
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "KnifeRidgeRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one KnifeRidgeRadius in the ridge detail, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported knife-ridge radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != KNIFE_RIDGE_R_TOL_TYPE:
        raise RuntimeError(
            f"KnifeRidgeRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), KNIFE_RIDGE_R / 1000.0,
        rel_tol=0.0, abs_tol=_NATIVE_NOMINAL_TOL_M,
    ):
        raise RuntimeError("KnifeRidgeRadius does not measure the ridge round")
    _telemetry.info(f"knife ridge radius: text {display.GetText(1)!r}, MAX type")


# Datum A's box stands above the actual ridge round in Detail D.
RIDGE_DATUM_RISE = 0.001


def _ridge_datum(adapter: Any, detail: Any) -> Any:
    """Datum A on the knife-edge ridge itself, seen end-on in Detail D: the
    tag stands on the R.004 round's arc at the vertex. In the plan, A hung
    on the -Z ridge's tangent line down the stub's middle, which machinist
    review r9 read as a flat face, leaving no basic from A to the 20 holes;
    end-on it can only be the ridge line, the knife-edge pivot axis that the
    39.85 basic and the web arcs' "AXIS A" both name."""
    z_mm = -PLATE_L / 2.0 - HEX_DEPTH
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    centre_y = HEX_H / 2.0 - KNIFE_RIDGE_R / math.sin(half)
    edges = scan_view_edges(detail, label="knife detail datum")
    ridge_round = edges.circle_at(
        (0.0, centre_y, z_mm),
        KNIFE_RIDGE_R,
        axis=(0.0, 0.0, 1.0),
        label="-Z knife-edge ridge round",
    )
    crest, vertex = model_points_in_view(
        adapter,
        detail,
        [
            _metres((0.0, centre_y + KNIFE_RIDGE_R, z_mm)),
            _metres((0.0, HEX_H / 2.0, z_mm)),
        ],
        label="knife ridge datum",
        names=("crest", "vertex"),
    )
    return add_datum_feature(
        adapter,
        detail,
        edge_entity=ridge_round.edge,
        leader_attach_xy=crest,
        symbol_xy=(vertex[0], vertex[1] + RIDGE_DATUM_RISE),
        datum="A",
        label="knife-edge pivot axis",
        position_tolerance_m=0.003,
    )


# The plan's theoretical-sharp reference belongs to the -Z stub tagged A in
# Detail D. Its overrun extends 2 model mm past that stub's outboard face.
RIDGE_AXIS_OVERRUN_MM = 2.0


def _ridge_centerline(adapter: Any, top: Any) -> Any:
    """Theoretical-sharp centreline on datum A's -Z knife ridge in the plan.

    Both stubs share this nominal axis, but only the -Z ridge carries A.
    The round leaves no sharp edge; rule 16 dimensions to the sharp.
    """
    return _owned_centerline(
        adapter,
        top,
        tuple(
            (0.0, HEX_H / 2.0, z)
            for z in (
                -PLATE_L / 2.0,
                -PLATE_L / 2.0 - HEX_DEPTH - RIDGE_AXIS_OVERRUN_MM,
            )
        ),
        label="ridge centreline",
    )


def _owned_centerline(
    adapter: Any,
    view: Any,
    ends_mm: tuple[tuple[float, float, float], tuple[float, float, float]],
    *,
    label: str,
) -> Any:
    """A black centreline in ``view``'s sketch between two part-mm points.

    Its ends are model points projected to the sheet and taken into the
    view's sketch frame, placed direct to the database (an inferred end snaps
    onto nearby tangent lines 0.03 sheet mm away) and read back.
    Returns the ``ISketchSegment`` for a dimension to pick.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for its {label}")
    draw.ClearSelection2(True)
    ends = model_points_in_view(
        adapter,
        view,
        [_metres(point) for point in ends_mm],
        label=f"{label} end",
        names=("start", "end"),
    )
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in ends:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to create the {label}")
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
        placed = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        actual = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XYZ"]
        drift = max(abs(a - b) for a, b in zip(actual, expected))
        if drift > 1e-9:
            raise RuntimeError(
                f"{label} {accessor[3:-6].lower()} point sits "
                f"{drift * 1000.0:.4g} mm from where it was authored"
            )
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"{label} color did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"summing lever {label}")
    return segment


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


# Datum C's tag hangs below the coefficient top's extension line, right of the
# plate's free end in VIEW G: above it, the boss top's .28 witness runs 3.5 mm
# over the plate top; below, the field clears VIEW G's label.
PLATE_TOP_DATUM_OFFSET = (0.0105, -0.0035)


def _plate_top_datum(adapter: Any, front: Any) -> Any:
    """Datum C on the coefficient-plate top, edge-on in VIEW G: the face the 20
    spring taps run through clocks their pattern about A (machinist review
    e1d24c9: A|B left rotation about the knife-edge axis free)."""
    mid = ((RIB_REACH + PLATE_W) / 2.0, COEFFICIENT_TOP_Y, PLATE_L / 2.0)
    end = (PLATE_W, COEFFICIENT_TOP_Y, PLATE_L / 2.0)
    plate = scan_view_edges(front, label="VIEW G datum C").exact_line_through(
        mid, label="coefficient top end edge",
    )
    mid_xy, end_xy = model_points_in_view(
        adapter, front, (_metres(mid), _metres(end)), label="datum C",
    )
    outward = math.copysign(1.0, end_xy[0] - mid_xy[0])
    return add_datum_feature(
        adapter,
        front,
        edge_entity=plate.edge,
        symbol_xy=(
            end_xy[0] + outward * PLATE_TOP_DATUM_OFFSET[0],
            end_xy[1] + PLATE_TOP_DATUM_OFFSET[1],
        ),
        datum="C",
        label="coefficient-plate top face",
    )


def _set_witness_gap(display: Any, index: int, gap: float, *, label: str) -> None:
    """A local native gap, never a document-wide setting or a hidden witness."""
    if display.SetWitnessLineGap(index, False, gap) is not True:
        raise RuntimeError(f"{label}: native witness gap {index} was refused")
    ok, use_doc, actual = display.GetWitnessLineGap(index, False, 0.0)
    if (
        ok is not True or use_doc is not False
        or type(actual) not in (int, float) or not math.isfinite(actual)
        or not math.isclose(actual, gap, rel_tol=0.0, abs_tol=1e-8)
    ):
        raise RuntimeError(
            f"{label}: native witness gap {index} did not persist; "
            f"expected=(True, False, {gap!r}), actual={(ok, use_doc, actual)!r}"
        )


def _clear_plate_width_witnesses(
    adapter: Any, top: Any, annotations: list[Any],
) -> None:
    """Start width witnesses beyond the visible body end, not at middle Z.

    The dimension still owns its original model endpoints. Only the local
    blank part of each extension changes; both visible tails remain below
    the actual projected +Z end. No sheet-coordinate substitute for that end.
    """
    matches = [
        raw for raw in annotations
        if dimension_name(adapter, raw) == "PlateWidth"
    ]
    if len(matches) != 1:
        raise RuntimeError("expected one native PlateWidth in the top plan")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    middle, end, far_end = model_points_in_view(
        adapter, top,
        [
            _metres((0.0, COEFFICIENT_TOP_Y, 0.0)),
            _metres((0.0, COEFFICIENT_TOP_Y, PLATE_L / 2.0)),
            _metres((PLATE_W, COEFFICIENT_TOP_Y, PLATE_L / 2.0)),
        ],
        label="plate width witness origins",
        names=("middle", "end", "far end"),
    )
    if (
        not all(math.isfinite(value) for point in (middle, end, far_end) for value in point)
        or middle[1] <= end[1] or abs(end[1] - far_end[1]) > 1e-8
    ):
        raise RuntimeError(
            "PlateWidth: unexpected projected body-end direction; "
            f"middle_m={middle!r}, end_m={end!r}, far_end_m={far_end!r}"
        )
    gap = middle[1] - end[1] + 0.001
    for index in (0, 1):
        _set_witness_gap(display, index, gap, label="PlateWidth")
    rebuild_drawing(adapter, label="clear plan width witnesses")
    segments = dimension_segments(annotation)
    for point in (end, far_end):
        witnesses = [
            stroke for stroke in segments
            if all(abs(vertex[0] - point[0]) <= 1e-8 for vertex in stroke)
            and abs(stroke[1][1] - stroke[0][1]) > 1e-8
        ]
        if len(witnesses) != 1:
            raise RuntimeError(
                "PlateWidth: expected one visible witness at each width end; "
                f"expected_x_m={point[0]!r}, expected_high_m={point[1] - 0.001!r}, "
                f"matched_witnesses_m={witnesses!r}, native_segments_m={segments!r}"
            )
        low, high = sorted(vertex[1] for vertex in witnesses[0])
        if abs(high - (point[1] - 0.001)) > 1e-8 or high - low <= 0.0035:
            raise RuntimeError(
                "PlateWidth: witness did not start beyond its projected end; "
                f"projected_end_m={point!r}, expected_high_m={point[1] - 0.001!r}, "
                f"minimum_visible_length_m=0.0035, actual_low_high_m={(low, high)!r}, "
                f"native_segments_m={segments!r}"
            )


def _clear_ridge_witnesses(
    adapter: Any, detail: Any, annotations: list[Any],
) -> None:
    """Leave A's actual ridge attachment alone; start both witnesses above it."""
    vertex = model_point_in_view(
        adapter, detail,
        _metres((0.0, HEX_H / 2.0, -PLATE_L / 2.0 - HEX_DEPTH)),
        label="knife ridge witness origin",
    )
    wanted = {"RidgeFromLeft", "RidgeFromRight"}
    found = {}
    for raw in annotations:
        name = dimension_name(adapter, raw)
        if name not in wanted:
            continue
        if name in found:
            raise RuntimeError(f"knife detail: duplicate {name}")
        annotation = _early_bound(raw, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        # Both model dimensions start at height.end, the theoretical ridge
        # sharp, before their respective shoulder endpoint (not screen order).
        _set_witness_gap(display, 0, RIDGE_WITNESS_GAP, label=name)
        found[name] = annotation
    if found.keys() != wanted:
        raise RuntimeError("knife detail: missing ridge-to-side dimension")
    rebuild_drawing(adapter, label="clear ridge witnesses above datum A")
    for name, annotation in found.items():
        segments = dimension_segments(annotation)
        witnesses = [
            stroke for stroke in segments
            if all(abs(point[0] - vertex[0]) <= 1e-8 for point in stroke)
            and abs(stroke[1][1] - stroke[0][1]) > 1e-8
        ]
        if len(witnesses) != 1:
            raise RuntimeError(
                f"{name}: expected one visible ridge-side witness; "
                f"projected_vertex_m={vertex!r}, "
                f"expected_low_m={vertex[1] + RIDGE_WITNESS_GAP!r}, "
                f"matched_witnesses_m={witnesses!r}, native_segments_m={segments!r}"
            )
        low, high = sorted(point[1] for point in witnesses[0])
        if (
            abs(low - (vertex[1] + RIDGE_WITNESS_GAP)) > 1e-8
            or high - low <= 0.0035
        ):
            raise RuntimeError(
                f"{name}: native witness did not clear datum A; "
                f"projected_vertex_m={vertex!r}, "
                f"expected_low_m={vertex[1] + RIDGE_WITNESS_GAP!r}, "
                f"minimum_visible_length_m=0.0035, actual_low_high_m={(low, high)!r}, "
                f"native_segments_m={segments!r}"
            )


def _place_flank_text(adapter: Any, annotations: list[Any]) -> None:
    """Keep the model-owned exterior angle arc; move its whole block off it.

    Use the trammel-point recipe's native angular shelf pattern. Merely
    translating the two-row text on the arc leaves its qualifier struck.
    """
    name = "FlankToSide"
    matches = [raw for raw in annotations if dimension_name(adapter, raw) == name]
    if len(matches) != 1:
        raise RuntimeError("knife detail needs one native FlankToSide")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.OffsetText = False
    if display.OffsetText is not False:
        raise RuntimeError("FlankToSide: inherited text offset could not be reset")
    arc_xy = DETAIL_KEEP[name]
    if annotation.SetPosition2(*arc_xy, 0.0) is not True:
        raise RuntimeError("FlankToSide: native exterior arc placement was refused")
    position = annotation.GetPosition()
    if not position or math.dist(tuple(position[:2]), arc_xy) > 1e-5:
        raise RuntimeError("FlankToSide: native exterior arc placement did not persist")
    offset_dimension_text(adapter, [annotation], {name: FLANK_TEXT_XY})
    position = annotation.GetPosition()
    if (
        display.OffsetText is not True or not position
        or math.dist(tuple(position[:2]), FLANK_TEXT_XY) > 1e-5
    ):
        raise RuntimeError("FlankToSide: complete angular text did not stay on its shelf")


def _plate_thickness_check(
    adapter: Any, view: Any, annotations: list[Any],
) -> Callable[[], None]:
    """Preserve the imported free-end sketch thickness in VIEW F.

    The Front-plane slab profile authors this dimension on its X=PLATE_W
    vertical edge. Native witness origins, not a coincident seven-millimetre
    value, must still tie it to the visible top and bottom free-end edges.
    No synthetic witness move or value, tolerance, precision or gap edit.

    R6 captured two face-level witnesses plus a horizontal text leader joined
    to the split vertical dimension line. Classify those roles by projected
    face levels and connectivity, not the total horizontal stroke count.
    Any geometry refusal logs the complete small native rows and projection
    frame; diagnostic read failures never supply substitute geometry.
    """
    label = "VIEW F PlateThickness"
    slop = 1e-8
    matches = [
        raw for raw in annotations
        if dimension_name(adapter, raw) == "PlateThickness"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one imported thickness annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    view = _early_bound(view, "IView")

    def finite(value: Any) -> bool:
        return type(value) in (int, float) and math.isfinite(value)

    def same(first: Any, second: Any) -> bool:
        result = adapter.swApp.IsSame(first, second)
        return type(result) is int and result == 1

    def model_state() -> tuple[Any, Any, str, float, tuple[int, float, float]]:
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
            raise RuntimeError(f"{label}: could not activate its receiver sheet")
        count = view.GetAnnotationCount()
        owned = view.GetAnnotations()
        if (
            type(count) is not int or count < 1
            or not isinstance(owned, (tuple, list)) or len(owned) != count
        ):
            raise RuntimeError(f"{label}: invalid native view annotation inventory")
        kind, owner_type = annotation.GetType(), annotation.OwnerType
        if (
            type(kind) is not int or kind != 4
            or type(owner_type) is not int or owner_type != 0
            or annotation.IsDangling() is not False
            or sum(same(raw, annotation) for raw in owned) != 1
        ):
            raise RuntimeError(f"{label}: imported thickness is detached from its view")
        raw_display = annotation.GetSpecificAnnotation()
        if raw_display is None:
            raise RuntimeError(f"{label}: missing native display dimension")
        display = _early_bound(raw_display, "IDisplayDimension")
        raw_dimension = display.GetDimension2(0)
        if raw_dimension is None:
            raise RuntimeError(f"{label}: missing native model dimension")
        dimension = _early_bound(raw_dimension, "IDimension")
        name, value = dimension.FullName, dimension.SystemValue
        # FullName is Name@Feature@Model; the model title need not use SLDPRT.
        if (
            type(name) is not str
            or name.split("@")[:2] != ["PlateThickness", "PlateProfile"]
            or not finite(value)
            or not math.isclose(
                value, COEFFICIENT_T / 1000.0,
                rel_tol=0.0, abs_tol=_NATIVE_NOMINAL_TOL_M,
            )
        ):
            raise RuntimeError(
                f"{label}: wrong model identity or thickness; "
                f"FullName={name!r} ({type(name).__name__}), "
                "expected first two @ fields ['PlateThickness', 'PlateProfile']; "
                f"SystemValue={value!r} ({type(value).__name__}) m, "
                f"expected {COEFFICIENT_T / 1000.0!r} m "
                f"(abs_tol={_NATIVE_NOMINAL_TOL_M!r} m)"
            )
        raw_tolerance = dimension.Tolerance
        if raw_tolerance is None:
            raise RuntimeError(f"{label}: missing native model band")
        tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
        band = (tolerance.Type, tolerance.GetMinValue(), tolerance.GetMaxValue())
        if type(band[0]) is not int or not all(finite(v) for v in band[1:]):
            raise RuntimeError(
                f"{label}: invalid native model band for FullName={name!r}; "
                f"(Type, GetMinValue[m], GetMaxValue[m])={band!r}, "
                f"types={tuple(type(value).__name__ for value in band)!r}"
            )
        return display, dimension, name, value, band

    def geometry_failure(display: Any, failure: Exception, **context: Any) -> RuntimeError:
        """Capture independently: one unreadable row must not hide the others."""
        def observe(reader: Callable[[], Any]) -> Any:
            try:
                result = reader()
                return tuple(result) if isinstance(result, (list, tuple)) else result
            except Exception as exc:
                return {"error_type": type(exc).__name__, "error": str(exc)}

        def display_record(reader: Callable[[], Any]) -> dict[str, Any]:
            try:
                raw = reader()
                if raw is None:
                    return {"missing": True}
                data = _early_bound(raw, "IDisplayData")
            except Exception as exc:
                return {"error_type": type(exc).__name__, "error": str(exc)}
            record = {}
            for key, counter, getter in (
                ("lines", "GetLineCount", "GetLineAtIndex2"),
                ("arrows", "GetArrowHeadCount", "GetArrowHeadAtIndex2"),
                ("text_positions", "GetTextCount", "GetTextPositionAtIndex"),
            ):
                count = observe(lambda: getattr(data, counter)())
                entry = {"count": count, "rows": []}
                if type(count) is int and count >= 0:
                    # A single thickness callout has only a few rows. Bound a
                    # corrupt census without silently presenting it as complete.
                    entry["rows"] = [
                        observe(lambda index=index: getattr(data, getter)(index))
                        for index in range(min(count, 128))
                    ]
                    entry["omitted"] = max(0, count - 128)
                record[key] = entry
            return record

        def transform_data() -> Any:
            raw = view.ModelToViewTransform
            return None if raw is None else _early_bound(raw, "IMathTransform").ArrayData

        def model_record() -> dict[str, Any]:
            native = _early_bound(display.GetDimension2(0), "IDimension")
            record = {
                "FullName": observe(lambda: native.FullName),
                "SystemValue_m": observe(lambda: native.SystemValue),
            }
            tolerance = observe(lambda: _early_bound(native.Tolerance, "IDimensionTolerance"))
            if isinstance(tolerance, dict):
                record["tolerance"] = tolerance
            else:
                record["tolerance"] = {
                    "Type": observe(lambda: tolerance.Type),
                    "min_m": observe(lambda: tolerance.GetMinValue()),
                    "max_m": observe(lambda: tolerance.GetMaxValue()),
                }
            return record

        z_mm = -PLATE_L / 2.0
        model_points = {
            "bottom": _metres((PLATE_W, COEFFICIENT_BOTTOM_Y, z_mm)),
            "top": _metres((PLATE_W, COEFFICIENT_TOP_Y, z_mm)),
            "inboard": _metres((PLATE_W - 1.0, COEFFICIENT_BOTTOM_Y, z_mm)),
        }
        evidence = {
            "annotation_position_m": observe(lambda: annotation.GetPosition()),
            "requested_annotation_position_m": BACK_KEEP["PlateThickness"],
            "view_position_m": observe(lambda: view.Position),
            "model_to_view_transform": observe(transform_data),
            "native_model": observe(model_record),
            "native_gap_replies": [
                observe(lambda index=index: display.GetWitnessLineGap(index, False, 0.0))
                for index in (0, 1)
            ],
            # Keep both native providers distinct; neither substitutes for the
            # dimension display used by dimension_segments and the ink proof.
            "dimension_display": display_record(lambda: display.GetDisplayData()),
            "annotation_display": display_record(lambda: annotation.GetDisplayData()),
            "dimension_segments_m": observe(lambda: dimension_segments(annotation)),
            "expected_model_points_m": model_points,
            "expected_projected_points_m": {
                face: observe(lambda point=point, face=face: model_point_in_view(
                    adapter, view, point, label=f"{label} diagnostic {face}",
                ))
                for face, point in model_points.items()
            },
            "guard_requirements": {
                "coordinate_tolerance_m": slop,
                "top_minus_bottom_m": (0.0, COEFFICIENT_T / 1000.0),
                "inboard_minus_bottom_m": (0.001, 0.0),
                "witness_rule": "exactly one horizontal per projected bottom/top face",
                "gap_index_face_order": ("bottom", "top"),
                "origin_rule": "right_x = projected_free_end_x - effective_native_gap_m",
                "arrow_rule": "common x strictly inside both horizontal witnesses",
                "text_leader_rule": "horizontal endpoint joins the arrow-axis dimension line",
            },
            **context,
        }
        _telemetry.error(
            f"{label}: native geometry refusal", failure=str(failure), geometry=evidence,
        )
        # The task log is the only surviving r5 artifact. Preserve the same
        # unrounded evidence there even when structured logs are unavailable.
        return RuntimeError(f"{failure}; native_geometry={evidence!r}")

    def geometry() -> tuple[tuple[float, float], tuple[float, float]]:
        z_mm = -PLATE_L / 2.0
        edges = scan_view_edges(view, label="coefficient plate free end")
        points = []
        for face, y_mm in (
            ("bottom", COEFFICIENT_BOTTOM_Y), ("top", COEFFICIENT_TOP_Y),
        ):
            free_end = (PLATE_W, y_mm, z_mm)
            edge = edges.exact_line_through(
                (PLATE_W - 0.5, y_mm, z_mm), label=f"coefficient {face} edge",
            )
            if (
                min(math.dist(point, free_end) for point in edge.line) > 1e-6
                or any(
                    abs(point[1] - y_mm) > 1e-6 or abs(point[2] - z_mm) > 1e-6
                    for point in edge.line
                )
            ):
                raise RuntimeError(f"{label}: {face} edge does not reach the actual free end")
            points.append(model_point_in_view(
                adapter, view, _metres(free_end), label=f"{label} {face}",
            ))
        inset = model_point_in_view(
            adapter, view, _metres((PLATE_W - 1.0, COEFFICIENT_BOTTOM_Y, z_mm)),
            label=f"{label} inboard",
        )
        if any(
            len(point) != 2 or not all(finite(v) for v in point)
            for point in (*points, inset)
        ):
            raise RuntimeError(f"{label}: nonfinite projected plate geometry")
        bottom, top = points
        if (
            abs(top[0] - bottom[0]) > slop
            or abs(top[1] - bottom[1] - COEFFICIENT_T / 1000.0) > slop
            or abs(inset[0] - bottom[0] - 0.001) > slop
            or abs(inset[1] - bottom[1]) > slop
        ):
            raise RuntimeError(f"{label}: unexpected projected plate direction or scale")
        return bottom, top

    def native_ink(display: Any) -> tuple[Any, ...]:
        faces = geometry()
        gaps = []
        for index in (0, 1):
            ok, use_doc, value = display.GetWitnessLineGap(index, False, 0.0)
            if (
                ok is not True or type(use_doc) is not bool
                or not finite(value) or value < 0.0
            ):
                raise RuntimeError(f"{label}: invalid native witness gap {index}")
            gaps.append((use_doc, value))
        raw_data = display.GetDisplayData()
        if raw_data is None:
            raise RuntimeError(f"{label}: missing native display data")
        data = _early_bound(raw_data, "IDisplayData")
        count = data.GetArrowHeadCount()
        if type(count) is not int or count != 2:
            raise RuntimeError(f"{label}: expected two visible native arrows")
        tips = []
        for index in (0, 1):
            row = tuple(data.GetArrowHeadAtIndex2(index))
            if len(row) != 12 or not all(finite(value) for value in row):
                raise RuntimeError(f"{label}: invalid native arrow coordinates")
            tips.append((row[0], row[1]))
        tips.sort(key=lambda point: point[1])
        segments = dimension_segments(annotation)
        if not segments or any(
            not all(finite(value) for point in stroke for value in point)
            for stroke in segments
        ):
            raise RuntimeError(f"{label}: invalid native witness coordinates")
        horizontal = [
            stroke for stroke in segments
            if abs(stroke[1][1] - stroke[0][1]) <= slop
            and abs(stroke[1][0] - stroke[0][0]) > slop
        ]
        if abs(tips[0][0] - tips[1][0]) > slop:
            raise RuntimeError(f"{label}: native arrows do not share a dimension line")
        tails, witnesses = [], []
        for face, tip, (_use_doc, gap) in zip(faces, tips, gaps):
            candidates = [
                stroke for stroke in horizontal
                if all(abs(point[1] - face[1]) <= slop for point in stroke)
            ]
            if len(candidates) != 1:
                raise RuntimeError(f"{label}: expected one native witness at each plate face level")
            witness = candidates[0]
            witnesses.append(witness)
            left, right = sorted(point[0] for point in witness)
            if (
                abs(tip[1] - face[1]) > slop
                or abs(right - (face[0] - gap)) > slop
                or not left < tip[0] < right
            ):
                raise RuntimeError(f"{label}: unexpected native witness endpoint or arrow")
            tails.append(left)
        dimension_lines = [stroke for stroke in segments if stroke not in horizontal]
        if any(
            any(abs(point[0] - tips[0][0]) > slop for point in stroke)
            for stroke in dimension_lines
        ):
            raise RuntimeError(f"{label}: unexpected native dimension-line ink")
        # Text outside the arrows can add an underline/leader. It is not a
        # witness: its horizontal run joins an endpoint of the native vertical
        # dimension line, away from the two measured face levels.
        for stroke in horizontal:
            if stroke in witnesses:
                continue
            if not any(
                abs(point[0] - tips[0][0]) <= slop
                and any(
                    math.dist(point, endpoint) <= slop
                    for line in dimension_lines for endpoint in line
                )
                for point in stroke
            ):
                raise RuntimeError(f"{label}: unexpected native text-leader ink")
        return tuple(gaps), tuple(tips), tuple(tails)

    def ink(display: Any) -> tuple[Any, ...]:
        try:
            return native_ink(display)
        except Exception as exc:
            raise geometry_failure(display, exc) from exc

    display, dimension, name, value, band = model_state()
    original_ink = ink(display)

    def check_thickness() -> None:
        current, owner, current_name, current_value, current_band = model_state()
        same_display, same_dimension = same(current, display), same(owner, dimension)
        # Nominal precision applies only when admitting the imported value.
        # This snapshot must remain identical after layout/rebuild, including
        # any sub-budget value or manufacturing-band change.
        if (
            not same_display or not same_dimension
            or (current_name, current_value, current_band) != (name, value, band)
        ):
            raise RuntimeError(
                f"{label}: native model identity, value or band changed; "
                f"same_display={same_display}, same_dimension={same_dimension}; "
                "(FullName, SystemValue[m], band[Type, min_m, max_m]) "
                f"expected={(name, value, band)!r}, "
                f"observed={(current_name, current_value, current_band)!r}"
            )
        actual_gaps, actual_tips, actual_tails = ink(current)
        gaps, tips, tails = original_ink
        if (
            actual_gaps != gaps
            or any(math.dist(a, b) > slop for a, b in zip(actual_tips, tips))
            or any(abs(a - b) > slop for a, b in zip(actual_tails, tails))
        ):
            raise geometry_failure(
                current,
                RuntimeError(f"{label}: native witness gaps, arrow tips or tails moved"),
                original_ink=original_ink,
                regenerated_ink=(actual_gaps, actual_tips, actual_tails),
            )

    return check_thickness


def _dimension_ownership_check(
    adapter: Any, views: Iterable[tuple[str, str, Any, Iterable[str]]],
) -> Callable[[], None]:
    """Keep every marked dimension on exactly its assigned manufacturing view."""
    owners = {
        name: feature for feature, names in DIMENSIONS_BY_FEATURE.items() for name in names
    }
    assignments = tuple(
        (sheet, label, raw, frozenset(wanted)) for sheet, label, raw, wanted in views
    )

    def check_ownership() -> None:
        ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
        active_sheet = None
        for sheet, label, raw_view, wanted in assignments:
            if sheet != active_sheet:
                if ddoc.ActivateSheet(sheet) is not True:
                    raise RuntimeError(f"{label}: cannot activate native owner sheet {sheet!r}")
                active_sheet = sheet
            view = _early_bound(raw_view, "IView")
            count = view.GetAnnotationCount()
            raw_annotations = view.GetAnnotations()
            if (
                type(count) is not int or count < 0
                or (raw_annotations is None and count != 0)
                or (raw_annotations is not None and (
                    not isinstance(raw_annotations, (tuple, list))
                    or len(raw_annotations) != count
                ))
            ):
                raise RuntimeError(f"{label}: invalid native annotation census")
            found = []
            for raw in raw_annotations or ():
                annotation = _early_bound(raw, "IAnnotation")
                kind = annotation.GetType()
                if type(kind) is not int:
                    raise RuntimeError(f"{label}: unreadable native annotation type")
                if kind != 4:  # swDisplayDimension
                    continue
                display = _early_bound(
                    annotation.GetSpecificAnnotation(), "IDisplayDimension",
                )
                raw_dimension = display.GetDimension2(0)
                if raw_dimension is None:
                    if display.IsHoleCallout() is True:
                        continue
                    raise RuntimeError(f"{label}: non-callout dimension has no model owner")
                dimension = _early_bound(raw_dimension, "IDimension")
                full_name = dimension.FullName
                if not isinstance(full_name, str) or not full_name:
                    raise RuntimeError(f"{label}: model dimension has no native name")
                parts = full_name.split("@")
                name = parts[0]
                if name not in owners:
                    continue
                if (
                    len(parts) < 2 or parts[1] != owners[name]
                    or type(annotation.OwnerType) is not int or annotation.OwnerType != 0
                    or type(annotation.Visible) is not int or annotation.Visible != 1
                    or annotation.IsDangling() is not False
                ):
                    raise RuntimeError(f"{label}: {full_name} lost its native feature/view ownership")
                found.append(name)
            if sorted(found) != sorted(wanted):
                raise RuntimeError(
                    f"{label}: marked-dimension ownership mismatch: "
                    f"expected {sorted(wanted)}, found {sorted(found)}"
                )

    return check_ownership


_SW_HIDDEN = 2  # swDisplayMode_e.swHIDDEN: hidden lines removed


def _hidden_lines_removed_without_greyed_pass(view: Any) -> None:
    """Set HLR directly before annotating, without the label-generating grey pass.

    #1591 observed view-dependent automatic receiver labels after the shared
    hidden-line regeneration. These newly placed views need no such pass.
    """
    bound = _early_bound(view, "IView")
    placed = int(bound.GetDisplayMode2())
    bound.SetDisplayMode4(False, _SW_HIDDEN, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HIDDEN:
        raise RuntimeError(
            f"failed to set hidden-lines-removed drawing view (mode reads {mode})"
        )
    _telemetry.info(f"{bound.GetName2()} placed in display mode {placed}, now HLR")


def _remove_redundant_thread_notes(adapter: Any) -> None:
    """Inventory, delete and read back the actual automatic thread labels.

    Like draw_fr_top_frame, do not make their incidental count specification:
    #1591 recorded view-dependent labels. The three authored native callouts,
    not automatic notes, define the holes.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    draw = adapter.currentModel
    labels = 0
    for sheet_name in SHEET_NAMES:
        sheet = _early_bound(ddoc.Sheet(sheet_name), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            threads = 0
            found: list[str] = []
            hits: list[Any] = []
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                kind = int(annotation.GetType())
                if kind == _COSMETIC_THREAD_ANNOTATION:
                    threads += 1
                elif kind == 6:  # swNote
                    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
                    text = str(note.GetText() or "")
                    if "tapped hole" in text.lower():
                        found.append(f"{annotation.GetName()}={text!r}")
                        hits.append(annotation)
            labels += len(found)
            _telemetry.info(
                f"thread labels: {sheet_name}/{view_name(adapter, view)} "
                f"{threads} cosmetic threads, {len(found)} labels {found!r}"
            )
            for annotation in hits:
                draw.ClearSelection2(True)
                if not annotation.Select2(False, 0):
                    raise RuntimeError("failed to select an automatic tapped-hole note")
                draw.EditDelete()  # VT_VOID: the re-read below proves deletion.
            draw.ClearSelection2(True)
            survivors = [
                str(_early_bound(raw, "INote").GetText() or "")
                for raw in (view.GetNotes() or ())
                if "tapped hole" in str(_early_bound(raw, "INote").GetText() or "").lower()
            ]
            if survivors:
                raise RuntimeError(
                    f"{sheet_name}/{view_name(adapter, view)}: automatic tapped-hole "
                    f"notes survived deletion: {survivors!r}"
                )
    _telemetry.info(f"thread labels: {labels} in all")


def _finished_thread_annotation_check(
    adapter: Any, callouts: Iterable[tuple[str, Any, Any]]
) -> Callable[[], None]:
    """Keep the authored callouts' identity and native definitions through cleanup
    and the final settling rebuild, with no redundant note left on either sheet."""
    expected = []
    for label, view, raw_display in callouts:
        display = _early_bound(raw_display, "IDisplayDimension")
        if not display.IsHoleCallout():
            raise RuntimeError(f"{label}: authored annotation is not a native hole callout")
        expected.append((
            label, view, _early_bound(display.GetAnnotation(), "IAnnotation"),
            tuple(str(display.GetText(part) or "") for part in (5, 6, 7, 8)),
        ))

    def check_annotations() -> None:
        ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
        for sheet_name in SHEET_NAMES:
            sheet = _early_bound(ddoc.Sheet(sheet_name), "ISheet")
            for raw_view in sheet.GetViews() or ():
                view = _early_bound(raw_view, "IView")
                for raw_note in view.GetNotes() or ():
                    text = str(_early_bound(raw_note, "INote").GetText() or "")
                    if "tapped hole" in text.lower():
                        raise RuntimeError(
                            f"{sheet_name}/{view_name(adapter, view)}: redundant "
                            f"tapped-hole note remains: {text!r}"
                        )
        for label, view, original, definitions in expected:
            matches = [
                _early_bound(raw, "IAnnotation")
                for raw in (_early_bound(view, "IView").GetAnnotations() or ())
                if int(adapter.swApp.IsSame(raw, original)) == 1
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{label}: authored native hole callout is missing")
            annotation = matches[0]
            if annotation.IsDangling():
                raise RuntimeError(f"{label}: authored native hole callout is dangling")
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            if not display.IsHoleCallout() or definitions != tuple(
                str(display.GetText(part) or "") for part in (5, 6, 7, 8)
            ):
                raise RuntimeError(f"{label}: authored native hole callout changed")

    return check_annotations


def _mounting_rims(edges: ViewEdges) -> list[Any]:
    """Back looks from -Z directly onto the blind taps' entry circles."""
    return [
        edges.circle_at(
            point, TAP_DRILL_DIA / 2.0, axis=(0.0, 0.0, 1.0),
            label=f"bracket receiver {index}",
        )
        for index, point in enumerate(LEVER_HOLE_POINTS)
    ]


# VIEW F's controlled ReceiverY0 locates the bracket row from the actual plate
# top. The coefficient top and knife stay fixed; only the matched tap row
# moves down. Its owned centreline spans the two taps, not the hex centre.
RECEIVER_AXIS_OVERRUN_MM = 2.0


def _receiver_axis_centerline(adapter: Any, back: Any) -> Any:
    """Extend VIEW F's centreline along the relocated two-tap row only."""
    z_mm = -PLATE_L / 2.0
    stations = [point[0] for point in LEVER_HOLE_POINTS]
    return _owned_centerline(
        adapter,
        back,
        (
            (max(stations) + RECEIVER_AXIS_OVERRUN_MM, RECEIVER_ROW_Y, z_mm),
            (min(stations) - RECEIVER_AXIS_OVERRUN_MM, RECEIVER_ROW_Y, z_mm),
        ),
        label="receiver row centreline",
    )


# VIEW G carries the shared positive rib profile and its derived reach.
# The title block owns the R.040 MAX ceiling. The web's flush caption stands
# entirely above the boss's upper witness; 19.05 has no centering caption.
FRONT_KEEP = {
    "AnchorHeight": (0.145, 0.235),
    "WebThickness": (0.168, 0.258),
    "EdgeRibFrontArcR": (0.1948, 0.2120),
    "RibReach": (0.2443, 0.254),
}
# The native 6.985 mm face span uses the ordinary document .XX precision:
# its text is above the profile and right of RibReach's complete callout.
BOSS_FACE_LOCATION_XY = (0.284, 0.250)
# VIEW F's right-hand column is outside the boss's actual X400.0875 mm end.
# The short 2.594 span hangs its ordinary 2.59 below the view: predicted native
# text X403.5..415.1375 / Y125.2219..128.7219 mm, clear of the tap callout.
KNIFE_HEIGHT_LOCATION_XY = (0.4035, 0.128)
# Detail D at 10:1: the complete envelope fills a 120 mm crop on sheet 2.
# The ridge pair shares one line above the crop, with each whole callout
# outside its own model-side span. Back reverses X: RidgeFromLeft prints
# right, RidgeFromRight left, and the +X flank's exterior wedge is left.
# Keep that native angle arc; its complete text moves to a separate shelf.
# R.004 MAX stands right of the X155.4 mm witness, with a shallow arrow
# clear of A. Only the two ridge-side witnesses get a local gap above A.
DETAIL_KEEP = {
    "HexWidth": (0.203, 0.083),
    "HexHeight": (0.0342, DETAIL_CENTER[1]),
    "RidgeFromLeft": (0.201, 0.2483),
    "RidgeFromRight": (0.044, 0.25105),
    # 120 deg about the shoulder (74.5999, 175.6701) mm at the same 18.57 mm
    # radius. At 153.6 deg (58, 184) the offset connector landed by the lower
    # arrow (58.3, 166.7) and crossed its own arc up to the shelf above
    # (machinist review 41bbeec): seeded nearer the upper end, it lands on
    # the arc's upper part, below and right of the shelf, outside the arc.
    "FlankToSide": (0.0653, 0.1918),
    "KnifeRidgeRadius": (0.181, 0.219),
}
# Keep the native arc radius. R3's low shelf routed through the final SEAT T.
# Above the height's Y201.3401 witness, the whole two-row block clears it by
# 4.1036 mm and the X74.5999 ridge witness by 4.9138 mm. Any connector from
# the unchanged arc stays below the text; verify regenerated native/PDF ink.
FLANK_TEXT_XY = (0.051, 0.211)
RIDGE_WITNESS_GAP = 0.010
TOP_KEEP = {
    # The model width is authored at the plan's middle Z. Its native
    # witnesses therefore start at Y130 mm, not at the end face: R7 crossed
    # the spring callout and diameter. _clear_plate_width_witnesses starts
    # both 1 mm beyond the actual projected +Z end, preserving visible tails.
    # Keep the existing bottom dimension line and full width value.
    "PlateWidth": (0.266, 0.0813),
    # Right of the -Z rib's three lines (they end at x 0.4007; at 0.395 its
    # line crossed "DRILL", farm r7).  Its two callout lines (BODY END FACES,
    # 9 characters) end 2.9 mm inside the border.
    "PlateLength": (0.405, TOP_CENTER[1]),
    # The boss's diameter names the web arcs' ends under its value; its
    # four lines stand left of its leader, above the anchor tap's callout.
    "AnchorOuterDia": (0.145, 0.168),
    # Plan geometry (baseline render): the cylinder band x 0.2286..0.2417,
    # the -Z plate end at y 0.1681 with its stub to 0.179, the +Z end at
    # 0.0922, the summation web's arcs from the boss (x 0.2021) to the
    # cylinder ends.
    # Inside the web's upper arc (centre (0.1737, 0.2001), 69.4 sheet mm,
    # visible from -70 to -37 deg round it).  The leader starts at the text's
    # left end, at -60 deg and 46 mm from the centre, so it lands on the
    # visible arc: from -93 deg (farm r5) or -72 deg (r4) SolidWorks moved the
    # arrow to the opposite side, ruling the radius across the sheet.  Text
    # inside the arc rules the radius from its centre (farm r6), clear of
    # everything but the front view's rib-arc callout (see FRONT_KEEP).  The
    # text's far corner stays 7 mm inside the arc, 8 mm under the 21.72.
    # Foreshortened (_shorten_radii): the full line from the centre read as
    # a loose line (machinist review r8).
    "SummationArcRadius": (0.2096, 0.162),
    # Left of the -Z stub. Native text spanned x 213.0267..233.9732 mm
    # against the stub's x 232.2987 mm outline; move its anchor 5 mm left
    # to target 3.3 mm box clearance. Both stubs are one prism, so the length
    # remains the hidden KnifeStubReference's, along its -X side.
    "KnifeStubLength": (0.2185, 0.1735),
    # One model-owned 3X thickness sizes all three ribs, above its span.
    # R2's native text hangs LEFT of this anchor: x 191.1396..209.5 mm
    # crossed the boss-X witness at x 197.2187. Move the complete native
    # text/shoulder/arrow column 16 mm left, not toward the diameter above.
    # The translated native span x 175.1396..193.5 leaves 3.7187 mm to that
    # witness and 7.6201 mm to MID RIB CENTRE. Confirm regenerated native ink.
    "EdgeRibThickness": (0.1935, 0.1035),
    # The cylinder's diameter across its band, from the part's hidden
    # CylinderReference line (machinist review r10: in the front view its
    # leader landed on the rib outline that hides it).  Its text stands left
    # of the band, 2.8 mm over the line, which the dimension line covers
    # (farm r11: the dimension line prints that far below its text): right
    # of the boss's 76.20 extension line (x 0.1972), above and right of the
    # relocated 3X 5.00 block, and 2.3 mm clear of the web's lower arc.
    "CylinderDia": (0.209, _top_xy(0.0, -CYLINDER_REFERENCE_Z)[1] + 0.0028),
}
# VIEW F at 1:1, model X reversed. All stations, thickness and caption ride
# with the view; their ink clears D's native X192.6 mm outer extent.
BACK_KEEP = {
    "PlateThickness": (BACK_CENTER[0] - 0.072, BACK_CENTER[1] - 0.017),
    "ReceiverX0": (BACK_CENTER[0] - 0.005, BACK_CENTER[1] + 0.0315),
    "ReceiverX1": (BACK_CENTER[0] - 0.095, BACK_CENTER[1] + 0.0245),
    "ReceiverY0": (BACK_CENTER[0] - 0.082, BACK_CENTER[1] + 0.0085),
}
# Keep the native blind-tap callout below the receiver; its only added row
# identifies the bracket these holes fasten.
MOUNTING_CALLOUT_XY = (BACK_CENTER[0] + 0.025, BACK_CENTER[1] - 0.035)
# Keep the caption below the complete receiver callout; native regeneration
# must check its clearance after any wording change.
BACK_VIEW_NOTE_XY = (BACK_CENTER[0] - 0.075, BACK_CENTER[1] - 0.066)
# Sheet 1's plan names sheet 2's view: a letter arrow onto the -Z end, the
# face VIEW F looks at (fr_rocker_arm_support's VIEW B arrow).  Its tip is
# on the receiver rib's outer edge at model x 21.4 (sheet x 0.246), between
# the hex stub (x 0.2335..0.2375) and the 20X frame's leader (x 0.2545); the
# letter stands 8 mm above the edge, under that frame (bottom y 0.192).
# The leader leaves the letter's right side, VIEW_F_LEADER_DX right of the
# note's left (farm r13: note x 0.24422, leader start 0.24775), so the note
# stands that far left of the tip and the arrow drops square onto the end
# face.  Centred over the tip it leant 9 degrees, and machinist review r13
# read it as looking down onto the rib, like the plan, not at the end face.
# (note upper-left, leader tip) in sheet metres.
VIEW_LETTER_HEIGHT = 0.005
VIEW_F_LEADER_DX = 0.00353
_VIEW_F_TIP = _top_xy(21.4, PLATE_L / 2.0)
VIEW_F_ARROW = (
    (_VIEW_F_TIP[0] - VIEW_F_LEADER_DX, _VIEW_F_TIP[1] + 0.013),
    _VIEW_F_TIP,
)
# Sheet 1's end profile is VIEW G, so the plan carries its arrow too: up onto
# the +Z end (datum B) at model x 7.2 (sheet x 0.2389), 1.4 mm right of the
# hex stub, with datum B's tag moved right to leave the letter room.  The
# letter hangs below the edge and the leader leaves its left side, so the
# note stands at the tip (the left margin is squared on readback); its foot
# stays 3 mm over the 76.20/39.85 dimension line (y 0.0784).
VIEW_ARROW_SQUARE_TOL = 0.0003
_VIEW_G_TIP = _top_xy(7.2, -PLATE_L / 2.0)
VIEW_G_ARROW = (
    (_VIEW_G_TIP[0] - 0.0004, _VIEW_G_TIP[1] - 0.005),
    _VIEW_G_TIP,
)
# VIEW G's label stands under the end profile, right of Detail D's identifier
# and above the spring-pattern frame's leader. The point is its upper-left.
FRONT_VIEW_NOTE_XY = (0.258, 0.2120)


def _dress_bracket_depth_callout(callout: Any) -> None:
    """Keep native receiver depths; let the drill's decimals carry its general band."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    required_depths = {
        "hw-threaddepth": THREAD_DEPTH,
        "hw-tapdrldepth": DRILL_DEPTH,
    }
    for raw in callout.GetHoleCalloutVariables() or ():
        # Concrete callout interfaces alias the generic metadata DISPIDs.
        variable = dynamic_dispatch(raw._oleobj_)
        variable_name = str(variable.VariableName)
        if variable_name not in required_depths:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        expected_depth = required_depths.pop(variable_name)
        if abs(float(length.Length) * 1000.0 - expected_depth) > 1e-5:
            raise RuntimeError(f"bracket mounting callout has wrong {variable_name}")
        observed = (
            int(variable.ToleranceType),
            float(variable.ToleranceMin) * 1000.0,
            float(variable.ToleranceMax) * 1000.0,
        )
        _telemetry.info(
            f"bracket mounting callout {variable_name} imported tolerance "
            f"(type, lower mm, upper mm) = {observed!r}"
        )
        # Callout variables own their presentation, independently of the
        # source-model dimension tolerance. Keep the full thread's MIN.
        if variable_name == "hw-threaddepth":
            variable.ToleranceType = 5  # swTolType_e.swTolMIN
            if int(variable.ToleranceType) != 5:
                raise RuntimeError(
                    "bracket mounting callout full-thread depth did not "
                    "persist as a MIN limit"
                )
            continue
        # The source band is the title block's own row at the callout's places
        # on this sheet's unit (accessor, not a parsed display string).
        if not math.isclose(
            DRILL_DEPTH_BAND, printed_band_mm(RECEIVER_HOLE_PLACES, unit=UNIT)
        ):
            raise RuntimeError("bracket tap drill depth must retain its ordinary symmetric band")
        # As for the knife-mount drill-angle callout, suppress only the
        # variable's explicit band. Native .256 then inherits .XXX ±.005;
        # the source Hole Wizard dimension keeps its bounded symmetric band.
        variable.ToleranceType = 0  # swTolType_e.swTolNONE
        length.Precision = RECEIVER_HOLE_PLACES
        if (
            int(variable.ToleranceType) != 0
            or int(length.Precision) != RECEIVER_HOLE_PLACES
        ):
            raise RuntimeError(
                f"bracket mounting callout tolerance for {variable_name} did not "
                f"persist: wanted the inherited title-block band at "
                f"{RECEIVER_HOLE_PLACES} places"
            )
    if required_depths:
        raise RuntimeError(f"bracket tap callout omits native depths: {required_depths}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
            "Receiver Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
            "Receiver Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; gray iron; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="summing lever package")
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate lever geometry sheet")

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        _hidden_lines_removed_without_greyed_pass(view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    # The cylinder's diameter lives in a reference sketch the part saves
    # hidden (its band shows no silhouette to dimension): the hidden-owner
    # curate shows it in the plan, the one view that dimensions it.
    top_annotations = curate_hidden_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    assert_imported_precision(
        adapter, top_annotations, DRAWING_PRECISION["CoefficientsPlate"],
    )
    _attach_radial_leaders(
        adapter, front_annotations, ("EdgeRibFrontArcR",),
        label="front",
    )
    _attach_radial_leaders(
        adapter, top_annotations, ("SummationArcRadius",), label="top"
    )
    _shorten_radii(adapter, top_annotations, ("SummationArcRadius",), label="top")
    _apply_callouts(
        adapter, [*front_annotations, *top_annotations], label="lever geometry",
    )
    check_boss_faces = _boss_face_location_check(adapter, front)
    _plate_top_datum(adapter, front)
    _clear_plate_width_witnesses(adapter, top, top_annotations)
    # The boss's Ø19.05 takes one arrow on its near rim, no line through the
    # centre: there it crossed the anchor tap callout's leader, which runs
    # through the tap's centre (machinist review r13, rule 14).
    [boss_dia] = [
        annotation
        for annotation in top_annotations
        if dimension_name(adapter, annotation) == "AnchorOuterDia"
    ]
    set_near_side_diameter(boss_dia, "boss diameter")

    # Counter-anchor tap native callout (thread + depth) in the top plan.  Pick
    # a point on the hole rim (not its centre) so SolidWorks catches the
    # circular edge: its left quadrant, the leader then running up-left to
    # text between the boss and the Ø19.05's text -- up-left over the mid
    # rib it ran through that rib's two-line callout (farm r1 2026-10-16,
    # leader-through-text), and down-left its text took the room the boss's
    # Z location needs (machinist review r4 B3).
    anchor_tap_edge = _top_xy(TIP_X - COUNTER_R, 0.0)
    anchor_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=anchor_tap_edge,
        callout_xy=(0.145, 0.140),
        label="anchor tap",
    )
    set_hole_callout_precision(anchor_callout, COUNTER_TAP_PRECISION, label="anchor tap")

    # Datum A is the common knife-edge pivot ridge, tagged in Detail D on sheet 2.
    # One sweep of the plan's visible edges serves every
    # named pick below.  The ridge is the hexagon's top vertex line, y =
    # HEX_H/2 (vertex-up sketch centred on the pivot axis,
    # build_sm_summing_lever._hex_knife), rounded at R.004 MAX: the plan shows
    # the round's two tangent lines 0.05 sheet mm either side of it, and the
    # finish names the +X one (the edge of the upper-right face it controls)
    # by entity.  A SolidWorks Top view reverses model Z on the sheet: the
    # negative sheet offset selects the +Z ridge.
    top_edges = scan_view_edges(top, label="summing lever top plan")
    ridge_x, ridge_y = KNIFE_RIDGE_TANGENT_XY
    stub_mid_z = PLATE_L / 2.0 + HEX_DEPTH / 2.0
    finish_ridge = top_edges.exact_line_through(
        (ridge_x, ridge_y, stub_mid_z), label="+Z knife-edge ridge round"
    )
    # The ridge lands in a pocket closed by the 76.20 extension line (left),
    # the 76.20/39.85 dimension line (below) and the plate (above); the default
    # 43 mm body cannot fit, so the 2.5 mm body sits inside it (layout audit:
    # the old leader crossed 76.20's extension line and datum B's leader).
    # Its V stands 4 mm right of the 5.08 rib thickness's lower arrow (at
    # 0.208 it overprinted it, machinist review r9), the text ending 2.4 mm
    # short of the stub.
    add_surface_finish(
        adapter,
        top,
        edge_entity=finish_ridge.edge,
        leader_attach_xy=_top_xy(ridge_x, -stub_mid_z),
        symbol_xy=(0.216, 0.084),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
        char_height=0.0025,
    )
    # Both knife edges seat (Detail D's 2X), so the -Z ridge carries the same
    # grade through its own part control (machinist review r11, rule 6: one
    # symbol left the other edge open to as-cast).
    # It stands over the -Z stub: right of 21.72's upper dimension line (x
    # 0.2235), its text 3 mm over the F arrow's letter and 2 mm under the
    # 20X position frame (y 0.192); its leader enters the stub's right side.
    add_surface_finish(
        adapter,
        top,
        edge_entity=top_edges.exact_line_through(
            (ridge_x, ridge_y, -stub_mid_z), label="-Z knife-edge ridge round"
        ).edge,
        leader_attach_xy=_top_xy(ridge_x, stub_mid_z),
        symbol_xy=(0.233, 0.1828),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge_minus_z"),
        label="-Z knife-edge ridge finish",
        char_height=0.0025,
    )
    # X location of the anchor tap from datum A's -Z knife-edge pivot ridge:
    # a plain title-block dimension. The owned centreline depicts its
    # theoretical sharp (rule 16); nominally the +Z ridge shares that axis,
    # but the opposite manufactured ridge is not the datum feature. Both
    # this dimension and the spring row's BASIC X use the same -Z reference.
    # The other endpoint is the tap rim on the boss top, centre
    # (TIP_X, ANCHOR_H/2, 0), placed by _counter_anchor_tap. The mid rib's
    # apex shares the anchor tap's X station.
    ridge_dim_edge = _top_xy(0.0, PLATE_L / 2.0 + 0.3 * HEX_DEPTH)
    anchor_tap_bottom = _top_xy(TIP_X, -COUNTER_R)
    ridge_axis = _ridge_centerline(adapter, top)
    anchor_rim = top_edges.circle_at(
        (TIP_X, ANCHOR_H / 2.0, 0.0),
        COUNTER_R,
        axis=(0.0, 1.0, 0.0),
        label="counter-anchor tap rim",
    )
    ridge_entity_types = ("SKETCHSEGMENT", "EDGE")
    anchor_location = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=anchor_tap_bottom,
        text_xy=(0.216, 0.0723),
        label="anchor tap X location",
        orientation="horizontal",
        entity_types=ridge_entity_types,
        entities=(ridge_axis, anchor_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        anchor_location,
        expected_mm=-TIP_X,
        label="anchor tap X location",
        entities=(ridge_axis, anchor_rim.edge),
        entity_types=ridge_entity_types,
    )

    # Anchor-tap pattern control: datum B on the plate end the seed hole is
    # located from, BASIC row-X / start-Z / pitch coordinates off A|B, datum C
    # (VIEW G) clocking the pattern about A, a native thread callout, and a
    # 20X position frame -- the inspectable
    # pattern definition (the notes no longer carry these numbers as prose).
    # The plan prints model +Z DOWN the sheet, so the end at the bottom of the
    # view is the +Z end: the seed hole (HOLE_Z_LAST, HOLE_END_OFFSET_LAST off
    # that end) is the bottom hole of the column.
    # Hang B's tag straight down right of the +Z trunnion stub, between it and
    # the 39.85 extension line: left of the stub it sat in the finish leader's
    # only path (layout audit); the 20X callout now hangs on the middle hole,
    # well away from this tag.  It stands 10.2 mm right of the pick, clear of
    # VIEW G's letter beside the stub (at 9.0 its frame touched the letter,
    # farm r16).
    # Every datum and dimension here names its entities: a coordinate
    # hit-test on the plate corner resolved to the rib flange 5.08 mm inboard
    # (datum B on the flange, start Z reading 3.35 for 8.43 -- #1105), and a
    # value check alone cannot tell the seed rim from the nineteen others at
    # the same X or any equal-pitch pair. The picks below are the rims'
    # model positions (the hole wizard's seed at HOLE_Z_LAST, the pattern
    # marching -Z by CHANNEL_PITCH; build_summing_lever).
    plate_end_edge = _top_xy(10.0, -PLATE_L / 2.0)
    end_edge = _end_face_edge(top_edges, x_mm=10.0)
    add_datum_feature(
        adapter,
        top,
        edge_entity=end_edge.edge,
        symbol_xy=(plate_end_edge[0] + 0.0102, plate_end_edge[1] - 0.0035),
        datum="B",
        label="plate +Z end face",
    )
    # Z location of the anchor boss (machinist review r4 B3: the plan located
    # it only in X): datum B to the tap's centre, half the plate length.  The
    # pick sits at the end line's inboard end (the rib's top edge at the
    # cylinder), so the extension line runs left under the web's lower arc,
    # not along the outline; the text stands in the span left of the boss,
    # under the anchor tap's callout and right of the Ø19.05's leader.
    boss_z_pick = _top_xy(
        min(point[0] for point in end_edge.line) + 1.0, -PLATE_L / 2.0
    )
    boss_z = add_edge_dimension(
        adapter,
        top,
        p0=boss_z_pick,
        p1=anchor_tap_edge,
        text_xy=(0.150, 0.111),
        label="anchor boss Z location",
        orientation="vertical",
        entities=(end_edge.edge, anchor_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        boss_z,
        expected_mm=PLATE_L / 2.0,
        label="anchor boss Z location",
        entities=(end_edge.edge, anchor_rim.edge),
    )
    # The mid rib shares the boss's station (machinist review r6: its 5.08
    # thickness had no location along the plate), so this one 76.20 names
    # both under its value.
    boss_z_display = _early_bound(boss_z, "IDisplayDimension")
    boss_z_display.SetText(4, BOSS_Z_CALLOUT)  # swDimensionTextCalloutBelow
    if "MID RIB" not in str(boss_z_display.GetText(4) or ""):
        raise RuntimeError(
            f"anchor boss Z callout did not persist: {boss_z_display.GetText(4)!r}"
        )
    seed_rim = top_edges.circle_at(
        (HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z_LAST),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole seed rim",
    )
    second_rim = top_edges.circle_at(
        (HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z_LAST - CHANNEL_PITCH),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole second rim",
    )
    seed_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, -HOLE_Z_LAST)
    # The start-Z and pitch texts ride with the hole column (tuned at the 0.8
    # arm offset, seed centre at sheet y 0.0961), so a station move keeps them.
    seed_y = seed_rim_right[1]
    row_x = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=seed_rim_right,
        # The four-place boxed 1.5689 is wider than the mm 39.85 was: at 0.248
        # its box touched the hole column's extension line (machinist review).
        text_xy=(0.243, 0.0723),
        label="spring-hole row X",
        orientation="horizontal",
        entity_types=ridge_entity_types,
        entities=(ridge_axis, seed_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        row_x,
        expected_mm=HOLE_X,
        label="spring-hole row X",
        entities=(ridge_axis, seed_rim.edge),
        entity_types=ridge_entity_types,
    )
    set_basic_dimension(adapter, row_x, label="spring-hole row X")
    set_dimension_display_precision(
        adapter, "drawing", "spring-hole row X", BASIC_PLACES, display=row_x,
    )
    seed_rim_top = _top_xy(HOLE_X, -HOLE_Z_LAST + HOLE_DIA / 2.0)
    # The start Z (12.75) spans 6.4 mm of sheet (0.0919..0.0983); text between
    # the arrows would sit on its own line (3.35 there stood on 7.06's extension
    # line and the body-span line), so it hangs above the span. Each of these vertical
    # dimensions draws its line at its text's right end (farm r1 2026-10-16:
    # the 19X 7.06 text 0.275..0.2958 with its line there), so the 12.75 text
    # starts 4 mm right of that line -- at 0.292 its shoulder crossed it -- and
    # stays left of the 152.4 body-span line (0.396).
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=plate_end_edge,
        p1=seed_rim_top,
        text_xy=(0.300, seed_y + 0.0099),
        label="spring-hole start Z",
        orientation="vertical",
        entities=(end_edge.edge, seed_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        start_z,
        expected_mm=HOLE_END_OFFSET_LAST,
        label="spring-hole start Z",
        entities=(end_edge.edge, seed_rim.edge),
    )
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    set_dimension_display_precision(
        adapter, "drawing", "spring-hole start Z", BASIC_PLACES, display=start_z,
    )
    second_rim_bottom = _top_xy(
        HOLE_X, -HOLE_Z_LAST + CHANNEL_PITCH - HOLE_DIA / 2.0
    )
    pitch = add_edge_dimension(
        adapter,
        top,
        p0=seed_rim_top,
        p1=second_rim_bottom,
        text_xy=(0.275, seed_y + 0.0054),
        label="spring-hole pitch",
        orientation="vertical",
        entities=(seed_rim.edge, second_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        pitch,
        expected_mm=CHANNEL_PITCH,
        label="spring-hole pitch",
        entities=(seed_rim.edge, second_rim.edge),
    )
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    set_dimension_display_precision(
        adapter, "drawing", "spring-hole pitch", BASIC_PLACES, display=pitch,
    )
    # Twenty taps are nineteen pitches: the count rides the BASIC pitch as
    # its prefix, read back because SetText reports nothing.
    pitch_display = _early_bound(pitch, "IDisplayDimension")
    pitch_prefix = f"{HOLE_COUNT - 1}X "
    pitch_display.SetText(1, pitch_prefix)  # swDimensionTextPrefix
    if str(pitch_display.GetText(1) or "") != pitch_prefix:
        raise RuntimeError(
            f"spring-hole pitch count {pitch_prefix!r} did not persist: "
            f"{pitch_display.GetText(1)!r}"
        )
    # The 20X callout hangs on hole 7, with its complete process line in the
    # open field right of the column and clear of the mid-rib witnesses.
    callout_hole_z = HOLE_Z_LAST - (HOLE_COUNT // 2 - 3) * CHANNEL_PITCH
    callout_rim = top_edges.circle_at(
        (HOLE_X, COEFFICIENT_TOP_Y, callout_hole_z),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole callout rim",
    )
    spring_callout = add_native_hole_callout(
        adapter,
        top,
        edge=callout_rim.edge,
        callout_xy=(0.310, _top_xy(HOLE_X, -callout_hole_z)[1] + 0.0015),
        label="spring-hole pattern",
        process=SPRING_TAP_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        spring_callout, SPRING_TAP_PRECISION, label="spring-hole pattern"
    )
    # The Top view reverses model Z, so -HOLE_Z_FIRST prints the seed hole at
    # the TOP of the column. The frame sits above the +Z trunnion stub with
    # its right stub ending over the rim, so the leader drops just past the
    # receiver rib's end and runs only ~5 mm over the plate (the diagonal
    # from 0.175 crossed the stub and flange: leader-over-part, 24 mm).  The
    # seed rim is named by entity and the arrow set on its upper-left
    # quadrant: a hit-test at its left quadrant landed the arrow on the
    # rib's end corner 1 mm left of the hole (machinist review r9).
    seed_rim = top_edges.circle_at(
        (HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z_FIRST),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole seed rim",
    )
    rim_step = HOLE_DIA / 2.0 * math.sqrt(0.5)
    add_feature_control_frame(
        adapter,
        top,
        edge_entity=seed_rim.edge,
        leader_attach_xy=_top_xy(HOLE_X - rim_step, -HOLE_Z_FIRST + rim_step),
        frame_xy=(0.2133, 0.199),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["spring-hole pattern position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )
    _add_view_arrow(adapter, top, BACK_VIEW_LETTER, VIEW_F_ARROW)
    _add_view_arrow(adapter, top, FRONT_VIEW_LETTER, VIEW_G_ARROW)
    add_property_linked_note(adapter, "Front View Note", *FRONT_VIEW_NOTE_XY)

    # The isometric's view label, under the iso.
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.205)

    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate bracket receiver sheet")
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=(1, 1))
    receiver_iso = place_view(
        adapter, str(SOURCE), octant_view_name(*RECEIVER_ISOMETRIC_OCTANT),
        *ISO_CENTER, scale=(1, 4),
    )
    for view in (back, receiver_iso):
        set_hidden_lines_removed(adapter, view)
    # The reference envelope is hidden in the saved part. Show it only while
    # creating/curating D; its native items select through their existing parent.
    with part_sketches_shown(
        adapter,
        source_model,
        KNIFE_SKETCHES,
        label="knife envelope",
        base_view=back,
    ):
        detail = _knife_detail(adapter, back)
        _hidden_lines_removed_without_greyed_pass(detail)
        detail_annotations = curate_hidden_dimensions(
            adapter,
            detail,
            keep=DETAIL_KEEP,
            view_label="knife detail",
            dimensions_by_feature=DIMENSIONS_BY_FEATURE,
        )
    _attach_radial_leaders(
        adapter, detail_annotations, ("KnifeRidgeRadius",), label="knife detail",
    )
    _assert_knife_ridge_radius(adapter, detail_annotations)
    _ridge_datum(adapter, detail)
    _apply_callouts(adapter, detail_annotations, label="knife detail")
    _clear_ridge_witnesses(adapter, detail, detail_annotations)
    _place_flank_text(adapter, detail_annotations)
    back_edges = scan_view_edges(back, label="bracket receiver face")
    mounting_rims = _mounting_rims(back_edges)
    # Below VIEW F, clear of the receiver stations and the detail's width.
    mounting_callout = add_native_hole_callout(
        adapter, back, edge=mounting_rims[0].edge,
        callout_xy=MOUNTING_CALLOUT_XY, label="two blind bracket mounting taps",
        process=BRACKET_TAP_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        mounting_callout, BRACKET_TAP_PRECISION, label="two blind bracket mounting taps"
    )
    _dress_bracket_depth_callout(mounting_callout)
    back_annotations = curate_hidden_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="bracket receiver",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    check_plate_thickness = _plate_thickness_check(adapter, back, back_annotations)
    _apply_callouts(adapter, back_annotations, label="bracket receiver")
    _receiver_axis_centerline(adapter, back)
    check_knife_height = _knife_height_location_check(adapter, back)
    # Keep the removed-view identity below the actual end profile.
    add_property_linked_note(adapter, "Back View Note", *BACK_VIEW_NOTE_XY)
    # The existing sheet-2 pictorial now shows the continuous backing from
    # below, through the part's persisted and natively read-back octant view.
    add_property_linked_note(adapter, "Receiver Isometric View Note", 0.322, 0.205)
    check_thread_annotations = _finished_thread_annotation_check(
        adapter,
        (
            ("anchor tap", top, anchor_callout),
            ("spring-hole pattern", top, spring_callout),
            ("two blind bracket mounting taps", back, mounting_callout),
        ),
    )
    _remove_redundant_thread_notes(adapter)
    check_thread_annotations()
    check_dimension_ownership = _dimension_ownership_check(
        adapter,
        (
            (SHEET_NAMES[0], "VIEW G", front, FRONT_KEEP),
            (SHEET_NAMES[0], "top", top, TOP_KEEP),
            (SHEET_NAMES[0], "geometry isometric", iso, ()),
            (SHEET_NAMES[1], "knife detail D", detail, DETAIL_KEEP),
            (SHEET_NAMES[1], "VIEW F", back, BACK_KEEP),
            (SHEET_NAMES[1], "receiver isometric", receiver_iso, ()),
        ),
    )
    check_dimension_ownership()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        # This recipe deletes and proves its actual note inventory, as top-frame
        # does; the shared exact-count guard remains unchanged for other recipes.
        # Recheck after the final rebuild, before either drawing or PDF is saved.
        settled_checks=(
            check_thread_annotations, check_plate_thickness, check_dimension_ownership,
            check_boss_faces, check_knife_height,
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
