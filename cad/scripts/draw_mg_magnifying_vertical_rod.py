r"""Create the curated machinist drawing for the magnifying vertical rod.

A Ø5 x 132.5 brass rod (MHA-MG-004, #1559): a #4-40 threaded top end with a
relief at the shoulder that seats on MHA-MG-002, a full hemisphere at the
bottom. The rod axis is local +X, so the *Front view is the long side
elevation, thread tip left.

Sheet: the side view at 2:1 (the rod 265 mm long) carries the Ø5, the body
length from the shoulder (origin circle on the shoulder), the dome R and the
OD's finish; detail A, a cropped 8:1 *Front model view (draw_pd_transgear_knob_
shaft's detail-B recipe), carries the 7.5 threaded end: the thread length
from the shoulder (origin circle), the relief's width and Ø, and the thread
callout. A 1:1 shaded isometric shows the cosmetic thread.

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
from _surface_finish import surface_finish_by_key
import _telemetry
from mg_magnifying_vertical_rod_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    RELIEF_START_X,
    ROD_DIA,
    ROD_LENGTH,
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
R = ROD_DIA / 2.0
ISO_SCALE = (1, 1)
ISO_CENTER = (0.330, 0.200)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X station on the side view (centred on the bbox,
    thread tip to dome tip)."""
    return SIDE_CENTER[0] + (model_x_mm - _MID_X) * _S / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    return SIDE_CENTER[1] + model_y_mm * _S / 1000.0


TIP_X = _sheet_x(0.0)
SHOULDER_SHEET_X = _sheet_x(SHOULDER_X)
DOME_TIP_X = _sheet_x(ROD_LENGTH)

# Side view (drawing-guidelines.md rule 11, turned parts read like the lathe):
# the body length baselines from the shoulder, its origin circle on the
# shoulder's extension line, on one row under the rod over the title block.
SIDE_KEEP = {
    "BodyLength": ((SHOULDER_SHEET_X + DOME_TIP_X) / 2.0, SIDE_CENTER[1] - 0.025),
    # The Ø line crosses the body a third of the way along, text above it.
    "RodDia": (_sheet_x(0.33 * ROD_LENGTH), SIDE_CENTER[1] + 0.020),
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
# corner (4.25 off) and the relief: every reference the three dimensions
# take, since a crop drops a dimension whose reference it cuts away.
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
_RELIEF_MID_X = (RELIEF_START_X + SHOULDER_X) / 2.0
DETAIL_SHOULDER_X = _detail_xy(SHOULDER_X, 0.0)[0]
DETAIL_KEEP = {
    # Its line rises through the relief's air to text over the crop.
    "ReliefDia": (_detail_xy(_RELIEF_MID_X, 0.0)[0], _DETAIL_TOP + 0.008),
    # Under the crop, nearest the part: the relief's width.
    "ReliefWidth": (_detail_xy(_RELIEF_MID_X, 0.0)[0], _DETAIL_BOTTOM - 0.007),
    # The next row down: the thread end from the shoulder to the tip.
    "ThreadLength": (_detail_xy(SHOULDER_X / 2.0, 0.0)[0], _DETAIL_BOTTOM - 0.020),
}
# The thread callout's leader lands on the major-diameter silhouette mid-
# thread; the note stands up and left of the crop.
THREAD_PICK = _detail_xy((TIP_CHAMFER + RELIEF_START_X) / 2.0, THREAD_MAJOR / 2.0)
THREAD_NOTE_XY = (0.030, DETAIL_CENTER[1] + 0.036)
THREAD_NOTE_TEXT = f"{THREAD_CALLOUT}\nTIP 45° CHAMFER TO MINOR Ø"
DETAIL_LABEL_XY = (0.020, DETAIL_CENTER[1] - 0.020)
# The mark's letter, up-left of the mark circle round the side view's tip.
PARENT_LETTER_XY = (TIP_X - 0.010, SIDE_CENTER[1] + 0.014)

DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Each length names the face it reads from (drawing-guidelines.md rule 4).
DIMENSION_CALLOUTS = {
    "BodyLength": "FROM SHOULDER",
    "ThreadLength": "FROM SHOULDER",
}
# ASME Y14.5 dimension origin (swArrowStyle_e): both lengths read from the
# shoulder, the seating face that plumbs the rod.
ORIGIN_DIMENSIONS = ("BodyLength", "ThreadLength")
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD
# drawing-guidelines.md rule 6: the output fixture slides on the Ø5 OD; the
# symbol lands on the body's top silhouette two-thirds along, right of the Ø.
OD_FINISH_PICK = (_sheet_x(0.6 * ROD_LENGTH), _sheet_y(R))
OD_FINISH_SYMBOL = (_sheet_x(0.6 * ROD_LENGTH) + 0.004, SIDE_CENTER[1] + 0.015)
FINISH_CHAR_HEIGHT = 0.0025
# A point on the body face, clear of the Ø dimension line.
CENTERLINE_PICK = (_sheet_x(0.2 * ROD_LENGTH), SIDE_CENTER[1] + 0.002)
# Bottom-left, left of the title block, under the body-length row.
NOTES_XY = (0.020, 0.060)
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


def _label_detail(
    adapter: Any, detail: Any, side: Any, letter_xy: tuple[float, float]
) -> None:
    """Label detail A beside its crop and letter its mark on the side view;
    a note that did not land in its view raises."""
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
        _activate_view(adapter, view, label=label)
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to add the {label} note")
        texts = [
            _plain_text(_early_bound(found, "INote").GetText() or "")
            for found in (_early_bound(view, "IView").GetNotes() or ())
        ]
        if texts.count(_plain_text(text)) != 1:
            raise RuntimeError(f"{label} note did not land in its view: {texts!r}")


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one vertical-rod {name} dimension")
    return matches[0]


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
            "Manufacturing Notes",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
    add_surface_finish(
        adapter,
        side,
        edge_xy=spt(*OD_FINISH_PICK),
        entity_type="SILHOUETTE",
        symbol_xy=spt(*OD_FINISH_SYMBOL),
        leader_attach_xy=spt(*OD_FINISH_PICK),
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_vrod_slide"),
        label="vertical rod OD finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    # The mark and the labels go on once every pick is done, so no
    # coordinate pick in the side view meets the mark circle.
    _mark_detail_on_side(adapter, side)
    _label_detail(adapter, detail, side, spt(*PARENT_LETTER_XY))

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
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
