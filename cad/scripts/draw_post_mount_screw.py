r"""Create the modified-stock drawing for the MHA-142 cone pivot post mount screw.

MSC 40923898 is bought by SKU and cut to length, so the sheet is a
modified-purchased-part drawing (the boss hook's pattern), not the purchased
reference sheet: a Front view carrying the cut length -- the part's hidden
reference-sketch dimension, imported at its model-owned places -- and an
isometric, both 1:1.  No single length suits every in-band post and plate
(post_mount_screw_spec's U27 check), so the length prints as a REFERENCE,
"(86.0)", with no band and the cut-to-fit acceptance beneath it: cut at
assembly, end flush to the spec band's allowance short of the MHA-091
underside, never proud (post_mount_screw_spec.CUT_TO_FIT_CALLOUT -- no MHA-A03
procedure sheet exists to carry it, Codex P1 on #857).  The cut end's break
is a deburr (Main's MHA-142 eye pass on #857): a 0.1 dimension at 1:1 is
illegible and its printed +0/-0.1 band read as allowing no break at all, so
the Front view carries no break dimension.  A 10:1 detail of the tip carries
it instead as the single limit "0.1 MAX" (the model's CutEndBreak at
swTolMAX, generated from the spec band).  CutEndBreak is a driving
dimension of the deburr cutter's profile, and the detail takes it through
the ENTIRE-MODEL import plus the curate sweep, after a read of the detail's
visible entities (see ``_curate_tip_detail``).  The Front is re-activated
before the notes so they do not land in the detail.  The only
note says to deburr the cut end and that the
undimensioned purchased geometry is reference.  No installation sequence, engagement figure or rule
number is printed: the sequence is an MHA-A03 assembly step and the
engagement a model assert (Main's eye pass of warm-c486, policy rule 6).

Run with SolidWorks open::

    uv run python cad\scripts\draw_post_mount_screw.py post-mount-screw
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
from dataclasses import dataclass, field
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _stock_trim_drawing as trim_drawing
import _telemetry
from _common import _early_bound, check, run_build
import _drawing_common
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    dimension_name,
    read_required_properties,
    model_point_in_view,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _stock_trim_drawing import TrimSheet
from post_mount_screw_spec import (
    CUT_END_BREAK_DIMENSION,
    CUT_END_BREAK_MAX_MM,
    CUT_END_BREAK_TEXT,
    CUT_END_BREAK_TOL_TYPE,
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_TO_FIT_CALLOUT,
    DRAWING_PRECISION_BY_NAME,
    FRONT_VIEW_DIMENSIONS,
    HEAD_H_MM,
    THREAD_DIA_MM,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name

SPEC = DRAWINGS_BY_NAME["post_mount_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
TITLE = "Cone Pivot Post Mount Screw — Modified Stock Drawing"

SHEET_SCALE = (1.0, 1.0)
# The screw stands head up in the Front view: under-head face at model y 0,
# cut end at -CUT_LENGTH_MM, head top ~6 above.
FRONT_CENTER = (0.100, 0.165)
ISO_CENTER = (0.270, 0.185)
# The cut length reads on the left, where its reference line runs along the
# shank's silhouette, midway along the span, far enough out that its
# four-line acceptance callout (22 capitals at its widest) clears the head
# and stays inside the border.
# The cut end's break is not dimensioned in this 1:1 view (see the module
# docstring).  (The view is placed by its outline's centre: the end face is
# half the screw's overall height below it.)
TIP_Y = FRONT_CENTER[1] - (CUT_LENGTH_MM + HEAD_H_MM) / 2000.0
FRONT_KEEP = {
    CUT_LENGTH_DIMENSION: (FRONT_CENTER[0] - 0.047, FRONT_CENTER[1]),
}
DIMENSION_CALLOUTS = {CUT_LENGTH_DIMENSION: CUT_TO_FIT_CALLOUT}

# The 10:1 tip detail: its crop centres on the axis 1 mm above the cut end
# with a 3.6 mm fence, so both ends of the break's radial leg (r 3.075 and
# 3.175 on the end face) sit inside the crop -- a detail drops any dimension
# whose reference lies outside it.  It sits between the Front view and the
# isometric, above the note block and clear of the title block.
DETAIL_SCALE = (10.0, 1.0)
DETAIL_FENCE_MM = 3.6
DETAIL_OFFSET_MM = 1.0
DETAIL_CENTER = (0.190, 0.175)
DETAIL_RADIUS = DETAIL_FENCE_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
TIP_DETAIL = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=DETAIL_CENTER,
    detail_scale=DETAIL_SCALE,
    fence_radius_mm=DETAIL_FENCE_MM,
    cut_end_y_mm=-CUT_LENGTH_MM,
    detail_offset_mm=DETAIL_OFFSET_MM,
    detail_label_xy=(
        DETAIL_CENTER[0] - 0.020,
        DETAIL_CENTER[1] - DETAIL_RADIUS - 0.010,
    ),
    parent_letter_offset=(0.008, 0.006),
)


def _detail_point(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet position of a Front-view model point inside the tip detail."""
    ratio = DETAIL_SCALE[0] / DETAIL_SCALE[1]
    ref_y = -CUT_LENGTH_MM + DETAIL_OFFSET_MM
    return (
        DETAIL_CENTER[0] + ratio * x_mm / 1000.0,
        DETAIL_CENTER[1] + ratio * (y_mm - ref_y) / 1000.0,
    )


# The break's text sits below the end face, under the right-hand rim.
BREAK_RIM_XY = _detail_point(THREAD_DIA_MM / 2.0, -CUT_LENGTH_MM)
DETAIL_KEEP = {
    CUT_END_BREAK_DIMENSION: (BREAK_RIM_XY[0] - 0.006, BREAK_RIM_XY[1] - 0.012)
}
FRONT_PRECISION = {
    CUT_LENGTH_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_LENGTH_DIMENSION]
}
DETAIL_PRECISION = {
    CUT_END_BREAK_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_END_BREAK_DIMENSION]
}
# Below the Front view (its lower end ~0.119), above the stock rows.
NOTES_XY = (0.016, 0.100)
STOCK_ROWS = (
    ("Supplier", 0.016, 0.060),
    ("Supplier SKUs", 0.080, 0.060),
    ("Stock Name", 0.016, 0.049),
)


# swViewEntityType_e: Edge, Vertex
_VIEW_ENTITY_EDGE = 1
_VIEW_ENTITY_VERTEX = 2


def read_detail_visible_entities(adapter: Any, detail: Any) -> dict[str, int]:
    """Read the tip detail's visible edges and vertices BEFORE its import.

    Hypothesis-backed, not a proven cause: this read is the only delta
    between 3 empty imports (pms857-f543, -56f7, -6099) and 1 success
    (pms857-diag-9eca, which ran it just before the import); may be seat
    variance.  Kept as a named step, with its counts on the span, until a
    second leaf repeats the success.
    """
    view = _early_bound(detail, "IView")
    with _telemetry.span("drawing.tip_detail.visible_entities") as sp:
        components = list(view.GetVisibleComponents() or ()) or [None]
        edges = sum(
            len(view.GetVisibleEntities2(component, _VIEW_ENTITY_EDGE) or ())
            for component in components
        )
        vertices = sum(
            len(view.GetVisibleEntities2(component, _VIEW_ENTITY_VERTEX) or ())
            for component in components
        )
        counts = {"components": len(components), "edges": edges, "vertices": vertices}
        for key, value in counts.items():
            sp.set_attribute(key, value)
        return counts


def _curate_tip_detail(adapter: Any, detail: Any) -> list[Any]:
    """Import the break into the tip detail: entire-model import (source 0)
    plus the curate sweep, after the visible-entity read.

    Dead under {hidden ref sketch / source 1, cutter profile / source 1,
    cutter profile / source 0} on this 10:1 HLR detail: pms857-f543
    (f54309af5), pms857-56f7 (56f732997) and pms857-6099 (60996965b) each
    raised "tip detail break view is missing model dimensions:
    ['CutEndBreak']" with nothing imported.  pms857-diag-9eca (9eca9e227)
    imported it by source 0 after reading the detail's visible entities;
    see read_detail_visible_entities.  Source 0 is the boss hook, spring
    hook and cylinder gear detail form.
    """
    read_detail_visible_entities(adapter, detail)
    return _drawing_common.curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="tip detail break"
    )


def activate_front_for_notes(adapter: Any, front: Any) -> None:
    """Make the Front the active view before the property-linked notes.

    A note lands in the ACTIVE view.  The tip detail is active after its
    curate, so the four notes landed inside it and position_detail_label
    found 5 notes instead of its one native label (pms857-diag-9eca).
    """
    name = view_name(adapter, front)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the Front view {name!r} for the notes")


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    return [
        dimension_name(adapter, _early_bound(item, "IAnnotation"))
        for item in (_early_bound(view, "IView").GetAnnotations() or ())
    ]


def break_text(value_mm: float, places: int, tol_type: int, prefix: str, suffix: str) -> str:
    """The break dimension's printed text, composed from its read-back parts.

    The API exposes no rendered string for a toleranced value, so the seat
    check composes it: value at its places, the MAX limit when the type is
    swTolMAX, and whatever prefix and suffix the display carries.
    """
    limit = " MAX" if tol_type == CUT_END_BREAK_TOL_TYPE else ""
    return f"{prefix}{value_mm:.{places}f}{limit}{suffix}"


def _verify_tip_detail(adapter: Any, front: Any, detail: Any) -> None:
    """Seat read-back: the detail exists at its scale, carries the one break
    dimension as a MAX limit reading the spec's text, and the Front does not."""
    view = _early_bound(detail, "IView")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != DETAIL_SCALE:
        raise RuntimeError(f"tip detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    names = _view_dimension_names(adapter, detail)
    if names.count(CUT_END_BREAK_DIMENSION) != 1:
        raise RuntimeError(
            f"tip detail must carry one {CUT_END_BREAK_DIMENSION}: {names}"
        )
    front_names = _view_dimension_names(adapter, front)
    if CUT_END_BREAK_DIMENSION in front_names:
        raise RuntimeError(f"Front view still carries the 1:1 break: {front_names}")
    annotation = next(
        _early_bound(item, "IAnnotation")
        for item in view.GetAnnotations()
        if dimension_name(adapter, _early_bound(item, "IAnnotation"))
        == CUT_END_BREAK_DIMENSION
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value_mm = float(dimension.SystemValue) * 1000.0
    places = int(display.GetPrimaryPrecision2())
    tol_type = int(tolerance.Type)
    parenthesis = bool(display.ShowParenthesis)
    text = break_text(
        value_mm,
        places,
        tol_type,
        str(display.GetText(1) or ""),  # swDimensionTextPrefix
        str(display.GetText(2) or ""),  # swDimensionTextSuffix
    )
    _telemetry.event(
        "drawing.tip_detail_break",
        text=text,
        value_mm=value_mm,
        places=places,
        tol_type=tol_type,
        parenthesis=parenthesis,
        scale=f"{ratio[0]:g}:{ratio[1]:g}",
    )
    if (
        tol_type != CUT_END_BREAK_TOL_TYPE
        or abs(value_mm - CUT_END_BREAK_MAX_MM) > 1e-9
        or parenthesis
        or text != CUT_END_BREAK_TEXT
    ):
        raise RuntimeError(
            f"tip detail break reads {text!r} (type {tol_type}, parenthesis "
            f"{parenthesis}), expected {CUT_END_BREAK_TEXT!r}"
        )
    _telemetry.success(f"tip detail {ratio[0]:g}:{ratio[1]:g} reads {text}")


def _reference_cut_length(adapter: Any, annotations: list[Any]) -> None:
    """Re-read the imported cut length, then mark it reference.

    It must be the model's nominal and carry NO band (swTolNONE): a band
    would promise a fixed length the post and plate bands cannot honour.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != CUT_LENGTH_DIMENSION:
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - CUT_LENGTH_MM / 1000.0) > 1e-9:
            raise RuntimeError(
                f"cut length {float(dimension.SystemValue)!r} m is not the "
                f"modelled {CUT_LENGTH_MM} mm"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE
            raise RuntimeError("cut length carries a band; it must be reference")
        set_reference_dimension(adapter, annotation, label="cut length")
        return
    raise RuntimeError("Front view has no cut length to mark reference")


# =====================================================================
# TEMPORARY DIAGNOSTIC -- branch diag/mha142-bisect, never merged.
#
# Five views of the cut tip, each given a FRESH entire-model import of
# CutEndBreak (the production call, InsertModelAnnotations3(0, ...,
# DuplicateDims=True)).  DuplicateDims=True drops a dimension any other
# view already holds, so every successful probe DELETES its import before
# the next view runs, and every line carries prior_deletes.  The positive
# control (view 1) runs LAST as the canary: if it imports after N deletes,
# deletion is proven not to poison a re-import.  Execution order:
#   5 (replay 9eca, first detail after the Front import, label A, the
#      production position), 3, 4, 2, 1.
# Nothing here raises until the end; the build fails only if view 1 did
# not import (the diag is then invalid).
# =====================================================================

DIAG = "mha142-bisect"
# swDisplayMode_e
_DISPLAY_MODE_NAMES = {
    -1: "UNKNOWN",
    0: "WIREFRAME",
    1: "HLV",
    2: "HLR",
    3: "SHADED",
    4: "FACETED_WIREFRAME",
    5: "FACETED_HLV",
    6: "FACETED_HLR",
    7: "SHADED_EDGES",
    8: "DEFAULT",
}
_CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# Sheet layout of the probes (metres).  The production 10:1 detail keeps its
# centre (DETAIL_CENTER) for the replay; the isometric moves to 1:2 in the
# free corner above the title block.
DIAG_ISO_CENTER = (0.390, 0.105)
DIAG_ISO_SCALE = (1.0, 2.0)
DIAG_BREAK_TEXT_OFFSET = (-0.006, -0.012)


@dataclass(frozen=True)
class Probe:
    number: int
    kind: str  # detail | model-cropped | replay9eca
    scale: tuple[float, float]
    center: tuple[float, float]
    label: str
    display: str  # hlv | hlr


PROBES_IN_ORDER = (
    Probe(5, "replay9eca", DETAIL_SCALE, DETAIL_CENTER, "A", "hlr"),
    Probe(3, "detail", (10.0, 1.0), (0.275, 0.175), "B", "hlv"),
    Probe(4, "model-cropped", (10.0, 1.0), (0.360, 0.175), "", "hlr"),
    Probe(2, "detail", (5.0, 1.0), (0.190, 0.240), "C", "hlv"),
    Probe(1, "detail", (2.0, 1.0), (0.260, 0.240), "D", "hlv"),
)


@dataclass
class ProbeResult:
    probe: Probe
    order: int
    view: Any = None
    imported: bool = False
    available: list[str] = field(default_factory=list)
    error: str = ""


def _probe_sheet(probe: Probe) -> TrimSheet:
    """The production TIP_DETAIL fence and crop, at this probe's centre/scale."""
    return TrimSheet(
        sheet_scale=SHEET_SCALE,
        detail_center=probe.center,
        detail_scale=probe.scale,
        fence_radius_mm=DETAIL_FENCE_MM,
        cut_end_y_mm=-CUT_LENGTH_MM,
        detail_offset_mm=DETAIL_OFFSET_MM,
        detail_label_xy=TIP_DETAIL.detail_label_xy,
        parent_letter_offset=TIP_DETAIL.parent_letter_offset,
    )


def _probe_keep(probe: Probe) -> dict[str, tuple[float, float]]:
    """CutEndBreak's text below the right-hand rim, in this probe's view."""
    ratio = probe.scale[0] / probe.scale[1]
    ref_y = -CUT_LENGTH_MM + DETAIL_OFFSET_MM
    rim = (
        probe.center[0] + ratio * (THREAD_DIA_MM / 2.0) / 1000.0,
        probe.center[1] + ratio * (-CUT_LENGTH_MM - ref_y) / 1000.0,
    )
    return {
        CUT_END_BREAK_DIMENSION: (
            rim[0] + DIAG_BREAK_TEXT_OFFSET[0],
            rim[1] + DIAG_BREAK_TEXT_OFFSET[1],
        )
    }


def _labelled_end_detail(adapter: Any, front: Any, sheet: TrimSheet, label: str) -> Any:
    """``trim_drawing.end_detail`` verbatim, except the detail label (it
    hard-codes "A", which the replay keeps)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("cannot activate cut-end detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000 for value in sheet.detail_reference_mm),
        label="cut end detail center",
    )
    radius = sheet.fence_radius_mm * sheet.sheet_scale[0] / sheet.sheet_scale[1] / 1000
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
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("cannot create native cut-end detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *sheet.detail_center, 0.0, 0, *sheet.detail_scale, label, 1, True, False, False, 5
    )
    if detail is None:
        raise RuntimeError(f"cannot create native cut-end detail {label}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(sheet.detail_scale))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("invalid cut-end detail bounds")
    target = [
        position[i] + sheet.detail_center[i] - (outline[i] + outline[i + 2]) / 2
        for i in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("cannot position cut-end detail")
    draw.EditRebuild3()
    if tuple(float(value) for value in detail.ScaleRatio) != sheet.detail_scale:
        raise RuntimeError("cut-end detail scale did not persist")
    return detail


def _cropped_model_view(adapter: Any, probe: Probe) -> Any:
    """View 4: a standalone *Front model view at the probe scale (NOT a
    detail), moved so the tip reference point lands on the probe centre, then
    cropped by a closed sketch circle of the detail fence's size.

    Crop recipe: IDrawingDoc.ActivateView, ISketchManager.CreateCircle (the
    new circle stays selected), IView.Crop2(False, False, 5) -- the
    documented "Crop Drawing View" example shape.  Untested on seat.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *probe.center, scale=probe.scale),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    reference = tuple(value / 1000 for value in TIP_DETAIL.detail_reference_mm)
    tip = model_point_in_view(adapter, view, reference, label="model view tip")
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + probe.center[i] - tip[i] for i in range(2)]
    moved = bool(view.SetViewPosition(double_array(target), False))
    draw.EditRebuild3()
    tip_after = model_point_in_view(adapter, view, reference, label="model view tip")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"cannot activate model view {name!r} for its crop")
    draw.ClearSelection2(True)
    radius = DETAIL_FENCE_MM * probe.scale[0] / probe.scale[1] / 1000.0
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (tip_after, (tip_after[0] + radius, tip_after[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("cannot create the model view's crop circle")
    status = int(view.Crop2(False, False, 5))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"{DIAG} view={probe.number} crop: name={name!r} scale_read={ratio} "
        f"moved={moved} tip_sheet_before={[round(v, 5) for v in tip]} "
        f"tip_sheet_after={[round(v, 5) for v in tip_after]} "
        f"crop2_status={status} is_cropped={cropped} "
        f"outline={[round(float(v), 5) for v in view.GetOutline()]}"
    )
    if status != _CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"model view crop failed: Crop2 status {status}, IsCropped {cropped}"
        )
    return view


# --- 9eca replay: its diagnostic helpers, copied verbatim from 9eca9e227 ---
# (draw_post_mount_screw.py, "TEMPORARY DIAGNOSTIC" block), minus the
# post-import failure capture (capture_com_failure + sheet PNG), which ran
# only after a failed import and so cannot have changed it.


def _diag(label: str, fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - diagnostics must never mask
        return {"error": f"{type(exc).__name__}: {exc}"}


def _view_to_model(adapter: Any, view: Any, xy: tuple[float, float]) -> list[float]:
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    inverse = _early_bound(transform.Inverse(), "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        utility.CreatePoint(double_array([xy[0], xy[1], 0.0])), "IMathPoint"
    )
    moved = _early_bound(point.MultiplyTransform(inverse), "IMathPoint")
    return [round(float(v) * 1000.0, 4) for v in moved.ArrayData]


def _crop_in_model(adapter: Any, front: Any) -> dict[str, Any]:
    info = [float(v) for v in (_early_bound(front, "IView").GetDetailCircleInfo2() or ())]
    if not info:
        return {"detail_circles": 0}
    center, start = (info[2], info[3]), (info[5], info[6])
    center_model = _view_to_model(adapter, front, center)
    start_model = _view_to_model(adapter, front, start)
    return {
        "detail_circles": int(info[0]),
        "center_sheet_m": [round(v, 6) for v in center],
        "start_sheet_m": [round(v, 6) for v in start],
        "center_model_mm": center_model,
        "start_model_mm": start_model,
        "radius_model_mm": round(
            math.dist(center_model[:2], start_model[:2]), 4
        ),
    }


def _visible_entities(view: Any) -> dict[str, Any]:
    view = _early_bound(view, "IView")
    components = list(view.GetVisibleComponents() or ()) or [None]
    edges: list[dict[str, Any]] = []
    vertices: list[list[float]] = []
    for component in components:
        for raw in view.GetVisibleEntities2(component, 1) or ():  # Edge
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                c = [float(v) for v in curve.CircleParams]
                edges.append(
                    {
                        "circle_r_mm": round(c[6] * 1000.0, 4),
                        "center_y_mm": round(c[1] * 1000.0, 4),
                    }
                )
            else:
                edges.append({"type": int(curve.Identity())})
        for raw in view.GetVisibleEntities2(component, 2) or ():  # Vertex
            point = _early_bound(raw, "IVertex").GetPoint()
            vertices.append([round(float(v) * 1000.0, 4) for v in point])
    chamfer = {
        "inner_rim_r3.075_y-86": any(
            abs(e.get("circle_r_mm", 0) - 3.075) < 1e-3
            and abs(e.get("center_y_mm", 0) + 86.0) < 1e-3
            for e in edges
        ),
        "outer_rim_r3.175_y-85.9": any(
            abs(e.get("circle_r_mm", 0) - 3.175) < 1e-3
            and abs(e.get("center_y_mm", 0) + 85.9) < 1e-3
            for e in edges
        ),
    }
    return {
        "components": len(components),
        "edge_count": len(edges),
        "vertex_count": len(vertices),
        "circles": [e for e in edges if "circle_r_mm" in e][:40],
        "vertices_mm": vertices[:40],
        "chamfer_edges_visible": chamfer,
    }


def _detail_facts(adapter: Any, front: Any, detail: Any) -> dict[str, Any]:
    view = _early_bound(detail, "IView")
    base = view.GetBaseView()
    return {
        "detail_name": _diag("name", lambda: view_name(adapter, detail)),
        "detail_type": _diag("type", lambda: int(view.Type)),
        "detail_scale": _diag("scale", lambda: list(view.ScaleRatio)),
        "detail_outline_m": _diag("outline", lambda: list(view.GetOutline())),
        "detail_position_m": _diag("position", lambda: list(view.Position)),
        "parent_name": _diag("parent", lambda: view_name(adapter, base)),
        "parent_scale": _diag(
            "pscale", lambda: list(_early_bound(base, "IView").ScaleRatio)
        ),
        "crop": _diag("crop", lambda: _crop_in_model(adapter, front)),
        "visible": _diag("visible", lambda: _visible_entities(detail)),
    }


def _dimension_count(view: Any) -> Any:
    return _diag(
        "dims", lambda: int(_early_bound(view, "IView").GetDisplayDimensionCount())
    )


# --- per-probe reads ------------------------------------------------------


def _display_state(view: Any) -> dict[str, Any]:
    """IView.GetDisplayMode2 (swDisplayMode_e), GetUseParentDisplayMode,
    GetDisplayTangentEdges2 (swDisplayTangentEdges_e), GetFacettedHlrDisplay."""
    bound = _early_bound(view, "IView")
    mode = _diag("mode", lambda: int(bound.GetDisplayMode2()))
    return {
        "display": (
            f"{_DISPLAY_MODE_NAMES.get(mode, '?')}({mode})"
            if isinstance(mode, int)
            else repr(mode)
        ),
        "use_parent": _diag("parent", lambda: bool(bound.GetUseParentDisplayMode())),
        "tangent": _diag("tangent", lambda: int(bound.GetDisplayTangentEdges2())),
        "faceted": _diag("faceted", lambda: bool(bound.GetFacettedHlrDisplay())),
    }


def _break_annotations(adapter: Any, view: Any) -> list[Any]:
    return [
        annotation
        for annotation in (
            _early_bound(item, "IAnnotation")
            for item in (_early_bound(view, "IView").GetAnnotations() or ())
        )
        if dimension_name(adapter, annotation) == CUT_END_BREAK_DIMENSION
    ]


def _text_height_mm(adapter: Any, view: Any) -> str:
    """IAnnotation.GetTextFormat(0) -> ITextFormat.CharHeight (m), plus
    IAnnotation.GetUseDocTextFormat(0).  Untested on seat."""
    found = _break_annotations(adapter, view)
    if not found:
        return "na"
    annotation = found[0]
    height = _diag(
        "text_h",
        lambda: round(
            float(_early_bound(annotation.GetTextFormat(0), "ITextFormat").CharHeight)
            * 1000.0,
            3,
        ),
    )
    doc_format = _diag("doc_fmt", lambda: bool(annotation.GetUseDocTextFormat(0)))
    return f"{height}(doc_default={doc_format})"


def _delete_break(adapter: Any, view: Any) -> tuple[bool, list[str]]:
    """Select2 + EditDelete every CutEndBreak in ``view``, as
    delete_unnamed_imports does, then re-read the view's dimension names."""
    draw = adapter.currentModel
    for annotation in _break_annotations(adapter, view):
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select the probe's CutEndBreak")
        draw.EditDelete()
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="mha142_bisect_delete")
    remaining = _view_dimension_names(adapter, view)
    return CUT_END_BREAK_DIMENSION not in remaining, remaining


def _create_probe_view(adapter: Any, front: Any, probe: Probe) -> Any:
    """Create and display-set the probe's view; the replay also logs its
    initial (pre-HLR) display mode, i.e. what the production detail gets."""
    if probe.kind == "model-cropped":
        view = _cropped_model_view(adapter, probe)
    elif probe.kind == "replay9eca":
        view = trim_drawing.end_detail(adapter, front, TIP_DETAIL)
    else:
        view = _labelled_end_detail(adapter, front, _probe_sheet(probe), probe.label)
    _telemetry.info(
        f"{DIAG} view={probe.number} created name={view_name(adapter, view)!r} "
        f"initial={_display_state(view)}"
    )
    if probe.display == "hlv":
        set_hidden_lines_visible(adapter, view)
    else:
        set_hidden_lines_removed(adapter, view)
    _early_bound(view, "IView").UpdateViewDisplayGeometry()
    return view


def _import_into(adapter: Any, front: Any, probe: Probe, view: Any) -> None:
    """The import: production's entire-model curate (source 0).  The replay
    wraps it exactly as 9eca's _diagnosed_tip_detail did (facts, then the
    detail and Front dimension counts, then the curate, then counts)."""
    keep = _probe_keep(probe)
    if probe.kind != "replay9eca":
        _drawing_common.curate_view_dimensions(
            adapter, view, keep=keep, view_label=f"{DIAG} view {probe.number}"
        )
        return
    with _telemetry.span("diag.tip_detail") as sp:
        facts = _detail_facts(adapter, front, view)
        facts["detail_dims_before"] = _dimension_count(view)
        facts["front_dims_before"] = _dimension_count(front)
        try:
            _drawing_common.curate_view_dimensions(
                adapter, view, keep=keep, view_label="tip detail break"
            )
        finally:
            facts["detail_dims_after"] = _dimension_count(view)
            facts["front_dims_after"] = _dimension_count(front)
            _telemetry.info(f"DIAG tip detail: {json.dumps(facts, default=str)}")
            sp.set_attribute("diag", json.dumps(facts, default=str)[:8000])


def _run_probe(
    adapter: Any, front: Any, probe: Probe, order: int, prior_deletes: int
) -> ProbeResult:
    result = ProbeResult(probe=probe, order=order)
    ratio = probe.scale[0] / probe.scale[1]
    try:
        result.view = _create_probe_view(adapter, front, probe)
    except Exception as exc:  # noqa: BLE001 - every probe must run
        result.error = repr(exc)
        _telemetry.warn(f"{DIAG} view={probe.number} error={exc!r} (creation)")
        return result
    try:
        _import_into(adapter, front, probe, result.view)
    except Exception as exc:  # noqa: BLE001 - every probe must run
        result.error = repr(exc)
        _telemetry.warn(f"{DIAG} view={probe.number} error={exc!r}")
    names = _diag("names", lambda: _view_dimension_names(adapter, result.view))
    result.available = [n for n in names if n] if isinstance(names, list) else [repr(names)]
    result.imported = CUT_END_BREAK_DIMENSION in result.available
    state = _display_state(result.view)
    _telemetry.info(
        f"{DIAG} view={probe.number} order={order} kind={probe.kind} "
        f"scale={probe.scale[0]:g}:{probe.scale[1]:g} display={state['display']} "
        f"use_parent={state['use_parent']} tangent={state['tangent']} "
        f"faceted={state['faceted']} "
        "source=0/InsertModelAnnotations3(0,marked|hw_loc,False,True,True,False)"
        f"{'+9eca_prereads' if probe.kind == 'replay9eca' else ''} "
        f"available={result.available} imported={result.imported} "
        f"prior_deletes={prior_deletes} "
        f"sheet_text_h_mm={_diag('text', lambda: _text_height_mm(adapter, result.view))} "
        f"feature_on_sheet_mm={0.1 * ratio:g}"
    )
    if result.imported:
        deleted = _diag("delete", lambda: _delete_break(adapter, result.view))
        _telemetry.info(f"{DIAG} view={probe.number} deleted={deleted}")
    return result


def run_bisect(adapter: Any, front: Any) -> dict[int, ProbeResult]:
    """Run every probe in PROBES_IN_ORDER; never raises."""
    results: dict[int, ProbeResult] = {}
    prior_deletes = 0
    with _telemetry.span("diag.mha142_bisect"):
        for order, probe in enumerate(PROBES_IN_ORDER, start=1):
            with _telemetry.span(f"diag.mha142_bisect.view{probe.number}"):
                result = _run_probe(adapter, front, probe, order, prior_deletes)
            results[probe.number] = result
            prior_deletes += int(result.imported)
    return results


def reimport_survivor(adapter: Any, results: dict[int, ProbeResult]) -> str:
    """Put CutEndBreak back into the first surviving 10:1 view (3, 4, then 5)
    so the published PDF shows it for the legibility eye pass.  Never fatal."""
    for number in (3, 4, 5):
        result = results.get(number)
        if result is None or not result.imported or result.view is None:
            continue
        try:
            _drawing_common.curate_view_dimensions(
                adapter,
                result.view,
                keep=_probe_keep(result.probe),
                view_label=f"{DIAG} final view {number}",
            )
        except Exception as exc:  # noqa: BLE001 - diagnostics must not mask
            _telemetry.warn(f"{DIAG} final view={number} error={exc!r}")
        names = _diag("names", lambda: _view_dimension_names(adapter, result.view))
        imported = isinstance(names, list) and CUT_END_BREAK_DIMENSION in names
        _telemetry.info(
            f"{DIAG} final view={number} imported={imported} available={names} "
            f"sheet_text_h_mm={_diag('text', lambda: _text_height_mm(adapter, result.view))}"
        )
        return str(number)
    _telemetry.info(f"{DIAG} final view=none (no 10:1 view imported)")
    return "none"


def bisect_summary(results: dict[int, ProbeResult], final: str) -> str:
    outcomes = " ".join(
        f"v{number}={'Y' if results[number].imported else 'N'}"
        + ("(err)" if results[number].error else "")
        for number in sorted(results)
    )
    order = ",".join(str(probe.number) for probe in PROBES_IN_ORDER)
    return (
        f"{DIAG} summary host={socket.gethostname()} order={order} {outcomes} "
        f"final={final}"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open cut post mount screw", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: TITLE,
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-142; MSC Industrial Supply 40923898",
            4: "Native dimension-driven cut length",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    # DIAG: the isometric moves to 1:2 in the free corner (was ISO_CENTER, 1:1)
    # so the five probe views fit on the one sheet.
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *DIAG_ISO_CENTER, scale=DIAG_ISO_SCALE
    )
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    # The cut length lives on a part-hidden reference sketch, so the Front
    # view takes the opt-in curation that shows it in this view only.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="cut length",
        dimensions_by_feature=FRONT_VIEW_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_PRECISION)
    _reference_cut_length(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    # DIAG (diag/mha142-bisect): the production tip detail is replaced by the
    # five probes (see run_bisect); view 5 is its exact 9eca replay.  The
    # production detail checks are bypassed on this branch only:
    # assert_imported_precision + _verify_tip_detail (one CutEndBreak in THE
    # detail), position_detail_label (exactly one note per detail) and
    # position_parent_detail_letter (exactly one detail circle on the Front).
    results = run_bisect(adapter, front)
    final = _diag("final", lambda: reimport_survivor(adapter, results))
    summary = bisect_summary(results, str(final))
    _telemetry.info(summary)
    if not results[1].imported:
        raise RuntimeError(
            f"{DIAG}: positive control (view 1, 2:1 HLV detail) did not import "
            f"CutEndBreak; the diag is invalid "
            f"({'after deletes by earlier views' if any(r.imported for r in results.values()) else 'nothing imported into any view on this seat'}): "
            f"{summary}"
        )

    activate_front_for_notes(adapter, front)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )
    for name, x, y in STOCK_ROWS:
        add_property_linked_note(adapter, name, x, y, char_height=0.003)

    set_hidden_lines_removed(adapter, front)
    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=TITLE,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )
    _telemetry.info(summary)
    return artefacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
