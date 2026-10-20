r"""Create the MHA-DT-32 crank handle pivot screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the running-fit shoulder keeps its
native size band and one bearing-surface finish, the head keeps the two bands
the MHA-DT-035 cup sets, and the tip chamfer and seat edge break print as
single MAX limits.  The relief Ø retains its native size band, the relief
lead its native limits and the thread-side floor radius its native MAX;
every size keeps its part-authored places.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the thread tip on
the left and the slotted head on the right.  Axial locations baseline from the
tip, the one faced end (see ``dt_crank_handle_pivot_screw_spec``).  The
head-end view is the ``*Back`` orientation, which is exactly the third-angle
RIGHT view of that profile, so it sits on the profile's axis to its right and
shows the slot.
The relief width, lead, thread-side floor radius and modelled seat edge
break read in a standalone cropped 10:1 ``*Right`` model view, labelled
DETAIL A and circled on the side view.  A temporary face-on Front donor imports
the true-circle relief Ø and transfers only its annotation to SIDE before
deletion.  The main profile keeps the root text below-right, the thread length
above and the thread note below-left.  Rebuilt relief and all three axial
dimension ink groups must stay separate; no typed size or style fallback.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_pivot_screw.py dt-crank-handle-pivot-screw
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import math
import sys
from typing import Any, Sequence

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    delete_view,
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
import _drawing_leaders
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_crank_handle_pivot_screw_spec import (
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_DIA,
    HEAD_DIA_CALLOUT,
    HEAD_LENGTH,
    HEAD_LENGTH_CALLOUT,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
    RELIEF_CORNER_CALLOUT,
    RELIEF_CORNER_RADIUS_MAX,
    RELIEF_DIA,
    RELIEF_DIAMETER_SKETCH,
    RELIEF_DIA_CALLOUT,
    RELIEF_DIA_ROOT_CALLOUT,
    RELIEF_END_STATION,
    RELIEF_LEAD,
    RELIEF_LEAD_CALLOUT,
    RELIEF_WIDTH,
    SEAT_EDGE_BREAK_CALLOUT,
    SEAT_STATION,
    SHOULDER_CALLOUT,
    SHOULDER_DIA,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_MODEL_DIA,
    THREAD_SIZE,
    TIP_CHAMFER,
    UNDER_HEAD_CALLOUT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle_pivot_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The main orthographic views print at the sheet scale without captions;
# DETAIL A labels its enlarged scale.  3:1 lays the 67.0 profile 201 mm long
# and the 1.0 slot 3 mm wide.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.160, 0.190)
# Third-angle right view of the slotted head end, on the profile's axis,
# clear of the head Ø's callout.
END_CENTER = (0.383, SIDE_CENTER[1])
ISO_CENTER = (0.380, 0.245)
ISO_SCALE = (1, 1)


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left).

    The view is centred on the model bbox, head face (z=0) to thread tip.
    """
    return SIDE_CENTER[0] + (OVERALL_LENGTH / 2.0 - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


HEAD_FACE_X = _sheet_x(0.0)
UNDERHEAD_X = _sheet_x(HEAD_LENGTH)
SEAT_X = _sheet_x(SEAT_STATION)
RELIEF_END_X = _sheet_x(RELIEF_END_STATION)
TIP_X = _sheet_x(OVERALL_LENGTH)
# Where the full thread meets the tip chamfer.
THREAD_START_X = _sheet_x(OVERALL_LENGTH - TIP_CHAMFER)
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
SHOULDER_TOP_Y = _sheet_y(SHOULDER_DIA / 2.0)
THREAD_TOP_Y = _sheet_y(THREAD_MODEL_DIA / 2.0)

# ThreadLength reads above the shorter TipChamfer dimension, so the tiny
# inner witness cannot cross its long line.  The two tip-baseline references
# stay below the profile, 19 mm apart.  Actual rebuilt ink, not a requested
# text centre or assumed native offset, gates the relief leader below.
_ROW_Y = (SIDE_CENTER[1] + 0.035, SIDE_CENTER[1] - 0.055, SIDE_CENTER[1] - 0.074)
# The 4-mm head prints 12 mm long, narrower than its ~21-mm value, so the head
# length, the head Ø and the slot depth stand outside the head face rather
# than between extension lines that would strike their text (v43 render).
# Each head band's one-line reason callout is centred under its value.
# Its half-width at 2.8 mm a character leaves 6 mm clear of the head-face
# extension line and the centreline's overshoot, even with the longer reasons.
HEAD_LENGTH_TEXT_X = HEAD_FACE_X + 0.006 + len(HEAD_LENGTH_CALLOUT) * 0.0028 / 2.0
HEAD_DIA_TEXT_X = HEAD_FACE_X + 0.006 + len(HEAD_DIA_CALLOUT) * 0.0028 / 2.0
SLOT_DEPTH_TEXT_X = HEAD_FACE_X + 0.012
SIDE_KEEP = {
    "ThreadLength": ((TIP_X + SEAT_X) / 2.0, _ROW_Y[0]),
    "HeadLength": (HEAD_LENGTH_TEXT_X, SIDE_CENTER[1] - 0.034),
    # The under-head face located from the tip, like every axial location.
    "UnderHeadLocation": ((TIP_X + UNDERHEAD_X) / 2.0, _ROW_Y[1]),
    "OverallLength": ((TIP_X + HEAD_FACE_X) / 2.0, _ROW_Y[2]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The shoulder's dimension line
    # crosses the shoulder near its thread end; the head's stands clear of the
    # head face, left of the end view.
    "ShoulderDia": (SEAT_X + 0.056, SIDE_CENTER[1] + 0.030),
    # The head Ø's value stands a little above the axis so its callout below
    # stays between the head's extension lines.
    "HeadDia": (HEAD_DIA_TEXT_X, SIDE_CENTER[1] + 0.0025),
    # Reserve the complete native text to the RIGHT, not half its width about
    # the ask: native broken text can be right/left justified, not centred.
    # Actual rebuilt ink must still clear both physical groove corners.
    "ReliefDia": (SEAT_X + 0.014, SIDE_CENTER[1] - 0.024),
    # The native tip leg and X45 reason stand above-left, outside the thread
    # profile and clear of the relief diameter's lower seating-reason rows.
    "TipChamfer": (TIP_X - 0.020, SIDE_CENTER[1] + 0.020),
    # The slot shows as a notch in the head face; its depth reads above it,
    # outside the head face.
    "SlotDepth": (SLOT_DEPTH_TEXT_X, SIDE_CENTER[1] + 0.026),
}
# The 3-mm slot is narrower than the text, so the value stands above its
# extension lines rather than between them.
END_KEEP = {
    "SlotWidth": (END_CENTER[0] + 0.022, END_CENTER[1] + 0.010),
}
# A standalone cropped model view offers the tiny model-owned dimensions
# that a true detail child did not offer in the VN post-mount-screw recipe.
# The radius owns the upper row, with 3.2 mm nominal reason-to-witness air
# at a conservative 1.3 mm tiny-leg overrun.  The broad width sits below the
# crop so its dimension line cannot cross the native radius leader.
DETAIL_SCALE = (10.0, 1.0)
DETAIL_CENTER = (0.115, 0.058)
DETAIL_RADIUS_MM = 3.0
DETAIL_RADIUS = DETAIL_RADIUS_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
DETAIL_STATION = SEAT_STATION + RELIEF_WIDTH / 2.0
DETAIL_REFERENCE_MM = (0.0, 0.0, DETAIL_STATION)
DETAIL_KEEP = {
    "ReliefCornerRadius": (DETAIL_CENTER[0], 0.1015),
    "ReliefWidth": (DETAIL_CENTER[0], 0.0265),
    "ReliefLead": (0.075, 0.0955),
    "SeatEdgeBreak": (0.180, 0.0955),
}
DETAIL_LETTER = "A"
DETAIL_VIEW_LABEL = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]:g}:{DETAIL_SCALE[1]:g}"
)
DETAIL_LABEL_XY = (0.165, 0.055)
DETAIL_PARENT_LETTER_XY = (
    _sheet_x(DETAIL_STATION) + 0.014,
    SIDE_CENTER[1] + 0.019,
)
DETAIL_PARENT_RADIUS = DETAIL_RADIUS_MM * _S / 1000.0
# Sheet-space readbacks reject inference-snapped circles and an ignored move.
CIRCLE_TOL_M = 0.00005
DETAIL_VIEW_POSITION_TOLERANCE_M = 0.0001
ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# The thread callout's leader lands on the edge where the full thread meets
# the tip chamfer, the full-thread portion's own end edge in the side view (the
# relief-flank edge at the other end would read as pointing at the groove).
# The complete one-line note stays 4 mm left of the tip witness; its leader
# runs out left from the unchanged full-thread/tip edge.
THREAD_PICK = (THREAD_START_X, SIDE_CENTER[1] + 0.004)
THREAD_NOTE_XY = (
    TIP_X - 0.004 - len(THREAD_CALLOUT) * 0.0028,
    SIDE_CENTER[1] - 0.008,
)
# The running shoulder's lower flank, right of the Ø dimension line: above the
# shoulder the Ø value carries its mate callout, which the symbol's leader
# would run through (r1 layout audit).
FINISH_PICK = (UNDERHEAD_X - 0.050, 2.0 * SIDE_CENTER[1] - SHOULDER_TOP_Y)
FINISH_SYMBOL = (UNDERHEAD_X - 0.038, SIDE_CENTER[1] - 0.022)
# The under-head reference ends on a short construction witness lying ON the
# under-head annulus's edge (build_dt_crank_handle_pivot_screw); the curate
# leaves the sketch shown so its dimension prints, so the witness would draw
# its grey dash-dot over the black edge.  Drawn in the outline's black it IS
# the edge (draw_ch_fulcrum_keeper._blacken_reference_lines' recipe).
REFERENCE_SKETCH = "StationReference"
UNDER_HEAD_WITNESS_LEN = (HEAD_DIA - SHOULDER_DIA) / 2.0
REFERENCE_WITNESS_COLOR = 0  # COLORREF black, the outline's colour.
SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
REFERENCE_WITNESS_LEN_TOL = 0.01  # mm; the line is a fully defined sketch length
# A point on the shoulder face, clear of the Ø6.00 dimension line.
CENTERLINE_PICK = (UNDERHEAD_X - 0.080, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.352, 0.218)
# The single assembly-only note sits above the profile, clear of DETAIL A.
NOTES_XY = (0.016, 0.250)
AXIAL_DIMENSIONS = ("ThreadLength", "UnderHeadLocation", "OverallLength")


def _reference_line_in_view(view: Any, sketch_name: str, length_mm: float) -> Any:
    """The drawing-view instance of one reference sketch's construction line,
    chosen on the model (the sketch's one construction segment of that
    length) and mapped into ``view`` -- a point pick on the outline would
    resolve to the edge under it (draw_ch_fulcrum_keeper)."""
    native = _early_bound(view, "IView")
    model = native.ReferencedDocument
    if model is None:
        raise RuntimeError(f"{sketch_name}: the side view references no model")
    feature = _early_bound(model, "IPartDoc").FeatureByName(sketch_name)
    if feature is None:
        raise RuntimeError(f"{sketch_name}: no such feature in the screw model")
    sketch = _early_bound(
        _early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch"
    )
    matches = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        length = float(segment.GetLength()) * 1000.0
        if (
            bool(segment.ConstructionGeometry)
            and abs(length - length_mm) <= REFERENCE_WITNESS_LEN_TOL
        ):
            matches.append(segment)
    if len(matches) != 1:
        raise RuntimeError(
            f"{sketch_name}: {len(matches)} construction segments are "
            f"{length_mm:.3f} mm long; the witness must be exactly one"
        )
    in_view = native.GetCorresponding(matches[0])
    if in_view is None:
        raise RuntimeError(f"{sketch_name}: its witness has no instance in the side view")
    return _early_bound(in_view, "ISketchSegment")


@_telemetry.traced("drawing.crank_handle_pivot_screw.blacken_under_head_witness")
def _blacken_under_head_witness(adapter: Any, view: Any) -> None:
    """Draw the under-head witness in the outline's black."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the MHA-DT-032 side view for its witness")
    expected = UNDER_HEAD_WITNESS_LEN
    line = _reference_line_in_view(view, REFERENCE_SKETCH, expected)
    draw.ClearSelection2(True)
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection.CreateSelectData()
    selection_data.View = view
    if not line.Select4(False, selection_data):
        raise RuntimeError("failed to select the under-head witness")
    kind = int(selection.GetSelectedObjectType3(1, -1))
    if kind != SW_SEL_EXT_SKETCH_SEGS:
        raise RuntimeError(f"under-head witness pick resolved to type {kind}")
    segment = _early_bound(selection.GetSelectedObject6(1, -1), "ISketchSegment")
    length = float(segment.GetLength()) * 1000.0
    construction = bool(segment.ConstructionGeometry)
    if abs(length - expected) > REFERENCE_WITNESS_LEN_TOL or not construction:
        raise RuntimeError(
            f"under-head witness pick resolved to {segment.GetName()} "
            f"({length:.3f} mm, want {expected:.3f}; construction={construction})"
        )
    drawing.SetLineColor(REFERENCE_WITNESS_COLOR)
    draw.ClearSelection2(True)
    _telemetry.info("crank-handle-pivot-screw: under-head witness drawn black")
    draw.EditRebuild3()


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
) -> Any:
    """Sketch a view-owned circle from sheet coordinates, leaving it selected.

    As in the VN post-mount-screw crop, transform through the view sketch and
    use AddToDB so screen-space inference cannot snap the crop or parent mark.
    """
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    prior = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = prior
    if circle is None:
        raise RuntimeError(f"cannot sketch the {label} circle")
    # Convert the sheet tolerance to sketch units using the asked radius.
    asked = math.dist(points[0][:2], points[1][:2])
    tol = CIRCLE_TOL_M * asked / radius
    arc = _early_bound(circle, "ISketchArc")
    made = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    off = math.dist((float(made.X), float(made.Y)), points[0][:2])
    made_radius = float(arc.GetRadius())
    if off > tol or abs(made_radius - asked) > tol:
        raise RuntimeError(
            f"{label} circle landed off its ask: centre {off / asked * radius * 1000.0:.3f} mm "
            f"away, radius {made_radius / asked * radius * 1000.0:.3f} mm for "
            f"{radius * 1000.0:.3f} mm (tolerance {CIRCLE_TOL_M * 1000.0:.2f} mm)"
        )
    return circle


def _activate(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _note_texts(view: Any) -> list[str]:
    return [
        str(_early_bound(note, "INote").GetText())
        for note in (_early_bound(view, "IView").GetNotes() or ())
    ]


def cropped_relief_view(adapter: Any) -> Any:
    """Centre and crop a standalone 10:1 *Right model view at the relief.

    The VN crop pattern keeps the model dimensions available for native
    import, unlike a true detail child.  Crop2 consumes the selected circle
    in the activated view's sketch; both placement and crop are read back.
    """
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Right", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"relief view scale {ratio!r}, expected {DETAIL_SCALE!r}")
    reference = tuple(value / 1000.0 for value in DETAIL_REFERENCE_MM)
    relief = model_point_in_view(adapter, view, reference, label="relief view reference")
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + DETAIL_CENTER[i] - relief[i] for i in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("cannot move the relief view onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, reference, label="relief view reference")
    if math.dist(center, DETAIL_CENTER) > DETAIL_VIEW_POSITION_TOLERANCE_M:
        raise RuntimeError(
            f"relief view reference sits at {center!r}, not {DETAIL_CENTER!r}"
        )
    _activate(adapter, view, label="relief view")
    _sketch_circle(adapter, view, center, DETAIL_RADIUS, label="relief view crop")
    status = int(view.Crop2(False, False, 5))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"relief view {view_name(adapter, view)!r}: {ratio[0]:g}:{ratio[1]:g}, "
        f"Crop2 status {status}, IsCropped {cropped}"
    )
    if status != _CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"relief view is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    return view


def import_relief_diameter(adapter: Any, side: Any) -> Any:
    """Import the hidden true-circle carrier face-on without showing it in SIDE."""
    donor = place_view(
        adapter, str(SOURCE), "*Front", 0.030, 0.230, scale=VIEW_SCALE
    )
    annotations = curate_view_dimensions(
        adapter,
        donor,
        keep={"ReliefDia": SIDE_KEEP["ReliefDia"]},
        view_label="relief diameter donor",
        dimensions_by_feature={
            RELIEF_DIAMETER_SKETCH: DRAWING_DIMENSIONS[RELIEF_DIAMETER_SKETCH]
        },
    )
    if len(annotations) != 1 or dimension_name(adapter, annotations[0]) != "ReliefDia":
        raise RuntimeError("MHA-DT-032 relief diameter donor did not own exactly ReliefDia")
    moved = move_model_dimension(
        adapter, annotations[0], side, SIDE_KEEP["ReliefDia"], source_view=donor
    )
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("MHA-DT-032 relief diameter donor was not deleted")
    return moved


def _assert_relief_diameter_carrier(annotation: Any) -> None:
    """Reject styled linear carriers and unrelated circles before styling/ink."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    kind = int(display.Type2)  # swDimensionType_e.swDiameterDimension = 6
    if kind != 6:
        raise RuntimeError(
            f"MHA-DT-032 relief diameter wrong native type: Type2={kind!r}, expected 6"
        )
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError("MHA-DT-032 relief diameter missing native model dimension")
    dimension = _early_bound(raw, "IDimension")
    full_name = str(dimension.FullName)
    if full_name.split("@")[:2] != ["ReliefDia", RELIEF_DIAMETER_SKETCH]:
        raise RuntimeError(
            "MHA-DT-032 relief diameter wrong native owner: "
            f"FullName={full_name!r}, expected ReliefDia@{RELIEF_DIAMETER_SKETCH}"
        )
    value = float(dimension.SystemValue)
    expected = RELIEF_DIA / 1000.0
    if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(
            "MHA-DT-032 relief diameter wrong native value: "
            f"FullName={full_name!r}, SystemValue={value!r}, expected={expected!r}"
        )


def _assert_relief_diameter_leader(
    segments: Sequence[_drawing_leaders.Segment],
    axial_segments: Mapping[str, Sequence[_drawing_leaders.Segment]],
) -> None:
    """Require actual floor landing, corner air and pairwise axial separation."""
    groups = {"ReliefDia": segments, **axial_segments}
    if not segments:
        raise RuntimeError(
            f"MHA-DT-032 relief diameter has no native leader ink; segments={groups!r}"
        )
    for name in AXIAL_DIMENSIONS:
        if name not in axial_segments:
            raise RuntimeError(
                "MHA-DT-032 relief axial annotation missing: "
                f"{name}; segments={groups!r}"
            )
        if not axial_segments[name]:
            raise RuntimeError(
                f"MHA-DT-032 relief axial native ink empty: {name}; segments={groups!r}"
            )
    floor_left, floor_right = sorted(
        (
            _sheet_x(RELIEF_END_STATION - RELIEF_CORNER_RADIUS_MAX),
            _sheet_x(SEAT_STATION + RELIEF_LEAD),
        )
    )
    floor_y = SIDE_CENTER[1] - RELIEF_DIA * _S / 2000.0
    if not any(
        math.hypot(
            x - min(max(x, floor_left), floor_right),
            y - floor_y,
        )
        <= 0.00015
        for segment in segments
        for x, y in segment
    ):
        raise RuntimeError(
            "MHA-DT-032 relief diameter leader does not land on the lower groove floor; "
            f"floor=({floor_left!r}, {floor_y!r})..({floor_right!r}, {floor_y!r}); "
            f"segments={groups!r}"
        )
    shoulder_bottom = SIDE_CENTER[1] - SHOULDER_DIA * _S / 2000.0
    thread_bottom = SIDE_CENTER[1] - THREAD_MODEL_DIA * _S / 2000.0
    for (x0, y0), (x1, y1) in segments:
        if min(x0, x1) <= SEAT_X <= max(x0, x1):
            if x0 == x1:
                crossing_y = max(y0, y1)
            else:
                crossing_y = y0 + (SEAT_X - x0) * (y1 - y0) / (x1 - x0)
            if crossing_y > shoulder_bottom - 0.002:
                raise RuntimeError(
                    "MHA-DT-032 relief diameter leader crosses the seat face/witness "
                    "instead of passing below its corner; "
                    f"crossing=({SEAT_X!r}, {crossing_y!r}), "
                    f"maximum_y={shoulder_bottom - 0.002!r}; segments={groups!r}"
                )
        if min(x0, x1) <= RELIEF_END_X <= max(x0, x1):
            if x0 == x1:
                crossing_y = max(y0, y1)
            else:
                crossing_y = y0 + (RELIEF_END_X - x0) * (y1 - y0) / (x1 - x0)
            if crossing_y > thread_bottom - 0.002:
                raise RuntimeError(
                    "MHA-DT-032 relief diameter leader crosses the thread-side corner "
                    "instead of passing below its corner; "
                    f"crossing=({RELIEF_END_X!r}, {crossing_y!r}), "
                    f"maximum_y={thread_bottom - 0.002!r}; segments={groups!r}"
                )
    # Baseline references legitimately share their tip witness.  Compare
    # Root-versus-each only, never foreign-versus-foreign.
    for name in AXIAL_DIMENSIONS:
        foreign = axial_segments[name]
        crossings = _drawing_leaders.leader_crossings(
            {"ReliefDia": segments, name: foreign}
        )
        if crossings:
            crossing_segments = [
                (diameter, axial)
                for diameter in segments
                for axial in foreign
                if _drawing_leaders.segments_cross(diameter, axial)
            ]
            raise RuntimeError(
                f"MHA-DT-032 relief diameter foreign axial ink: {name}; "
                f"crossings={crossings!r}; crossing_segments={crossing_segments!r}; "
                f"segments={groups!r}"
            )


def style_relief_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Style the true-circle carrier and prove rebuilt ink clears all axial groups."""
    remaining = {
        "ReliefDia": SIDE_KEEP["ReliefDia"],
        "ReliefLead": DETAIL_KEEP["ReliefLead"],
        "SeatEdgeBreak": DETAIL_KEEP["SeatEdgeBreak"],
    }
    relief_diameter = None
    axial_annotations = dict.fromkeys(AXIAL_DIMENSIONS)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name in AXIAL_DIMENSIONS:
            axial_annotations[name] = annotation
            continue
        xy = remaining.pop(name, None)
        if xy is None:
            continue
        if name == "ReliefDia":
            _assert_relief_diameter_carrier(annotation)
            _drawing_leaders.set_near_side_diameter(
                annotation, "MHA-DT-032 relief diameter"
            )
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            if not bool(display.Diametric):
                raise RuntimeError("MHA-DT-032 relief diameter native style lost Diametric")
            relief_diameter = annotation
        else:
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            display.CenterText = False
            display.ArrowSide = ARROWS_OUTSIDE
        if not annotation.SetPosition2(*xy, 0.0):
            raise RuntimeError(f"cannot position the MHA-DT-032 {name} text")
        if name != "ReliefDia" and (
            int(display.ArrowSide) != ARROWS_OUTSIDE or bool(display.CenterText)
        ):
            raise RuntimeError(
                f"{name} arrows/centring did not take: ArrowSide {display.ArrowSide}, "
                f"CenterText {display.CenterText}"
            )
    if remaining:
        raise RuntimeError(f"relief dimension styles not applied: {sorted(remaining)}")
    for name in AXIAL_DIMENSIONS:
        if axial_annotations[name] is None:
            raise RuntimeError(
                "MHA-DT-032 relief axial annotation missing: "
                f"{name}; annotations="
                f"{sorted(key for key, value in axial_annotations.items() if value is not None)!r}"
            )
    adapter.currentModel.EditRebuild3()
    _assert_relief_diameter_leader(
        _drawing_leaders.dimension_segments(relief_diameter),
        {
            name: _drawing_leaders.dimension_segments(axial_annotations[name])
            for name in AXIAL_DIMENSIONS
        },
    )


def label_relief_view(adapter: Any, view: Any) -> None:
    """Give the cropped model view its own two-line DETAIL A scale label."""
    _activate(adapter, view, label="relief view")
    if add_note(adapter, DETAIL_VIEW_LABEL, *DETAIL_LABEL_XY) is None:
        raise RuntimeError("failed to add the relief view label")
    texts = _note_texts(view)
    if texts.count(DETAIL_VIEW_LABEL) != 1:
        raise RuntimeError(
            f"relief view label did not land in the relief view: its notes are {texts!r}"
        )


def mark_relief_on_side(adapter: Any, side: Any) -> None:
    """Circle the same model reference on SIDE and add its view-owned A."""
    _activate(adapter, side, label="side view")
    reference = tuple(value / 1000.0 for value in DETAIL_REFERENCE_MM)
    center = model_point_in_view(adapter, side, reference, label="side relief mark")
    _sketch_circle(
        adapter, side, center, DETAIL_PARENT_RADIUS, label="side relief mark"
    )
    adapter.currentModel.ClearSelection2(True)
    if add_note(adapter, DETAIL_LETTER, *DETAIL_PARENT_LETTER_XY) is None:
        raise RuntimeError("failed to letter the side view's relief mark")
    texts = _note_texts(side)
    if texts.count(DETAIL_LETTER) != 1:
        raise RuntimeError(
            f"side relief letter did not land in the side view: its notes are {texts!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-pivot-screw source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Pivot Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"crank handle pivot; slotted shoulder screw; {THREAD_SIZE}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    detail = cropped_relief_view(adapter)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, detail, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep={name: xy for name, xy in SIDE_KEEP.items() if name != "ReliefDia"},
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="head-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="relief detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations.append(import_relief_diameter(adapter, side))
    annotations = [*side_annotations, *end_annotations, *detail_annotations]
    # Each native dimension carries its own angle or functional reason below
    # the value; the two tiny legs remain separate in the enlarged view.
    set_dimension_callouts(
        adapter,
        annotations,
        {
            "ReliefDia": RELIEF_DIA_CALLOUT,
            "ReliefLead": RELIEF_LEAD_CALLOUT,
            "ReliefCornerRadius": RELIEF_CORNER_CALLOUT,
            "SeatEdgeBreak": SEAT_EDGE_BREAK_CALLOUT,
            "TipChamfer": CHAMFER_CALLOUT,
            "HeadDia": HEAD_DIA_CALLOUT,
            "HeadLength": HEAD_LENGTH_CALLOUT,
            "UnderHeadLocation": UNDER_HEAD_CALLOUT,
        },
        location="below",
    )
    # ABOVE is single-line only in the native display: keep the root reason
    # here, separate from the relief's two BELOW seating/mate lines.
    # The running mate's to-suit rule stays above the shoulder value.
    set_dimension_callouts(
        adapter,
        annotations,
        {
            "ReliefDia": RELIEF_DIA_ROOT_CALLOUT,
            "ShoulderDia": SHOULDER_CALLOUT,
        },
        location="above",
    )
    style_relief_dimensions(adapter, annotations)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-DT-32 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-DT-32 {name}")
    _blacken_under_head_witness(adapter, side)

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-DT-32 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-DT-32 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-DT-32 thread callout",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_shoulder"),
        label="MHA-DT-32 pivot-shoulder finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    label_relief_view(adapter, detail)
    mark_relief_on_side(adapter, side)
    _activate(adapter, side, label="side view notes")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Pivot Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
