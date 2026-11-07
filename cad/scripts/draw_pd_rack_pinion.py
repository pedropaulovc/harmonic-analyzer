r"""Create the curated manufacturing drawing for the rack-pinion reduction disc (MHA-PD-06).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). Drawn 1:1;
the 150 physical teeth use the finite 48DP stock #1/reference-135 master.
The face view (``*Front``, the rear face) prints the controlling native
17-tooth actual-flank span, supported blank and bore with its reamed limits.
The bore's fit and the native #0-80 tap callout's assembly transfer are
numbered notes their callouts link (``pd_rack_pinion_callouts``); the span
and the blank link the GEAR DATA block, which names the mesh once with its
backlash acceptance (no bolt-circle position). Section A-A, cut on the bore
axis where the edge view stood, prints the disc thickness (its size envelope
holds the faces parallel, so no frame prints); its 10:1 detail B carries the
bore's front-edge chamfer, which the face view cannot show.
Decimal-inch sheet (#290); the model keeps its millimetre nominals.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

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
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_sections import create_section_view
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _native_axis_datum import add_native_axis_datum
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _section_axis import position_section_caption
import _telemetry
from paper_drive_stock_drawing import add_toothspace_callout, require_source_control
from pd_rack_pinion_callouts import (
    BORE_CALLOUT,
    CHAMFER_CALLOUT,
    CHAMFER_SUFFIX,
    DRAWING_NOTES,
    FACE_WIDTH_CALLOUT,
    GEAR_DATA_NOTE,
    MESH_CALLOUT,
    SPAN_CALLOUT,
    TAP_CALLOUT_QUALIFIER,
)
from pd_rack_pinion_spec import (
    CUTTER_NUMBER,
    CUTTER_REFERENCE_TEETH,
    DIAMETRAL_PITCH,
    BORE_DIA,
    BORE_FRONT_CHAMFER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    PRESSURE_ANGLE_DEG,
    STOCK_PROFILE,
    TAP_CENTRES,
    TAP_DRILL_DIA,
    TEETH,
    TOOTH_SPACE_GAUGE_PIN_DIA_MM,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_rack_pinion"]
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

SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.220, 0.175)
# Section A-A stands where the edge view stood and reads like it: model +Y
# up, model -Z right, so the clamped front face (z = 0) is its right face.
SECTION_CENTER = (0.320, 0.175)
ISO_CENTER = (0.383, 0.210)  # 0.388 clipped the zone border right by 1.4 mm
# The bore is a static seat (clamped to the MHA-PD-17 flange): no finish
# symbol (machinist review, rule 6).
# The GEAR DATA block is the sheet's (pd_rack_pinion_callouts.GEAR_DATA_NOTE:
# the part's cutting rows, the mate and its backlash acceptance), top-left.
GEAR_DATA_XY = (0.018, 0.262)
GEAR_DATA_CHAR_HEIGHT = 0.0022
# The numbered notes the bore and tap callouts link stand in the clear
# lower-left lane: under the tap callout's shoulder, left of the title
# block (x 0.216), at the document's note font (about 2.6 mm a character,
# 69 characters: x 0.020-0.200).
NOTES_XY = (0.020, 0.080)
# Three rows use the clear upper-right lane, above all physical gear views.
# x 0.262, not 0.230: run 12's leader from 0.230 down to the gap-18 flank
# (237.7, 201.5 mm) ran 3.6 mm through the ToothSpan text [228-245, 226-230
# mm]; from 0.262 it passes that text 3 mm to its right.
TOOTH_SPACE_CALLOUT_XY = (0.262, 0.260)
TOOTH_SPACE_CALLOUT_CHAR_HEIGHT = 0.0035  # standard note font
TOOTH_SPACE_GAP_INDEX = 18  # actual upper-right flank under the control-note lane

HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
FRONT_FACE_X = SECTION_CENTER[0] + FACE_WIDTH * VIEW_SCALE[0] / 2000.0
_BORE_R = BORE_DIA / 2.0
# A-A's cutting line runs up the face view's vertical centre line through
# the bore axis (model x = 0), past the tooth tips each end, so the cut
# shows the bore's front corner in true shape.
SECTION_LINE_OVERRUN_MM = 4.0
SECTION_LINE_MODEL_M = tuple(
    (0.0, sign * (OUTSIDE_DIA / 2.0 + SECTION_LINE_OVERRUN_MM) / 1000.0, 0.0)
    for sign in (-1.0, 1.0)
)
# The native caption's top centre, under the thickness's text block (its
# ENGAGEMENT row bottoms near y 0.114), clear of the title block (x 0.216+
# from y 0.066 up only).
SECTION_CAPTION_XY = (SECTION_CENTER[0], 0.100)

# DETAIL B: at 1:1 the .010 chamfer is a quarter-millimetre of A-A, so a
# native 10:1 detail of the bore's upper front corner carries its leg
# (draw_dt_crank_handle's detail of a section).  The fence, in the cut plane
# x = 0 (model mm as (x, y, z)), takes in the chamfer's two ends (the leg's
# references: a detail imports only a dimension whose references it shows),
# the bore wall behind it and the front face above it.
DETAIL_LETTER = "B"
DETAIL_SCALE = (10, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
DETAIL_FOCUS_MM = (0.0, _BORE_R + 0.25, 0.75)
DETAIL_RADIUS_MM = 1.4
_FENCE_MARGIN_MM = 0.3
_CHAMFER_ENDS_MM = (
    (0.0, _BORE_R + BORE_FRONT_CHAMFER, 0.0),
    (0.0, _BORE_R, BORE_FRONT_CHAMFER),
)
if any(
    math.dist(DETAIL_FOCUS_MM, point) > DETAIL_RADIUS_MM - _FENCE_MARGIN_MM
    for point in _CHAMFER_ENDS_MM
):
    raise AssertionError("detail B's fence must take in both ends of the bore chamfer")
# Left of the face view, under GEAR DATA (its last row near y 0.234) and
# left of the bore's text (x >= 0.140): the circle spans x 0.036..0.064,
# y 0.164..0.192; the label hangs from its top centre under the circle.
DETAIL_CENTER = (0.050, 0.178)
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS
DETAIL_LABEL_XY = (DETAIL_CENTER[0], DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - 0.004)
# The fence on A-A sits on the bore's upper front corner (x ~0.321,
# y ~0.182); its letter stands up-left of it in the gap between the face
# view's rim (x <= 0.261) and A-A.
DETAIL_LETTER_XY = (0.304, 0.194)
# The leg's text stands right of the detail, beyond the front face, its
# value line CHAMFER_TEXT_DROP under the bore wall (the leg's dimension line
# runs in the bore's air, off the hatch) and its block's left end past the
# circle; the corner itself is projected once the detail stands.
CHAMFER_TEXT_OFFSET = 0.034
CHAMFER_TEXT_DROP = 0.006

# The bore's and the blank's diameters print near-side: one arrow on the rim
# nearest the text, no line through the centre (machinist review: their
# native rim-to-rim lines, and the root REF's, which no longer prints, met
# the bore's leader at the bore).  Each leader leaves its block's lower
# corner on the part's side (SolidWorks' shoulder), so each block is placed
# by that corner; each *_TEXT_BLOCK is the block's estimated (width, height).
BORE_TEXT_BLOCK = (0.032, 0.021)
OD_TEXT_BLOCK = (0.035, 0.0138)
# The bore's text stands left of the face view, its shoulder 15° above the
# horizontal through the centre: its leader crosses the rim to the bore's
# 165° point, clear of datum A below and the 120° tap above.
_BORE_SHOULDER = (
    FRONT_CENTER[0] - 0.048,
    FRONT_CENTER[1] + 0.048 * math.tan(math.radians(15.0)),
)
# The blank's text stands below the face view, right of the tap's leader,
# its shoulder on the -80° ray, far enough out that the block clears the
# rim: its leader rises to the rim's -80° point, clear of the tap's leader
# (left of it) and far from the span's upper-right extension lines.
_OD_SHOULDER = (
    FRONT_CENTER[0] + 0.065 * math.cos(math.radians(-80.0)),
    FRONT_CENTER[1] + 0.065 * math.sin(math.radians(-80.0)),
)
NEAR_SIDE_DIAMETERS = ("BoreDia", "OutsideDia")
FRONT_KEEP = {
    "BoreDia": (
        _BORE_SHOULDER[0] - BORE_TEXT_BLOCK[0] / 2.0,
        _BORE_SHOULDER[1] + BORE_TEXT_BLOCK[1] / 2.0,
    ),
    "OutsideDia": (
        _OD_SHOULDER[0] + OD_TEXT_BLOCK[0] / 2.0,
        _OD_SHOULDER[1] + OD_TEXT_BLOCK[1] / 2.0,
    ),
    # Above the cutting line's upper arrow (y ~0.220): the value rows and
    # the one-line route above them stand y ~0.229..0.243, under the
    # tooth-space control (y >= 0.250) and left of its leader.
    "ToothSpan": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.061),
}
# Below the cut disc, clear of the isometric to the right; the whole text
# block (value and its ~.046-wide callout) stands right of the front face's
# extension line, so neither extension line nor the dimension line strikes
# it (machinist review, r3: centred on the line, the callout straddled both
# extension lines).
SECTION_KEEP = {
    "FaceWidth": (FRONT_FACE_X + 0.028, SECTION_CENTER[1] - HALF_OD - 0.012),
}
DETAIL_KEEP_NAMES = ("BoreFrontChamferSize",)
# The bore's process and its note link stand under its size, on the bore
# dimension's own leader: a separate fit-note leader converged on the small
# bore with the size, datum, diameter and finish leaders (machinist review,
# stack6: clarity).  The tip and the span link the GEAR DATA block, which
# names their one mate (rule 4); the span's above its value, clear of the rim
# below.  The thickness names the screw engagement its .XXX band holds; the
# chamfer's leg reads "X 45°" and names the root it clears.
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "OutsideDia": MESH_CALLOUT,
}
DIMENSION_CALLOUTS_ABOVE = {"ToothSpan": SPAN_CALLOUT}
SECTION_DIMENSION_CALLOUTS = {"FaceWidth": FACE_WIDTH_CALLOUT}
DETAIL_DIMENSION_CALLOUTS = {"BoreFrontChamferSize": CHAMFER_CALLOUT}
DETAIL_DIMENSION_SUFFIXES = {"BoreFrontChamferSize": CHAMFER_SUFFIX}
# Lower-left of the face view, off the rim: the leader rises almost straight
# to the lower-left tap from the block's lower-right corner, left of the
# tap's centre, so it crosses neither the OD's line (lower right) nor datum
# A's leader (machinist review: from the block's right end past the tap, it
# crossed the OD's line).  The pick is on that tap's drill circle at 225°
# about its centre, off the centre-mark lines.  The face view is symmetric
# about its horizontal axis, so the sheet's lower-left tap is the model's
# x < 0 centre drawn under the axis whichever way the view mirrors.
# (19e33c6c2 let visible_circle_edge break the tie between the two x < 0
# taps on float noise: it took the upper one and the leader crossed the bore.)
# Four rows (the native drill and thread lines and TAP_CALLOUT_LINES): the
# block grows upward from the fixed shoulder, well under the tip circle; its
# widest line, the mouth breaks', sets its width.
TAP_TEXT_BLOCK = (0.100, 0.0215)
_TAP_SHOULDER = (FRONT_CENTER[0] - 0.015, FRONT_CENTER[1] - 0.085)
TAP_CALLOUT_XY = (
    _TAP_SHOULDER[0] - TAP_TEXT_BLOCK[0] / 2.0,
    _TAP_SHOULDER[1] + TAP_TEXT_BLOCK[1] / 2.0,
)
_TAP_X, _TAP_Y = min(TAP_CENTRES)  # either x < 0 centre: only |y| is drawn
TAP_SHEET_CENTER = (
    FRONT_CENTER[0] + _TAP_X * VIEW_SCALE[0] / 1000.0,
    FRONT_CENTER[1] - abs(_TAP_Y) * VIEW_SCALE[0] / 1000.0,
)
_TAP_SHEET_RADIUS = TAP_DRILL_DIA * VIEW_SCALE[0] / 2000.0
TAP_PICK = (
    TAP_SHEET_CENTER[0] + _TAP_SHEET_RADIUS * math.cos(math.radians(225.0)),
    TAP_SHEET_CENTER[1] + _TAP_SHEET_RADIUS * math.sin(math.radians(225.0)),
)


_THREAD_CLASS = re.compile(r"\s*-\s*<hw-threadclass>|<hw-threadclass>", re.IGNORECASE)


def tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the thread class the title block's thread row already states, and
    append the mouth-break and transfer lines, in the one thread compartment."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    updated = dict(definitions)
    part = thread_parts[0]
    thread = _THREAD_CLASS.sub("", updated[part]).rstrip()
    updated[part] = f"{thread}\n{TAP_CALLOUT_QUALIFIER}"
    return updated


def _set_near_side_diameters(adapter: Any, annotations: list[Any]) -> None:
    """One arrow on the near rim, no line through the centre, for each of
    NEAR_SIDE_DIAMETERS."""
    for name in NEAR_SIDE_DIAMETERS:
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"disc {name} near-side leader")
    rebuild_drawing(adapter, label="disc near-side diameter leaders")


def _set_tap_callout_text(display: Any) -> None:
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = tap_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNF" in text]
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(TAP_CALLOUT_QUALIFIER)
    ):
        raise RuntimeError(
            "rack-pinion tap callout lines did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _add_sheet_note(
    adapter: Any,
    text: str,
    xy: tuple[float, float],
    *,
    label: str,
    char_height: float | None = None,
) -> None:
    """Place one free note of the sheet's own text at ``xy`` (its top-left),
    at ``char_height`` when given, and read its text back."""
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    if char_height is not None:
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"the {label} note has no text format")
        text_format.CharHeight = float(char_height)
        if annotation.SetTextFormat(0, False, text_format) is not True:
            raise RuntimeError(f"failed to set the {label} note's text height")
    printed = str(note.GetText() or "").replace("\r\n", "\n")
    if printed != text:
        raise RuntimeError(f"the {label} note reads {printed!r}, not {text!r}")


def _section_axes(adapter: Any, native: Any) -> tuple[tuple[float, float], ...]:
    """Sheet vectors of model -Z and +Y (1 mm each) in section A-A."""
    origin, right, up = model_points_in_view(
        adapter,
        native,
        [(0.0, 0.0, 0.0), (0.0, 0.0, -0.001), (0.0, 0.001, 0.0)],
        label="section A-A axes",
    )
    return tuple((p[0] - origin[0], p[1] - origin[1]) for p in (right, up))


def _orient_section(adapter: Any, section: Any) -> None:
    """Model +Y up and model -Z right in section A-A, as in the *Right edge
    view it replaces (draw_fr_top_frame ``_orient_cut_section``): a cut that
    looks the other way mirrors the pair, so its direction is reversed first,
    then the view is turned."""
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    horizontal, vertical = _section_axes(adapter, native)
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="disc section A-A cut reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("disc section A-A cutting direction did not persist")
        horizontal, vertical = _section_axes(adapter, native)
    native.Angle = float(native.Angle) - math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="disc section A-A turned")
    horizontal, vertical = _section_axes(adapter, native)
    if (
        horizontal[0] <= 0.0
        or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0
        or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"disc section A-A axes did not persist: {horizontal=}, {vertical=}"
        )


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the disc's mid-thickness on its axis on SECTION_CENTER; a
    section's Position is its cut-plane origin, not its outline's centre
    (draw_pd_platen ``_centre_section``)."""
    native = _early_bound(section, "IView")
    anchor = (0.0, 0.0, FACE_WIDTH / 2000.0)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre disc section A-A")
        rebuild_drawing(adapter, label="disc section A-A re-centred")
    raise RuntimeError(f"disc section A-A centre stands at {projected}, not {SECTION_CENTER}")


def _bore_section(adapter: Any, front: Any) -> Any:
    """Full section A-A on the bore axis, in the edge view's place."""
    line = model_points_in_view(
        adapter, front, list(SECTION_LINE_MODEL_M), label="section A-A line"
    )
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="disc bore section",
    )
    _orient_section(adapter, section)
    set_hidden_lines_removed(adapter, section)
    _centre_section(adapter, section)
    position_section_caption(adapter, section, SECTION_CAPTION_XY, label="disc section A-A")
    return section


def _chamfer_detail(adapter: Any, section: Any) -> Any:
    """Native 10:1 detail B of the bore's upper front corner in section A-A
    (draw_dt_crank_handle ``_ferrule_seat_detail``): fence, scale, outline,
    label and letter each read back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(section, "IView")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate detail B's parent section")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        section,
        tuple(value / 1000.0 for value in DETAIL_FOCUS_MM),
        label="detail B fence centre",
    )
    parent_scale = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
    sheet_xy = [center[:2], (center[0] + DETAIL_RADIUS_MM * parent_scale, center[1])]
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_xy:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    # Straight to the database: an inferred circle snaps onto nearby section
    # edges (draw_dt_pinion_lever r2), so the fence is read back before use.
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError("failed to create detail B's fence")
    arc = _early_bound(fence, "ISketchArc")
    placed = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    placed_centre = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XY"]
    if math.dist(placed_centre, points[0][:2]) > 1e-9 or not math.isclose(
        float(arc.GetRadius()), math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError("detail B's fence moved from where it was placed")
    draw.ClearSelection2(True)
    if not _early_bound(fence, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select detail B's fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        DETAIL_LETTER,
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("CreateDetailViewAt4 returned no detail B")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1]
    ):
        raise RuntimeError(f"detail B scale {ratio!r}, expected {DETAIL_SCALE!r}")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("detail B has invalid bounds")
    span = 2.0 * DETAIL_CROP_RADIUS
    _telemetry.info(
        f"detail B outline {outline[2] - outline[0]:.5f} x "
        f"{outline[3] - outline[1]:.5f} m (fence {span:.5f})"
    )
    if min(outline[2] - outline[0], outline[3] - outline[1]) < 0.95 * span:
        raise RuntimeError(f"detail B is smaller than its fence: {outline}")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position detail B")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail B label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position detail B's label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"detail B's label position did not persist: {actual}")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail circle on section A-A, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"detail B's letter did not persist: {letter}")
    return detail


def _chamfer_keep(adapter: Any, detail: Any) -> dict[str, tuple[float, float]]:
    """Where the chamfer leg's text stands in detail B: CHAMFER_TEXT_OFFSET
    beyond the front face and CHAMFER_TEXT_DROP into the bore's air from the
    bore's front corner, each direction read off the detail itself."""
    radius_m = _BORE_R / 1000.0
    corner, beyond, inside = model_points_in_view(
        adapter,
        detail,
        [(0.0, radius_m, 0.0), (0.0, radius_m, -0.001), (0.0, radius_m - 0.001, 0.0)],
        label="detail B bore front corner",
    )
    return {
        "BoreFrontChamferSize": (
            corner[0] + math.copysign(CHAMFER_TEXT_OFFSET, beyond[0] - corner[0]),
            corner[1] + math.copysign(CHAMFER_TEXT_DROP, inside[1] - corner[1]),
        )
    }


_CHAMFER_DIMENSION = 10  # swDimensionType_e.swChamferDimension


def _set_dimension_suffixes(
    adapter: Any, annotations: list[Any], suffixes: dict[str, str]
) -> None:
    """Append each named dimension's suffix after its value, read back.  A
    leg the seat imports as a native chamfer dimension already prints its
    angle, so it takes none."""
    remaining = dict(suffixes)
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        suffix = remaining.pop(name, None)
        if suffix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if int(display.Type2) == _CHAMFER_DIMENSION:
            _telemetry.info(f"{name}: native chamfer dimension, angle printed natively")
            continue
        display.SetText(2, suffix)  # swDimensionTextSuffix
        if str(display.GetText(2) or "") != suffix:
            raise RuntimeError(f"{name} suffix did not persist")
    if remaining:
        raise RuntimeError(f"dimension suffixes not applied: {sorted(remaining)}")



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rack-pinion source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
    )
    require_source_control(
        properties[TOOTH_SPACE_CALLOUT_PROPERTY], TOOTH_SPACE_CALLOUT,
        label="rack-pinion tooth-space control",
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pd-rack-pinion"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rack-Pinion Disc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                f"reducer disc; brass; {TEETH} physical teeth; {DIAMETRAL_PITCH:g}DP "
                f"PA{PRESSURE_ANGLE_DEG:g}; stock #{CUTTER_NUMBER}/ref{CUTTER_REFERENCE_TEETH}"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    section = _bore_section(adapter, front)
    detail = _chamfer_detail(adapter, section)
    set_hidden_lines_removed(adapter, detail)

    # Detail B is dimensioned FIRST: a native detail imported nothing after
    # its parent's import and deletions (draw_dt_crank_handle).
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=_chamfer_keep(adapter, detail),
        view_label="bore chamfer detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter,
        [*front_annotations, *section_annotations, *detail_annotations],
        DRAWING_PRECISION_BY_NAME,
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(
        adapter, front_annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    set_dimension_callouts(adapter, section_annotations, SECTION_DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, detail_annotations, DETAIL_DIMENSION_CALLOUTS)
    _set_dimension_suffixes(adapter, detail_annotations, DETAIL_DIMENSION_SUFFIXES)
    _set_near_side_diameters(adapter, front_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to disc bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_native_axis_datum(
        adapter,
        front,
        entity=bore_edge,
        source_path=SOURCE,
        radius_m=BORE_DIA / 2000.0,
        datum="A",
        label="disc bore axis",
        shoulder=True,
        stability_tolerance_m=0.0001,
    )
    # The tooth-space control reads datum A above, the bore, at the shop row;
    # the assembled limit is MHA-PD-00's centring at the transfer step.
    add_toothspace_callout(
        adapter,
        front,
        profile=STOCK_PROFILE,
        actual_pin_diameter_mm=TOOTH_SPACE_GAUGE_PIN_DIA_MM,
        rotate_rad=math.pi / TEETH + TOOTH_SPACE_GAP_INDEX * 2.0 * math.pi / TEETH,
        axial_station_mm=FACE_WIDTH,
        property_name=TOOTH_SPACE_CALLOUT_PROPERTY,
        note_xy=TOOTH_SPACE_CALLOUT_XY,
    )

    # The native thread and drill ride the callout; the mouth breaks and the
    # link to the assembly-transfer note are the sheet's lines under it.
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=TAP_PICK,
        callout_xy=TAP_CALLOUT_XY,
        label="#0-80 transferred disc taps",
    )
    _set_tap_callout_text(tap_callout)
    set_hole_callout_precision(
        tap_callout, {"hw-thrutapdrldia": 3}, label="#0-80 transferred disc taps"
    )

    _add_sheet_note(
        adapter,
        GEAR_DATA_NOTE,
        GEAR_DATA_XY,
        label="gear data",
        char_height=GEAR_DATA_CHAR_HEIGHT,
    )
    _add_sheet_note(adapter, DRAWING_NOTES, NOTES_XY, label="numbered")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rack-Pinion Disc Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note to the face view once
        # the tap carries a hole callout; the callout already states it.
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
