r"""Create the curated machinist drawing for the platen support bar (MHA-PD-007).

A 452 x 28 x 9 steel bar clamped across the frame columns. Its BACK face
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
  counterbores' native callout (depth at .XX) naming the back-arc taps the
  row locates to, and the front face's slide roughness. Each
  roughness symbol has its reason beside it; the sheet has no general note.
* Detail C looks face-on at the outer slot: the slot's and its
  counterbore's widths and travels, the slot's width naming the MHA-SH-002
  taps it takes up and the counterbore's the MHA-VN-021 head it holds.
  Section B-B cuts the inner slot across the bar for the counterbore's depth.
* Each face view carries its caption; section A-A cuts the pivot tap across
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
# audit: outside-border). Naming the MHA-SH-002 taps makes it four lines of
# at most 11 characters: about 18-47 mm by 97-117 mm, under its lower
# extension line (122 mm) and left of detail C's letter (51 mm).
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
# face-on at the outer slot at 2:1, between section B-B and the title block:
# the counterbore's width left of it, its text over the counterbore's upper
# edge on a shouldered leader (inside its 17 mm span the three-line block
# met its own extension line and arrow, r6 machinist review), the slot's
# right, its text under the slot's lower edge the same way (inside its 4.98
# span the block was struck by its own dimension line, r4), the slot's
# travel below and the counterbore's above; its label right of the slot's
# width. It is a cropped
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
DETAIL_FOCUS = (DETAIL_SLOT_X, 0.0, -BAR_DEPTH / 2.0)  # model mm
DETAIL_CENTER = (0.106, 0.048)
DETAIL_SCALE = (2, 1)
DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0  # sheet metres per mm
DETAIL_RADIUS_MM = 7.5
DETAIL_LABEL = f"DETAIL C\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
DETAIL_LABEL_XY = (0.195, 0.040)  # top centre
DETAIL_LETTER = "C"
DETAIL_LETTER_TOP = (LEFT_END - 0.004, BACK_CENTER[1] - 0.0025)  # top centre
DETAIL_POSITION_TOL_M = 1e-4
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
# Measured on the r4, r6 and r7 sheets (2.55-2.65 mm a character, 5.5 mm a
# line): a kept text outside its extension lines hangs beside its dimension
# line, on the side away from the feature, its block centred on the keep's
# height (ClampRowHeight, and the r6 slot width: keep 31.0, block 21.9-41.1);
# inside them it centres on the keep. The counterbore's block (27.4 mm by
# 14.7, its shoulder 28.5 long; r7, line at x 78: 49.7-77.1) hangs left of
# its line at x 89, 3 mm right of section B-B's back face so the section can
# rise beside it, and 1.9 mm under the 440.50 extension line's end; the
# slot's (46 mm by 24.7) right of its line at x 132, 1 mm under the slot's
# lower edge.
DETAIL_KEEP = {
    "ClampSlotCboreWidth": (DETAIL_CENTER[0] - 0.017, DETAIL_CENTER[1] + 0.020),
    "ClampSlotWidth": (DETAIL_CENTER[0] + 0.026, DETAIL_CENTER[1] - 0.019),
    "ClampSlotTravel": (DETAIL_CENTER[0] + 0.015, DETAIL_CENTER[1] - 0.020),
    "ClampSlotCboreTravel": (DETAIL_CENTER[0] + 0.015, DETAIL_CENTER[1] + 0.021),
}
# Section B-B cuts the inner slot across the bar, at 1:1 in the sheet's
# lower-left corner: the counterbore's depth with its text and callout
# outside the front face the counterbore enters, the caption under it. The
# depth's line runs at the bar's mid-height, through the counterbore's mouth
# and the through slot, so neither extension line crosses the cut: over the
# top face (r6) the floor's extension line ran up through the hatch and read
# as a seam (its 0.13 stroke from the floor's lower corner, PDF paths). The
# text's centre stands SLOT_DEPTH_SHELF_DROP over the line, the drop the r6
# sheet measured from a kept four-line depth text to its shelf (72.00 to
# 60.85), and far enough off the face for the block to clear it and the
# border. The caption's top centre stands SLOT_CAPTION_DROP under the
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

# Section A-A: the thickness up-left of the cut bar, its text outside the
# extension lines since the 2:1 span is narrower than it. The caption drops
# under the section.
SECTION_KEEP_NAMES = ("Depth",)
SECTION_DEPTH_RISE = 0.010
SECTION_DEPTH_SIDE = 0.028
CAPTION_DROP = 0.035
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
            (max(CLAMP_ROUND_X), 0.0, -BAR_DEPTH / 2.0),
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
    draw_vn_post_mount_screw measured, while the same part's projected views
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
    """Section B-B's depth text from its own projection, whichever way the cut
    looks: outside the front face the counterbore enters, its line at the
    bar's mid-height."""

    def point(z: float, y: float = 0.0) -> tuple[float, float]:
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
