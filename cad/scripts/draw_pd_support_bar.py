r"""Create the curated machinist drawing for the platen support bar (MHA-PD-007).

A 452 x 28 x 9 steel bar clamped across the frame columns. Its BACK face
carries the transgear pivot's flat-bottomed #8-32 tap and the latch hook's two
#4-40 through taps on one row; its FRONT face, which the platen slides on,
carries the four clamp screws: two counterbored holes on the east column and
two counterbored slots on the west one (owner ruling 2026-10-15, option A).

* The upper view looks on the back face (model +Z, ``*Front``): the length,
  the hanger row's banded stations from the left end, each naming its mate,
  and its height from the top face (the part-hidden HangerRowReference
  sketch), the pivot drill's Ø with its tap, both countersinks' MAX Ø
  (CountersinkReference), the latch-hook taps' native callout (its thread
  class left to the title block) and the top face's slide roughness.
* The lower view looks on the front face (``*Back``, so the left end is on
  the sheet's right): the banded height, the clamp row's banded stations
  from the same end and its banded height (ClampRowReference), the round
  counterbores' native callout (depth at .XX) naming the back-arc taps the
  row locates to, and the front face's slide roughness. Each
  roughness symbol has its reason beside it; the sheet has no general note.
* Detail C looks face-on at the outer slot: the slot's and its
  counterbore's widths and travels, the slot's width naming why it is one.
  Section B-B cuts the inner slot across the bar for the counterbore's depth.
* Each face view carries its caption; section A-A cuts the pivot tap across
  the bar: the banded thickness, the drill's depth limits and the full
  thread's MIN (PivotThreadReference, in the cutting plane).

Every value and band is a native model dimension authored by
``build_pd_support_bar``; the sheet only places and curates them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_support_bar.py pd-support-bar
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view, view_name

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
from _drawing_annotation_extent import move_annotation
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_resolve import resolve_faces
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _surface_finish import surface_finish_by_key
from build_pd_support_bar import (
    BAR_LENGTH,
    CLAMP_CBORE_DEPTH,
    CLAMP_CBORE_DIA,
    CLAMP_ROUND_X,
    CLAMP_SLOT_X,
)
from pd_support_bar_spec import (
    BACK_FACE_Z,
    BAR_DEPTH,
    BAR_HEIGHT,
    BRACKET_TAP_CSK_DIA,
    BRACKET_TAP_SPEC,
    BRACKET_TAP_X,
    HANGER_TAP_Y,
    PIVOT_TAP_X,
)
from pd_support_bar_drawing_spec import (
    BACK_VIEW_CAPTION,
    CLAMP_CBORE_CALLOUT,
    CLAMP_CBORE_DEPTH_PLACES,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_VIEW_CAPTION,
    FRONT_FINISH_REASON,
    STATION_END_LABEL,
    SURFACE_FINISHES,
    TOP_FINISH_REASON,
)


SPEC = DRAWINGS_BY_NAME["pd_support_bar"]
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

SHEET_SCALE = (1, 2)
FACE_SCALE = (1, 2)
SECTION_SCALE = (2, 1)
# 1:4 so the holes read in the pictorial (r5 review: a sliver at 1:6).
ISO_SCALE = (1, 4)
_S = FACE_SCALE[0] / FACE_SCALE[1] / 1000.0  # sheet metres per model mm

# The back face above, the front face below, both at 1:2 with their ends
# aligned; section A-A right of the back face's end, the isometric under it
# (its 1:4 diagonal runs down-right, under the section's caption and clear
# of the title block), its scale note under its left half, right of the
# front view's end extension lines.
FACE_CENTER = (0.170, 0.222)
BACK_CENTER = (0.170, 0.122)
SECTION_CENTER = (0.385, 0.200)
ISO_CENTER = (0.368, 0.097)
ISO_NOTE_XY = (0.300, 0.076)

LEFT_END = FACE_CENTER[0] - BAR_LENGTH * _S / 2.0
RIGHT_END = FACE_CENTER[0] + BAR_LENGTH * _S / 2.0
FACE_TOP = FACE_CENTER[1] + BAR_HEIGHT * _S / 2.0
FACE_BOTTOM = FACE_CENTER[1] - BAR_HEIGHT * _S / 2.0
BACK_TOP = BACK_CENTER[1] + BAR_HEIGHT * _S / 2.0
BACK_BOTTOM = BACK_CENTER[1] - BAR_HEIGHT * _S / 2.0
# The -X end every station runs from, named beside it in both views: left of
# the back face's left end, right of the front face's right end (inside the
# bar height's extension lines, midway between the clamp stations' end
# extension lines and its dimension line).
FACE_END_LABEL_TOP = (LEFT_END - 0.012, FACE_CENTER[1] + 0.002)
BACK_END_LABEL_TOP = (RIGHT_END + 0.011, BACK_CENTER[1] + 0.002)


def _face_x(model_x: float) -> float:
    """Sheet x of a model x in the back-face view (model +X to the right)."""
    return FACE_CENTER[0] + model_x * _S


def _back_x(model_x: float) -> float:
    """Sheet x of a model x in the front-face view (model +X to the left)."""
    return BACK_CENTER[0] - model_x * _S


# The hanger stations are baselines from the left end, stacked under the bar
# shortest first (13 mm rows: each value carries its mate's line), the length
# outermost; their texts step right so none crosses a longer row's extension
# line, and stand clear of the pivot station's. The row's height (from the
# top face, its rise on the right end) stands off the right end. The section
# line runs up through the pivot, its arrows and letters left of it, so the
# pivot's Ø and countersink stand right of it, the Ø higher and further left
# (its leader passes left of the countersink's text, slanting off the line);
# the latch-hook taps' callout (high) and countersink (low) stand right of the
# pivot's, their leaders between the two pairs.
ROW_STEP = 0.013
FRONT_KEEP = {
    "PivotTapStation": (LEFT_END + 0.042, FACE_BOTTOM - ROW_STEP),
    "BracketTapStation1": (LEFT_END + 0.115, FACE_BOTTOM - 2.0 * ROW_STEP),
    "BracketTapStation2": (LEFT_END + 0.118, FACE_BOTTOM - 3.0 * ROW_STEP),
    "Length": (FACE_CENTER[0], FACE_BOTTOM - 4.0 * ROW_STEP),
    "HangerRowHeight": (RIGHT_END + 0.022, FACE_BOTTOM - 0.010),
    "PivotTapDrillDia": (_face_x(PIVOT_TAP_X) + 0.032, FACE_TOP + 0.030),
    "PivotCskDia": (_face_x(PIVOT_TAP_X) + 0.043, FACE_TOP + 0.014),
    "BracketCskDia": (_face_x(BRACKET_TAP_X[0]) + 0.059, FACE_TOP + 0.014),
}
BRACKET_CALLOUT_XY = (_face_x(BRACKET_TAP_X[1]) + 0.056, FACE_TOP + 0.031)
# The top face's slide roughness on its edge, left of the section line.
TOP_FINISH_MODEL_X = -178.0
TOP_FINISH_SYMBOL_XY = (LEFT_END + 0.030, FACE_TOP + 0.014)
TOP_REASON_TOP = (TOP_FINISH_SYMBOL_XY[0] + 0.003, FACE_TOP + 0.032)
# Under the length line, left of the round counterbores' callout.
FACE_CAPTION_TOP = (0.150, FACE_BOTTOM - 4.0 * ROW_STEP - 0.008)

# The clamp stations from the same left (x = -226) end, on the sheet's right
# here, shortest nearest the bar. The first two spans (5.75 and 23.25 mm on
# the sheet) are too short for their banded texts, which stand right of the
# end's extension line, under END A and left of the isometric view; the long
# rows' texts stand between their holes and the end. The bar height reads off
# that end too (the BarProfile dimension's model edge), the clamp row's height
# off the other end, where its rise is: its text stands left of its dimension
# line, so the line hugs the bar to keep the text inside the border (r5
# audit: outside-border).
BACK_KEEP = {
    "ClampStation1": (RIGHT_END + 0.019, BACK_BOTTOM - 0.010),
    "ClampStation2": (RIGHT_END + 0.019, BACK_BOTTOM - 0.018),
    "ClampStation3": (RIGHT_END - 0.150, BACK_BOTTOM - 0.026),
    "ClampStation4": (RIGHT_END - 0.170, BACK_BOTTOM - 0.034),
    "Height": (RIGHT_END + 0.022, BACK_TOP + 0.016),
    "ClampRowHeight": (LEFT_END - 0.010, BACK_BOTTOM - 0.008),
}
# The round counterbores' callout stands over the east pair, its leader
# dropping to the inner one, between the face view's caption and the bar
# height's text. Its text block centres 2.8 mm under this point, so its four
# lines (the mate's under the size) run from ~156 down to ~136 mm: under the
# face view's length line (160.2 mm, r7 audit text-on-line at +0.0216) and
# over the bar.
CLAMP_CALLOUT_XY = (_back_x(max(CLAMP_ROUND_X)) - 0.005, BACK_TOP + 0.017)
# The front face's slide roughness, seen face-on: a leader to a point clear
# of the holes, the symbol above the view, left of the counterbores' callout.
FRONT_FINISH_MODEL_XY = (-40.0, 6.0)
FRONT_FINISH_SYMBOL_XY = (0.192, BACK_TOP + 0.014)
# Its reason stands left of it, under the face view's caption.
FRONT_REASON_TOP = (0.1575, BACK_TOP + 0.013)
BACK_CAPTION_TOP = (BACK_CENTER[0], BACK_BOTTOM - 0.042)
FINISH_CHAR_HEIGHT = 0.0025
CAPTION_SETTLE_M = 0.0006

# The west slots in the clear field under the front-face view. Detail C looks
# face-on at the outer slot at 2:1, left of the view's caption and the title
# block: the counterbore's width left of it, the slot's right (its callout
# saying why it is a slot), the slot's travel below and the counterbore's
# above; its label right of the slot's width, its letter over the bar.
DETAIL_SLOT_X = max(CLAMP_SLOT_X)
DETAIL_CENTER = (0.120, 0.040)
DETAIL_SCALE = (2, 1)
DETAIL_RADIUS_MM = 7.5
DETAIL_LABEL_XY = (0.190, 0.034)  # top centre
DETAIL_LETTER_RISE = 0.010
DETAIL_KEEP = {
    "ClampSlotCboreWidth": (DETAIL_CENTER[0] - 0.030, DETAIL_CENTER[1]),
    "ClampSlotWidth": (DETAIL_CENTER[0] + 0.035, DETAIL_CENTER[1]),
    "ClampSlotTravel": (DETAIL_CENTER[0] + 0.015, DETAIL_CENTER[1] - 0.020),
    "ClampSlotCboreTravel": (DETAIL_CENTER[0] + 0.015, DETAIL_CENTER[1] + 0.021),
}
# Section B-B cuts the inner slot across the bar, at 1:1 in the sheet's
# lower-left corner: the counterbore's depth over it, its text outside the
# front face and its callout above it (below would cross the cut bar), the
# caption under it.
SLOT_SECTION_X = min(CLAMP_SLOT_X)
SLOT_SECTION_CENTER = (0.040, 0.045)
SLOT_SECTION_SCALE = (1, 1)
SLOT_SECTION_CAPTION_XY = (SLOT_SECTION_CENTER[0], 0.028)  # top centre
SLOT_SECTION_KEEP_NAMES = ("ClampSlotCboreDepth",)
SLOT_DEPTH_RISE = 0.005
SLOT_DEPTH_TEXT_SIDE = 0.006
CALLOUTS_ABOVE = ("ClampSlotCboreDepth",)

# Section A-A: the thickness up-left of the cut bar, the full thread and the
# drill depth below it (shorter nearer). Each text stands outside its
# extension lines, beyond the tap's mouth, since the 2:1 spans are narrower
# than the texts. The caption drops under them.
SECTION_KEEP_NAMES = ("Depth", "ThreadMin", "DrillDepth")
SECTION_DEPTH_RISE = 0.010
SECTION_DEPTH_SIDE = 0.028
SECTION_DEPTH_TEXT_SIDE = 0.016
# The full thread's text states its 1.5D shortfall, so it stands further out.
SECTION_THREAD_TEXT_SIDE = 0.026
SECTION_THREAD_DROP = 0.010
SECTION_DRILL_DROP = 0.027
CAPTION_DROP = 0.035
SECTION_OVERRUN = 3.0  # mm the cutting line runs past each long edge

DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _sheet(
    adapter: Any, view: Any, xyz_mm: tuple[float, float, float], label: str
) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in xyz_mm), label=label
    )


def _direction(
    adapter: Any, view: Any, axis: tuple[float, float, float], label: str
) -> tuple[float, float]:
    origin = _sheet(adapter, view, (0.0, 0.0, 0.0), f"{label} origin")
    tip = _sheet(adapter, view, axis, f"{label} axis")
    return tip[0] - origin[0], tip[1] - origin[1]


def _turn_y_up(adapter: Any, view: Any, *, label: str) -> None:
    """Turn ``view`` about its centre until model +Y points sheet-up
    (draw_dt_cone_pivot_post_tl_bond_cradle._turn)."""
    native = _early_bound(view, "IView")
    dx, dy = _direction(adapter, native, (0.0, 1.0, 0.0), label)
    native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
    rebuild_drawing(adapter, label=f"turn {label}")
    dx, dy = _direction(adapter, native, (0.0, 1.0, 0.0), label)
    if dy <= 0.0 or abs(dx) > 1e-9:
        raise RuntimeError(f"{label}: model +Y is not sheet-up ({dx:g}, {dy:g})")


def _section_keep(adapter: Any, section: Any) -> dict[str, tuple[float, float]]:
    """Section A-A's text positions from its own projection, whichever way the
    cut looks: the thickness left of the bar's left face, the depths beyond
    the tap's mouth."""

    def point(z: float, y: float = HANGER_TAP_Y) -> tuple[float, float]:
        return _sheet(adapter, section, (PIVOT_TAP_X, y, z), "section A-A")

    top = point(0.0, BAR_HEIGHT / 2.0)[1]
    bottom = point(0.0, -BAR_HEIGHT / 2.0)[1]
    mouth = point(BACK_FACE_Z)[0]
    front = point(-BACK_FACE_Z)[0]
    away = math.copysign(1.0, mouth - front)
    outside = mouth + away * SECTION_DEPTH_TEXT_SIDE
    return {
        "Depth": (min(mouth, front) - SECTION_DEPTH_SIDE, top + SECTION_DEPTH_RISE),
        "ThreadMin": (
            mouth + away * SECTION_THREAD_TEXT_SIDE,
            bottom - SECTION_THREAD_DROP,
        ),
        "DrillDepth": (outside, bottom - SECTION_DRILL_DROP),
    }


def _move_caption(
    adapter: Any, view: Any, place: Callable[[float, float], tuple[float, float]]
) -> None:
    """Move a section's native caption from where it stands, ``(x, y)``, to
    ``place(x, y)``, keeping its linked fields
    (draw_dt_cone_pivot_post_tl_bond_cradle._lower_caption)."""
    view = _early_bound(view, "IView")
    captions = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(
            token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")
        ):
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(
            f"expected one native linked view caption, found {len(captions)}"
        )
    note, linked_text = captions[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    x, y = (float(value) for value in tuple(annotation.GetPosition())[:2])
    target = place(x, y)
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    rebuild_drawing(adapter, label="move section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


def _hole_rims(face: Any, back: Any) -> tuple[Any, Any]:
    """The first latch-hook tap's drill edge under its back-face countersink
    (a Hole Wizard tap edge, so its callout is native) and the inner east
    clamp counterbore's rim on the front face (the round pair's Hole Wizard
    feature; the west pair are slots)."""
    tap_dia = blind_cut_dia_mm(BRACKET_TAP_SPEC)
    tap_csk_depth = (BRACKET_TAP_CSK_DIA - tap_dia) / 2.0
    tap = (
        scan_view_edges(face, label="support-bar back face")
        .circle_at(
            (BRACKET_TAP_X[0], HANGER_TAP_Y, BACK_FACE_Z - tap_csk_depth),
            tap_dia / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="latch-hook tap edge",
            radius_tol_mm=0.025,
        )
        .edge
    )
    cbore = (
        scan_view_edges(back, label="support-bar front face")
        .circle_at(
            (max(CLAMP_ROUND_X), 0.0, -BAR_DEPTH / 2.0),
            CLAMP_CBORE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="clamp counterbore rim",
            radius_tol_mm=0.025,
        )
        .edge
    )
    return tap, cbore


def _slot_detail(adapter: Any, back: Any) -> Any:
    """Native detail C: a fence round the outer west slot in the front-face
    view, the 2:1 detail centred on DETAIL_CENTER, its label at
    DETAIL_LABEL_XY and its parent letter over the bar
    (draw_dt_pinion_lift_rod._front_end_detail, draw_ms_stick's letter)."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(back, "IView")
    if not drawing.ActivateView(view_name(adapter, back)):
        raise RuntimeError("failed to activate the slot detail's parent")
    draw.ClearSelection2(True)
    center = _sheet(
        adapter, back, (DETAIL_SLOT_X, 0.0, -BAR_DEPTH / 2.0), "slot detail centre"
    )
    radius = DETAIL_RADIUS_MM * _S
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
        raise RuntimeError("failed to create the slot detail's fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "C",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create the slot detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("the slot detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position the slot detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the slot detail's label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"the slot detail's label did not persist: {actual}")
    circles = [
        _early_bound(circle, "IDetailCircle")
        for circle in parent.GetDetailCircles() or ()
    ]
    matching = [circle for circle in circles if circle.GetLabel() == "C"]
    if len(matching) != 1:
        raise RuntimeError("the slot detail: expected one parent circle C")
    letter_xy = (center[0], center[1] + DETAIL_LETTER_RISE)
    matching[0].SetLabelPosition(*letter_xy)
    rebuild_drawing(adapter, label="place the slot detail's parent letter")
    actual = tuple(float(value) for value in matching[0].GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, letter_xy) > 1e-8:
        raise RuntimeError(f"the slot detail's letter placement rejected: {actual}")
    return detail


def _slot_section_keep(adapter: Any, section: Any) -> dict[str, tuple[float, float]]:
    """Section B-B's depth text from its own projection, whichever way the cut
    looks: over the bar, outside the front face the counterbore enters."""

    def point(z: float, y: float = 0.0) -> tuple[float, float]:
        return _sheet(adapter, section, (SLOT_SECTION_X, y, z), "section B-B")

    top = point(0.0, BAR_HEIGHT / 2.0)[1]
    front = point(-BAR_DEPTH / 2.0)[0]
    floor = point(-BAR_DEPTH / 2.0 + CLAMP_CBORE_DEPTH)[0]
    away = math.copysign(1.0, front - floor)
    return {
        "ClampSlotCboreDepth": (
            front + away * SLOT_DEPTH_TEXT_SIDE,
            top + SLOT_DEPTH_RISE,
        )
    }


_THREAD_CLASS_TOKEN = " <hw-threadclass>"


def _drop_thread_class(adapter: Any, display: Any) -> None:
    """Drop the Hole Wizard's thread-class token from the native TAP
    callout's definition (rule 2: the title block's THREADS row carries the
    class); the other tokens stay live (draw_sm_knife_mount precedent)."""
    display = _early_bound(display, "IDisplayDimension")
    before = str(display.GetText(5) or "")  # swDimensionTextPrefixDefinition
    if before.count(_THREAD_CLASS_TOKEN) != 1:
        raise RuntimeError(
            f"latch-hook tap callout has no lone class token: {before!r}"
        )
    wanted = before.replace(_THREAD_CLASS_TOKEN, "")
    display.SetText(1, wanted)
    if str(display.GetText(5) or "") != wanted:
        raise RuntimeError(
            f"latch-hook tap callout class did not drop: {display.GetText(5)!r}"
        )
    rebuild_drawing(adapter, label="latch-hook tap callout class")


def _name_clamp_screws(display: Any) -> None:
    """Hang the back-arc taps the holes locate to and the screws' part number
    under the counterbores' native callout, and print its depth at the .XX
    its head clearance takes."""
    set_hole_callout_precision(
        display,
        {"hw-cbdepth": CLAMP_CBORE_DEPTH_PLACES},
        label="clamp-screw counterbores",
    )
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, CLAMP_CBORE_CALLOUT)  # swDimensionTextCalloutBelow
    # Multi-line text may read back with CR LF; draw_dt_crank_hub strips it too.
    applied = str(display.GetText(4) or "").replace("\r", "")
    if applied != CLAMP_CBORE_CALLOUT:
        raise RuntimeError(
            f"clamp counterbore callout's mate lines did not persist: {applied!r}"
        )


def _place_caption(adapter: Any, text: str, top_centre: tuple[float, float]) -> None:
    """A view caption whose measured box's top centre lands on ``top_centre``
    (INote.GetExtent; draw_pd_transgear_feed_pinion._place_rear_caption)."""
    raw_note = add_note(adapter, text, *top_centre)
    if raw_note is None:
        raise RuntimeError(f"caption {text!r} was not inserted")
    note = _early_bound(raw_note, "INote")
    for _attempt in range(4):
        extent = tuple(float(value) for value in note.GetExtent())
        error = (
            top_centre[0] - (extent[0] + extent[3]) / 2.0,
            top_centre[1] - extent[4],
        )
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        move_annotation(adapter, note.GetAnnotation(), *error, label=text)
    else:
        raise RuntimeError(f"caption {text!r} stayed at {extent}, asked {top_centre}")
    _telemetry.info(f"caption {text!r}: extent {extent}")


def _add_slide_finishes(adapter: Any, face: Any, back: Any) -> None:
    """The platen's two slide faces: the top face on its edge in the back-face
    view, the front face seen face-on, a leader to a point on it."""
    top = _sheet(
        adapter, face, (TOP_FINISH_MODEL_X, BAR_HEIGHT / 2.0, BACK_FACE_Z), "top finish"
    )
    add_surface_finish(
        adapter,
        face,
        edge_xy=top,
        leader_attach_xy=top,
        symbol_xy=TOP_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "top_slide"),
        label="top slide finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    control = surface_finish_by_key(SURFACE_FINISHES, "front_slide")
    front_face = resolve_faces(
        _early_bound(_early_bound(back, "IView").ReferencedDocument, "IModelDoc2"),
        {control.key: control.face},
    )[control.key]
    add_surface_finish(
        adapter,
        back,
        entity=front_face,
        entity_type="FACE",
        leader_attach_xy=_sheet(
            adapter, back, (*FRONT_FINISH_MODEL_XY, -BAR_DEPTH / 2.0), "front finish"
        ),
        symbol_xy=FRONT_FINISH_SYMBOL_XY,
        control=control,
        label="front slide finish",
        char_height=FINISH_CHAR_HEIGHT,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open support-bar source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        source_model, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet_model = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Support Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "support bar; steel bar; counterbored clamp holes; tapped hanger holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=FACE_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=FACE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (face, back, iso):
        set_hidden_lines_removed(adapter, view)

    # Each face view shows the part-hidden row sketch that owns its stations
    # and height (_drawing_hidden_sketches); the back face also the
    # countersinks' reference circles.
    face_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        face,
        keep=FRONT_KEEP,
        view_label="back face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    back_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="front face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    # Section A-A cuts down the pivot axis across the whole height; its
    # full-thread line lies in the cutting plane and is shown while it is cut.
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        ("PivotThreadReference",),
        label="pivot section",
        base_view=face,
    ):
        reach = BAR_HEIGHT / 2.0 + SECTION_OVERRUN
        section = create_section_view(
            adapter,
            face,
            line_start=_sheet(adapter, face, (PIVOT_TAP_X, reach, 0.0), "cut top"),
            line_end=_sheet(adapter, face, (PIVOT_TAP_X, -reach, 0.0), "cut foot"),
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            label="section A-A",
        )
        _turn_y_up(adapter, section, label="section A-A")
        set_hidden_lines_removed(adapter, section)
        section_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=_section_keep(adapter, section),
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )

    # The west slots: detail C face-on at the outer one, section B-B across
    # the inner one for the counterbore's depth.
    detail = _slot_detail(adapter, back)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="slot detail C",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    slot_section = create_section_view(
        adapter,
        back,
        line_start=_sheet(adapter, back, (SLOT_SECTION_X, reach, 0.0), "B cut top"),
        line_end=_sheet(adapter, back, (SLOT_SECTION_X, -reach, 0.0), "B cut foot"),
        view_xy=SLOT_SECTION_CENTER,
        section_label="B",
        scale=SLOT_SECTION_SCALE,
        label="section B-B",
    )
    _turn_y_up(adapter, slot_section, label="section B-B")
    set_hidden_lines_removed(adapter, slot_section)
    slot_section_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        slot_section,
        keep=_slot_section_keep(adapter, slot_section),
        view_label="section B-B",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    annotations = [
        *face_annotations,
        *back_annotations,
        *section_annotations,
        *detail_annotations,
        *slot_section_annotations,
    ]
    set_dimension_callouts(
        adapter,
        annotations,
        {
            name: text
            for name, text in DIMENSION_CALLOUTS.items()
            if name not in CALLOUTS_ABOVE
        },
    )
    set_dimension_callouts(
        adapter,
        annotations,
        {name: DIMENSION_CALLOUTS[name] for name in CALLOUTS_ABOVE},
        location="above",
    )
    # Places (and so each dimension's band or limit) are authored on the part;
    # the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    tap_edge, cbore_edge = _hole_rims(face, back)
    _drop_thread_class(
        adapter,
        add_native_hole_callout(
            adapter,
            face,
            edge=tap_edge,
            callout_xy=BRACKET_CALLOUT_XY,
            label="latch-hook base taps",
            process="TAP",
        ),
    )
    _name_clamp_screws(
        add_native_hole_callout(
            adapter,
            back,
            edge=cbore_edge,
            callout_xy=CLAMP_CALLOUT_XY,
            label="clamp-screw counterbores",
            process="DRILL, C'BORE",
        )
    )
    _add_slide_finishes(adapter, face, back)
    _move_caption(adapter, section, lambda x, y: (x, y - CAPTION_DROP))
    _move_caption(adapter, slot_section, lambda _x, _y: SLOT_SECTION_CAPTION_XY)
    _place_caption(adapter, FACE_VIEW_CAPTION, FACE_CAPTION_TOP)
    _place_caption(adapter, BACK_VIEW_CAPTION, BACK_CAPTION_TOP)
    _place_caption(adapter, TOP_FINISH_REASON, TOP_REASON_TOP)
    _place_caption(adapter, FRONT_FINISH_REASON, FRONT_REASON_TOP)
    _place_caption(adapter, STATION_END_LABEL, FACE_END_LABEL_TOP)
    _place_caption(adapter, STATION_END_LABEL, BACK_END_LABEL_TOP)

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # The native TAP callout restates the taps, so the Hole Wizard's own
    # "Tapped Hole" note is the one redundant automatic note.
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Support Bar Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
