r"""Create the MHA-DT-32 crank handle pivot screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the running-fit shoulder keeps its
native size band and one bearing-surface finish, the head keeps the two bands
the MHA-DT-35 cup sets, and the tip chamfer and seat edge break print as
single MAX limits.  The relief Ø retains its native size band, the relief
lead its native limits and the thread-side floor radius its native MAX;
every size keeps its part-authored places.
The actual under-head face remains at its original station between a real
concave R0.1 MAX and a native 0.11–0.26 X45 LIMIT outer bevel, whose explicit
range overrides the generic edge break only there. Both features retain
their part-owned carriers, limits and precision and their settled actual
ink must clear each other and the head/slot/shoulder/fitted-span corridors.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the thread tip on
the left and the slotted head on the right.  Axial locations baseline from the
tip, the one faced end (see ``dt_crank_handle_pivot_screw_spec``).  The
head-end view is the ``*Back`` orientation, which is exactly the third-angle
RIGHT view of that profile, so it sits on the profile's axis to its right and
shows the slot.
The relief diameter, lead, thread-side floor radius and modelled seat edge
break read in a standalone cropped 10:1 ``*Right`` model view, labelled
DETAIL A and circled on the side view.  The ordinary associative two-arrow
diameter crosses both neck surfaces within the straight floor; its full text
block stays below the model.  The width stays on SIDE, avoiding witnesses
through that text. Rebuilt native diameter ink must clear both groove corners
and each of the other three detail dimensions. Its validated native metric
text hulls also keep 3 mm from the model/spec lower-thread profile (not
pixel-exact PDF boxes). Every printable generated annotation's actual text,
symbol and leader ink stays inside the unchanged ASME inner border, every
foreign DETAIL pair stays uncrossed, and the tip's shared thread/file-and-stake
leader misses both tip-reference witnesses in both native inventories.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_pivot_screw.py dt-crank-handle-pivot-screw
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import math
import sys
import textwrap
from typing import Any, Sequence

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
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
    set_dimension_callouts,
    set_reference_dimension,
)
import _drawing_layout_audit
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
import _drawing_leaders
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_resolve import resolve_faces
import _layout_audit
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_crank_handle_pivot_screw_spec import (
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION_BY_NAME,
    HEAD_DIA,
    HEAD_DIA_CALLOUT,
    HEAD_LENGTH,
    HEAD_LENGTH_CALLOUT,
    HEAD_OUTER_CHAMFER,
    HEAD_OUTER_CHAMFER_BAND,
    HEAD_OUTER_CHAMFER_CALLOUT,
    HEAD_OUTER_CHAMFER_MAX,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
    RELIEF_CORNER_CALLOUT,
    RELIEF_CORNER_RADIUS_MAX,
    RELIEF_DIA,
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
    UNDER_HEAD_CORNER_RADIUS_MAX,
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
# inner witness cannot cross its long line. The two plain tip-baseline
# references stay below the profile, 19 mm apart; the local fitted-span REF
# owns its own to-suit row. Actual rebuilt ink, not a requested text centre
# or assumed native offset, gates the relief and tip leaders below.
_ROW_Y = (SIDE_CENTER[1] + 0.035, SIDE_CENTER[1] - 0.055, SIDE_CENTER[1] - 0.074)
# The 4-mm head prints 12 mm long, narrower than its ~21-mm value, so the head
# length, the head Ø and the slot depth stand outside the head face rather
# than between extension lines that would strike their text (v43 render).
# Each head band's one-line reason callout is centred under its value.
# The head-length reason's measured left edge clears the head Ø arrow stub
# at 307.1 mm by 5.6 mm; its right edge stays inside the 419.1 mm border.
HEAD_LENGTH_TEXT_X = 0.360
HEAD_DIA_TEXT_X = HEAD_FACE_X + 0.006 + len(HEAD_DIA_CALLOUT) * 0.0028 / 2.0
SLOT_DEPTH_TEXT_X = HEAD_FACE_X + 0.012
SIDE_KEEP = {
    "ThreadLength": ((TIP_X + SEAT_X) / 2.0, _ROW_Y[0]),
    "HeadLength": (HEAD_LENGTH_TEXT_X, 0.1765),
    # The under-head face located from the tip, like every axial location.
    "UnderHeadLocation": ((TIP_X + UNDERHEAD_X) / 2.0, _ROW_Y[1]),
    # Existing model-owned fitted span, local REF only; its to-suit block
    # shares the 63 column rather than centring over the physical span.
    "ShoulderLength": ((TIP_X + UNDERHEAD_X) / 2.0, 0.1575),
    "OverallLength": ((TIP_X + HEAD_FACE_X) / 2.0, _ROW_Y[2]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The shoulder's dimension line
    # crosses the shoulder near its thread end; the head's stands clear of the
    # head face, left of the end view.
    "ShoulderDia": (SEAT_X + 0.056, SIDE_CENTER[1] + 0.030),
    # The head Ø's value stands a little above the axis so its callout below
    # stays between the head's extension lines.
    "HeadDia": (HEAD_DIA_TEXT_X, SIDE_CENTER[1] + 0.0025),
    "ReliefWidth": ((SEAT_X + RELIEF_END_X) / 2.0, SIDE_CENTER[1] - 0.030),
    # The native tip leg and X45 reason stand above-left, outside the thread
    # profile.
    "TipChamfer": (TIP_X - 0.020, SIDE_CENTER[1] + 0.020),
    # The slot shows as a notch in the head face; its depth reads above it,
    # outside the head face.
    "SlotDepth": (SLOT_DEPTH_TEXT_X, SIDE_CENTER[1] + 0.026),
    "UnderHeadCornerRadius": (0.215, 0.212),
    "HeadOuterChamfer": (0.245, 0.250),
}
# The 3-mm slot is narrower than the text, so the value stands above its
# extension lines rather than between them.
END_KEEP = {
    "SlotWidth": (END_CENTER[0] + 0.022, END_CENTER[1] + 0.010),
}
# A standalone cropped model view offers the tiny model-owned dimensions
# that a true detail child did not offer in the dt-vn-post-mount-screw recipe.
# The radius stays above the upper thread fillet; the lead reads below-right
# and the seat break above-right so their native leaders cannot interleave.
# The width's long witnesses remain on SIDE.
DETAIL_SCALE = (10.0, 1.0)
DETAIL_CENTER = (0.320, 0.130)
DETAIL_RADIUS_MM = 3.0
DETAIL_RADIUS = DETAIL_RADIUS_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
DETAIL_STATION = SEAT_STATION + RELIEF_WIDTH / 2.0
DETAIL_REFERENCE_MM = (0.0, 0.0, DETAIL_STATION)
DETAIL_KEEP = {
    "ReliefCornerRadius": (0.320, 0.1635),
    "ReliefLead": (0.378, 0.106),
    "SeatEdgeBreak": (0.378, 0.1615),
    "ReliefDia": (0.320, 0.0905),
}
DETAIL_LETTER = "A"
DETAIL_VIEW_LABEL = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]:g}:{DETAIL_SCALE[1]:g}"
)
DETAIL_LABEL_XY = (0.342, 0.0845)
DETAIL_PARENT_LETTER_XY = (
    _sheet_x(DETAIL_STATION) - 0.002,
    SIDE_CENTER[1] + DETAIL_RADIUS_MM * _S / 1000.0 + 0.0055,
)
DETAIL_PARENT_RADIUS = DETAIL_RADIUS_MM * _S / 1000.0
# Sheet-space readbacks reject inference-snapped circles and an ignored move.
CIRCLE_TOL_M = 0.00005
DETAIL_VIEW_POSITION_TOLERANCE_M = 0.0001
ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
SOLID_LEADER_ALIGNED_TEXT = 1  # swDisplayDimensionLeaderText_e
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# Only the leader changes: land on the real tip-face circular EDGE projection,
# above the 63/67 witness tops and below the upper ThreadLength witness.
# The complete seven-line block stays 4 mm left of the tip witness. Wrap
# only the assembly instruction: the thread designation remains one line.
# Final settlement checks actual display/registered leader ink and arrows;
# this requested pick alone is not proof of the solved native route.
THREAD_PICK = (TIP_X, SIDE_CENTER[1] + 0.003)
THREAD_NOTE_TEXT = "\n".join(
    [THREAD_CALLOUT, *textwrap.wrap(
        DRAWING_NOTES, width=13, break_long_words=False, break_on_hyphens=False
    )]
)
THREAD_NOTE_XY = (
    TIP_X - 0.004 - max(map(len, THREAD_NOTE_TEXT.splitlines())) * 0.0028,
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
UNDER_HEAD_WITNESS_LEN = (
    (HEAD_DIA - SHOULDER_DIA) / 2.0
    - HEAD_OUTER_CHAMFER_MAX - UNDER_HEAD_CORNER_RADIUS_MAX
)
REFERENCE_WITNESS_COLOR = 0  # COLORREF black, the outline's colour.
SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
REFERENCE_WITNESS_LEN_TOL = 0.01  # mm; the line is a fully defined sketch length
# A point on the shoulder face, clear of the Ø6.00 dimension line.
CENTERLINE_PICK = (UNDERHEAD_X - 0.080, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.352, 0.218)
DETAIL_DIMENSIONS = ("ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius")
UNDER_HEAD_DIMENSIONS = ("UnderHeadCornerRadius", "HeadOuterChamfer")
UNDER_HEAD_FOREIGN_DIMENSIONS = ("HeadDia", "SlotDepth", "ShoulderDia", "ShoulderLength", "HeadLength")


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
        raise RuntimeError("failed to activate the MHA-DT-32 side view for its witness")
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

    As in the dt-vn-post-mount-screw crop, transform through the view sketch and
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
    """Canonicalize native CRLF without relaxing exact note text or ownership."""
    return [
        str(_early_bound(note, "INote").GetText()).replace("\r\n", "\n")
        for note in (_early_bound(view, "IView").GetNotes() or ())
    ]


def cropped_relief_view(adapter: Any) -> Any:
    """Centre and crop a standalone 10:1 *Right model view at the relief.

    The dt-vn-post-mount-screw crop keeps the model dimensions available for native
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


def _assert_relief_diameter_carrier(annotation: Any) -> None:
    """Require the associative native diameter imported directly into DETAIL."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    kind = int(display.Type2)  # swDimensionType_e.swDiameterDimension = 6
    if kind != 6:
        raise RuntimeError(
            f"MHA-DT-32 relief diameter wrong native type: Type2={kind!r}, expected 6"
        )
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError("MHA-DT-32 relief diameter missing native model dimension")
    dimension = _early_bound(raw, "IDimension")
    full_name = str(dimension.FullName)
    if full_name.split("@")[:2] != ["ReliefDia", "ScrewProfile"]:
        raise RuntimeError(
            "MHA-DT-32 relief diameter wrong native owner: "
            f"FullName={full_name!r}, expected ReliefDia@ScrewProfile"
        )
    value = float(dimension.SystemValue)
    expected = RELIEF_DIA / 1000.0
    if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-9):
        raise RuntimeError(
            "MHA-DT-32 relief diameter wrong native value: "
            f"FullName={full_name!r}, SystemValue={value!r}, expected={expected!r}"
        )


def _assert_relief_diameter_style(display: Any) -> None:
    """Read every native style setting, including the explicit second arrow."""
    actual = {
        "Diametric": bool(display.Diametric),
        "ArrowSide": int(display.ArrowSide),
        "CenterText": bool(display.CenterText),
        "SolidLeader": bool(display.SolidLeader),
        "GetUseDocBrokenLeader": bool(display.GetUseDocBrokenLeader()),
        "GetBrokenLeader2": int(display.GetBrokenLeader2()),
        "GetUseDocSecondArrow": bool(display.GetUseDocSecondArrow()),
        "GetSecondArrow": bool(display.GetSecondArrow()),
    }
    expected = {
        "Diametric": True,
        "ArrowSide": ARROWS_INSIDE,
        "CenterText": False,
        "SolidLeader": True,
        "GetUseDocBrokenLeader": False,
        "GetBrokenLeader2": SOLID_LEADER_ALIGNED_TEXT,
        "GetUseDocSecondArrow": False,
        "GetSecondArrow": True,
    }
    if actual != expected:
        raise RuntimeError(
            "MHA-DT-32 relief diameter native two-arrow style did not persist: "
            f"actual={actual!r}; expected={expected!r}"
        )


def _assert_relief_diameter_ink(
    segments: Sequence[_drawing_leaders.Segment],
    detail_segments: Mapping[str, Sequence[_drawing_leaders.Segment]],
) -> None:
    """Prove the conventional diameter in DETAIL, not a near-side surrogate.

    Coordinates are actual rebuilt sheet ink.  A normal 1 mm extension gap
    is measured along the extension at a real floor endpoint, never used as
    slack in the physical neck's Y coordinate.
    """
    groups = {"ReliefDia": segments, **detail_segments}
    if not segments:
        raise RuntimeError(
            f"MHA-DT-32 relief diameter has no native ink; segments={groups!r}"
        )
    for name in DETAIL_DIMENSIONS:
        if name not in detail_segments:
            raise RuntimeError(
                f"MHA-DT-32 relief detail annotation missing: {name}; segments={groups!r}"
            )
        if not detail_segments[name]:
            raise RuntimeError(
                f"MHA-DT-32 relief detail native ink empty: {name}; segments={groups!r}"
            )
        if not all(
            math.isfinite(value)
            for stroke in detail_segments[name] for point in stroke for value in point
        ):
            raise RuntimeError(
                f"MHA-DT-32 relief detail nonfinite native ink: {name}; segments={groups!r}"
            )
    if not all(math.isfinite(value) for stroke in segments for point in stroke for value in point):
        raise RuntimeError(
            f"MHA-DT-32 relief diameter nonfinite native ink; segments={groups!r}"
        )
    scale = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
    cx, cy = DETAIL_CENTER
    floor_left = round(cx + (DETAIL_STATION - RELIEF_END_STATION + RELIEF_CORNER_RADIUS_MAX) * scale, 12)
    floor_right = round(cx + (DETAIL_STATION - SEAT_STATION - RELIEF_LEAD) * scale, 12)
    neck_bottom, neck_top = (cy - RELIEF_DIA * scale / 2.0, cy + RELIEF_DIA * scale / 2.0)
    tol = 0.00015
    # No blanket exemption for horizontal extensions: every root stroke must
    # clear the physical shoulder and thread at their respective corners.
    for label, station, diameter in (
        ("seat face/witness", SEAT_STATION, SHOULDER_DIA),
        ("thread-side corner", RELIEF_END_STATION, THREAD_MODEL_DIA),
    ):
        x = round(cx + (DETAIL_STATION - station) * scale, 12)
        bottom, top = cy - diameter * scale / 2.0, cy + diameter * scale / 2.0
        forbidden = (bottom - 0.002, top + 0.002)
        for (x0, y0), (x1, y1) in segments:
            if not min(x0, x1) <= x <= max(x0, x1):
                continue
            if x0 == x1:
                low, high = sorted((y0, y1))
                if high <= forbidden[0] or low >= forbidden[1]:
                    continue
                crossing_y = max(low, forbidden[0])
            else:
                crossing_y = y0 + (x - x0) * (y1 - y0) / (x1 - x0)
                if crossing_y <= forbidden[0] or crossing_y >= forbidden[1]:
                    continue
            raise RuntimeError(
                f"MHA-DT-32 relief diameter ink crosses the {label}; "
                f"crossing=({x!r}, {crossing_y!r}), "
                f"physical_y=({bottom!r}, {top!r}), clearance=0.002; segments={groups!r}"
            )
    verticals = [
        stroke for stroke in segments
        if abs(stroke[0][0] - stroke[1][0]) <= 1e-9
        and min(stroke[0][1], stroke[1][1]) <= neck_bottom + tol
        and max(stroke[0][1], stroke[1][1]) >= neck_top - tol
    ]
    if not verticals or any(
        not floor_left <= point[0] <= floor_right
        for stroke in verticals for point in stroke
    ):
        raise RuntimeError(
            "MHA-DT-32 relief diameter lacks a vertical stroke within the straight floor "
            "spanning both neck surfaces; "
            f"floor_x=({floor_left!r}, {floor_right!r}), "
            f"neck_y=({neck_bottom!r}, {neck_top!r}), tolerance={tol!r}; segments={groups!r}"
        )
    for surface, y in (("lower", neck_bottom), ("upper", neck_top)):
        associated = False
        for stroke in verticals:
            x = stroke[0][0]
            direct = any(math.dist(point, (x, y)) <= tol for point in stroke)
            extensions = [
                extension for extension in segments
                if abs(extension[0][1] - extension[1][1]) <= 1e-9
                and abs(extension[0][1] - y) <= tol
                and abs(extension[1][0] - extension[0][0]) > tol
            ]
            connected = False
            for extension in extensions:
                start, end = sorted(extension, key=lambda point: abs(point[0] - x), reverse=True)
                # The model-facing end must be on the real straight floor,
                # or precisely one normal gap from a real floor endpoint.
                on_floor = floor_left <= start[0] <= floor_right
                gapped_endpoint = any(
                    abs(start[0] - (edge + gap)) <= tol
                    for edge in (floor_left, floor_right) for gap in (-0.001, 0.001)
                )
                reaches_line = min(start[0], end[0]) <= x <= max(start[0], end[0])
                if not reaches_line or not (on_floor or gapped_endpoint):
                    raise RuntimeError(
                        f"MHA-DT-32 relief diameter floating {surface} neck extension; "
                        f"extension={extension!r}, expected_surface_y={y!r}, "
                        f"floor_x=({floor_left!r}, {floor_right!r}), dimension_x={x!r}; "
                        f"segments={groups!r}"
                    )
                connected = True
            associated |= direct or connected
        if not associated:
            raise RuntimeError(
                f"MHA-DT-32 relief diameter missing {surface} neck association; "
                f"expected_surface_y={y!r}, floor_x=({floor_left!r}, {floor_right!r}), "
                f"tolerance={tol!r}; segments={groups!r}"
            )
    # Foreign dimensions may share their own witnesses.  Only root-versus-
    # each is relevant; retain exact offending strokes in a native refusal.
    for name in DETAIL_DIMENSIONS:
        foreign = detail_segments[name]
        crossings = _drawing_leaders.leader_crossings({"ReliefDia": segments, name: foreign})
        if crossings:
            crossing_segments = [
                (diameter, other) for diameter in segments for other in foreign
                if _drawing_leaders.segments_cross(diameter, other)
            ]
            raise RuntimeError(
                f"MHA-DT-32 relief diameter foreign detail ink: {name}; "
                f"crossings={crossings!r}; crossing_segments={crossing_segments!r}; "
                f"segments={groups!r}"
            )


def style_relief_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Author and read back the native two-arrow Ø and all four DETAIL groups."""
    remaining = {name: DETAIL_KEEP[name] for name in ("ReliefDia", "ReliefLead", "SeatEdgeBreak")}
    relief_diameter = None
    detail_annotations = dict.fromkeys(DETAIL_DIMENSIONS)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name in detail_annotations:
            detail_annotations[name] = annotation
        xy = remaining.pop(name, None)
        if xy is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name == "ReliefDia":
            _assert_relief_diameter_carrier(annotation)
            display.Diametric = True
            display.ArrowSide = ARROWS_INSIDE
            display.CenterText = False
            display.SetSecondArrow(False, True)
            display.SolidLeader = True
            status = int(display.SetBrokenLeader2(False, SOLID_LEADER_ALIGNED_TEXT))
            if status != 0:
                raise RuntimeError(
                    "MHA-DT-32 relief diameter solid aligned leader rejected: "
                    f"SetBrokenLeader2 status={status!r}"
                )
            _assert_relief_diameter_style(display)
            relief_diameter = annotation
        else:
            display.CenterText = False
            display.ArrowSide = ARROWS_OUTSIDE
        if not annotation.SetPosition2(*xy, 0.0):
            raise RuntimeError(f"cannot position the MHA-DT-32 {name} text")
        if name != "ReliefDia" and (
            int(display.ArrowSide) != ARROWS_OUTSIDE or bool(display.CenterText)
        ):
            raise RuntimeError(
                f"{name} arrows/centring did not take: ArrowSide {display.ArrowSide}, "
                f"CenterText {display.CenterText}"
            )
    if remaining:
        raise RuntimeError(f"relief dimension styles not applied: {sorted(remaining)}")
    for name in DETAIL_DIMENSIONS:
        if detail_annotations[name] is None:
            raise RuntimeError(
                f"MHA-DT-32 relief detail annotation missing: {name}; annotations="
                f"{sorted(key for key, value in detail_annotations.items() if value is not None)!r}"
            )
    adapter.currentModel.EditRebuild3()
    _assert_relief_diameter_carrier(relief_diameter)
    _assert_relief_diameter_style(
        _early_bound(relief_diameter.GetSpecificAnnotation(), "IDisplayDimension")
    )
    _assert_relief_diameter_ink(
        _drawing_leaders.dimension_segments(relief_diameter),
        {name: _drawing_leaders.dimension_segments(detail_annotations[name]) for name in DETAIL_DIMENSIONS},
    )


def _assert_under_head_carrier(annotation: Any, name: str) -> None:
    """Part-owned radius/axial leg, native bounds and precision, no value override."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(f"{name}: missing native model dimension")
    dimension = _early_bound(raw, "IDimension")
    expected_type = (5,) if name == "UnderHeadCornerRadius" else (2, 11)
    expected_value = UNDER_HEAD_CORNER_RADIUS_MAX if name == "UnderHeadCornerRadius" else HEAD_OUTER_CHAMFER
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    upper, lower = (0.0, 0.0) if name == "UnderHeadCornerRadius" else HEAD_OUTER_CHAMFER_BAND
    if (
        str(dimension.FullName).split("@")[:2] != [name, "ScrewProfile"]
        or int(display.Type2) not in expected_type
        or bool(display.GetOverride())
        or not math.isclose(float(dimension.SystemValue), expected_value / 1000.0, rel_tol=0.0, abs_tol=1e-9)
        or int(tolerance.Type) != (6 if name == "UnderHeadCornerRadius" else 3)
        or not math.isclose(float(tolerance.GetMinValue()), lower / 1000.0, rel_tol=0.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), upper / 1000.0, rel_tol=0.0, abs_tol=1e-12)
        or int(display.GetPrimaryPrecision2()) != DRAWING_PRECISION_BY_NAME[name]
        or int(display.GetPrimaryTolPrecision2()) != DRAWING_PRECISION_BY_NAME[name]
    ):
        raise RuntimeError(f"{name}: native owner/type/value/bounds/precision drift")


def style_under_head_dimensions(adapter: Any, annotations: Sequence[Any]) -> None:
    """Keep the tiny bevel's native witnesses outside its limits/reason block."""
    matches = {name: [] for name in UNDER_HEAD_DIMENSIONS}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name in matches:
            matches[name].append(annotation)
    for name, records in matches.items():
        if len(records) != 1:
            raise RuntimeError(f"{name}: expected one native under-head annotation; count={len(records)}")
        annotation = records[0]
        _assert_under_head_carrier(annotation, name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name == "HeadOuterChamfer":
            display.CenterText = False
            display.ArrowSide = ARROWS_OUTSIDE
        if not annotation.SetPosition2(*SIDE_KEEP[name], 0.0):
            raise RuntimeError(f"{name}: cannot position native under-head text")
    adapter.currentModel.EditRebuild3()
    for name, records in matches.items():
        _assert_under_head_carrier(records[0], name)
        if name == "HeadOuterChamfer":
            display = _early_bound(records[0].GetSpecificAnnotation(), "IDisplayDimension")
            if bool(display.CenterText) or int(display.ArrowSide) != ARROWS_OUTSIDE:
                raise RuntimeError(f"{name}: native arrows/centring did not persist")


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


def _add_shoulder_finish(adapter: Any, view: Any) -> None:
    """Attach Ra to the part-owned face, with the original flank landing."""
    # R14 lost silhouette ownership after rebuild.  Resolve the same face the
    # part PMI controls, and let the separate landing readback pin the flank.
    control = surface_finish_by_key(SURFACE_FINISHES, "pivot_shoulder")
    document = _early_bound(
        _early_bound(view, "IView").ReferencedDocument, "IModelDoc2"
    )
    face = resolve_faces(document, {control.key: control.face})[control.key]
    add_surface_finish(
        adapter,
        view,
        entity=face,
        entity_type="FACE",
        leader_attach_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=control,
        label="MHA-DT-32 pivot-shoulder finish",
        char_height=0.0025,
    )


def _annotation_ink_errors(annotation: Mapping[str, Any], label: str) -> list[str]:
    """Check actual native primitives, never substitute an anchor or font guess.

    Text bounds use reported DisplayData origin/width/height/angle, not exact
    exported-PDF glyph pixels. Native renders and the exported audit remain
    the final authority for visual clearance.
    """
    errors: list[str] = []
    display = annotation.get("display")
    if not isinstance(display, Mapping) or not display:
        return [f"{label}: missing actual display ink; actual={display!r}"]
    minimum = {"lines": 8, "arcs": 17, "polylines": 7,
               "polygons": 5, "triangles": 9, "arrows": 8}
    for kind, records in display.items():
        if kind not in minimum and kind != "texts" and records:
            errors.append(f"{label}: unsupported actual {kind} ink; actual={records!r}")
    for kind, size in minimum.items():
        for index, raw in enumerate(display.get(kind, ())):
            try:
                values = tuple(float(value) for value in raw)
                valid = len(values) >= size and all(map(math.isfinite, values))
                if kind == "polylines" and valid:
                    count = int(values[6])
                    valid = count >= 2 and (
                        len(values) >= 7 + 3 * count
                        or len(values) >= 7 + int(values[1]) + 3 * count
                    )
                if kind == "polygons" and valid:
                    valid = int(values[4]) >= 2 and len(values) >= 5 + 3 * int(values[4])
                if kind == "arrows" and valid:
                    valid = math.hypot(values[3], values[4]) > 0 and values[6] > 0 and values[7] > 0
            except (TypeError, ValueError, OverflowError):
                valid = False
            if not valid:
                errors.append(f"{label}: malformed/nonfinite {kind}[{index}]; actual={raw!r}")
    for index, text in enumerate(display.get("texts", ())):
        try:
            pos = tuple(float(value) for value in text["pos"])
            h, w, angle = (float(text[key]) for key in ("h", "w", "ang"))
            valid = len(pos) >= 2 and all(map(math.isfinite, (*pos, h, w, angle))) and h > 0 and w > 0
        except (KeyError, TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            errors.append(f"{label}: missing/malformed/nonfinite actual text[{index}]; actual={text!r}")
    for index, raw in enumerate(annotation.get("leaders", ())):
        try:
            valid = len(raw) >= 6 and len(raw) % 3 == 0 and all(math.isfinite(float(v)) for v in raw)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            errors.append(f"{label}: malformed/nonfinite leader[{index}]; actual={raw!r}")
    note = annotation.get("note")
    if note is not None:
        raw = note.get("extent", ())
        try:
            valid = len(raw) == 6 and all(math.isfinite(float(v)) for v in raw)
            valid = valid and raw[0] <= raw[3] and raw[1] <= raw[4]
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            errors.append(f"{label}: missing/malformed/nonfinite note extent; actual={raw!r}")
    return errors


def _actual_arc_extrema(raw: Sequence[float]) -> list[tuple[float, float]]:
    """Exact cardinal extrema supplement the audit's sampled arc hull."""
    sx, sy, ex, ey, cx, cy = (float(raw[i]) for i in (4, 5, 7, 8, 10, 11))
    radius = math.hypot(sx - cx, sy - cy)
    start, end = math.atan2(sy - cy, sx - cx), math.atan2(ey - cy, ex - cx)
    ccw = (raw[16] != 0) == (raw[15] >= 0)
    full = math.hypot(ex - sx, ey - sy) < 1e-9
    sweep = ((end - start) if ccw else (start - end)) % math.tau
    points = [(sx, sy), (ex, ey)]
    for angle in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        along = ((angle - start) if ccw else (start - angle)) % math.tau
        if full or along <= sweep:
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _relief_lower_thread_profile() -> _drawing_leaders.Segment:
    """Model/spec lower thread, clipped to DETAIL's unchanged circular crop."""
    scale = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
    cx, cy = DETAIL_CENTER
    half = THREAD_MODEL_DIA * scale / 2.0
    y = cy - half
    return (
        (cx - math.sqrt(DETAIL_RADIUS**2 - half**2), y),
        (cx + (DETAIL_STATION - RELIEF_END_STATION) * scale, y),
    )


def _relief_text_profile_errors(annotation: Mapping[str, Any]) -> list[str]:
    """Native metric text hulls versus model/spec profile, not PDF glyph pixels."""
    label = "DETAIL/ReliefDia"
    display = annotation.get("display")
    texts = display.get("texts") if isinstance(display, Mapping) else None
    if not isinstance(texts, Sequence) or isinstance(texts, (str, bytes)) or not texts:
        return [f"{label}: missing/malformed actual text inventory; actual={texts!r}"]
    errors = []
    roots = sum(isinstance(text, Mapping) and text.get("t") == RELIEF_DIA_ROOT_CALLOUT
                for text in texts)
    if roots != 1:
        errors.append(f"{label}: expected one actual ROOT text; count={roots}; actual={texts!r}")
    profile = _relief_lower_thread_profile()
    for index, text in enumerate(texts):
        primitive = {"texts": [text]}
        invalid = _annotation_ink_errors({"display": primitive}, f"{label}/text[{index}]")
        errors.extend(invalid)
        if invalid:
            continue
        try:
            box = _layout_audit.display_box(primitive)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError, IndexError) as exc:
            errors.append(f"{label}/text[{index}]: unreadable actual metric text hull: {exc}; actual={text!r}")
            continue
        if box is None:  # Native blank tolerance separators carry no text ink.
            continue
        bounds = (box.xmin, box.ymin, box.xmax, box.ymax)
        air = _drawing_leaders.distance_to_box(profile, bounds)
        if air < 0.003:
            errors.append(
                f"{label}/text[{index}]: metric text/profile clearance below 0.003; "
                f"text={text.get('t')!r}; air={air!r}; actual_box={bounds!r}; "
                f"model_spec_profile={profile!r}"
            )
    return errors


def _actual_stroke_inventory(
    annotation: Mapping[str, Any], kind: str, label: str,
) -> tuple[list[_drawing_leaders.Segment], list[str]]:
    """Parse one required, collected native inventory without route substitutes."""
    display = annotation.get("display")
    records = (annotation.get("leaders") if kind == "leaders" else
               display.get(kind) if isinstance(display, Mapping) else None)
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        return [], [f"{label}: missing/malformed actual {kind} inventory; actual={records!r}"]
    strokes, errors = [], []
    for index, raw in enumerate(records):
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            errors.append(f"{label}/{kind}[{index}]: malformed actual primitive; actual={raw!r}")
            continue
        primitive = ({"display": {"texts": []}, "leaders": [raw]} if kind == "leaders"
                     else {"display": {kind: [raw]}})
        invalid = _annotation_ink_errors(primitive, f"{label}/{kind}[{index}]")
        errors.extend(invalid)
        if invalid:
            continue
        if kind == "leaders":
            points = [(float(raw[i]), float(raw[i + 1])) for i in range(0, len(raw), 3)]
            strokes.extend((a, b) for a, b in zip(points, points[1:]) if a != b)
        else:
            strokes.extend(
                ((line.x0, line.y0), (line.x1, line.y1))
                for line in _layout_audit._display_segments(primitive["display"])
            )
    if not strokes:
        errors.append(f"{label}: empty actual {kind} ink; actual={records!r}")
    return strokes, errors


def _settled_profile_and_tip_errors(dumps: Sequence[Mapping[str, Any]]) -> list[str]:
    """Mandatory ROOT and tip/63/67 reads from the already collected native dump.

    DisplayData lines, registered leader points and the actual arrow outline
    are independent inventories: none can replace a missing or malformed one.
    CRLF becomes LF only; wrong text, duplicate notes and missing witnesses
    fail closed. Every valid offending primitive still reaches the report.
    """
    errors = []
    required = {name: [] for name in ("ReliefDia", "UnderHeadLocation", "OverallLength")}
    tips = []
    for sheet in dumps:
        for annotation in _layout_audit.audited_annotations(_layout_audit.printed_dump(sheet)):
            if annotation.get("owner_type") != 0:
                continue
            name = annotation.get("name")
            if name in required:
                required[name].append(annotation)
            note = annotation.get("note")
            if isinstance(note, Mapping) and isinstance(note.get("text"), str):
                if note["text"].replace("\r\n", "\n") == THREAD_NOTE_TEXT:
                    tips.append(annotation)
    for name, records in {**required, "ThreadNote": tips}.items():
        if len(records) != 1:
            errors.append(f"{name}: expected one settled native annotation; count={len(records)}")
        expected_type = 6 if name == "ThreadNote" else 4
        for annotation in records:
            if annotation.get("type") != expected_type or annotation.get("visible") != 1:
                errors.append(f"{name}: wrong settled native type/visibility; actual={annotation!r}")
    for annotation in required["ReliefDia"]:
        errors.extend(_relief_text_profile_errors(annotation))
    references = {}
    for name in ("UnderHeadLocation", "OverallLength"):
        references[name] = []
        for annotation in required[name]:
            lines, invalid = _actual_stroke_inventory(annotation, "lines", f"SIDE/{name}")
            errors.extend(invalid)
            witnesses = [line for line in lines
                         if abs(line[0][0] - line[1][0]) <= 1e-9 and line[0][1] != line[1][1]]
            if len(witnesses) != 2:
                errors.append(f"SIDE/{name}: expected two actual reference witnesses; actual={lines!r}")
            references[name].extend(witnesses)
    for annotation in tips:
        for kind in ("lines", "leaders", "arrows"):
            strokes, invalid = _actual_stroke_inventory(annotation, kind, "SIDE/ThreadNote")
            errors.extend(invalid)
            for name, witnesses in references.items():
                crossings = [(a, b) for a in strokes for b in witnesses
                             if _drawing_leaders.segments_cross(a, b)]
                if crossings:
                    errors.append(
                        f"SIDE/ThreadNote/{kind} vs {name}: tip-leader/reference-witness crossing; "
                        f"actual={crossings!r}"
                    )
    return errors


def _settled_under_head_errors(dumps: Sequence[Mapping[str, Any]]) -> list[str]:
    """Collect both new features against each other and every head/53 corridor.

    Only actual native strokes, arrows and metric text hulls are accepted.
    Missing/malformed data never hides other valid offending primitives.
    """
    names = (*UNDER_HEAD_DIMENSIONS, *UNDER_HEAD_FOREIGN_DIMENSIONS)
    records = {name: [] for name in names}
    for sheet in dumps:
        for annotation in _layout_audit.audited_annotations(_layout_audit.printed_dump(sheet)):
            if annotation.get("owner_type") == 0 and annotation.get("name") in records:
                records[annotation["name"]].append(annotation)
    errors, strokes, boxes = [], {}, {}
    for name, matching in records.items():
        strokes[name], boxes[name] = [], []
        if len(matching) != 1:
            errors.append(f"SIDE/{name}: expected one settled under-head corridor annotation; count={len(matching)}")
        for annotation in matching:
            if annotation.get("type") != 4 or annotation.get("visible") != 1:
                errors.append(f"SIDE/{name}: wrong native corridor type/visibility; actual={annotation!r}")
            display = annotation.get("display")
            for kind in ("lines", "arrows"):
                actual, invalid = _actual_stroke_inventory(annotation, kind, f"SIDE/{name}")
                errors.extend(invalid)
                strokes[name].extend(actual)
            if annotation.get("leaders"):
                actual, invalid = _actual_stroke_inventory(annotation, "leaders", f"SIDE/{name}")
                errors.extend(invalid)
                strokes[name].extend(actual)
            for kind in ("arcs", "polylines", "polygons", "triangles"):
                if isinstance(display, Mapping) and display.get(kind):
                    actual, invalid = _actual_stroke_inventory(annotation, kind, f"SIDE/{name}")
                    errors.extend(invalid)
                    strokes[name].extend(actual)
            texts = display.get("texts") if isinstance(display, Mapping) else None
            if not isinstance(texts, Sequence) or isinstance(texts, (str, bytes)) or not texts:
                errors.append(f"SIDE/{name}: missing actual corridor text; actual={texts!r}")
                continue
            for text in texts:
                invalid = _annotation_ink_errors({"display": {"texts": [text]}}, f"SIDE/{name}")
                errors.extend(invalid)
                if invalid:
                    continue
                try:
                    box = _layout_audit.display_box({"texts": [text]})
                except (AttributeError, KeyError, TypeError, ValueError, OverflowError, IndexError) as exc:
                    errors.append(f"SIDE/{name}: unreadable actual corridor text: {exc}; actual={text!r}")
                    continue
                if box is not None:
                    boxes[name].append((box.xmin, box.ymin, box.xmax, box.ymax))
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            if name not in UNDER_HEAD_DIMENSIONS and other not in UNDER_HEAD_DIMENSIONS:
                continue
            crossings = [(a, b) for a in strokes[name] for b in strokes[other]
                         if _drawing_leaders.segments_cross(a, b)]
            if crossings:
                errors.append(f"SIDE/{name} vs {other}: under-head foreign ink crossing; actual={crossings!r}")
            for first, second in ((name, other), (other, name)):
                for box in boxes[first]:
                    close = [line for line in strokes[second]
                             if _drawing_leaders.distance_to_box(line, box) < 0.003]
                    if close:
                        errors.append(f"SIDE/{first} text vs {second}: under-head ink air below 0.003; actual_box={box!r}; actual={close!r}")
            for a in boxes[name]:
                for b in boxes[other]:
                    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
                    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
                    if math.hypot(dx, dy) < 0.003:
                        errors.append(f"SIDE/{name} text vs {other}: under-head text air below 0.003; actual={a!r},{b!r}")
    return errors


def _assert_generated_annotation_ink(
    dumps: Sequence[Mapping[str, Any]],
    detail_groups: Mapping[str, Sequence[_drawing_leaders.Segment]],
    *,
    collection_errors: Sequence[str] = (),
    settled: bool = False,
) -> None:
    """Collect every border/DETAIL violation; production also requires ROOT/tip reads.

    Isolated border/foreign-DETAIL fixtures may omit the unrelated settled
    inventories. The production finalizer always enables ``settled``.
    """
    errors = list(collection_errors)
    if settled:
        errors.extend(_settled_profile_and_tip_errors(dumps))
        errors.extend(_settled_under_head_errors(dumps))
    if not dumps:
        errors.append("no drawing sheets collected")
    inner = (0.0127, 0.0127, 0.4191, 0.2667)
    for sheet in dumps:
        if sheet.get("read_errors"):
            errors.append(f"{sheet.get('sheet')}: native collection errors={sheet['read_errors']!r}")
        printable = _layout_audit.printed_dump(sheet)
        for index, annotation in enumerate(_layout_audit.audited_annotations(printable)):
            label = f"{sheet.get('sheet')}/{annotation.get('name') or index}"
            if annotation.get("owner_type") == 2:
                continue  # template ink, never generated drawing annotation ink
            try:
                if annotation.get("owner_type") not in (0, 1):
                    errors.append(f"{label}: unknown annotation owner; actual={annotation!r}")
                if annotation.get("visible") != 1:
                    errors.append(f"{label}: unknown annotation visibility; actual={annotation!r}")
                try:
                    errors.extend(_annotation_ink_errors(annotation, label))
                except (AttributeError, TypeError, ValueError, IndexError) as exc:
                    errors.append(f"{label}: malformed actual ink: {exc}; actual={annotation!r}")
                points = []
                # A malformed record does not hide valid offending primitives
                # in the SAME annotation, nor errors in later annotations.
                display = annotation.get("display") or {}
                for kind in ("lines", "arcs", "polylines", "polygons", "triangles", "arrows", "texts"):
                    records = display.get(kind) or ()
                    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
                        errors.append(f"{label}: malformed actual {kind} inventory; actual={records!r}")
                        continue
                    for raw in records:
                        primitive = {"display": {kind: [raw]}}
                        try:
                            if _annotation_ink_errors(primitive, label):
                                continue
                            box = _layout_audit.display_box(primitive["display"])
                            if box is not None:
                                points.extend(((box.xmin, box.ymin), (box.xmax, box.ymax)))
                            if kind == "arcs":
                                points.extend(_actual_arc_extrema(raw))
                        except (AttributeError, KeyError, TypeError, ValueError, OverflowError, IndexError) as exc:
                            errors.append(f"{label}: malformed actual {kind}: {exc}; actual={raw!r}")
                leaders = annotation.get("leaders") or ()
                if not isinstance(leaders, Sequence) or isinstance(leaders, (str, bytes)):
                    errors.append(f"{label}: malformed actual leader inventory; actual={leaders!r}")
                    leaders = ()
                for raw in leaders:
                    try:
                        if len(raw) >= 6 and len(raw) % 3 == 0 and all(math.isfinite(float(v)) for v in raw):
                            points.extend((float(raw[i]), float(raw[i + 1])) for i in range(0, len(raw), 3))
                    except (TypeError, ValueError, OverflowError) as exc:
                        errors.append(f"{label}: malformed actual leader: {exc}; actual={raw!r}")
                note = annotation.get("note") or {}
                extent = note.get("extent") if isinstance(note, Mapping) else ()
                try:
                    if extent and len(extent) == 6 and all(math.isfinite(float(v)) for v in extent):
                        points.extend(((extent[0], extent[1]), (extent[3], extent[4])))
                except (TypeError, ValueError, OverflowError) as exc:
                    errors.append(f"{label}: malformed actual note extent: {exc}; actual={extent!r}")
                if not points or not all(math.isfinite(v) for point in points for v in point):
                    errors.append(f"{label}: missing/nonfinite actual ink bounds; actual={annotation!r}")
                    continue
                bounds = (min(p[0] for p in points), min(p[1] for p in points),
                          max(p[0] for p in points), max(p[1] for p in points))
                if bounds[0] < inner[0] or bounds[1] < inner[1] or bounds[2] > inner[2] or bounds[3] > inner[3]:
                    errors.append(f"{label}: actual ink outside inner border; actual={bounds!r}; inner={inner!r}")
            except (AttributeError, KeyError, TypeError, ValueError, OverflowError, IndexError) as exc:
                errors.append(f"{label}: unreadable actual ink bounds: {exc}; actual={annotation!r}")
    valid_groups = {}
    for name in DETAIL_KEEP:
        strokes = detail_groups.get(name)
        valid_strokes = []
        if not isinstance(strokes, Sequence) or not strokes:
            errors.append(f"DETAIL/{name}: missing/malformed/nonfinite actual ink; actual={strokes!r}")
        for stroke in strokes if isinstance(strokes, Sequence) else ():
            try:
                valid = len(stroke) == 2 and all(
                    len(point) == 2 and all(math.isfinite(v) for v in point)
                    for point in stroke
                )
            except (TypeError, ValueError, OverflowError):
                valid = False
            if not valid:
                errors.append(f"DETAIL/{name}: missing/malformed/nonfinite actual ink; actual={stroke!r}")
            else:
                valid_strokes.append(stroke)
        if valid_strokes:
            valid_groups[name] = valid_strokes
    names = list(valid_groups)
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            crossings = [(a, b) for a in valid_groups[name] for b in valid_groups[other]
                         if _drawing_leaders.segments_cross(a, b)]
            if crossings:
                errors.append(f"DETAIL/{name} vs {other}: foreign ink crossing; actual={crossings!r}")
    if errors:
        raise RuntimeError("MHA-DT-32 generated annotation ink violations:\n" + "\n".join(errors))


def assert_final_annotation_ink(adapter: Any, detail_annotations: Sequence[Any]) -> None:
    """Collect all settled ink, including mandatory metric ROOT and native tip routes."""
    reader = _drawing_layout_audit._Reader(adapter)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    dumps, errors = [], []
    try:
        rows = ddoc.GetViews() or ()
    except Exception as exc:
        rows = ()
        errors.append(f"drawing sheet inventory failed: {exc}")
    try:
        names = tuple(ddoc.GetSheetNames() or ())
        if not names or len(names) != len(rows):
            errors.append(f"drawing sheet inventory mismatch; sheets={names!r}; view_rows={len(rows)}")
    except Exception as exc:
        errors.append(f"drawing sheet-name inventory failed: {exc}")
    for index, row in enumerate(rows):
        dump: dict[str, Any] = {"sheet": f"sheet[{index}]", "views": [], "sheet_annotations": []}
        if not row:
            errors.append(f"sheet[{index}]: empty view inventory")
        for view_index, raw_view in enumerate(row or ()):
            try:
                view = _early_bound(raw_view, "IView")
                records = []
                # Strict enumeration: an unreadable inventory cannot become
                # a clean border gate through the audit's tolerant call.
                for raw in view.GetAnnotations() or ():
                    try:
                        record = _drawing_layout_audit._dump_annotation(reader, raw)
                        if record is None:
                            errors.append(f"sheet[{index}]/view[{view_index}]: unreadable annotation")
                        else:
                            records.append(record)
                    except Exception as exc:
                        errors.append(f"sheet[{index}]/view[{view_index}]: annotation collection failed: {exc}")
                if view_index == 0:
                    dump["sheet_annotations"] = records
                else:
                    dump["views"].append({"annotations": records})
            except Exception as exc:
                errors.append(f"sheet[{index}]/view[{view_index}]: inventory failed: {exc}")
        try:
            dump["layers"] = _drawing_layout_audit._layer_states(reader, dump)
        except Exception as exc:
            errors.append(f"sheet[{index}]: native layer collection failed: {exc}")
        dump["read_errors"] = reader.take_errors()
        dumps.append(dump)
    groups = {}
    for annotation in detail_annotations:
        try:
            name = dimension_name(adapter, annotation)
            if name in DETAIL_KEEP:
                if name in groups:
                    errors.append(f"DETAIL/{name}: duplicate native annotation")
                groups[name] = _drawing_leaders.dimension_segments(annotation)
        except Exception as exc:
            errors.append(f"DETAIL: actual ink collection failed: {exc}")
    _assert_generated_annotation_ink(dumps, groups, collection_errors=errors, settled=True)


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
        keep=SIDE_KEEP,
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
            "HeadOuterChamfer": HEAD_OUTER_CHAMFER_CALLOUT,
            "TipChamfer": CHAMFER_CALLOUT,
            "HeadDia": HEAD_DIA_CALLOUT,
            "HeadLength": HEAD_LENGTH_CALLOUT,
            "ShoulderLength": UNDER_HEAD_CALLOUT,
        },
        location="below",
    )
    # ABOVE is single-line only in the native display: keep the root reason
    # here, separate from the relief's two BELOW seating/mate lines.
    # The running mate stays above the shoulder-diameter value.
    set_dimension_callouts(
        adapter,
        annotations,
        {
            "ReliefDia": RELIEF_DIA_ROOT_CALLOUT,
            "ShoulderDia": SHOULDER_CALLOUT,
        },
        location="above",
    )
    style_relief_dimensions(adapter, detail_annotations)
    style_under_head_dimensions(adapter, side_annotations)
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
        text=THREAD_NOTE_TEXT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-DT-32 thread callout",
    )
    _add_shoulder_finish(adapter, side)
    label_relief_view(adapter, detail)
    mark_relief_on_side(adapter, side)
    _activate(adapter, side, label="side view notes")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Pivot Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: assert_final_annotation_ink(adapter, detail_annotations),),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
