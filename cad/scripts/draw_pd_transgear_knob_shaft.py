r"""Create the manufacturing drawing for the transgear knob shaft (MHA-PD-08).

A turned side view, aligned rear and front end views, a 10:1 detail of the
front neck, and an isometric.
The side view imports the source-owned turned sizes, D-flat and unchanged
stations. The front end view carries genuine finite-root REF and driven
parallel-tangent span inspection dimensions; the rear view identifies the
actual running journal datum. The #8-32 thread callout belongs to its real
thread blank. Cutter identity, root acceptance and approved inspection
controls are properties of the saved source, never values retyped here.
The source-linked formed-flank callout carries radial TIR, the paid
pitch-index range at REF pitch diameter, all-space/wrap receiving and the
certified pin. Neither span thickness nor a pin-centre radius substitutes
for that independent index control.
The rear cup remains match-pinned at assembly; the front D-core has no
crosshole. This script does not certify a native build or release a prototype
toothspace runout grade.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
    view_name,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _gtol_face_resolve import resolve_faces
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from paper_drive_stock_drawing import add_toothspace_callout, require_source_control
from pd_transgear_knob_shaft_spec import (
    CHAMFER_CALLOUT,
    CORE_DIA,
    CORE_FRONT_Z,
    CORE_REAR_Z,
    CUTTER_NUMBER,
    FRONT_CORNER_RADIUS,
    FRONT_RELIEF_DIA,
    FRONT_RELIEF_WIDTH,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    FACE_WIDTH_CALLOUT,
    JOURNAL_DIA,
    OUTSIDE_DIA,
    PLAIN_CORE,
    PRESSURE_ANGLE_DEG,
    GEOMETRIC_CONTROLS,
    GEOMETRIC_TOLERANCES_MM,
    PART_DATUMS,
    REAR_END_Z,
    SURFACE_FINISHES,
    STOCK_PROFILE,
    TOOTH_SPACE_GAUGE_PIN_DIA_MM,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
    TEETH,
    THREAD_CALLOUT,
    TIP_CHAMFER,
    TIP_STATION,
    TIP_Z,
)

SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_shaft"]
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

# The retained shaft stations fit at 3:1. Inspection carriers use a separate
# aligned front end view, not the journal-obscured rear projection.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.180, 0.160)
# Third-angle: the rear face is the side view's LEFT end, so the view from
# the rear stands left of it, on the shaft axis.
END_CENTER = (0.045, SIDE_CENTER[1])
FRONT_CENTER = (0.335, SIDE_CENTER[1])
ISO_CENTER = (0.365, 0.215)
ISO_SCALE = (1, 1)
_BBOX_MID_Z = (TIP_Z + REAR_END_Z) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left).

    The view is centred on the model bbox, stud tip to rear face.
    """
    return SIDE_CENTER[0] + (_BBOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the shaft axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


REAR_X = _sheet_x(REAR_END_Z)
PINION_REAR_X = _sheet_x(FACE_WIDTH)
F_X = _sheet_x(0.0)
CORE_END_X = _sheet_x(CORE_FRONT_Z)
THREAD_END_X = _sheet_x(-PLAIN_CORE)
TIP_X = _sheet_x(TIP_Z)
# Where the thread blank meets the tip chamfer.
CHAMFER_START_X = _sheet_x(-(TIP_STATION - TIP_CHAMFER))
HALF_OD = OUTSIDE_DIA * _S / 2000.0

# Turned sizes stay beside their own axial regions. Baseline lengths nest
# below F. The D-flat's native plane-to-axis dimension is visible edge-on in
# the side view.
_ABOVE_Y = SIDE_CENTER[1] + HALF_OD + 0.016
_ROW_PITCH = 0.010
_ROW_Y = tuple(SIDE_CENTER[1] - HALF_OD - 0.016 - i * _ROW_PITCH for i in range(6))
SIDE_KEEP: dict[str, tuple[float, float]] = {
    "OutsideDia": ((F_X + PINION_REAR_X) / 2.0, _ABOVE_Y),
    "CoreDia": ((F_X + CORE_END_X) / 2.0, _ABOVE_Y + 0.010),
    # Run 12: from the relief's mid the hung text's shoulder started left of
    # F's witness line (214.4) and ran through the front-neck frame. Four
    # fifths along the relief it starts right of F, above that frame.
    "ReliefDia": ((CORE_END_X + 4.0 * THREAD_END_X) / 5.0, _ABOVE_Y + 0.0265),
    # A Ø's line stands at its point; right of the view's centre the text
    # hangs LEFT of it (the pinion's and core's, run 20261001T085006647Z), and
    # the blank's banded text and shoulder run 27.5 mm (19e33c6c2: from the
    # blank's mid the shoulder crossed the relief's line).  9 mm in from the
    # chamfer the line stands clear of the core runout frame below the text
    # and stays 9 mm off the thread callout's leader to the chamfer.
    "ThreadBlankDia": (CHAMFER_START_X - 0.009, _ABOVE_Y),
    "JournalDia": ((PINION_REAR_X + REAR_X) / 2.0, _ABOVE_Y),
    # Its two-line text (45.7 mm wide with "DISC CLUSTER STACK") is wider
    # than the 17.7 mm between its witness lines, so it stands outside right
    # of F's (214.4): text ~218.6..264.3 mm, under the empty rows past F.
    "FaceWidth": (F_X + 0.027, _ROW_Y[4]),
    "CoreFront": ((F_X + CORE_END_X) / 2.0, _ROW_Y[0]),
    "PlainCore": ((F_X + THREAD_END_X) / 2.0, _ROW_Y[1]),
    "JournalLength": ((PINION_REAR_X + REAR_X) / 2.0, _ROW_Y[0]),
    "TipStation": ((F_X + TIP_X) / 2.0, _ROW_Y[2]),
    "FlatToAxis": (CORE_END_X + 0.018, SIDE_CENTER[1] - HALF_OD - 0.004),
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - HALF_OD),
}
END_KEEP: dict[str, tuple[float, float]] = {
    # Right of the view, its leader entering the -15 deg tooth gap (this view
    # prints teeth at 0 and -30 deg): the shoulder end stands 22 mm out along
    # -15 deg, the 50 mm text right of it.  Left of the view, its text and
    # shoulder ran over the side view's tip witness and axial rows
    # (mr-stack6).
    "RootEnvelope": (FRONT_CENTER[0] + 0.0494, FRONT_CENTER[1] - 0.0021),
    "ToothSpan": (FRONT_CENTER[0] + 0.029, FRONT_CENTER[1] + HALF_OD + 0.021),
}
# The face width's ±band names the disc cluster stack (rule 4); its one
# line hangs into the empty sixth baseline row below it.
DIMENSION_CALLOUTS_BELOW = {
    "TipChamfer": CHAMFER_CALLOUT,
    "FaceWidth": FACE_WIDTH_CALLOUT,
}

# The thread callout lands on the edge where the thread blank meets the tip
# chamfer and stands up and left, clear of the tooth-tip Ø over the pinion.
THREAD_PICK = (CHAMFER_START_X, SIDE_CENTER[1] + 0.002)
THREAD_NOTE_XY = ((THREAD_END_X + CHAMFER_START_X) / 2.0, _ABOVE_Y + 0.020)
# The actual active core (not the new neck) and running journal own finishes.
JOURNAL_FINISH_SYMBOL = (END_CENTER[0] + 0.008, END_CENTER[1] + HALF_OD + 0.012)
_JOURNAL_R = JOURNAL_DIA * _S / 2000.0
JOURNAL_FINISH_ATTACH = (
    END_CENTER[0] + _JOURNAL_R * 0.5,
    END_CENTER[1] + _JOURNAL_R * 3.0**0.5 / 2.0,
)
CORE_FINISH_PICK = (
    _sheet_x((CORE_FRONT_Z + CORE_REAR_Z) / 2.0), _sheet_y(CORE_DIA / 2.0)
)
# Over the core, right of its rear end.
CORE_FINISH_SYMBOL = (F_X + 0.0115, SIDE_CENTER[1] + HALF_OD + 0.004)
# A point on the journal's face for the turning axis.
CENTERLINE_PICK = ((PINION_REAR_X + REAR_X) / 2.0, SIDE_CENTER[1] + 0.003)
# Lower left, under the journal's 40.938 row (y 0.133) and over the notes
# (top 0.070): detail B took the upper-left lane.
GEAR_DATA_XY = (0.016, 0.118)
GEAR_DATA_CHAR_HEIGHT = 0.0025
NOTES_XY = (0.016, 0.070)
ROOT_ACCEPTANCE_XY = (0.286, 0.103)
DATUM_A_SYMBOL = (END_CENTER[0] - 0.017, END_CENTER[1] - 0.018)
# The core frame sits low over the thread blank, under the blank's Ø text;
# its leader runs under the core finish symbol to the core's front quarter
# (run 12: from above it crossed the blank's Ø and thread callout texts).
CORE_RUNOUT_LANDING = (
    _sheet_x(CORE_REAR_Z + 0.75 * (CORE_FRONT_Z - CORE_REAR_Z)),
    _sheet_y(CORE_DIA / 2.0),
)
CORE_RUNOUT_FRAME = (THREAD_END_X + 0.0066, SIDE_CENTER[1] + 0.0155)

# --- Detail B: the front neck at 10:1 -----------------------------------------
# At 3:1 the 0.400 neck is 1.2 mm of sheet: its Ø, width, corner R and
# runout frame crossed one another and the core's annotations (mr-stack6).
# Detail B is a cropped 10:1 *Right MODEL view, draw_dt_pinion_spring's
# detail-A recipe: native detail views imported no dimensions on the
# amplitude bar (r743-6), dt_vn_post_mount_screw and the pinion spring
# (pc-r13/14).
DETAIL_SCALE = (10, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1]
DETAIL_LETTER = "B"  # A is the journal datum.
DETAIL_LABEL_TEXT = f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
# The fence, model mm (z, y): mid-neck, 0.1 under the axis.  Radius 2.7
# holds both neck floors (the Ø's two arrows land on drawn floor), the
# core's top step corner (2.53 out), the Ø's lower arrow tail (2.6 under
# the axis; 2.52 out), and the axis and F origin that
# FrontReliefDia and FrontReliefWidth reference: a crop drops a dimension
# whose reference it cuts away.
DETAIL_FOCUS_MM = (-FRONT_RELIEF_WIDTH / 2.0, -0.1)
_DETAIL_FOCUS_M = (0.0, DETAIL_FOCUS_MM[1] / 1000.0, DETAIL_FOCUS_MM[0] / 1000.0)
DETAIL_RADIUS_MM = 2.7
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS / 1000.0
# Upper left, over the journal: x 0.078-0.132 clears the end view's journal
# finish symbol (x <= 0.068) and the journal Ø's witness line (x 0.1353);
# y 0.196-0.250 stands over the journal Ø's text (top 0.193) and leaves the
# frame row under the border (0.2667).
DETAIL_CENTER = (0.105, 0.223)
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# The focus, and the neck landing that proves the view's scale and handing,
# must land within 0.1 mm of where this script places them.
DETAIL_POSITION_TOL_M = 1e-4


def _detail_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (z, y) mm in detail B (model +Z runs left)."""
    return (
        DETAIL_CENTER[0] + (DETAIL_FOCUS_MM[0] - z_mm) * _DS / 1000.0,
        DETAIL_CENTER[1] + (y_mm - DETAIL_FOCUS_MM[1]) * _DS / 1000.0,
    )


_NECK_FLOOR_R = FRONT_RELIEF_DIA / 2.0
_STEP_X = _detail_xy(-FRONT_RELIEF_WIDTH, 0.0)[0]
_CORNER_CENTER = _detail_xy(-FRONT_CORNER_RADIUS, _NECK_FLOOR_R + FRONT_CORNER_RADIUS)
_DETAIL_TOP = DETAIL_CENTER[1] + DETAIL_CROP_RADIUS
_DETAIL_BOTTOM = DETAIL_CENTER[1] - DETAIL_CROP_RADIUS
# The neck frame's leader lands on the straight floor 0.15 from F and climbs
# the neck's air to a frame left of it, 1 mm right of the corner R's arrow.
# A frame prints 31.3 mm wide and 7 mm tall with a 6.3 mm shoulder at
# mid-height (stack PDF: box x 0.1884-0.2197, shoulder to 0.2260), so its
# right edge stands one shoulder left of the landing and the leader climbs
# plumb.  Its row sits low, 8.3 mm over the crop's top: the box's corner
# nearest the crop (x 0.0982, y 0.2513) stands 2.1 mm off the circle.
_FRAME_WIDTH = 0.0313
_FRAME_HEIGHT = 0.007
_FRAME_SHOULDER = 0.0063
_FRAME_ROW_TOP = _DETAIL_TOP + 0.0083
NECK_LANDING_Z_MM = -0.15
NECK_RUNOUT_LANDING = _detail_xy(NECK_LANDING_Z_MM, _NECK_FLOOR_R)
NECK_RUNOUT_FRAME = (
    NECK_RUNOUT_LANDING[0] - _FRAME_SHOULDER - _FRAME_WIDTH, _FRAME_ROW_TOP
)
DETAIL_KEEP: dict[str, tuple[float, float]] = {
    # Its line rises through the neck's air 0.30 from F, 1.5 mm right of the
    # frame's leader, past the frame's row to text over it.  The text hangs
    # LEFT of the line (3f50160d9 full build: [87.8, 256.6]..[104.6, 260.2]
    # mm for a keep at (106.0, 258.5), right edge 1.4 mm short of the line),
    # so level with the frame the frame's shoulder ran 6.35 mm through it.
    # Over the frame the shoulder and the plumb leader both stay under the
    # text: centred 4.6 mm over the frame's top, the 3.6 mm text clears the
    # frame by 2.8 mm and the border (0.2667) by 2.0 mm on either side.
    "FrontReliefDia": (_detail_xy(-0.30, 0.0)[0], _FRAME_ROW_TOP + 0.0046),
    # Under the crop, the text right of the step's witness line: centred on
    # the 4 mm span it would sit on both witness lines.
    "FrontReliefWidth": (_STEP_X + 0.0078, _DETAIL_BOTTOM - 0.007),
    # Left of the crop: the leader runs from the corner 12-24 deg below
    # level, inside the corner's own quadrant, through the pinion's blank
    # interior under its root and over the axis.
    "FrontCornerRadius": (_CORNER_CENTER[0] - 0.0325, _CORNER_CENTER[1] - 0.006),
}
# Top-left anchors.  The label stands left of the crop, 3 mm under the
# corner R's text (its limits print to 5 mm under its point).
DETAIL_LABEL_XY = (0.042, _CORNER_CENTER[1] - 0.014)
# The mark's "B" stands under the pinion, between the tooth-tip Ø's lower arrow
# (x 0.2056) and F's witness lines (x 0.2144), clear of the mark circle.
PARENT_LETTER_XY = (F_X - 0.0057, SIDE_CENTER[1] - HALF_OD - 0.0025)

# Each frame's leader landing on its surface's upper outline, and the frame.
# The neck's straight floor is 0.3 mm long between its two 0.05 corner tori,
# so a silhouette hit-test there landed on a neighbour (run 10: a type-46
# silhouette of another face). Like main's arbor finishes, each frame
# attaches to the model FACE its spec control names, resolved on the
# referenced part, at this landing, in the view CONTROL_VIEWS names.
CONTROL_ATTACHMENTS = {
    "core_total_runout": (CORE_RUNOUT_LANDING, CORE_RUNOUT_FRAME),
    "front_neck_total_runout": (NECK_RUNOUT_LANDING, NECK_RUNOUT_FRAME),
}
CONTROL_VIEWS = {"core_total_runout": "side", "front_neck_total_runout": "detail"}
# Upper right: the leader drops nearly straight to the gap.
TOOTHSPACE_NOTE_XY = (0.322, 0.258)


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
    add_to_db: bool = False,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points.

    The sheet points go through the view sketch's ModelToSketchTransform.
    Without ``add_to_db`` the circle is left SELECTED, which Crop2 consumes.
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
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _placed_detail_view(adapter: Any) -> Any:
    """Detail B, uncropped: a 10:1 *Right model view moved so the fence's
    focus lands on DETAIL_CENTER.  The neck landing is projected too, so a
    view at another scale or handing than _detail_xy assumes raises."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Right", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"neck detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    center = model_point_in_view(adapter, view, _DETAIL_FOCUS_M, label="neck detail focus")
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the neck detail onto its sheet position")
    draw.EditRebuild3()
    landing_m = (0.0, _NECK_FLOOR_R / 1000.0, NECK_LANDING_Z_MM / 1000.0)
    for point, expected, label in (
        (_DETAIL_FOCUS_M, DETAIL_CENTER, "neck detail focus"),
        (landing_m, NECK_RUNOUT_LANDING, "neck runout landing"),
    ):
        found = model_point_in_view(adapter, view, point, label=label)
        if math.dist(found, expected) > DETAIL_POSITION_TOL_M:
            raise RuntimeError(f"{label} sits at {found!r}, not {expected!r}")
    return view


def _crop_detail_view(adapter: Any, view: Any) -> None:
    """Crop detail B to its fence circle round DETAIL_CENTER.

    Sketch the circle in the active view's own sketch and Crop2 while it is
    still selected, with the circle as the outline.  Crop status,
    IsCropped, the outline and its style are read back and raise.
    """
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="neck detail")
    _sketch_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="neck-detail crop"
    )
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"knob-shaft: neck detail {name!r}, Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"neck detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 10:1 view spans the whole 70.7 mm shaft (~707 mm of
    # sheet), the crop 48 mm, so a crop that took at least halves the width.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"neck-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"neck detail's crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    """The model-dimension names ``view`` holds, sorted."""
    return sorted(
        name
        for name in (
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        )
        if name
    )


def _dimension_then_crop_detail(adapter: Any, detail: Any) -> list[Any]:
    """Import and curate detail B's dimensions uncropped, then crop it.

    The names are read back before and after the crop as one
    ``neck_detail.crop`` event; any kept dimension missing afterwards raises.
    """
    annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="neck detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_detail_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "neck_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    if lost:
        raise RuntimeError(
            f"neck detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _mark_detail_on_side(adapter: Any, side: Any) -> None:
    """Circle detail B's fence on the side view in the outline's black."""
    _activate_view(adapter, side, label="side view")
    center = model_point_in_view(adapter, side, _DETAIL_FOCUS_M, label="neck detail mark")
    circle = _sketch_circle(
        adapter,
        side,
        center,
        DETAIL_RADIUS_MM * _S / 1000.0,
        label="neck-detail mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("neck-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _label_detail(adapter: Any, detail: Any, side: Any) -> None:
    """Label detail B beside its crop and letter its mark on the side view.

    A note lands in the ACTIVE view, so each view is activated first; a
    note that did not land in its view raises.
    """
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before labelling the neck detail")
    for view, text, xy, label in (
        (detail, DETAIL_LABEL_TEXT, DETAIL_LABEL_XY, "neck-detail label"),
        (side, DETAIL_LETTER, PARENT_LETTER_XY, "neck-detail letter"),
    ):
        _activate_view(adapter, view, label=label)
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to add the {label} note")
        texts = [
            _plain_text(_early_bound(found, "INote").GetText() or "")
            for found in (_early_bound(view, "IView").GetNotes() or ())
        ]
        if texts.count(_plain_text(text)) != 1:
            raise RuntimeError(f"{label} note did not land in its view: {texts!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-knob-shaft source", await adapter.open_model(str(SOURCE)))
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Root Acceptance",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Root Acceptance",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
    )
    require_source_control(
        source_properties[TOOTH_SPACE_CALLOUT_PROPERTY], TOOTH_SPACE_CALLOUT,
        label="knob shaft toothspace grade",
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                f"transgear knob shaft; steel; {TEETH}T {DIAMETRAL_PITCH:g}DP "
                f"PA{PRESSURE_ANGLE_DEG:g}; finite stock #{CUTTER_NUMBER}; #8-32 stud; D-core"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, front, iso):
        set_hidden_lines_removed(adapter, view)

    # Detail B is placed and dimensioned FIRST: its three dimensions live in
    # StudProfile with the side view's, and a dimension already on the sheet
    # is never imported again (draw_dt_pinion_spring's detail A), so the
    # side view's targeted import skips the three the detail holds.  The
    # detail is dimensioned uncropped and cropped after.
    detail = _placed_detail_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = _dimension_then_crop_detail(adapter, detail)
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=END_KEEP,
        view_label="front finite-form inspection",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations, *detail_annotations]
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    add_view_centerline(
        adapter, side, face_xy=CENTERLINE_PICK, label="MHA-PD-08 turning axis"
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-PD-08 stud thread callout",
    )

    # The two running surfaces, authored on the part and read back (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
    add_surface_finish(
        adapter,
        end,
        symbol_xy=JOURNAL_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "journal"),
        label="journal finish",
        entity=visible_circle_edge(adapter, end, JOURNAL_DIA),
        leader_attach_xy=JOURNAL_FINISH_ATTACH,
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=CORE_FINISH_PICK,
        symbol_xy=CORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "core"),
        label="core finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    # The saved source owns datum/control semantics. The drawing attaches
    # those same source declarations to the actual journal/core entities.
    journal_datum = PART_DATUMS[0]
    add_datum_feature(
        adapter,
        end,
        entity=visible_circle_edge(adapter, end, JOURNAL_DIA),
        symbol_xy=DATUM_A_SYMBOL,
        datum=journal_datum.letter,
        label="knob running journal datum",
    )
    controls = {control.key: control for control in GEOMETRIC_CONTROLS}
    if set(controls) != set(GEOMETRIC_TOLERANCES_MM):
        raise RuntimeError("knob shaft frames do not cover the spec's geometric controls")
    control_faces = resolve_faces(
        _early_bound(_early_bound(side, "IView").ReferencedDocument, "IModelDoc2"),
        {key: control.face for key, control in controls.items()},
    )
    views = {"side": side, "detail": detail}
    for (key,) in (("core_total_runout",), ("front_neck_total_runout",)):
        control = controls[key]
        landing, frame_xy = CONTROL_ATTACHMENTS[key]
        add_feature_control_frame(
            adapter,
            views[CONTROL_VIEWS[key]],
            entity=control_faces[key],
            leader_attach_xy=landing,
            frame_xy=frame_xy,
            characteristic=control.characteristic,
            tolerance=GEOMETRIC_TOLERANCES_MM[key],
            datums=control.datums,
            diameter=control.tolerance_zone == "diametral",
            entity_type="FACE",
            label=control.key,
        )
    add_toothspace_callout(
        adapter, front, profile=STOCK_PROFILE,
        actual_pin_diameter_mm=TOOTH_SPACE_GAUGE_PIN_DIA_MM,
        rotate_rad=math.pi / TEETH, axial_station_mm=0.0,
        property_name=TOOTH_SPACE_CALLOUT_PROPERTY,
        note_xy=TOOTHSPACE_NOTE_XY,
    )
    # The mark and the labels go on once every pick is done, so no
    # coordinate pick in the side view meets the mark circle.
    _mark_detail_on_side(adapter, side)
    _label_detail(adapter, detail, side)
    add_property_linked_note(
        adapter, "Gear Data", *GEAR_DATA_XY, char_height=GEAR_DATA_CHAR_HEIGHT
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.0025
    )
    add_property_linked_note(
        adapter, "Root Acceptance", *ROOT_ACCEPTANCE_XY, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Shaft Manufacturing Drawing",
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
