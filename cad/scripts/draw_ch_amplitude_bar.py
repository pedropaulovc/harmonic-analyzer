r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only), a 4:1 top end view for the square
section, a small 1:8 isometric, and a 4:1 native detail of each end notch that
carries its centring ledge, width and depth (and, at the foot, the floor's Ra
symbol); the top pin hole is dimensioned in the notes.  The sheet runs at 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_amplitude_bar.py amplitude-bar
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from ch_amplitude_bar_drawing_spec import SURFACE_FINISHES
from ch_amplitude_bar_spec import (
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_WIDTH,
    BOTTOM_NOTCH_HEIGHT,
    BOTTOM_NOTCH_WIDTH,
    DRAWING_DIMENSIONS,
    BOTTOM_NOTCH_OFFSET,
    DRAWING_PRECISION,
    TOP_NOTCH_HEIGHT,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view, view_name


SPEC = DRAWINGS_BY_NAME["ch_amplitude_bar"]
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

SHEET_SCALE = (1.0, 4.0)  # 1:4
FRONT_CENTER = (0.110, 0.140)
TOP_CENTER = (0.220, 0.150)  # square-section end view (4:1)
ISO_CENTER = (0.330, 0.140)


FRONT_KEEP = {
    "BarLength": (0.075, FRONT_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}


@dataclass(frozen=True)
class NotchDetail:
    """A detail of one end notch: a cropped 4:1 *Front model view.

    ``fence_mm`` is the crop circle's centre in part (x, y) -- the Front-plane
    profile frame the front view shows unrotated, bar width along x from the
    origin corner, length along y -- and ``centre`` where that point lands on
    the sheet.
    """

    label: str
    scale: tuple[int, int]
    fence_mm: tuple[float, float]
    radius_mm: float
    centre: tuple[float, float]

    @property
    def mm(self) -> float:
        """Sheet metres per part millimetre in the detail."""
        return self.scale[0] / self.scale[1] / 1000.0

    def sheet_xy(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        return (
            self.centre[0] + (x_mm - self.fence_mm[0]) * self.mm,
            self.centre[1] + (y_mm - self.fence_mm[1]) * self.mm,
        )

    @property
    def label_xy(self) -> tuple[float, float]:
        """The view-owned label note's top centre, under the crop circle."""
        return (
            self.centre[0],
            self.centre[1] - self.radius_mm * self.mm - DETAIL_LABEL_DROP,
        )

    @property
    def label_text(self) -> str:
        """The native detail label's words."""
        return f"DETAIL {self.label}\nSCALE {self.scale[0]} : {self.scale[1]}"

    @property
    def crop_radius(self) -> float:
        """The crop circle's radius on the sheet, metres."""
        return self.radius_mm * self.mm

    @property
    def mark_radius(self) -> float:
        """The same circle drawn on the 1:4 front view, metres."""
        return self.radius_mm * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0


# A model view has no native label the API can show, so each detail's label
# is a note the view owns, in the native label's words, its top edge this far
# under the crop circle; the front view carries the crop circle and the letter,
# east of the bar.
DETAIL_LABEL_DROP = 0.007
PARENT_LETTER_GAP = 0.005
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
NOTE_CENTRING_PASSES = 2

# At 1:4 an end notch is under a millimetre on the sheet, so each end's
# centring ledge, width and depth -- the foot notch's depth with its one-sided
# band (Codex #936 PRRT_kwDOPHDy386mWF0L) -- print in a 4:1 detail (Main
# ruling 2026-09-27). Each is a cropped *Front model view, dimensioned while
# uncropped and cropped after: r743-6 (d92938949, leaf
# 20260927T020523Z-1-e3f9f1f7) showed a native detail of the front view
# refusing the targeted import (available=[]), the MHA-VN-031 / MHA-DT-022 / MHA-DT-024
# pattern (the pc-r15 kink detail, d6b8ed93f). DETAIL A (the foot) sits under
# the end view, left of the title block, its circle centred on the bar's end,
# right of the notch, to take the width row and the floor's Ra symbol;
# DETAIL B (the 12.7-deep top notch) right of the notes, left of and above the
# isometric. A crop drops any dimension whose reference lies outside it, so
# every printed edge's ends stay inside the circle
# (test_notch_details_frame_their_ends...).
DETAIL_A = NotchDetail("A", (4, 1), (BAR_WIDTH / 2.0 + 2.0, 0.0), 7.5, (0.170, 0.100))
DETAIL_B = NotchDetail(
    "B", (4, 1), (BAR_WIDTH / 2.0, BAR_LENGTH - 6.0), 8.0, (0.300, 0.205)
)
# A callout's text stands this far outside the bar's edge, or outside
# DETAIL A's fence; a width/ledge row this far outside the bar's end.
DETAIL_TEXT_GAP = 0.010
DETAIL_A_FENCE_TEXT_GAP = 0.014
DETAIL_ROW_GAP = 0.012
DETAIL_A_WIDTH_ROW_GAP = 0.020
# A width with its +0.3/0.0 stack prints ~20 mm wide, wider than the 12.4 mm
# mouth at 4:1: centred on the mouth it straddled both extension lines, and in
# DETAIL A the Ra leader ran through it (r743-6b, 64fedd3cc). So each width's
# text stands west of the bar, its centre this far out from the bar's edge,
# and the dimension line runs out to it.
WIDTH_TEXT_OFFSET = 0.014
_DETAIL_A_TEXT_X = (
    DETAIL_A.centre[0] - DETAIL_A.radius_mm * DETAIL_A.mm - DETAIL_A_FENCE_TEXT_GAP
)
_DETAIL_A_ROW_Y = DETAIL_A.sheet_xy(0.0, 0.0)[1] - DETAIL_ROW_GAP
_DETAIL_A_WIDTH_ROW_Y = DETAIL_A.sheet_xy(0.0, 0.0)[1] - DETAIL_A_WIDTH_ROW_GAP
DETAIL_A_KEEP = {
    # Left of the fence, level with the notch: the depth and its band.
    "BottomNotchHeight": (
        _DETAIL_A_TEXT_X,
        DETAIL_A.sheet_xy(0.0, BOTTOM_NOTCH_HEIGHT / 2.0)[1],
    ),
    # One row under the open end: the centring ledge, its text left of the
    # fence. The width a row lower, its witnesses running down the walls
    # through the notch's air and its text west of the bar, so its dimension
    # line runs west and leaves the air under the right cheek to the Ra symbol.
    "BottomLeftLedge": (_DETAIL_A_TEXT_X, _DETAIL_A_ROW_Y),
    "BottomNotchWidth": (
        DETAIL_A.sheet_xy(0.0, 0.0)[0] - WIDTH_TEXT_OFFSET,
        _DETAIL_A_WIDTH_ROW_Y,
    ),
}
_DETAIL_B_TEXT_X = DETAIL_B.sheet_xy(BAR_WIDTH, 0.0)[0] + DETAIL_TEXT_GAP
_DETAIL_B_ROW_Y = DETAIL_B.sheet_xy(0.0, BAR_LENGTH)[1] + DETAIL_ROW_GAP
DETAIL_B_KEEP = {
    "TopNotchHeight": (
        _DETAIL_B_TEXT_X,
        DETAIL_B.sheet_xy(0.0, BAR_LENGTH - TOP_NOTCH_HEIGHT / 2.0)[1],
    ),
    # One row over the open end, chained on the ledge's inner witness: the
    # width's text west of the bar, the ledge's east of it.
    "TopNotchWidth": (
        DETAIL_B.sheet_xy(0.0, 0.0)[0] - WIDTH_TEXT_OFFSET,
        _DETAIL_B_ROW_Y,
    ),
    "TopRightLedge": (_DETAIL_B_TEXT_X, _DETAIL_B_ROW_Y),
}

# The foot notch floor's Ra (Main ruling B, 2026-09-27). The symbol is ~17 mm
# wide at the fleet's 2.5 mm height, wider than the 12.7 mm mouth, so it
# stands under the right cheek, inside the fence, and its bent leader climbs
# through the mouth to the floor. With the width row hanging under the mouth,
# a leader out of it must cross a witness or the dimension line; it crosses
# only the right witness, between the bar's end and the row (an extension
# line may be crossed; a dimension line should not be).
FLOOR_FINISH_ATTACH = DETAIL_A.sheet_xy(BAR_WIDTH / 2.0 + 0.5, BOTTOM_NOTCH_HEIGHT)
FLOOR_FINISH_SYMBOL = (
    DETAIL_A.sheet_xy(BAR_WIDTH / 2.0, 0.0)[0] + 0.0163,
    DETAIL_A.sheet_xy(0.0, 0.0)[1] - 0.017,
)
FINISH_CHAR_HEIGHT = 0.0025
# The bent leader's shoulder runs this far from the symbol's vertex toward the
# attach point before it turns (measured on the pivot-shaft sheet, r743-5).
FINISH_SHOULDER = 0.0063


# The cropped-detail helpers below are copied from draw_dt_pinion_spring's pc-r15
# kink detail (d6b8ed93f); a shared crop module is #1036, after the release.


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
    Without ``add_to_db`` the circle is left SELECTED, which is what Crop2
    consumes.
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


def _placed_detail_view(adapter: Any, detail: NotchDetail) -> Any:
    """``detail``, uncropped: a standalone *Front model view at its scale,
    moved so the circle's centre lands on ``detail.centre`` (checked to
    DETAIL_POSITION_TOL_M)."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *detail.centre, scale=detail.scale),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in detail.scale):
        raise RuntimeError(
            f"detail {detail.label} scale {ratio!r}, expected {detail.scale!r}"
        )
    focus = (detail.fence_mm[0] / 1000.0, detail.fence_mm[1] / 1000.0, 0.0)
    label = f"detail {detail.label} centre"
    center = model_point_in_view(adapter, view, focus, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + detail.centre[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move detail {detail.label} onto its spot")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, focus, label=label)
    if math.dist(center, detail.centre) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"detail {detail.label} centre sits at {center!r}, not {detail.centre!r}"
        )
    return view


def _crop_detail_view(adapter: Any, view: Any, detail: NotchDetail) -> None:
    """Crop ``view`` to its circle round ``detail.centre``: activate it,
    sketch the circle in its own sketch and Crop2 while the circle is still
    selected. Crop status, IsCropped, the outline and its style are read back
    and raise."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    label = f"detail {detail.label}"
    name = _activate_view(adapter, view, label=label)
    _sketch_circle(
        adapter, view, detail.centre, detail.crop_radius, label=f"{label} crop"
    )
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"amplitude-bar: {label} {name!r} Crop2 status {status}, IsCropped "
        f"{cropped}, outline {tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 4:1 view spans the whole 808 mm bar (~3.2 m on the
    # sheet); the crop is one ~60 mm circle.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[3] - outline[1] > (uncropped[3] - uncropped[1]) / 2.0
    ):
        raise RuntimeError(
            f"{label} crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"{label}'s crop boundary is not its plain circle: jagged, "
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


def _dimension_then_crop(
    adapter: Any, view: Any, detail: NotchDetail, keep: dict[str, tuple[float, float]]
) -> list[Any]:
    """Import and curate ``detail``'s dimensions while it is uncropped, then
    crop it. The names read back before and after the crop ride one
    ``notch_detail.crop`` event; any kept dimension missing after raises."""
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=f"detail {detail.label}",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, view)
    _crop_detail_view(adapter, view, detail)
    after = _view_dimension_names(adapter, view)
    lost = sorted(set(keep) - set(after))
    _telemetry.event(
        "notch_detail.crop",
        detail=detail.label,
        dimensions_before=",".join(before),
        dimensions_after=",".join(after),
        lost=",".join(lost),
    )
    _telemetry.info(
        f"amplitude-bar: detail {detail.label} dimensions before crop {before}, "
        f"after {after}"
    )
    if lost:
        raise RuntimeError(
            f"detail {detail.label} lost {lost} to its crop; before {before}, "
            f"after {after}"
        )
    return annotations


def _mark_detail_on_front(
    adapter: Any, front: Any, detail: NotchDetail
) -> tuple[float, float]:
    """Circle ``detail``'s region on the 1:4 front view; returns its sheet
    centre. A plain view-sketch circle, drawn direct to the database in the
    outline's black."""
    _activate_view(adapter, front, label="front view")
    center = model_point_in_view(
        adapter,
        front,
        (detail.fence_mm[0] / 1000.0, detail.fence_mm[1] / 1000.0, 0.0),
        label=f"detail {detail.label} mark centre",
    )
    circle = _sketch_circle(
        adapter,
        front,
        center,
        detail.mark_radius,
        label=f"detail {detail.label} mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"detail {detail.label} mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return center


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _note_centring_error(
    box: tuple[float, float, float, float],
    center_x: float,
    top: float | None,
    center_y: float | None,
) -> tuple[float, float]:
    """How far a note's extent sits from its target: its horizontal centre
    against ``center_x``, and its top edge against ``top`` or else its
    vertical centre against ``center_y``."""
    error_x = (box[0] + box[2]) / 2.0 - center_x
    if top is not None:
        return error_x, box[3] - top
    if center_y is None:
        raise ValueError("a centred note needs a top edge or a centre height")
    return error_x, (box[1] + box[3]) / 2.0 - center_y


def _centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    label: str,
) -> tuple[float, float, float, float]:
    """Insert a note owned by ``view``, centred on ``center_x`` by its extent;
    ``top`` pins its top edge, ``center_y`` its middle. A note that does not
    centre, or lands in another view, raises."""
    _activate_view(adapter, view, label=label)
    y = top if top is not None else center_y
    note = add_note(adapter, text, center_x, y)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    box = _note_box(note, label=label)
    for _ in range(NOTE_CENTRING_PASSES):
        error_x, error_y = _note_centring_error(box, center_x, top, center_y)
        if max(abs(error_x), abs(error_y)) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if not annotation.SetPosition2(
            position[0] - error_x, position[1] - error_y, 0.0
        ):
            raise RuntimeError(f"failed to centre the {label} note")
        adapter.currentModel.EditRebuild3()
        box = _note_box(note, label=label)
    error_x, error_y = _note_centring_error(box, center_x, top, center_y)
    _telemetry.info(
        f"amplitude-bar: {label} note {text!r} extent "
        f"({box[0] * 1000:.1f}, {box[1] * 1000:.1f})-({box[2] * 1000:.1f}, "
        f"{box[3] * 1000:.1f}) mm",
        label=label,
    )
    if max(abs(error_x), abs(error_y)) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error_x * 1000:.2f}, "
            f"{error_y * 1000:.2f}) mm"
        )
    first_line = _plain_text(text.split("\n")[0])
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(found.startswith(first_line) for found in texts) != 1:
        raise RuntimeError(
            f"{label} note did not land in its view: its notes are {texts!r}"
        )
    return box


def _label_detail(
    adapter: Any, view: Any, front: Any, detail: NotchDetail, mark: tuple[float, float]
) -> None:
    """Label ``detail`` under its crop circle and letter its mark on the front,
    east of the bar."""
    _centred_view_note(
        adapter,
        view,
        detail.label_text,
        center_x=detail.label_xy[0],
        top=detail.label_xy[1],
        label=f"detail {detail.label} label",
    )
    _centred_view_note(
        adapter,
        front,
        detail.label,
        center_x=mark[0] + detail.mark_radius + PARENT_LETTER_GAP,
        center_y=mark[1],
        label=f"detail {detail.label} letter",
    )


def _notch_floor_edge(view: Any) -> Any:
    """The foot notch floor's near edge in DETAIL A: edge-on it IS the floor's
    line, and its faces include the floor the control names."""
    span = sorted((BOTTOM_NOTCH_OFFSET, BOTTOM_NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH))
    matches = []
    for raw in visible_view_entities(view, 1, label="bottom notch floor"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        points = [
            tuple(float(v) * 1000.0 for v in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in (start, end)
        ]
        if any(abs(p[1] - BOTTOM_NOTCH_HEIGHT) > 0.01 for p in points):
            continue
        if not all(
            math.isclose(a, b, abs_tol=0.01)
            for a, b in zip(sorted(p[0] for p in points), span)
        ):
            continue
        matches.append((points[0][2], edge))
    # The near (z = BarDepth) and far (z = 0) edges project onto one line and
    # both bound the floor; take the near one when both are listed.
    depths = sorted(round(z, 2) for z, _edge in matches)
    if depths not in ([0.0], [round(BAR_DEPTH, 2)], [0.0, round(BAR_DEPTH, 2)]):
        raise RuntimeError(f"unexpected bottom notch floor edges at z={depths} mm")
    return max(matches, key=lambda item: item[0])[1]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open amplitude-bar source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Amplitude Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "amplitude bar; chrome steel; coefficient bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 8))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    # The details are placed and dimensioned FIRST, one at a time, each while
    # it is uncropped, then cropped. The profile owns every printed dimension,
    # so a targeted import of it delivers the whole set; a dimension already on
    # the sheet is never imported again, while a deleted one is. Detail A keeps
    # the foot's three and deletes the rest, detail B takes the top's three
    # back, and the front view's import then brings only the length (r743-6:
    # front first, its deletions and a native detail left detail A nothing).
    annotations: list[Any] = []
    details = {}
    for detail, keep in ((DETAIL_A, DETAIL_A_KEEP), (DETAIL_B, DETAIL_B_KEEP)):
        view = _placed_detail_view(adapter, detail)
        annotations += _dimension_then_crop(adapter, view, detail, keep)
        details[detail.label] = view
    annotations += curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the band each dimension claims) are authored on
    # the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    # The circles and labels go on once every import is done, so nothing of
    # the front view's own sketch is near its import.
    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before labelling the details")
    for detail in (DETAIL_A, DETAIL_B):
        mark = _mark_detail_on_front(adapter, front, detail)
        _label_detail(adapter, details[detail.label], front, detail, mark)

    add_surface_finish(
        adapter,
        details[DETAIL_A.label],
        edge_entity=_notch_floor_edge(details[DETAIL_A.label]),
        symbol_xy=FLOOR_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bottom_notch_floor"),
        label="bottom notch floor finish",
        leader_attach_xy=FLOOR_FINISH_ATTACH,
        char_height=FINISH_CHAR_HEIGHT,
    )

    # The projected end outline is not a selectable topological EDGE after the
    # end notches are overlaid. The manufacturing note owns the explicit 6.35
    # square section; this enlarged end view confirms its shape without a
    # duplicate, topology-fragile dimension.

    add_property_linked_note(adapter, "Manufacturing Notes", 0.150, 0.230)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.070)
    # The end view runs 16x the sheet scale -- label it or "do not scale
    # drawing" leaves its size unreadable.
    # Below the 4:1 end view -- the manufacturing-notes block above descends
    # to ~y=0.175 and owns the old 0.180 spot (layout audit).
    add_property_linked_note(adapter, "End View Note", 0.205, 0.120)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Amplitude Bar Manufacturing Drawing",
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
