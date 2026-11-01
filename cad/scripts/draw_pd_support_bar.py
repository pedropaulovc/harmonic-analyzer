r"""Create the curated machinist drawing for the platen support bar (MHA-PD-07).

A 17.8 x 1.010 x .374 steel bar clamped across the frame columns, printed in
decimal inch (#290). Its BACK face
carries the transgear pivot's #8-32 through tap and the latch hook's two
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
  counterbores' native callout (depth at .XX, sizes at .XXX) naming the back-arc taps the
  row locates to, and the front face's slide roughness. Each
  roughness symbol has its reason beside it; the sheet has no general note.
* Detail C looks face-on at the outer slot: the slot's and its
  counterbore's widths and travels, the slot's width naming the MHA-SH-02
  taps it takes up and the counterbore's the MHA-SH-VN-53 head it holds.
  Section B-B cuts the inner slot across the bar for the counterbore's depth;
  its arrows face right, away from the outer slot's station witness.
* Each face view carries its caption below its own dimension stack, with
  native text clearance from detail C; section A-A cuts the pivot tap across
  the bar: the banded thickness and the tap's countersunk mouths on both
  faces.

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
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    callout_ink,
    move_annotation,
    require_clear,
    require_inside,
    require_leader_clear,
    sheet_region,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_layout_audit import annotation_display
from _drawing_leaders import dimension_segments, distance_to_box, leader_crossings
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_resolve import resolve_faces
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _layout_audit import display_box
from _layout_geometry import Box, Segment, segment_box_overlap_length
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
import _telemetry
from _surface_finish import surface_finish_by_key
from build_pd_support_bar import (
    BAR_LENGTH,
    CLAMP_CBORE_DEPTH,
    CLAMP_CBORE_DIA,
    CLAMP_ROUND_X,
    CLAMP_SLOT_WIDTH,
    CLAMP_SLOT_X,
)
from _column_clamp_interface import BAR_DEPTH
from pd_support_bar_spec import (
    BACK_FACE_Z,
    BAR_HEIGHT,
    BRACKET_TAP_CSK_DIA,
    BRACKET_TAP_SPEC,
    BRACKET_TAP_X,
    CLAMP_TAP_Y,
    HANGER_TAP_Y,
    PIVOT_TAP_X,
)
from pd_support_bar_drawing_spec import (
    BACK_VIEW_CAPTION,
    BRACKET_TAP_CALLOUT_PRECISION,
    CLAMP_CALLOUT_PRECISION,
    CLAMP_CBORE_CALLOUT,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_VIEW_CAPTION,
    FRONT_FINISH_REASON,
    STATION_END_LABEL,
    SURFACE_FINISHES,
    TOP_FINISH_REASON,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


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
# pivot's, their leaders between the two pairs.  Move that pair 8 mm farther
# right for the full pivot vendor-number row, keeping the hook leader left of
# its own countersink text instead of widening a text/leader allowance.
ROW_STEP = 0.013
FRONT_KEEP = {
    "PivotTapStation": (LEFT_END + 0.042, FACE_BOTTOM - ROW_STEP),
    "BracketTapStation1": (LEFT_END + 0.115, FACE_BOTTOM - 2.0 * ROW_STEP),
    "BracketTapStation2": (LEFT_END + 0.118, FACE_BOTTOM - 3.0 * ROW_STEP),
    "Length": (FACE_CENTER[0], FACE_BOTTOM - 4.0 * ROW_STEP),
    "HangerRowHeight": (RIGHT_END + 0.022, FACE_BOTTOM - 0.010),
    "PivotTapDrillDia": (_face_x(PIVOT_TAP_X) + 0.032, FACE_TOP + 0.030),
    "PivotCskDia": (_face_x(PIVOT_TAP_X) + 0.039, FACE_TOP + 0.014),
    "BracketCskDia": (_face_x(BRACKET_TAP_X[0]) + 0.067, FACE_TOP + 0.014),
}
BRACKET_CALLOUT_XY = (_face_x(BRACKET_TAP_X[1]) + 0.064, FACE_TOP + 0.031)
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
# audit: outside-border). Naming the MHA-SH-02 taps makes it four lines of
# at most 11 characters: about 18-47 mm by 97-117 mm, under its lower
# extension line (122 mm) and left of detail C's letter (51 mm). The long
# rows stand 6 and 7 mm apart, not 8: 8 mm stepping put the 17.345 line a
# hairline over detail C's counterbore-width text, whose upper limit then
# read as part of the 17.345 dimension (machinist review, 2026-10-23).
BACK_KEEP = {
    "ClampStation1": (RIGHT_END + 0.019, BACK_BOTTOM - 0.010),
    "ClampStation2": (RIGHT_END + 0.019, BACK_BOTTOM - 0.018),
    "ClampStation3": (RIGHT_END - 0.150, BACK_BOTTOM - 0.024),
    "ClampStation4": (RIGHT_END - 0.170, BACK_BOTTOM - 0.031),
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
# Centre the front caption under the native outer station span, then keep
# its complete text block right of detail C's native dimension text.
FRONT_CAPTION_AIR_M = 0.004
FINISH_CHAR_HEIGHT = 0.0025
CAPTION_SETTLE_M = 0.0006

# The west slots in the clear field under the front-face view. Detail C looks
# face-on at the outer slot at 2:1, between section B-B and the title block:
# the counterbore's width left of it, its text over the counterbore's upper
# edge on a shouldered leader (inside its 17 mm span the three-line block
# met its own extension line and arrow, r6 machinist review), the slot's
# right, its text under the slot's lower edge the same way (inside its 4.98
# span the block was struck by its own dimension line, r4), the slot's
# travel below and the counterbore's above; its label right of the slot's
# width. The slot width's block centres on its point; its five callout
# lines (the head's reason for the upper limit, then the take-up's) put
# that point 5 mm higher than the three-line block's, off the border, and
# the label 4.5 mm higher to keep its air over the block. It is a cropped
# *Back model view, dimensioned uncropped then cropped (the
# draw_ch_amplitude_bar notch details): a model view has no native label or
# parent circle, so its label is a note in the native label's words and its
# mark a black circle and letter on the front-face view. The letter stands
# off the bar's end, under the clamp row's extension line: over the bar it
# printed on section B-B's upper letter, whose arrows end over the outer slot.
# The crop prints no outline (draw_fr_rocker_arm_support's VIEW B): its full
# circle drawn tight round the obround counterbore read as a round
# counterbore (r7 machinist review).
DETAIL_SLOT_X = max(CLAMP_SLOT_X)
DETAIL_FOCUS = (DETAIL_SLOT_X, CLAMP_TAP_Y, -BAR_DEPTH / 2.0)  # model mm
DETAIL_CENTER = (0.124, 0.048)
DETAIL_SCALE = (2, 1)
DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0  # sheet metres per mm
DETAIL_RADIUS_MM = 7.5
DETAIL_LABEL = f"DETAIL C\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
DETAIL_LABEL_XY = (0.200, 0.0645)  # top centre, above the slot-width text
DETAIL_LETTER = "C"
DETAIL_LETTER_TOP = (LEFT_END - 0.004, BACK_CENTER[1] - 0.0025)  # top centre
DETAIL_POSITION_TOL_M = 1e-4
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# The counterbore's shouldered callout stands left of detail C, clear of
# section B-B even with the full shared vendor identity and native limit
# rows. Read back both its text and leader against the section before export;
# fixed character-width estimates missed the previous collision.
DETAIL_KEEP = {
    "ClampSlotCboreWidth": (DETAIL_CENTER[0] - 0.017, DETAIL_CENTER[1] + 0.020),
    "ClampSlotWidth": (DETAIL_CENTER[0] + 0.026, DETAIL_CENTER[1] - 0.014),
    "ClampSlotTravel": (DETAIL_CENTER[0] + 0.015, DETAIL_CENTER[1] - 0.020),
    "ClampSlotCboreTravel": (DETAIL_CENTER[0] + 0.015, DETAIL_CENTER[1] + 0.021),
}
# Section B-B cuts the inner slot across the bar, at 1:1 in the sheet's
# lower-left corner: the counterbore's depth with its text and callout
# outside the front face the counterbore enters, the caption under it. The
# depth's line runs on the clamp line, through the counterbore's mouth
# and the through slot, so neither extension line crosses the cut: over the
# top face (r6) the floor's extension line ran up through the hatch and read
# as a seam (its 0.13 stroke from the floor's lower corner, PDF paths).
# SLOT_DEPTH_SHELF_DROP seeds the dimension line through the open slot.
# After the callout is hung, OffsetText keeps the original line in the open
# slot while placing its native text right of B-B, below detail C's shelf.
# Native segment readback must stay out of the actual section material.
# The caption's top centre stands SLOT_CAPTION_DROP under the
# section's centre: its block (r7: 14.6 tall, its top 0.05 under the anchor)
# then has 3 mm of air under the cut and 3.4 over the inner border's edge
# (y 12.9), which the r7 caption touched (0.4) at centre y 45.
SLOT_SECTION_X = min(CLAMP_SLOT_X)
SLOT_SECTION_CENTER = (0.053, 0.048)
SLOT_SECTION_SCALE = (1, 1)
SLOT_CAPTION_DROP = 0.017
SLOT_SECTION_CAPTION_XY = (
    SLOT_SECTION_CENTER[0],
    SLOT_SECTION_CENTER[1] - SLOT_CAPTION_DROP,
)  # top centre
SLOT_SECTION_KEEP_NAMES = ("ClampSlotCboreDepth",)
SLOT_DEPTH_SHELF_DROP = 0.0112
SLOT_DEPTH_TEXT_SIDE = 0.018
SLOT_CALLOUT_AIR_M = 0.003

# Section A-A: the thickness up-left of the cut bar, its text outside the
# extension lines since the 2:1 span is narrower than it. Nothing is
# dimensioned under the cut bar, so its caption's top stands just under the
# bar's foot at the native caption's x (r4 review: a 35 mm drop, kept from
# when the thread and drill depths stood there, put it beside the isometric).
SECTION_KEEP_NAMES = ("Depth",)
SECTION_DEPTH_RISE = 0.010
SECTION_DEPTH_SIDE = 0.028
SECTION_CAPTION_GAP = 0.004
SECTION_CAPTION_TOP_Y = (
    SECTION_CENTER[1]
    - BAR_HEIGHT * SECTION_SCALE[0] / SECTION_SCALE[1] / 2000.0
    - SECTION_CAPTION_GAP
)
# How far (model mm) each cutting line runs past the bar's top and bottom
# edges. Both views are 1:2, and SolidWorks stands each end's letter at the
# same offset from its arrow's line (r7: from 1.28 mm under it to 4.89 over),
# so the foot's letter, unlike the top's, rises toward the bar. At 1.5 mm
# the lower B and A sat across the bottom edges and the upper ones 0.2 mm
# over the top (r7 machinist review, rule 14); these clear the letters by
# 3.0 - 1.28 = 1.72 mm over the top edge and 6.5 - 4.89 = 1.61 under the
# bottom.
SECTION_OVERRUN_TOP = 6.0
SECTION_OVERRUN_FOOT = 13.0

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
    """Section A-A's text position from its own projection, whichever way the
    cut looks: the thickness left of the bar's left face."""

    def point(z: float, y: float = HANGER_TAP_Y) -> tuple[float, float]:
        return _sheet(adapter, section, (PIVOT_TAP_X, y, z), "section A-A")

    top = point(0.0, BAR_HEIGHT / 2.0)[1]
    mouth = point(BACK_FACE_Z)[0]
    front = point(-BACK_FACE_Z)[0]
    return {
        "Depth": (min(mouth, front) - SECTION_DEPTH_SIDE, top + SECTION_DEPTH_RISE),
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
            (max(CLAMP_ROUND_X), CLAMP_TAP_Y, -BAR_DEPTH / 2.0),
            CLAMP_CBORE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="clamp counterbore rim",
            radius_tol_mm=0.025,
        )
        .edge
    )
    return tap, cbore


def _activate(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
    add_to_db: bool,
) -> Any:
    """A circle in the ACTIVE ``view``'s own sketch from sheet points, through
    the view sketch's ModelToSketchTransform. Without ``add_to_db`` the circle
    is left SELECTED, which is what Crop2 consumes
    (draw_ch_amplitude_bar._sketch_circle)."""
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


def _slot_detail(adapter: Any) -> Any:
    """Detail C, uncropped: a standalone 2:1 *Back model view moved so the
    outer slot's centre lands on DETAIL_CENTER (checked to
    DETAIL_POSITION_TOL_M). Not a native detail: the r3 farm leaf's native
    detail of the front-face view imported none of the slot profiles'
    dimensions (available=[]), the refusal draw_ch_amplitude_bar and
    draw_dt_vn_post_mount_screw measured, while the same part's projected views
    import their consumed profiles' dimensions (PivotTapProfile's in the
    back-face view)."""
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Back", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"slot detail C scale {ratio!r}, expected {DETAIL_SCALE!r}")
    label = "slot detail C centre"
    center = _sheet(adapter, view, DETAIL_FOCUS, label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move slot detail C onto its spot")
    draw.EditRebuild3()
    center = _sheet(adapter, view, DETAIL_FOCUS, label)
    if math.dist(center, DETAIL_CENTER) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"slot detail C centre sits at {center!r}, not {DETAIL_CENTER!r}"
        )
    return view


def _crop_slot_detail(adapter: Any, view: Any) -> None:
    """Crop ``view`` to its circle round DETAIL_CENTER: activate it, sketch
    the circle in its own sketch and Crop2 while the circle is still selected.
    Crop status, IsCropped, the outline and its style are read back and raise
    (draw_ch_amplitude_bar._crop_detail_view)."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    uncropped = tuple(float(value) for value in view.GetOutline())
    _activate(adapter, view, label="slot detail C")
    _sketch_circle(
        adapter,
        view,
        DETAIL_CENTER,
        DETAIL_RADIUS_MM * DETAIL_MM,
        label="slot detail C crop",
        add_to_db=False,
    )
    status = int(view.Crop2(False, True, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"slot detail C Crop2 status {status}, IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm"
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"slot detail C is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # Uncropped, the 2:1 view spans the whole 452 mm bar (~0.9 m on the
    # sheet); the crop is one 30 mm circle.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] > (uncropped[2] - uncropped[0]) / 2.0
    ):
        raise RuntimeError(
            f"slot detail C crop did not take: outline {outline!r}, "
            f"before {uncropped!r}"
        )
    # The jagged-outline accessor is invalid without an outline
    # (_drawing_detail_crop), so only the no-outline flag is read back.
    if not bool(view.CropViewNoOutline):
        raise RuntimeError("slot detail C's crop prints an outline; expected none")


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


def _dimension_then_crop(adapter: Any, view: Any) -> list[Any]:
    """Import and curate detail C's dimensions while it is uncropped, then
    crop it; a kept dimension the crop drops raises."""
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        view,
        keep=DETAIL_KEEP,
        view_label="slot detail C",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    before = _view_dimension_names(adapter, view)
    _crop_slot_detail(adapter, view)
    after = _view_dimension_names(adapter, view)
    _telemetry.info(f"slot detail C dimensions before crop {before}, after {after}")
    lost = sorted(set(DETAIL_KEEP) - set(after))
    if lost:
        raise RuntimeError(
            f"slot detail C lost {lost} to its crop; before {before}, after {after}"
        )
    return annotations


def _label_slot_detail(adapter: Any, detail: Any, back: Any) -> None:
    """Detail C's label right of its callouts, owned by the detail, and its
    mark on the front-face view: a black circle round the outer slot and the
    letter off the bar's end. The back view is left active."""
    _activate(adapter, detail, label="slot detail C")
    _place_caption(adapter, DETAIL_LABEL, DETAIL_LABEL_XY)
    _activate(adapter, back, label="front face view")
    mark = _sheet(adapter, back, DETAIL_FOCUS, "slot detail C mark")
    circle = _sketch_circle(
        adapter,
        back,
        mark,
        DETAIL_RADIUS_MM * _S,
        label="slot detail C mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("slot detail C mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    _place_caption(adapter, DETAIL_LETTER, DETAIL_LETTER_TOP)


def _slot_section_keep(adapter: Any, section: Any) -> dict[str, tuple[float, float]]:
    """Seed the associative depth's line through the open slot; its text is
    subsequently offset right of B-B and below detail C."""

    def point(z: float, y: float = CLAMP_TAP_Y) -> tuple[float, float]:
        return _sheet(adapter, section, (SLOT_SECTION_X, y, z), "section B-B")

    front, middle = point(-BAR_DEPTH / 2.0)
    floor = point(-BAR_DEPTH / 2.0 + CLAMP_CBORE_DEPTH)[0]
    away = math.copysign(1.0, front - floor)
    return {
        "ClampSlotCboreDepth": (
            front + away * SLOT_DEPTH_TEXT_SIDE,
            middle + SLOT_DEPTH_SHELF_DROP,
        )
    }


def _assert_slot_callout_clear(
    adapter: Any, annotations: list[Any], section: Any, back_annotations: list[Any]
) -> None:
    """Prove detail C's native width text and leader clear section B-B, and its
    text has air under the front view's 17.345 line (machinist review: its
    upper limit hung a hairline under that line and read as part of it)."""
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        == "ClampSlotCboreWidth"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one slot counterbore width, found {len(matches)}")
    outline = tuple(
        float(value) for value in _early_bound(section, "IView").GetOutline()
    )
    if len(outline) != 4 or outline[0] >= outline[2] or outline[1] >= outline[3]:
        raise RuntimeError(f"section B-B has no usable native outline: {outline!r}")
    ink = callout_ink(adapter, matches[0], label="slot counterbore width")
    others = {"section B-B": outline}
    require_clear(ink.label, ink.text, others)
    require_leader_clear(ink, others)
    text = _native_text_box(adapter, matches[0], label="slot counterbore width")
    station = _dimension_annotation(adapter, back_annotations, "ClampStation4")
    station_lines = dimension_segments(station)
    air = min(distance_to_box(line, text) for line in station_lines)
    if air < CLEAR_GAP_M:
        raise RuntimeError(
            f"slot counterbore width text {text!r} is {air:.4f} m from the "
            f"17.345 station's lines {station_lines!r}"
        )
    _telemetry.info(
        f"slot counterbore width clearance: text={ink.text!r}, "
        f"native text={text!r}, 17.345 air={air:.4f}, "
        f"segments={ink.leader!r}, section B-B outline={outline!r}"
    )


def _slot_depth_text_target(
    box: tuple[float, ...], outline: tuple[float, ...], width_box: tuple[float, ...]
) -> tuple[float, float]:
    """Text centre/bottom in the measured lane right of B-B and below C."""
    left = outline[2] + SLOT_CALLOUT_AIR_M
    top = width_box[1] - SLOT_CALLOUT_AIR_M
    return left + (box[2] - box[0]) / 2.0, top - (box[3] - box[1])


def _slot_section_material_boxes(
    adapter: Any, section: Any, witnesses: list[Any]
) -> dict[str, tuple[float, ...]]:
    """The centre-of-slot cut: bar minus through-slot and counterbore voids.

    Project the authored model geometry, not GetOutline's padded rectangle.
    The two associative witnesses give the native front/floor surface x's;
    they must match those projected surfaces at the existing 1 um readback
    tolerance. Using their actual x's also retains exact boundary landings.
    """

    def point(y: float, z: float = 0.0) -> tuple[float, float]:
        return _sheet(adapter, section, (SLOT_SECTION_X, y, z), "B-B material")

    front = point(CLAMP_TAP_Y, -BAR_DEPTH / 2.0)
    floor = point(CLAMP_TAP_Y, -BAR_DEPTH / 2.0 + CLAMP_CBORE_DEPTH)
    back = point(CLAMP_TAP_Y, BAR_DEPTH / 2.0)
    xs = [line[0][0] for line in witnesses]
    front_x = min(xs, key=lambda x: abs(x - front[0]))
    floor_x = min(xs, key=lambda x: abs(x - floor[0]))
    if abs(front_x - front[0]) > 1e-6 or abs(floor_x - floor[0]) > 1e-6:
        raise RuntimeError(
            "section B-B depth: witnesses are not on the front/floor surfaces"
        )
    xmin, xmax = sorted((back[0], front_x))
    rear_min, rear_max = sorted((back[0], floor_x))
    bottom, top = sorted(point(y)[1] for y in (-BAR_HEIGHT / 2.0, BAR_HEIGHT / 2.0))
    slot_bottom, slot_top = sorted(
        point(CLAMP_TAP_Y + y)[1]
        for y in (-CLAMP_SLOT_WIDTH / 2.0, CLAMP_SLOT_WIDTH / 2.0)
    )
    cbore_bottom, cbore_top = sorted(
        point(CLAMP_TAP_Y + y)[1]
        for y in (-CLAMP_CBORE_DIA / 2.0, CLAMP_CBORE_DIA / 2.0)
    )
    return {
        "upper bar": (xmin, cbore_top, xmax, top),
        "lower bar": (xmin, bottom, xmax, cbore_bottom),
        "rear upper step": (rear_min, slot_top, rear_max, cbore_top),
        "rear lower step": (rear_min, cbore_bottom, rear_max, slot_bottom),
    }


def _require_slot_depth_ink_outside_material(
    lines: list[Any], material: dict[str, tuple[float, ...]]
) -> None:
    for start, end in lines:
        segment = Segment(*start, *end)
        for name, bounds in material.items():
            # Existing interior clipping permits surface contact, not
            # penetration. No outline inset or hatch allowance is introduced.
            if segment_box_overlap_length(segment, Box(*bounds)) > 0.0:
                raise RuntimeError(
                    f"section B-B depth ink crosses {name}: {start!r}->{end!r}, {bounds!r}"
                )


def _require_slot_depth_witnesses(lines: list[Any], witnesses: list[Any]) -> None:
    for expected in witnesses:
        if not any(
            all(math.dist(a, b) <= 1e-6 for a, b in zip(expected, candidate))
            for line in lines
            for candidate in (line, line[::-1])
        ):
            raise RuntimeError(f"section B-B depth: native witness moved: {expected!r}")


def _assert_slot_depth_callout_clear(
    adapter: Any,
    section: Any,
    detail_annotations: list[Any],
    section_annotations: list[Any],
    back_annotations: list[Any],
    witnesses: list[Any],
) -> None:
    depth = _dimension_annotation(adapter, section_annotations, "ClampSlotCboreDepth")
    display = _early_bound(
        _early_bound(depth, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    if not bool(display.OffsetText):
        raise RuntimeError("section B-B depth: native offset text did not persist")
    depth_box = _native_text_box(adapter, depth, label="section B-B depth")
    depth_lines = dimension_segments(depth)
    _require_slot_depth_witnesses(depth_lines, witnesses)
    material = _slot_section_material_boxes(adapter, section, witnesses)
    _require_slot_depth_ink_outside_material(depth_lines, material)
    outline = tuple(
        float(value) for value in _early_bound(section, "IView").GetOutline()
    )
    others = {"section B-B": outline}
    caption_count = 0
    for raw_note in _early_bound(section, "IView").GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked = str(note.PropertyLinkedText or "")
        if all(token in linked for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            caption_count += 1
            others["section B-B caption"] = _native_text_box(
                adapter, note.GetAnnotation(), label="section B-B caption"
            )
    if caption_count != 1:
        raise RuntimeError(
            f"section B-B depth: expected one native caption, found {caption_count}"
        )
    if any(
        distance_to_box(line, others["section B-B caption"]) < CLEAR_GAP_M
        for line in depth_lines
    ):
        raise RuntimeError("section B-B depth ink meets its native section caption")
    detail_lines = {}
    for annotation in detail_annotations:
        name = dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        others[name] = _native_text_box(adapter, annotation, label=name)
        detail_lines[name] = dimension_segments(annotation)
    if "ClampSlotCboreWidth" not in detail_lines:
        raise RuntimeError("section B-B depth: missing detail C counterbore width")
    for annotation in back_annotations:
        name = dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        others[name] = _native_text_box(adapter, annotation, label=name)
        if any(
            distance_to_box(line, depth_box) < CLEAR_GAP_M
            for line in dimension_segments(annotation)
        ):
            raise RuntimeError(f"section B-B depth text meets front-view {name} ink")
    require_clear("section B-B depth", depth_box, others)
    require_inside("section B-B depth", depth_box, sheet_region(adapter))
    for name, lines in detail_lines.items():
        if (
            any(distance_to_box(line, depth_box) < CLEAR_GAP_M for line in lines)
            or any(
                distance_to_box(line, others[name]) < CLEAR_GAP_M
                for line in depth_lines
            )
            or leader_crossings({"section B-B depth": depth_lines, name: lines})
        ):
            raise RuntimeError(f"section B-B depth text/leader meets detail C {name}")
    _telemetry.info(
        f"section B-B depth native text={depth_box!r}, lines={depth_lines!r}, "
        f"fixed witnesses={witnesses!r}, material={material!r}, neighbouring text={others!r}"
    )


def _place_slot_depth_callout(
    adapter: Any,
    section: Any,
    detail_annotations: list[Any],
    section_annotations: list[Any],
    back_annotations: list[Any],
) -> list[Any]:
    """Move only the native depth text; retain its original dimension line."""
    depth = _dimension_annotation(adapter, section_annotations, "ClampSlotCboreDepth")
    original_lines = dimension_segments(depth)
    witnesses = [
        line
        for line in original_lines
        if abs(line[0][0] - line[1][0]) < 1e-9 and abs(line[0][1] - line[1][1]) > 1e-9
    ]
    if len(witnesses) != 2:
        raise RuntimeError(
            f"section B-B depth: expected two native witnesses: {witnesses!r}"
        )
    widget = [
        line
        for line in original_lines
        if abs(line[0][1] - line[1][1]) < 1e-9
        and {line[0][0], line[1][0]} == {witness[0][0] for witness in witnesses}
    ]
    if len(widget) != 1:
        raise RuntimeError(
            "section B-B depth: no unambiguous native dimension baseline"
        )
    baseline_y = widget[0][0][1]
    annotation = _early_bound(depth, "IAnnotation")
    x, _y, z = (float(value) for value in annotation.GetPosition())
    # OffsetText can re-dress a line onto its annotation's creation-point y.
    # Seed that point on the already-native void-height baseline first, then
    # enable offset text, following the trammel, harmonic-base and v-block pattern.
    if not annotation.SetPosition2(x, baseline_y, z):
        raise RuntimeError("section B-B depth: could not seed its native baseline")
    display = _early_bound(
        _early_bound(depth, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    display.OffsetText = True
    rebuild_drawing(adapter, label="section B-B offset depth text")
    if not bool(display.OffsetText):
        raise RuntimeError("section B-B depth: native offset text did not persist")
    _require_slot_depth_witnesses(dimension_segments(depth), witnesses)
    width = _dimension_annotation(adapter, detail_annotations, "ClampSlotCboreWidth")
    for _attempt in range(4):
        _early_bound(section, "IView").UpdateViewDisplayGeometry()
        box = _native_text_box(adapter, depth, label="section B-B depth")
        outline = tuple(
            float(value) for value in _early_bound(section, "IView").GetOutline()
        )
        width_box = _native_text_box(adapter, width, label="detail C counterbore width")
        centre, bottom = _slot_depth_text_target(box, outline, width_box)
        error = (centre - (box[0] + box[2]) / 2.0, bottom - box[1])
        if math.hypot(*error) <= CAPTION_SETTLE_M:
            break
        move_annotation(adapter, depth, *error, label="section B-B depth text")
    else:
        raise RuntimeError("section B-B depth text did not settle in its measured lane")
    _assert_slot_depth_callout_clear(
        adapter,
        section,
        detail_annotations,
        section_annotations,
        back_annotations,
        witnesses,
    )
    return witnesses


def _dimension_annotation(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, _early_bound(annotation, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name}, found {len(matches)}")
    return matches[0]


def _native_text_box(adapter: Any, annotation: Any, *, label: str) -> tuple[float, ...]:
    """Use the native text widths/anchors, not a note's selection extent."""
    display, errors = annotation_display(adapter, annotation)
    if errors:
        raise RuntimeError(f"{label}: refused native display reads: {errors!r}")
    texts = []
    for raw in display.get("texts", ()):
        if not str(raw["t"]).strip():
            continue
        at = tuple(float(value) for value in raw["pos"])
        width, height, angle = (float(raw.get(key, 0.0)) for key in ("w", "h", "ang"))
        reference = raw["ref"]
        if (
            len(at) != 3
            or not all(map(math.isfinite, (*at, width, height, angle)))
            or width <= 0.0
            or height <= 0.0
            or reference not in range(6)
        ):
            raise RuntimeError(f"{label}: unreadable native text bounds: {raw!r}")
        # swTextPosition_e, as in draw_sh_vn_music_wire: display_box takes
        # lower-left coordinates, whereas the native reference can differ.
        dx, dy = {
            0: (0.0, -height),
            1: (0.0, 0.0),
            2: (-width / 2, -height / 2),
            3: (-width, -height),
            4: (-width, 0.0),
            5: (-width / 2, -height),
        }[reference]
        c, s = math.cos(angle), math.sin(angle)
        texts.append(
            {
                **raw,
                "ref": 1,
                "pos": (at[0] + c * dx - s * dy, at[1] + s * dx + c * dy, at[2]),
            }
        )
    box = display_box({"texts": texts})
    if box is None:
        raise RuntimeError(f"{label}: no native text bounds")
    return box.xmin, box.ymin, box.xmax, box.ymax


def _front_caption_target(
    station_lines: list[Any],
    caption: tuple[float, ...],
    details: dict[str, tuple[float, ...]],
) -> tuple[float, float]:
    """Top centre below the outer station row and clear of detail C."""
    horizontal = [
        (start, end)
        for start, end in station_lines
        if abs(start[1] - end[1]) < 1e-9 and abs(start[0] - end[0]) > 1e-9
    ]
    if not horizontal:
        raise RuntimeError("front caption: outer station has no native dimension line")
    start, end = max(horizontal, key=lambda line: math.dist(*line))
    # The witness extends 1 mm past the dimension line. Keep clear of that
    # actual lower endpoint as well, without moving any dimension attachment.
    top = (
        min(point[1] for line in station_lines for point in line) - FRONT_CAPTION_AIR_M
    )
    centre = (start[0] + end[0]) / 2.0
    bottom = top - (caption[3] - caption[1])
    neighbours = [
        box
        for box in details.values()
        if box[1] < top + FRONT_CAPTION_AIR_M and box[3] + FRONT_CAPTION_AIR_M > bottom
    ]
    if neighbours:
        centre = max(
            centre,
            max(box[2] for box in neighbours)
            + FRONT_CAPTION_AIR_M
            + (caption[2] - caption[0]) / 2.0,
        )
    return centre, top


def _front_caption_geometry(
    adapter: Any,
    caption: Any,
    back_annotations: list[Any],
    detail_annotations: list[Any],
) -> tuple[tuple[float, ...], tuple[float, float], dict[str, tuple[float, ...]]]:
    station = _dimension_annotation(adapter, back_annotations, "ClampStation4")
    details = {
        dimension_name(
            adapter, _early_bound(annotation, "IAnnotation")
        ): _native_text_box(adapter, annotation, label="detail C dimension")
        for annotation in detail_annotations
    }
    if not details:
        raise RuntimeError("front caption: detail C has no native dimensions")
    box = _native_text_box(adapter, caption, label=BACK_VIEW_CAPTION)
    target = _front_caption_target(dimension_segments(station), box, details)
    return box, target, details


def _assert_front_caption_clear(
    adapter: Any,
    caption: Any,
    back_annotations: list[Any],
    detail_annotations: list[Any],
) -> None:
    box, target, details = _front_caption_geometry(
        adapter, caption, back_annotations, detail_annotations
    )
    actual = ((box[0] + box[2]) / 2.0, box[3])
    if math.dist(actual, target) > CAPTION_SETTLE_M:
        raise RuntimeError(
            f"front caption left its own dimension stack: {box!r}, {target!r}"
        )
    require_clear(BACK_VIEW_CAPTION, box, details)
    _telemetry.info(
        f"front caption native bounds={box!r}, target={target!r}, detail C={details!r}"
    )


def _place_front_caption(
    adapter: Any, back: Any, back_annotations: list[Any], detail_annotations: list[Any]
) -> Any:
    _activate(adapter, back, label="front face caption")
    note = add_note(adapter, BACK_VIEW_CAPTION, *BACK_CENTER)
    if note is None:
        raise RuntimeError("front face caption was not inserted")
    caption = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    for _attempt in range(4):
        _early_bound(back, "IView").UpdateViewDisplayGeometry()
        box, target, _details = _front_caption_geometry(
            adapter, caption, back_annotations, detail_annotations
        )
        error = (target[0] - (box[0] + box[2]) / 2.0, target[1] - box[3])
        if math.hypot(*error) <= CAPTION_SETTLE_M:
            break
        move_annotation(adapter, caption, *error, label=BACK_VIEW_CAPTION)
    else:
        raise RuntimeError("front caption did not settle below its dimension stack")
    _assert_front_caption_clear(adapter, caption, back_annotations, detail_annotations)
    return caption


def _place_slot_section_markers(adapter: Any, section: Any) -> tuple[float, ...]:
    """Put both B arrows right of the cut, leaving the section plane intact."""
    native = _early_bound(section, "IView")
    definition = _early_bound(native.GetSection(), "IDrSection")
    line = tuple(float(value) for value in definition.GetLineInfo())
    if len(line) != 6 or not all(map(math.isfinite, line)):
        raise RuntimeError(f"section B-B: unreadable native cutting line: {line!r}")
    arrows = tuple(float(value) for value in definition.GetArrowInfo())
    if len(arrows) != 12 or not all(map(math.isfinite, arrows)):
        raise RuntimeError("section B-B: unreadable native arrows")
    if arrows[3] < arrows[0] and arrows[9] < arrows[6]:
        reversed_cut = not bool(definition.GetReversedCutDirection())
        definition.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section B-B arrows right")
        if bool(definition.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section B-B: cut-direction write did not persist")
    elif not (arrows[3] > arrows[0] and arrows[9] > arrows[6]):
        raise RuntimeError(
            f"section B-B: arrows are not horizontal counterparts: {arrows!r}"
        )
    _turn_y_up(adapter, native, label="section B-B")
    # A direction change can offset a section's displayed profile. Preserve
    # its established sheet centre by the rebuilt outline, not Position alone.
    outline = tuple(float(value) for value in native.GetOutline())
    position = tuple(float(value) for value in native.Position)
    if not native.SetViewPosition(
        double_array(
            [
                position[0] + SLOT_SECTION_CENTER[0] - (outline[0] + outline[2]) / 2.0,
                position[1] + SLOT_SECTION_CENTER[1] - (outline[1] + outline[3]) / 2.0,
            ]
        ),
        False,
    ):
        raise RuntimeError("section B-B: could not retain its profile centre")
    rebuild_drawing(adapter, label="section B-B profile centre")
    return line


def _assert_slot_marker_clear(
    adapter: Any, section: Any, line: tuple[float, ...], back_annotations: list[Any]
) -> None:
    definition = _early_bound(_early_bound(section, "IView").GetSection(), "IDrSection")
    outline = tuple(
        float(value) for value in _early_bound(section, "IView").GetOutline()
    )
    if (
        len(outline) != 4
        or not all(map(math.isfinite, outline))
        or outline[0] >= outline[2]
        or outline[1] >= outline[3]
        or math.dist(
            ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0),
            SLOT_SECTION_CENTER,
        )
        > 1e-6
    ):
        raise RuntimeError(
            f"section B-B: displayed profile left its centre: {outline!r}"
        )
    # A native direction flip may reverse the endpoint traversal without
    # moving the cutting plane. Keep the same coordinate tolerance in either
    # order; accepting a permutation never accepts a translated or tilted cut.
    actual = tuple(float(value) for value in definition.GetLineInfo())
    if (
        len(actual) != 6
        or len(line) != 6
        or not all(map(math.isfinite, actual))
        or not any(
            all(abs(a - b) <= 1e-9 for a, b in zip(actual, expected))
            for expected in (line, line[3:] + line[:3])
        )
    ):
        raise RuntimeError(
            f"section B-B: cutting plane changed: {line!r} -> {actual!r}"
        )
    arrows = tuple(float(value) for value in definition.GetArrowInfo())
    texts = tuple(float(value) for value in definition.GetTextInfo())
    if (
        len(arrows) != 12
        or len(texts) != 6
        or not all(map(math.isfinite, (*arrows, *texts)))
    ):
        raise RuntimeError("section B-B: unreadable native marker")
    if arrows[3] <= arrows[0] or arrows[9] <= arrows[6]:
        raise RuntimeError(f"section B-B: arrows did not stay right-facing: {arrows!r}")
    station = _dimension_annotation(adapter, back_annotations, "ClampStation4")
    witness_x = min(
        point[0] for segment in dimension_segments(station) for point in segment
    )
    # GetTextInfo gives each letter's upper-left origin. With right-facing
    # arrows, the entire letter and both shafts must stand right of this
    # left-slot witness; a reversal flag alone is not a placement proof.
    marker_left = min((*arrows[0::3], *texts[0::3]))
    if marker_left - witness_x < FRONT_CAPTION_AIR_M:
        raise RuntimeError(
            f"section B-B marker still meets 17.345 witness: "
            f"arrows={arrows!r}, texts={texts!r}, witness_x={witness_x!r}"
        )
    _telemetry.info(
        f"section B-B unchanged plane={actual!r}, arrows={arrows!r}, "
        f"texts={texts!r}, 17.345 witness_x={witness_x!r}"
    )


_THREAD_CLASS_TOKEN = " <hw-threadclass>"


def _drop_thread_class(adapter: Any, display: Any) -> None:
    """Drop the Hole Wizard's thread-class token from the native TAP
    callout's definition (rule 2: the title block's THREADS row carries the
    class); the other tokens stay live (draw_sm_knife_mount precedent). The
    tap drill prints .XXX."""
    set_hole_callout_precision(
        display, BRACKET_TAP_CALLOUT_PRECISION, label="latch-hook base taps"
    )
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
    under the counterbores' native callout; its sizes print .XXX, its depth
    the .XX its head clearance takes."""
    set_hole_callout_precision(
        display,
        CLAMP_CALLOUT_PRECISION,
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

    # Section A-A cuts down the pivot axis across the whole height.
    top = BAR_HEIGHT / 2.0 + SECTION_OVERRUN_TOP
    foot = -(BAR_HEIGHT / 2.0 + SECTION_OVERRUN_FOOT)
    section = create_section_view(
        adapter,
        face,
        line_start=_sheet(adapter, face, (PIVOT_TAP_X, top, 0.0), "cut top"),
        line_end=_sheet(adapter, face, (PIVOT_TAP_X, foot, 0.0), "cut foot"),
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

    # The west slots: detail C face-on at the outer one (a cropped model
    # view, dimensioned before its crop), section B-B across the inner one
    # for the counterbore's depth.
    detail = _slot_detail(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = _dimension_then_crop(adapter, detail)
    slot_section = create_section_view(
        adapter,
        back,
        line_start=_sheet(adapter, back, (SLOT_SECTION_X, top, 0.0), "B cut top"),
        line_end=_sheet(adapter, back, (SLOT_SECTION_X, foot, 0.0), "B cut foot"),
        view_xy=SLOT_SECTION_CENTER,
        section_label="B",
        scale=SLOT_SECTION_SCALE,
        label="section B-B",
    )
    slot_section_line = _place_slot_section_markers(adapter, slot_section)
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
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's band or limit) are authored on the part;
    # the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Detail C's label and mark go on once every import is done, so nothing of
    # the front-face view's own sketch is near an import.
    _label_slot_detail(adapter, detail, back)
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
    _move_caption(adapter, section, lambda x, _y: (x, SECTION_CAPTION_TOP_Y))
    _move_caption(adapter, slot_section, lambda _x, _y: SLOT_SECTION_CAPTION_XY)
    _place_caption(adapter, FACE_VIEW_CAPTION, FACE_CAPTION_TOP)
    front_caption = _place_front_caption(
        adapter, back, back_annotations, detail_annotations
    )
    _place_caption(adapter, TOP_FINISH_REASON, TOP_REASON_TOP)
    _place_caption(adapter, FRONT_FINISH_REASON, FRONT_REASON_TOP)
    _place_caption(adapter, STATION_END_LABEL, FACE_END_LABEL_TOP)
    _place_caption(adapter, STATION_END_LABEL, BACK_END_LABEL_TOP)
    rebuild_drawing(adapter, label="slot callout clearance")
    slot_depth_witnesses = _place_slot_depth_callout(
        adapter,
        slot_section,
        detail_annotations,
        slot_section_annotations,
        back_annotations,
    )
    _assert_slot_callout_clear(
        adapter, detail_annotations, slot_section, back_annotations
    )
    _assert_slot_marker_clear(
        adapter, slot_section, slot_section_line, back_annotations
    )

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
        settled_checks=(
            lambda: _assert_front_caption_clear(
                adapter, front_caption, back_annotations, detail_annotations
            ),
            lambda: _assert_slot_marker_clear(
                adapter, slot_section, slot_section_line, back_annotations
            ),
            lambda: _assert_slot_callout_clear(
                adapter, detail_annotations, slot_section, back_annotations
            ),
            lambda: _assert_slot_depth_callout_clear(
                adapter,
                slot_section,
                detail_annotations,
                slot_section_annotations,
                back_annotations,
                slot_depth_witnesses,
            ),
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
