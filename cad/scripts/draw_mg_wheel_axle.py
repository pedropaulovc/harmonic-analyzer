r"""Create the curated machinist drawing for the magnifying-wheel axle.

A 3/16 drill-rod pin (MHA-MG-07): pressed into MG-WHEEL-BAR to MHA-MG-00's
gauge, the magnifying wheel running on its shank, a #4-40 end for the nut
stack with a thread relief at the shank step, and a domed tip.

Sheet: the side view at 3:1 carries the shank Ø with both of its fits and
the journal's Ra 1.6, both lengths from the shank step (origin circles on
the step), the "(56.0)" overall reference, the dome R and the thread
callout; detail A, a cropped 10:1 *Front model view turned like the side view
(draw_mg_magnifying_vertical_rod's detail-A recipe), carries the relief's
width, its Ø and its two root radii, all single MAX limits. A 3:1 shaded
isometric shows the cosmetic thread. No general notes: every requirement
rides its own callout, and every callout is authored on the part
(mg_wheel_axle_callouts); this sheet only reads them back (#1942).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_wheel_axle.py mg-wheel-axle
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_outline,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
    view_name,
)
from _drawing_detail_crop import native_circle_geometry
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision
from _drawing_finish import add_surface_finish
from _drawing_leader_notes import add_attached_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import mg_wheel_axle_callouts as callouts
from mg_wheel_axle_spec import (
    BACK_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_DIA,
    RELIEF_DIA,
    RELIEF_ROOT_R,
    RELIEF_WIDTH,
    SINGLE_LIMITS,
    STEP_Y,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_END_Y,
    THREAD_MAJOR,
    TIP_Y,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["mg_wheel_axle"]
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

# Every full view prints at the sheet scale, so none needs a caption. 3:1
# lays the pin (about 56 with the MHA-MG-11 spacer's length in it) about
# 168 mm long, its 3/16 shank 14 mm across, and keeps the isometric (model +Y
# up the sheet, about 137 mm tall) inside the border; 4:1 ran both off the
# sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# One side view: the *Front view (parallel to the profile sketch, so its
# dimensions import), turned so the pin lies horizontal, back end left. It
# stands 15 mm higher than before the relief so detail A fits under its rows.
SIDE_CENTER = (0.160, 0.185)
SIDE_VIEW_ANGLE = -math.pi / 2.0  # model +Y (back end -> tip) to paper right
ISO_CENTER = (0.335, 0.185)
_MID_Y = (BACK_Y + TIP_Y) / 2.0


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the side view (the view is centred on
    the model bbox, back end to tip)."""
    return SIDE_CENTER[0] + (model_y_mm - _MID_Y) * _S / 1000.0


BACK_X = _sheet_x(BACK_Y)
STEP_X = _sheet_x(STEP_Y)
THREAD_END_X = _sheet_x(THREAD_END_Y)
TIP_X = _sheet_x(TIP_Y)

# Rows below the profile (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the shank and the thread both
# baseline from the gauged step (the press gauge's face), each with the
# dimension-origin circle on the step's extension line and named on its
# callout, then the overall as a reference. The thread's block is the band's
# two lines plus three callout lines.
_ROW_Y = (SIDE_CENTER[1] - 0.032, SIDE_CENTER[1] - 0.0588, SIDE_CENTER[1] - 0.0800)
# The thread length spans about 25 mm of sheet, its ~78 mm callout block
# wider: the block stands wholly left of the step's extension line (4 mm air,
# room for the origin circle there), clear of the overall's extension line
# dropping from the tip on the right.
_THREAD_BLOCK_HALF = 0.041
# The overall reference's value sits in a break of its dimension line: on
# the unbroken line the parentheses' tails touched it (run
# 20261027T030250671Z review; draw_ch_channel_assembly #1660 r8).
BROKEN_LINE_DIMENSIONS = ("PinLength",)
BROKEN_LINE_ALIGNED_TEXT = 3  # swDisplayDimensionLeaderText_e.swBrokenLeaderAlignedText
SIDE_KEEP = {
    "ShankLength": ((BACK_X + STEP_X) / 2.0, _ROW_Y[0]),
    "ThreadLength": (STEP_X - 0.004 - _THREAD_BLOCK_HALF, _ROW_Y[1]),
    "PinLength": ((BACK_X + TIP_X) / 2.0, _ROW_Y[2]),
    # The shank's dimension line crosses the shank near the step; its text
    # runs left from the line, the fit callout's three lines under it, so the
    # block stands high enough to keep them off the shank and over the Ra 1.6.
    "PinDia": (STEP_X - 0.030, SIDE_CENTER[1] + 0.052),
    # Above-right of the tip: the leader lands on the dome's upper half, clear
    # of the overall's extension line dropping from the tip, and under the
    # thread callout.
    "DomeR": (TIP_X + 0.015, SIDE_CENTER[1] + 0.015),
}

# --- Detail A: the thread relief at 10:1 --------------------------------------
# Native detail views import no dimensions (draw_pd_transgear_knob_shaft
# detail B), so detail A is a second *Front model view at 10:1, turned like
# the side view (model +Y to paper right, the profile's +X down the paper),
# moved so the fence's focus lands on DETAIL_CENTER and cropped to the fence
# circle.
DETAIL_SCALE = (10, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1]
DETAIL_LETTER = "A"
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
# The fence, model mm (x = radius, y = axial): mid-relief, 0.6 off the axis
# on the -x side (up the sheet). Farm run 20261024T140241347Z attached the
# imported ReliefRootR to the root on that side of the axis (the revolve's
# mirror silhouette, not the sketch's +x half), so the fence frames that
# side: its step face out to the shank's corner (1.86 off), the floor, both
# roots and the flank to the thread major. Radius 2.0 also holds the axis
# and the +x floor (1.62 off), so whichever floor silhouette a linear
# dimension takes stays inside: a crop drops a dimension whose reference it
# cuts away.
DETAIL_FOCUS_MM = (-0.6, STEP_Y + RELIEF_WIDTH / 2.0)
_DETAIL_FOCUS_M = (DETAIL_FOCUS_MM[0] / 1000.0, DETAIL_FOCUS_MM[1] / 1000.0, 0.0)
DETAIL_RADIUS_MM = 2.0
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS / 1000.0
# Lower left, under the side view's rows and left of the title block:
# x 0.060-0.100, y 0.038-0.078.
DETAIL_CENTER = (0.080, 0.058)
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
CIRCLE_TOL_M = 1e-7


def _detail_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) mm in detail A (model +Y runs right, +X
    down)."""
    return (
        DETAIL_CENTER[0] + (y_mm - DETAIL_FOCUS_MM[1]) * _DS / 1000.0,
        DETAIL_CENTER[1] - (x_mm - DETAIL_FOCUS_MM[0]) * _DS / 1000.0,
    )


_DETAIL_TOP = DETAIL_CENTER[1] + DETAIL_CROP_RADIUS
_DETAIL_BOTTOM = DETAIL_CENTER[1] - DETAIL_CROP_RADIUS
_DETAIL_RIGHT = DETAIL_CENTER[0] + DETAIL_CROP_RADIUS
# The roots' centres (model mm): each R0.2 sits in its corner of the floor,
# the step's and the flank's, on both sides of the axis (a radius may attach
# to either silhouette of the turned fillet).
RELIEF_ROOT_CENTRES_MM = tuple(
    (side * (RELIEF_DIA / 2.0 + RELIEF_ROOT_R), axial)
    for side in (-1.0, 1.0)
    for axial in (STEP_Y + RELIEF_ROOT_R, STEP_Y + RELIEF_WIDTH - RELIEF_ROOT_R)
)
ROOT_TIP_TOL_M = 0.0002
DETAIL_KEEP = {
    # Under the crop: its extension lines fall from the floor's two ends
    # through the groove's air; its text block (~58 mm wide: the value over
    # its two-line mate callout) stands wholly right of the flank's extension
    # line (x 0.0855) with 4 mm air, and its top clears the crop circle (run
    # 20261027T030250671Z: centred between the extension lines, both struck
    # every line of it).
    "ReliefWidth": (0.1185, _DETAIL_BOTTOM - 0.008),
    # Over the crop: its line runs between the two floors 0.3 (3 mm) from the
    # step, inside the flat floor (the step's root ends 0.4 from it) and left
    # of the radius's arrow, then rises through the groove's open mouth.
    "ReliefDia": (
        _detail_xy(0.0, STEP_Y + 0.3)[0],
        _DETAIL_TOP + 0.005,
    ),
    # "2X / R0.2 MAX" up-right of the crop, opposite the step-side root's own
    # (down-left) quarter on the -x side: its leader leaves that root's
    # up-right point through the groove's mouth at about 32 deg, 3 mm over the
    # thread's crest at the flank, and right of the Ø's text.
    "ReliefRootR": (DETAIL_CENTER[0] + 0.022, DETAIL_CENTER[1] + 0.022),
}
# Left of the crop, so the label reads with its view.
DETAIL_LABEL_XY = (0.015, DETAIL_CENTER[1] + 0.005)
# The mark's letter, under the mark circle round the side view's step,
# between the step's and the thread end's extension lines.
PARENT_LETTER_XY = (STEP_X + 0.008, SIDE_CENTER[1] - 0.009)

DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# The thread callout's leader lands on the thread's major-diameter silhouette
# midway along the threaded length; the note stands up and right so the
# leader leans back onto it, clear of the dome.
THREAD_PICK = (
    (STEP_X + THREAD_END_X) / 2.0,
    SIDE_CENTER[1] + THREAD_MAJOR / 2.0 * _S / 1000.0,
)
THREAD_NOTE_XY = (THREAD_END_X + 0.012, SIDE_CENTER[1] + 0.042)
# ASME Y14.5 dimension origin (swArrowStyle_e): the open circle marks the end
# a dimension reads from, so both lengths show the step as their origin
# rather than a chain through it; the other end keeps the closed arrowhead.
ORIGIN_DIMENSIONS = ("ShankLength", "ThreadLength")
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD
# The journal's finish (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)) lands on the shank's top silhouette
# between the Ø line and the step, where the wheel runs (the Ø callout names
# it); the symbol stands just above, left of the thread callout's leader.
JOURNAL_FINISH_PICK = (STEP_X - 0.012, SIDE_CENTER[1] + PIN_DIA / 2.0 * _S / 1000.0)
JOURNAL_FINISH_SYMBOL = (STEP_X - 0.010, SIDE_CENTER[1] + 0.020)
FINISH_CHAR_HEIGHT = 0.0025
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (BACK_X + 0.020, SIDE_CENTER[1] + 0.003)


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center, so a part that is not origin-symmetric (this pin spans
    y BACK_Y..TIP_Y, about -8.9..47) lands its geometry offset from the requested center. Every
    layout constant in this recipe is authored about the intended geometry
    center; shifting by this delta makes the edge picks and text positions
    track wherever SolidWorks actually put the geometry.
    """
    outline = view_outline(adapter, view)
    if outline is None:
        raise RuntimeError(f"{label} drawing view has no outline")
    cx = (outline[0] + outline[2]) / 2.0
    cy = (outline[1] + outline[3]) / 2.0
    _telemetry.debug(
        f"{label} view geometry center ({cx:.4f}, {cy:.4f}) vs intended "
        f"({intended[0]:.4f}, {intended[1]:.4f})"
    )
    return cx - intended[0], cy - intended[1]


def _shift(
    points: dict[str, tuple[float, float]], dx: float, dy: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y + dy) for name, (x, y) in points.items()}


def _arrowheads(annotation: Any, label: str) -> list[tuple[float, int]]:
    """Each arrowhead's tip x on the sheet and its style.

    ``IDisplayData::GetArrowHeadAtIndex2`` returns tip[3], dir[3], width,
    height, style, normal[3]; a length dimension carries exactly two.
    """
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    heads = []
    for index in range(int(data.GetArrowHeadCount() or 0)):
        values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
        if len(values) < 9:
            raise RuntimeError(f"{label} arrowhead {index} is incomplete: {values!r}")
        heads.append((values[0], round(values[8])))
    if len(heads) != 2:
        raise RuntimeError(f"{label} has {len(heads)} arrowheads, expected 2")
    return heads


def _set_dimension_origin(
    adapter: Any, annotation: Any, *, origin_x: float, label: str
) -> None:
    """Put the dimension-origin circle on the arrowhead at ``origin_x``.

    Which arrowhead ``SetArrowHeadStyle2``'s first style lands on is the
    dimension's own order, so the styles are read back from the ink: if the
    circle came out at the far end, the pair is applied swapped and read
    again. Either way the sheet is proved, never assumed.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    heads = _arrowheads(annotation, label)
    near = min(range(2), key=lambda index: abs(heads[index][0] - origin_x))
    styles = [_CLOSED_ARROWHEAD, _CLOSED_ARROWHEAD]
    styles[near] = _ORIGIN_ARROWHEAD
    for attempt in (styles, styles[::-1]):
        if not display.SetArrowHeadStyle2(False, *attempt):
            raise RuntimeError(f"failed to set the {label} arrowhead styles")
        rebuild_drawing(adapter, label=f"{label} dimension origin")
        heads = _arrowheads(annotation, label)
        at_origin = min(heads, key=lambda head: abs(head[0] - origin_x))
        far = max(heads, key=lambda head: abs(head[0] - origin_x))
        if (at_origin[1], far[1]) == (_ORIGIN_ARROWHEAD, _CLOSED_ARROWHEAD):
            return
    raise RuntimeError(f"{label} origin circle is not at the step: {heads!r}")


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _exact_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points,
    straight to the sketch database (AddToDB: no sketch inference, which
    otherwise snaps the centre and rim to nearby view geometry), restore
    AddToDB, and read it back: a moved or resized circle raises
    (draw_ms_stick's exact fence)."""
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
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    actual_centre, actual_radius = native_circle_geometry(circle, label=label)
    asked_radius = math.dist(points[0], points[1])
    _telemetry.info(
        f"{label} circle: centre {actual_centre} (asked {points[0]}), radius "
        f"{actual_radius} (asked {asked_radius})"
    )
    if (
        math.dist(actual_centre, points[0]) > CIRCLE_TOL_M
        or abs(actual_radius - asked_radius) > CIRCLE_TOL_M
    ):
        raise RuntimeError(f"the {label} circle moved or changed radius")
    return circle


def _placed_detail_view(adapter: Any) -> Any:
    """Detail A, uncropped: a 10:1 *Front model view turned like the side
    view and moved so the fence's focus lands on DETAIL_CENTER; a root centre
    is projected too, so a view at another scale or handing than _detail_xy
    assumes raises."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    view.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(view.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to rotate the relief detail")
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"relief detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    center = model_point_in_view(
        adapter, view, _DETAIL_FOCUS_M, label="relief detail focus"
    )
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the relief detail onto its sheet position")
    draw.EditRebuild3()
    root_mm = RELIEF_ROOT_CENTRES_MM[0]
    for point, expected, label in (
        (_DETAIL_FOCUS_M, DETAIL_CENTER, "relief detail focus"),
        (
            (root_mm[0] / 1000.0, root_mm[1] / 1000.0, 0.0),
            _detail_xy(*root_mm),
            "step-side relief root centre",
        ),
    ):
        found = model_point_in_view(adapter, view, point, label=label)
        if math.dist(found, expected) > DETAIL_POSITION_TOL_M:
            raise RuntimeError(f"{label} sits at {found!r}, not {expected!r}")
    return view


def _crop_detail_view(adapter: Any, view: Any) -> None:
    """Crop detail A to its exact fence circle round DETAIL_CENTER; status,
    IsCropped, the outline and its style are read back and raise."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="relief detail")
    circle = _exact_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="relief-detail crop"
    )
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = _early_bound(selection.CreateSelectData(), "ISelectData")
    data.View = view
    if _early_bound(circle, "ISketchSegment").Select4(False, data) is not True:
        raise RuntimeError("cannot select the relief-detail crop circle")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"wheel-axle: relief detail {name!r}, Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"relief detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 10:1 view spans the whole 56 pin (~560 mm of sheet), the
    # crop 40 mm, so a crop that took at least halves the width.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"relief-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"relief detail's crop boundary is not its plain circle: jagged, "
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
    """Import and curate detail A's dimensions uncropped, then crop it; any
    kept dimension the crop drops raises."""
    annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="relief detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_detail_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "relief_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    if lost:
        raise RuntimeError(
            f"relief detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _mark_detail_on_side(adapter: Any, side: Any) -> None:
    """Circle detail A's fence on the side view in the outline's black."""
    _activate_view(adapter, side, label="side view")
    center = model_point_in_view(
        adapter, side, _DETAIL_FOCUS_M, label="relief detail mark"
    )
    circle = _exact_circle(
        adapter,
        side,
        center,
        DETAIL_RADIUS_MM * _S / 1000.0,
        label="relief-detail mark",
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("relief-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _add_view_note(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], *, label: str
) -> None:
    """A free note in ``view`` at ``xy`` (its top-left corner); a note that
    did not land in its view raises."""
    _activate_view(adapter, view, label=label)
    if add_note(adapter, text, *xy) is None:
        raise RuntimeError(f"failed to add the {label} note")
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if texts.count(_plain_text(text)) != 1:
        raise RuntimeError(f"{label} note did not land in its view: {texts!r}")


def _label_detail(
    adapter: Any, detail: Any, side: Any, letter_xy: tuple[float, float]
) -> None:
    """Label detail A beside its crop and letter its mark on the side view."""
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(
            "failed to pin sheet scale before labelling the relief detail"
        )
    for view, text, xy, label in (
        (detail, DETAIL_LABEL_TEXT, DETAIL_LABEL_XY, "relief-detail label"),
        (side, DETAIL_LETTER, letter_xy, "relief-detail letter"),
    ):
        _add_view_note(adapter, view, text, xy, label=label)


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one wheel-axle {name} dimension")
    return matches[0]


def _break_line_at_text(adapter: Any, annotations: list[Any], name: str) -> None:
    """Put ``name``'s value in a break of its dimension line, read back
    (draw_ch_channel_assembly._break_line_at_text)."""
    display = _early_bound(
        _early_bound(
            _named(adapter, annotations, name), "IAnnotation"
        ).GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    if display.SetBrokenLeader2(False, BROKEN_LINE_ALIGNED_TEXT) != 0:
        raise RuntimeError(f"wheel axle {name}: failed to break the dimension line")
    if int(display.GetBrokenLeader2()) != BROKEN_LINE_ALIGNED_TEXT:
        raise RuntimeError(f"wheel axle {name}: broken dimension line did not persist")


def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the text lanes its part authored
    (draw_pd_transgear_pin).

    The mates, the stack and the reference marks print nowhere else on the
    sheet, so a lost lane must fail the drawing.  Read-only: text set from
    the sheet would write through to the source part (#1942).
    """
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    printed = {
        (name, lane): str(displays[name][0].GetText(lane) or "")
        for name, lanes in wanted.items()
        for lane in lanes
    }
    wrong = {
        key: text
        for key, text in printed.items()
        if callouts.callout_rows(text) != callouts.callout_rows(wanted[key[0]][key[1]])
    }
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


def _assert_single_limits(adapter: Any, annotations: list[Any]) -> None:
    """Each relief size imported with its part's native MAX type and value."""
    for (_feature, name), (limit, tol_type) in SINGLE_LIMITS.items():
        display = _early_bound(
            _early_bound(
                _named(adapter, annotations, name), "IAnnotation"
            ).GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != tol_type:
            raise RuntimeError(
                f"{name} lost its native MAX type: {int(tolerance.Type)}"
            )
        if not math.isclose(float(dimension.SystemValue), limit / 1000.0, abs_tol=1e-9):
            raise RuntimeError(f"{name} does not measure its part's limit {limit}")


def _dress_relief_roots(adapter: Any, detail: Any, annotations: list[Any]) -> None:
    """Land detail A's ReliefRootR leader on a root's circle, on its text's
    side (draw_mg_magnifying_vertical_rod._dress_relief_roots).

    Read back: radial. SolidWorks ends a radial leader at the circle point
    facing its text and does not carry it through the centre, so
    ``ArcExtensionLineOrOppositeSide`` True draws the arc's extension out to
    that point. The rebuilt arrow tip must sit on one root's circle (either
    root, either side of the axis), on its text's side of that root's centre.
    """
    annotation = _early_bound(
        _named(adapter, annotations, "ReliefRootR"), "IAnnotation"
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported relief root radius is not radial")
    display.ArcExtensionLineOrOppositeSide = True
    if display.ArcExtensionLineOrOppositeSide is not True:
        raise RuntimeError("ReliefRootR refused its arc extension line")
    rebuild_drawing(adapter, label="relief roots radius leader")
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError("ReliefRootR has no rebuilt display data")
    data = _early_bound(raw, "IDisplayData")
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError("ReliefRootR must draw exactly one radial arrow")
    arrow = tuple(float(v) for v in data.GetArrowHeadAtIndex2(0))
    if len(arrow) != 12 or not all(math.isfinite(v) for v in arrow):
        raise RuntimeError("ReliefRootR has incomplete arrow-head coordinates")
    tip = (arrow[0], arrow[1])
    radius = RELIEF_ROOT_R * _DS / 1000.0
    text = DETAIL_KEEP["ReliefRootR"]
    for index, centre_mm in enumerate(RELIEF_ROOT_CENTRES_MM):
        centre = model_point_in_view(
            adapter,
            detail,
            (centre_mm[0] / 1000.0, centre_mm[1] / 1000.0, 0.0),
            label=f"relief root {index} centre",
        )
        off = (tip[0] - centre[0], tip[1] - centre[1])
        toward_text = (text[0] - centre[0]) * off[0] + (text[1] - centre[1]) * off[1]
        if abs(math.hypot(*off) - radius) <= ROOT_TIP_TOL_M and toward_text > 0.0:
            _telemetry.info(
                f"relief roots radius: text {display.GetText(1)!r}, arrow tip {tip} "
                f"on root {index}'s circle ({centre_mm} mm)"
            )
            return
    raise RuntimeError(
        f"ReliefRootR's arrow tip {tip} is on no relief root's circle on its "
        f"text's side (R {radius})"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Wheel Axle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"wheel axle; 3/16 drill-rod pin; {THREAD_CALLOUT}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=VIEW_SCALE)
    native = _early_bound(side, "IView")
    native.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to rotate the wheel-axle side view")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    # Detail A is placed and dimensioned FIRST: its dimensions live in
    # PinProfile with the side view's, and a dimension already on the sheet
    # is never imported again, so the side view's import skips them.
    detail = _placed_detail_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = _dimension_then_crop_detail(adapter, detail)

    dx, dy = _view_center_delta(adapter, side, SIDE_CENTER, "side")

    def spt(x: float, y: float) -> tuple[float, float]:
        return (x + dx, y + dy)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_shift(SIDE_KEEP, dx, dy),
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *detail_annotations]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_authored_text(adapter, annotations)
    _assert_single_limits(adapter, annotations)
    _dress_relief_roots(adapter, detail, annotations)
    for name in BROKEN_LINE_DIMENSIONS:
        _break_line_at_text(adapter, annotations, name)
    rebuild_drawing(adapter, label="wheel axle broken dimension lines")
    # Both lengths read from the step: the origin circle on its extension line.
    for name in ORIGIN_DIMENSIONS:
        _set_dimension_origin(
            adapter,
            _named(adapter, annotations, name),
            origin_x=spt(STEP_X, 0.0)[0],
            label=f"wheel axle {name}",
        )
    add_view_centerline(
        adapter,
        side,
        face_xy=spt(*CENTERLINE_PICK),
        label="wheel axle turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=spt(*THREAD_PICK),
        note_xy=spt(*THREAD_NOTE_XY),
        label="wheel axle thread callout",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=spt(*JOURNAL_FINISH_PICK),
        entity_type="SILHOUETTE",
        symbol_xy=spt(*JOURNAL_FINISH_SYMBOL),
        leader_attach_xy=spt(*JOURNAL_FINISH_PICK),
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_axle_journal"),
        label="wheel axle journal finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    # The mark and the labels go on once every pick is done, so no
    # coordinate pick in the side view meets the mark circle.
    _mark_detail_on_side(adapter, side)
    _label_detail(adapter, detail, side, spt(*PARENT_LETTER_XY))

    # The shaded isometric shows the #4-40 the callout names; imported before
    # finalize's note cleanup, so its label is counted rather than first
    # appearing at the native save (draw_pn_pen_hanger).
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, iso)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "wheel-axle isometric cosmetic threads: "
            f"seeds/instances={(thread_seeds, thread_instances)!r}, expected (1, 1)"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Axle Manufacturing Drawing",
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
