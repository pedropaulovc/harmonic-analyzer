r"""Create the curated machinist drawing for the magnifying vertical rod.

A Ø5 x 132.5 brass rod (MHA-MG-004, #1559): a #4-40 threaded top end with a
relief at the shoulder that seats on MHA-MG-002, a full hemisphere at the
bottom. The rod axis is local +X, so the *Front view is the long side
elevation, thread tip left.

Sheet: the side view at 2:1 (the rod 265 mm long) carries the Ø5, the body
length from the shoulder (origin circle on the shoulder), the overall
"(132.5)" reference, the dome R and the body's Ra 3.2 thumb-screw seat
(the output fixture's screw bears wherever the fixture is set; its reason
beside the symbol); detail A, a
cropped 8:1 *Front model view (draw_pd_transgear_knob_shaft's detail-B
recipe), carries the 7.5 threaded end: the thread length from the shoulder
(origin circle) with the seat it guards, the relief's width, its Ø MAX and
its two root radii (one "2X R MAX"), and the thread callout. A 1:1 shaded
isometric shows the cosmetic thread.
No general notes: every requirement rides its own callout.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_vertical_rod.py mg-magnifying-vertical-rod
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
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _surface_finish import surface_finish_by_key
from mg_magnifying_vertical_rod_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    RELIEF_DIA,
    RELIEF_ROOT_R,
    RELIEF_ROOT_R_TOL_TYPE,
    RELIEF_ROOTS_CALLOUT,
    RELIEF_START_X,
    ROD_DIA,
    ROD_LENGTH,
    SEAT_FINISH_REASON,
    SHOULDER_X,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_MAJOR,
    TIP_CHAMFER,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_vertical_rod"]
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

# 2:1 lays the 132.5 rod 265 mm long and its Ø5 10 mm across, above the title
# block (top 0.066, left 0.216) on the B landscape sheet; at 1:1 the 7.5
# threaded end would be 7.5 mm of sheet, hence detail A at 8:1.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.190, 0.105)
_MID_X = ROD_LENGTH / 2.0
ISO_SCALE = (1, 1)
ISO_CENTER = (0.330, 0.200)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X station on the side view (centred on the bbox,
    thread tip to dome tip)."""
    return SIDE_CENTER[0] + (model_x_mm - _MID_X) * _S / 1000.0


TIP_X = _sheet_x(0.0)
SHOULDER_SHEET_X = _sheet_x(SHOULDER_X)
DOME_TIP_X = _sheet_x(ROD_LENGTH)

# Side view (drawing-guidelines.md rule 11, turned parts read like the lathe):
# the body length baselines from the shoulder, its origin circle on the
# shoulder's extension line, on the row under the rod; the overall reference
# runs outermost under it, left of the body length's text and clear of the
# title block (top 0.066 right of 0.216).
SIDE_KEEP = {
    "BodyLength": ((SHOULDER_SHEET_X + DOME_TIP_X) / 2.0, SIDE_CENTER[1] - 0.012),
    "OverallLength": (_sheet_x(0.25 * ROD_LENGTH), SIDE_CENTER[1] - 0.027),
    # The Ø line crosses the body three quarters along, its value above the
    # rod, clear of detail A's rows, of the seat's reason and of the body
    # length's text; a plain title-block .X size, no callout.
    "RodDia": (_sheet_x(0.75 * ROD_LENGTH), SIDE_CENTER[1] + 0.020),
    # Above-right of the dome: the leader lands on its upper quarter.
    "DomeR": (DOME_TIP_X + 0.012, SIDE_CENTER[1] + 0.017),
}

# --- Detail A: the threaded end at 8:1 ---------------------------------------
# Native detail views imported no dimensions (draw_pd_transgear_knob_shaft
# detail B), so detail A is a second *Front model view at 8:1, moved so the
# fence's focus lands on DETAIL_CENTER and cropped to the fence circle.
DETAIL_SCALE = (8, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1]
DETAIL_LETTER = "A"
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
# The fence, model mm (x, y): mid-thread-end, 0.5 over the axis. Radius 5.0
# holds the tip face and its axis point (3.78 off), the shoulder's outer
# corner (4.25 off), the relief and the shoulder's lower root (4.09 off at
# its far edge): every reference the four dimensions take, since a crop
# drops a dimension whose reference it cuts away.
DETAIL_FOCUS_MM = (SHOULDER_X / 2.0, 0.5)
_DETAIL_FOCUS_M = (DETAIL_FOCUS_MM[0] / 1000.0, DETAIL_FOCUS_MM[1] / 1000.0, 0.0)
DETAIL_RADIUS_MM = 5.0
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS / 1000.0
# Upper left, over the side view's tip: x 0.080-0.160, y 0.165-0.245.
DETAIL_CENTER = (0.120, 0.205)
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4


def _detail_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) mm in detail A (model +X runs right)."""
    return (
        DETAIL_CENTER[0] + (x_mm - DETAIL_FOCUS_MM[0]) * _DS / 1000.0,
        DETAIL_CENTER[1] + (y_mm - DETAIL_FOCUS_MM[1]) * _DS / 1000.0,
    )


_DETAIL_TOP = DETAIL_CENTER[1] + DETAIL_CROP_RADIUS
_DETAIL_BOTTOM = DETAIL_CENTER[1] - DETAIL_CROP_RADIUS
DETAIL_SHOULDER_X = _detail_xy(SHOULDER_X, 0.0)[0]
# The radius lands on its first pick's edge (build_mg_magnifying_vertical_rod)
# under the axis, as the filing stud's did: the shoulder's lower root, its
# arc the up-right quarter round this centre (model mm; sheet 0.1484, 0.1920).
# Its text stands opposite that quarter, so the arrow lands on the root
# circle's down-left side, on the arc's extension (farm r4, 0676a2115: tip
# (0.14757, 0.19063), R 1.6 mm off the centre).
RELIEF_ROOT_CENTRE_MM = (
    SHOULDER_X - RELIEF_ROOT_R,
    -(RELIEF_DIA / 2.0 + RELIEF_ROOT_R),
)
ROOT_TIP_TOL_M = 0.0002
DETAIL_KEEP = {
    # Its line rises through the relief's air to text over the crop, 0.5
    # (4 mm) off the thread end: right of the thread-side root's tangent
    # (2.4 mm), and left of the root radius's leader under the relief.
    "ReliefDia": (_detail_xy(RELIEF_START_X + 0.5, 0.0)[0], _DETAIL_TOP + 0.008),
    # Under the crop, nearest the part, its text right of the shoulder's
    # extension line (outside both of its own) and over the thread length's
    # block, which it no longer shares a column with.
    "ReliefWidth": (DETAIL_SHOULDER_X + 0.013, _DETAIL_BOTTOM - 0.003),
    # The next row down: the thread end from the shoulder to the tip.
    "ThreadLength": (_detail_xy(SHOULDER_X / 2.0, 0.0)[0], _DETAIL_BOTTOM - 0.020),
    # "2X / R0.2 MAX" under the thread, opposite its arc: x ~0.108-0.128,
    # 22 mm under the thread's silhouette and ~7 mm over the thread length's
    # "+0.25". Its leader rises up-right at ~51 deg through the root centre
    # to the arc, crossing only the relief width's thread-end extension line
    # (y ~0.179) and passing ~3.5 mm under the Ø's lower arrow stub.
    "ReliefRootR": (DETAIL_SHOULDER_X - 0.032, _DETAIL_BOTTOM + 0.003),
}
# The thread callout's leader lands on the major-diameter silhouette mid-
# thread; the note stands up and left of the crop.
THREAD_PICK = _detail_xy((TIP_CHAMFER + RELIEF_START_X) / 2.0, THREAD_MAJOR / 2.0)
THREAD_NOTE_XY = (0.030, DETAIL_CENTER[1] + 0.036)
THREAD_NOTE_TEXT = f"{THREAD_CALLOUT}\nTIP 45° CHAMFER TO MINOR Ø"
# Under detail A's lower-left, left of the thread length's tip extension
# line (sheet x 0.090), so the label reads with its view.
DETAIL_LABEL_XY = (0.050, _DETAIL_BOTTOM + 0.008)
# The mark's letter, up-left of the mark circle round the side view's tip.
PARENT_LETTER_XY = (TIP_X - 0.010, SIDE_CENTER[1] + 0.014)

DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Each length names the face it reads from (drawing-guidelines.md rule 4);
# the thread length's band names its mate at the callout: it keeps the tip
# off the bottom of MHA-MG-002's tap so the shoulder, not the tip, seats.
DIMENSION_CALLOUTS = {
    "BodyLength": "FROM SHOULDER",
    "ThreadLength": "FROM SHOULDER\nSEATS ON MHA-MG-002;\nTIP CLEARS ITS TAP",
    "DomeR": "TANGENT HEMISPHERE",
}
# The roots' count stands above their one radius.
DIMENSION_CALLOUTS_ABOVE = {"ReliefRootR": RELIEF_ROOTS_CALLOUT}
# ASME Y14.5 dimension origin (swArrowStyle_e): both lengths read from the
# shoulder, the seating face that plumbs the rod.
ORIGIN_DIMENSIONS = ("BodyLength", "ThreadLength")
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD
# A point on the body face, clear of the Ø dimension line.
CENTERLINE_PICK = (_sheet_x(0.2 * ROD_LENGTH), SIDE_CENTER[1] + 0.002)
# The thumb-screw seat's Ra 3.2 (SURFACE_FINISHES "screw_seat") lands on the
# body's top silhouette 0.40 along, inside the fixture screw's reach; the
# symbol stands just over it, its bent leader's shoulder left of the V, and
# its reason reads on the symbol's own row, just right of its "Ra 3.2" (r4
# review: a label floating near detail A did not read as the symbol's). r5
# farm render (20261017T070700133Z) measured the symbol's ink against its
# anchor: the "Ra 3.2" text ends 14.9 mm right of it and spans 3.7..7.0 mm
# over it; a note's position is its top-left corner and the 16-character
# reason prints 44.6 x 3.9 mm. So the reason starts 3 mm past the "Ra 3.2",
# centred on its row, and ends ~228 mm, 15 mm short of the Ø value's text
# (~244 mm); the symbol's shoulder (~161 mm) stays right of detail A's
# shoulder extension line (150 mm) and under its thread-length row (132 mm).
_ROD_TOP_Y = SIDE_CENTER[1] + ROD_DIA / 2.0 * _S / 1000.0
SEAT_FINISH_PICK = (_sheet_x(0.40 * ROD_LENGTH), _ROD_TOP_Y)
SEAT_FINISH_SYMBOL = (SEAT_FINISH_PICK[0] + 0.002, _ROD_TOP_Y + 0.014)
SEAT_REASON_XY = (SEAT_FINISH_SYMBOL[0] + 0.018, SEAT_FINISH_SYMBOL[1] + 0.0075)
FINISH_CHAR_HEIGHT = 0.0025
ISO_NOTE_XY = (0.290, 0.160)


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center; the rod spans x 0..ROD_LENGTH from its origin at the tip, so
    every side-view constant (authored about the box center) shifts by this.
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
    """Each arrowhead's tip x on the sheet and its style (draw_mg_wheel_axle)."""
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
    """Put the dimension-origin circle on the arrowhead at ``origin_x``, read
    back from the ink (draw_mg_wheel_axle)."""
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
    raise RuntimeError(f"{label} origin circle is not at the shoulder: {heads!r}")


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
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points
    (draw_pd_transgear_knob_shaft). Without ``add_to_db`` the circle is left
    SELECTED, which Crop2 consumes."""
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
    """Detail A, uncropped: an 8:1 *Front model view moved so the fence's
    focus lands on DETAIL_CENTER; the thread pick is projected too, so a view
    at another scale or handing than _detail_xy assumes raises."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"thread detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    center = model_point_in_view(
        adapter, view, _DETAIL_FOCUS_M, label="thread detail focus"
    )
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the thread detail onto its sheet position")
    draw.EditRebuild3()
    pick_m = (
        (TIP_CHAMFER + RELIEF_START_X) / 2000.0,
        THREAD_MAJOR / 2000.0,
        0.0,
    )
    for point, expected, label in (
        (_DETAIL_FOCUS_M, DETAIL_CENTER, "thread detail focus"),
        (pick_m, THREAD_PICK, "thread callout landing"),
    ):
        found = model_point_in_view(adapter, view, point, label=label)
        if math.dist(found, expected) > DETAIL_POSITION_TOL_M:
            raise RuntimeError(f"{label} sits at {found!r}, not {expected!r}")
    return view


def _crop_detail_view(adapter: Any, view: Any) -> None:
    """Crop detail A to its fence circle round DETAIL_CENTER; status,
    IsCropped, the outline and its style are read back and raise."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="thread detail")
    _sketch_circle(
        adapter, view, DETAIL_CENTER, DETAIL_CROP_RADIUS, label="thread-detail crop"
    )
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"vertical-rod: thread detail {name!r}, Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"thread detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 8:1 view spans the whole 132.5 rod (~1060 mm of sheet),
    # the crop 80 mm, so a crop that took at least halves the width.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"thread-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"thread detail's crop boundary is not its plain circle: jagged, "
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
        view_label="thread detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, detail)
    _crop_detail_view(adapter, detail)
    after = _view_dimension_names(adapter, detail)
    lost = sorted(set(DETAIL_KEEP) - set(after))
    _telemetry.event(
        "thread_detail.crop",
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    if lost:
        raise RuntimeError(
            f"thread detail lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _mark_detail_on_side(adapter: Any, side: Any) -> None:
    """Circle detail A's fence on the side view in the outline's black."""
    _activate_view(adapter, side, label="side view")
    center = model_point_in_view(
        adapter, side, _DETAIL_FOCUS_M, label="thread detail mark"
    )
    circle = _sketch_circle(
        adapter,
        side,
        center,
        DETAIL_RADIUS_MM * _S / 1000.0,
        label="thread-detail mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("thread-detail mark circle colour did not persist")
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
            "failed to pin sheet scale before labelling the thread detail"
        )
    for view, text, xy, label in (
        (detail, DETAIL_LABEL_TEXT, DETAIL_LABEL_XY, "thread-detail label"),
        (side, DETAIL_LETTER, letter_xy, "thread-detail letter"),
    ):
        _add_view_note(adapter, view, text, xy, label=label)


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one vertical-rod {name} dimension")
    return matches[0]


def _dress_relief_roots(adapter: Any, detail: Any, annotations: list[Any]) -> None:
    """Prove detail A's imported ReliefRootR prints the roots' R MAX under
    its "2X", and land its leader on the shoulder's lower root.

    Read back: radial, measuring RELIEF_ROOT_R, the part's native swTolMAX
    and the count above the value. The text stands down-left of the root,
    opposite the arc's own (up-right) quarter. SolidWorks ends a radial
    leader at the circle point facing its text and does not carry it through
    the centre (farm r4, 0676a2115), so ``ArcExtensionLineOrOppositeSide``
    True draws the arc's extension out to that point. The rebuilt arrow tip
    must sit on the root's circle, on the text's side of its centre.
    """
    annotation = _early_bound(
        _named(adapter, annotations, "ReliefRootR"), "IAnnotation"
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported relief root radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != RELIEF_ROOT_R_TOL_TYPE:
        raise RuntimeError(
            f"ReliefRootR lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), RELIEF_ROOT_R / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("ReliefRootR does not measure the relief roots")
    callout = str(display.GetText(3) or "")  # swDimensionTextCalloutAbove
    if callout != RELIEF_ROOTS_CALLOUT:
        raise RuntimeError(f"ReliefRootR count did not persist: {callout!r}")
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
    centre = model_point_in_view(
        adapter,
        detail,
        (RELIEF_ROOT_CENTRE_MM[0] / 1000.0, RELIEF_ROOT_CENTRE_MM[1] / 1000.0, 0.0),
        label="shoulder's lower relief root centre",
    )
    radius = RELIEF_ROOT_R * _DS / 1000.0
    off = (tip[0] - centre[0], tip[1] - centre[1])
    if abs(math.hypot(*off) - radius) > ROOT_TIP_TOL_M or max(off) > ROOT_TIP_TOL_M:
        raise RuntimeError(
            f"ReliefRootR's arrow tip {tip} is not on the shoulder's lower root "
            f"circle's text side (centre {centre}, R {radius})"
        )
    _telemetry.info(
        f"relief roots radius: text {display.GetText(1)!r}, MAX type, count "
        f"{callout!r}, arrow tip {tip} on the shoulder's lower root"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-vertical-rod source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Vertical Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"magnifying vertical rod; turned brass rod; {THREAD_CALLOUT} end",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    # Detail A is placed and dimensioned FIRST: its three dimensions live in
    # RodProfile with the side view's, and a dimension already on the sheet
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
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    _dress_relief_roots(adapter, detail, annotations)
    for name, origin_x in (
        ("BodyLength", spt(SHOULDER_SHEET_X, 0.0)[0]),
        ("ThreadLength", DETAIL_SHOULDER_X),
    ):
        _set_dimension_origin(
            adapter,
            _named(adapter, annotations, name),
            origin_x=origin_x,
            label=f"vertical rod {name}",
        )
    add_view_centerline(
        adapter,
        side,
        face_xy=spt(*CENTERLINE_PICK),
        label="vertical rod turning axis",
    )
    add_attached_note(
        adapter,
        detail,
        text=THREAD_NOTE_TEXT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="vertical rod thread callout",
        entity_type="SILHOUETTE",
    )
    # The seat's symbol lands by a coordinate pick too, so it goes on before
    # the mark circle.
    add_surface_finish(
        adapter,
        side,
        edge_xy=spt(*SEAT_FINISH_PICK),
        entity_type="SILHOUETTE",
        symbol_xy=spt(*SEAT_FINISH_SYMBOL),
        leader_attach_xy=spt(*SEAT_FINISH_PICK),
        control=surface_finish_by_key(SURFACE_FINISHES, "screw_seat"),
        label="vertical rod thumb-screw seat finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    # The mark and the labels go on once every pick is done, so no
    # coordinate pick in the side view meets the mark circle.
    _mark_detail_on_side(adapter, side)
    _label_detail(adapter, detail, side, spt(*PARENT_LETTER_XY))
    _add_view_note(
        adapter,
        side,
        SEAT_FINISH_REASON,
        spt(*SEAT_REASON_XY),
        label="screw-seat reason",
    )

    add_property_linked_note(adapter, "Iso View Note", *ISO_NOTE_XY)
    # The shaded isometric shows the #4-40 the callout names; imported before
    # finalize's note cleanup (draw_mg_wheel_axle).
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, iso)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "vertical-rod isometric cosmetic threads: "
            f"seeds/instances={(thread_seeds, thread_instances)!r}, expected (1, 1)"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Vertical Rod Manufacturing Drawing",
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
