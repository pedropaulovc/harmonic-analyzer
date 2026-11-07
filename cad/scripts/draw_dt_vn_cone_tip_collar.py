"""Manufacturing drawing of the custom collar; its set screw is stock.

Native model dimensions own every made size, its places and its band.
The radial through tap is a native Hole Wizard callout, seen in VIEW A
(lettered with its viewing arrow on the turning view); the bore's REAM
callout sits in DETAIL B, a native 40:1 detail of the end view. Sheet 2
shows the stock set screw, a member of MHA-DT-VN-54, for reference.

The sheet's words are this recipe's (fan-out screen 20261107T081227004Z):
the part's saved view-note, title and stock-sheet properties are not read, so
their spec constants stay unchanged and the part, MHA-DT-04 and MHA-DT-00
keep their keys.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import dt_vn_cone_tip_collar_spec as spec
from _check import check
from _com import _early_bound, _read_member
from _drawing_attachment import _is_same_attachment
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs, finalize_drawing, new_project_drawing,
    read_required_properties, rebuild_drawing, stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, move_model_dimension, set_dimension_callouts
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _layout_geometry import format_findings
from _supplier_dimensions import assert_supplier_reference_dimension, supplier_reference_dimension
from diagnostics.drawing_layout_audit import audit_document
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_name, place_view, view_name

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_vn_cone_tip_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
SHEET_SCALE = (4, 1)
# Sheet 1 makes the collar; sheet 2 shows its stock set screw for reference.
SHEET_NAMES = ("COLLAR", f"{spec.SET_SCREW_SKU}-STOCK")
STOCK_SCALE = (12, 1)
SHEET_SCALES = {SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: STOCK_SCALE}
# Third angle: the socket end is the side view's right end, so its end view
# (*Right) stands right of the side view on its axis (screen r1-r3 blocker:
# left of it, it claimed the flat point's end). The diameter reads left of the
# side view, clear of the end view; the socket's across-flats text stands right
# of its extension lines and the end view's centre mark (rule 14: three lines
# struck it under the view).
STOCK_SIDE_CENTER = (0.180, 0.155)
STOCK_END_CENTER = (0.300, 0.155)
STOCK_ISO_CENTER = (0.345, 0.222)
STOCK_SIDE_KEEP = {
    "ScrewLength": (STOCK_SIDE_CENTER[0], STOCK_SIDE_CENTER[1] + 0.035),
    "ScrewMajorDia": (STOCK_SIDE_CENTER[0] - 0.070, STOCK_SIDE_CENTER[1]),
}
STOCK_END_KEEP = {"SocketAF": (STOCK_END_CENTER[0] + 0.032, STOCK_END_CENTER[1] - 0.030)}
# Rule 4: the stock screw is a member of MHA-DT-VN-54 (the collar with its set
# screw), named as a kit member with its catalogue code after the number.
STOCK_TITLE = "\n".join((
    "SET SCREW OF MHA-DT-VN-54: #2-56 X 5/16 FLAT POINT, McMASTER 94355A213.",
    "AS SUPPLIED; VIEWS ARE REFERENCE ONLY.",
))
END_CENTER = (0.080, 0.170)
SIDE_CENTER = (0.205, 0.170)
# The radial tap view stands over the end view, left of the turning view.
# Over the turning view, at (205, 240) mm, its gauge dimensions crossed the
# top border by 3.2 and 8.8 mm, its note sat on NoseLength's lines, and the
# root gauge and position leaders ran through the hole callout (run 14 at
# 7fda4144f). Offsets below are from TAP_CENTER. The view spans +/-11.5 x
# +/-16.76 mm at 2:1. Run 14 put the tap mouth at (+3.3, +1.8) mm, the callout
# text at [-39, -1] x [-5.6, -2.1] mm from its callout point, and the view
# note's 62 x 4.3 mm box with its left/top corner at the note point.
TAP_CENTER = (0.065, 0.238)
TAP_SCALE = spec.RADIAL_TAP_VIEW_SCALE
ISO_CENTER = (0.345, 0.210)
# Third angle: the turning view (*Front) and this end view (*Bottom, looking
# up the axis at the nose end) both take a quarter turn clockwise
# (_quarter_turn), so model +X, the flat's side, faces sheet DOWN in both and
# the end view projects on the left of the turning view, which shows the nose
# end on its left (r4 review: unturned, the end view put the flat on its
# right, facing the turning view's reader, while the turning view drew it at
# the bottom). FlatDistance is then vertical, axis (y 170 mm) to flat (y 142):
# its text right of the view (x <= 115), between the views. NoseDia is
# imported here only as the donor that moves onto the turning view.
END_KEEP = {"NoseDia": (0.027, 0.165), "FlatDistance": (0.125, 0.156)}
# Rule 11 (r4 review): the nose diameter across the nose on the turning view,
# its dimension line left of the nose's south face (x 182, y 157-183), clear
# of FlatDistance's text and below NoseLength's. Its text prints ~5.5 mm right
# of the keep: at x 0.165 it reached x 183.3 across NoseLength's south
# extension line at x 182 (farm run 20261101T005319353Z).
NOSE_DIA_ON_SIDE = (0.160, SIDE_CENTER[1])
# CollarDia is a turned-profile sketch dimension, native to the side view.
# Farm 20261031T205208603Z: the nose spans x 182-196 mm and the body x 196-228,
# y 135-205; NoseLength's south extension line runs x 182, y 169-213.
# ShoulderRadius reads up-right, above the body and left of CollarDia's
# dimension line (x 250): its leader leaves the fillet (194, 183) through the
# body top at x ~221, left of CollarDia's top extension line (x >= 228), and
# passes NoseLength's text at x ~230. At (165, 198) it crossed NoseLength's
# extension line; at (282, 205), CollarDia's dimension line (main's review).
# The .XXX nose length, width and tap station hold the tap's walls to the
# shoulder and the end face (spec.WORST_WALLS_MM; at .XX they fall below the
# wall target). Rules 3, 4 and 7: they name that function once, as one
# numbered note each of them flags; a location carries no other words. The
# flags: CollarWidth's below its value, into the open field under the view;
# NoseLength's ABOVE its value, out of its extension lines' reach (at x 182
# its old 53.5 mm function line stood 5.7 mm from the tap callout).
SIDE_KEEP = {"CollarWidth": (0.205, 0.110), "CollarDia": (0.250, SIDE_CENTER[1]),
             "NoseLength": (0.189, 0.218), "ShoulderRadius": (0.262, 0.232)}
WALL_FLAG = "SEE NOTE 1"
WALL_FLAGGED = ("NoseLength", "CollarWidth", "TapStation")
# The least of the two tap walls the flagged sizes hold, floored to .001 in
# (test_wall_note_states_the_least_booked_tap_wall pins it to the spec).
WALL_NOTE = "1. 2-56 TAP: WALL .081 MIN TO SHOULDER AND TO END FACE."
# One note block: note 1, then the stock line (spec.DRAWING_NOTES).
NOTES_TEXT = f"{WALL_NOTE}\n2. {spec.DRAWING_NOTES}"
# TapStation reads right of the tap centre's extension line, under the hole
# callout's leader and above the end view's top (y 205 mm at x 80 mm), so its
# flag clears both extension lines and the left border.  The two-line
# thread-major gauge reads right of the view, above the hole callout: left of
# the view (main's place) its leader crossed TapStation's extension line off
# the nose face (run 20261101T183557651Z).  It bounds the envelope the wall
# budget books (spec.THREAD_ENVELOPE_DIA), named in standard words (rule 26:
# TAP ROOT was a private phrase).
TAP_KEEP = {
    "TapStation": (TAP_CENTER[0] + 0.040, TAP_CENTER[1] - 0.024),
    "TapRootLimit": (TAP_CENTER[0] + 0.033, TAP_CENTER[1] + 0.012),
}
TAP_ROOT_CALLOUT = "THREAD MAJOR DIA"
# Right of the view: the hole callout's text starting past the view's right
# edge. The view note goes over the view, 3.7 mm inside the top border.
TAP_CALLOUT_XY = (TAP_CENTER[0] + 0.0553, TAP_CENTER[1] - 0.0062)
# The tap drill's size prints three inch places, as every Hole Wizard callout
# on an inch sheet does (#290, draw_dt_cone_tip_block). It is written at
# render time, the declared exception RV-01 in
# cad/config/parts/dt-vn-cone-tip-collar.yaml (delegated ruling 2026-11-02,
# owner review #2144): a part-authored precision does not reach the callout.
TAP_CALLOUT_PRECISION = {"hw-thrutapdrldia": 3}
TAP_NOTE_XY = (TAP_CENTER[0] - 0.030, TAP_CENTER[1] + 0.025)
# Rule 9: the radial tap view is VIEW A, its viewing arrow on the turning
# view's mounting flat at the tap station, looking up at the flat. One caption
# line: a second would reach the view's top under the border.
VIEW_A_LETTER = "A"
VIEW_A_CAPTION = (
    f"VIEW {VIEW_A_LETTER}  SCALE {spec.RADIAL_TAP_VIEW_SCALE[0]}:{spec.RADIAL_TAP_VIEW_SCALE[1]}"
)
# The letter hangs this far under the flat, its leader's arrow on the flat;
# it stands between CollarWidth's extension lines, over its text (y ~116 mm).
VIEW_ARROW_RUN = 0.010
VIEW_LETTER_HALF_WIDTH = 0.0015
# Rule 9: the enlarged bore is DETAIL B, a native 40:1 detail whose circle
# rides the end view's bore: the bore's largest limit plus a 3 mm sheet margin
# at 40:1, the frame the old cropped view had. Lower left, under the end view,
# between the isometric and the title block (main's review: there its REAM
# callout pressed against the isometric's label). BoreDia's four-line block
# (value, REAM THRU, the fit and its REF clearance) reads right of the circle,
# above the title block (y 64 mm) and below CollarWidth's block; the native
# label hangs 5 mm under the circle.
BORE_DETAIL_LETTER = "B"
BORE_FENCE_RADIUS_MM = spec.BORE_FINISHED_DIA_LIMITS_MM[1] / 2.0 + 0.075
BORE_CENTER = (0.050, 0.074)
BORE_KEEP = {"BoreDia": (0.150, 0.083)}
# Rule 4: the standard fit name with its mate's number, the clearance as REF
# (test_bore_callout_states_the_journal_fit pins both to the spec's limits).
BORE_CALLOUT = "\n".join((
    "REAM THRU",
    "SLIDING FIT ON MHA-DT-04 TERMINAL JOURNAL",
    "(CLEARANCE .0010-.0038)",
))
# The circle's letter on the end view: up-right of the bore, off the centre
# mark's lines and inside the nose circle.
BORE_LETTER_OFFSET = (0.0045, 0.0045)
# The two-line note block, under the detail's label.
NOTES_XY = (0.016, 0.030)
# swAnnotationType_e
_NOTE = 6
# swAnnotationOwnerType: sheet-owned, not the sheet format's template ink
# (diagnostics.drawing_layout_audit._OWNER_DRAWING_SHEET).
_OWNER_DRAWING_SHEET = 1


def _note_name(annotation: Any) -> str:
    """A note's drawing-unique annotation name (``DetailItemNNN``)."""
    name = str(_early_bound(annotation, "IAnnotation").GetName() or "")
    if not name:
        raise RuntimeError("collar note has no annotation name")
    return name


def _placed_note(adapter, property_name, x, y) -> str:
    """Place one property-linked note and return its annotation name."""
    note = _early_bound(add_property_linked_note(adapter, property_name, x, y), "INote")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"collar note {property_name!r} has no annotation")
    return _note_name(annotation)


def _literal_note(adapter, text, x, y) -> str:
    """Place one note with this recipe's text and return its annotation name."""
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to add collar note {text!r}")
    annotation = _early_bound(note, "INote").GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"collar note {text!r} has no annotation")
    return _note_name(annotation)


def _sheet_context(adapter) -> None:
    """Leave every view so the next free note belongs to the sheet."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if drawing.ActiveDrawingView is not None:
        raise RuntimeError("collar notes: cannot leave view context for the sheet")


def _sheet_views(adapter, sheet_name):
    """Walk the selected sheet explicitly; native GetViews order is undefined."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(sheet_name):
        raise RuntimeError(f"cannot activate collar package sheet {sheet_name}")
    views = []
    view = drawing.GetFirstView()
    while view is not None:
        view = _early_bound(view, "IView")
        views.append(view)
        view = view.GetNextView()
    if not views:
        raise RuntimeError(f"collar package sheet {sheet_name} has no sheet view")
    return views


def _sheet_notes(adapter, sheet_name=SHEET_NAMES[0]) -> dict[str, tuple[str, Any]]:
    """Notes on this sheet only, excluding its format's template ink."""
    sheet_view, *views = _sheet_views(adapter, sheet_name)
    notes = {}
    for owner, view in (("sheet", sheet_view), *((view_name(adapter, v), v) for v in views)):
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) != _NOTE:
                continue
            if view is sheet_view and int(annotation.OwnerType) != _OWNER_DRAWING_SHEET:
                continue
            name = _note_name(annotation)
            if name in notes:
                raise RuntimeError(f"collar note {name} listed twice")
            notes[name] = (owner, annotation)
    return notes


def _note_text(annotation: Any) -> str:
    return str(_early_bound(annotation.GetSpecificAnnotation(), "INote").GetText() or "")


def _delete_unplaced_notes(adapter, placed: frozenset[str], *, sheet_name=SHEET_NAMES[0]) -> None:
    """Delete every note this recipe did not place, then read none back.

    The first single-sheet render (8087fd13c) counted 16 annotations for the
    15 this recipe places. The extra, note DetailItem348, boxed
    [211.6,140.7]..[268.3,154.0] mm with its leader, sat across CollarWidth's
    extension line and CollarDia's dimension line. Selected by not being one
    of ours, not by its text, so no placed note can be taken with it.
    """
    draw = adapter.currentModel
    notes = _sheet_notes(adapter, sheet_name)
    if not placed <= notes.keys():
        raise RuntimeError(f"collar sheet lists {sorted(notes)}, not every placed note {sorted(placed)}")
    stray = {name: found for name, found in notes.items() if name not in placed}
    for name, (owner, annotation) in stray.items():
        _telemetry.info(f"collar: deleting unplaced note {name} on {owner}: {_note_text(annotation)!r}")
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError(f"cannot select unplaced collar note {name}")
        draw.EditDelete()
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="collar unplaced notes")
    left = sorted(set(_sheet_notes(adapter, sheet_name)) - placed)
    if left:
        raise RuntimeError(f"collar unplaced notes survived deletion: {left}")


def _assert_settled_annotations(adapter, placed: frozenset[str], callout: str) -> None:
    """After the last rebuild: exactly the placed notes, and the tap's one
    native hole callout still stating the through thread. Reads only."""
    notes = _sheet_notes(adapter)
    if set(notes) != placed:
        raise RuntimeError(
            f"collar notes after the last rebuild: {sorted(notes)}; placed {sorted(placed)}"
        )
    found = []
    for view in _sheet_views(adapter, SHEET_NAMES[0])[1:]:
        for raw in view.GetDisplayDimensions() or ():
            display = _early_bound(raw, "IDisplayDimension")
            if not display.IsHoleCallout():
                continue
            data = _early_bound(display.GetDisplayData(), "IDisplayData")
            text = " ".join(
                str(data.GetTextAtIndex(index) or "") for index in range(int(data.GetTextCount()))
            )
            name = str(_early_bound(display.GetAnnotation(), "IAnnotation").GetName() or "")
            found.append((view_name(adapter, view), name, text))
    # The callout prints the size without ANSI's '#': "2-56 UNC - 2B".
    thread = spec.SET_SCREW_THREAD.lstrip("#")
    if (
        len(found) != 1 or found[0][1] != callout
        or thread not in found[0][2] or "THRU" not in found[0][2]
    ):
        raise RuntimeError(f"collar tap callout {callout} ({thread} THRU) not settled: {found}")


def bore_detail_radius_m() -> float:
    """Sheet radius of detail B's circle at 40:1."""
    return BORE_FENCE_RADIUS_MM * spec.BORE_VIEW_SCALE[0] / (1000.0 * spec.BORE_VIEW_SCALE[1])


def _configuration(adapter, views, name):
    for view in views:
        native = _early_bound(view, "IView")
        native.ReferencedConfiguration = name
        if str(native.ReferencedConfiguration) != name:
            raise RuntimeError(f"view failed to reference {name}")
    rebuild_drawing(adapter, label=f"collar {name} views")


def _quarter_turn(adapter, view, label):
    """Turn ``view`` a quarter clockwise, so model +X faces sheet down."""
    native = _early_bound(view, "IView")
    native.Angle = -math.pi / 2.0
    if abs(float(native.Angle) + math.pi / 2.0) > 1e-9:
        raise RuntimeError(f"collar {label} did not keep its quarter turn")
    rebuild_drawing(adapter, label=f"collar {label} orientation")


def _nose_dia_onto_side(adapter, end_marks, end, side):
    """Move the end view's one NoseDia onto the turning view (rule 11: the
    nose Ø reads where its length does). Returns the end view's remaining
    marks and the moved Ø."""
    donors = [a for a in end_marks if dimension_name(adapter, a) == "NoseDia"]
    if len(donors) != 1:
        raise RuntimeError("expected one collar nose diameter donor dimension")
    moved = move_model_dimension(adapter, donors[0], side, NOSE_DIA_ON_SIDE, source_view=end)
    return [a for a in end_marks if a is not donors[0]], moved


def _side_callouts():
    """The turning view's note-1 flags: (below their values, above them).
    NoseLength's reads above: below it, 3.500's two extension lines ran up
    through its words (r4 review)."""
    below = _wall_flags(SIDE_KEEP)
    return below, {"NoseLength": below.pop("NoseLength")}


def _precision(keep):
    """The part-authored places of only the names this view keeps
    (main's per-view form, draw_ch_connecting_rod)."""
    return {name: spec.DRAWING_PRECISION_BY_NAME[name] for name in keep}


# Native tolerance types the part authors: MAX 6.
TAP_DIMENSION_TYPES = {"TapRootLimit": 6}
SIDE_DIMENSION_TYPES = {"ShoulderRadius": 6}


def _wall_flags(keep):
    """Note 1's flags on the .XXX sizes, for only the names this view keeps."""
    return {name: WALL_FLAG for name in WALL_FLAGGED if name in keep}


def _assert_functional_dimension_types(adapter, annotations, expected):
    observed = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in expected:
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            observed[name] = int(tolerance.Type)
    if observed != expected:
        raise RuntimeError(f"collar MAX dimensions lost native types: {observed}")


def _centre_view(adapter, view, model_mm, sheet_xy, *, label):
    """Move ``view`` so the model point ``model_mm`` lands on ``sheet_xy``."""
    view = _early_bound(view, "IView")
    model = tuple(value / 1000.0 for value in model_mm)
    at = model_point_in_view(adapter, view, model, label=label)
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(double_array([
        position[i] + sheet_xy[i] - at[i] for i in range(2)
    ]), False):
        raise RuntimeError(f"cannot centre {label}")
    rebuild_drawing(adapter, label=f"{label} position")
    at = model_point_in_view(adapter, view, model, label=f"{label} readback")
    if math.dist(at, sheet_xy) > 1e-4:
        raise RuntimeError(f"{label} did not remain centred")


@_telemetry.traced("cone_tip_collar.bore_detail")
def _bore_detail(adapter, end):
    """Native 40:1 DETAIL B of the end view's bore (rule 9: its circle and
    letter on the parent; draw_dt_crank_handle_pivot_screw's detail A): fence,
    scale, outline, label and letter each read back. Returns the detail and
    its native label's annotation name."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(end, "IView")
    if not drawing.ActivateView(view_name(adapter, end)):
        raise RuntimeError("failed to activate detail B's parent end view")
    draw.ClearSelection2(True)
    # The bore axis is the model's Y axis through the origin.
    axis = model_point_in_view(adapter, end, (0.0, 0.0, 0.0), label="detail B fence centre")
    radius = BORE_FENCE_RADIUS_MM * SHEET_SCALE[0] / (1000.0 * SHEET_SCALE[1])
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (axis[:2], (axis[0] + radius, axis[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    # Straight to the database: an inferred circle snaps onto nearby edges
    # (draw_dt_pinion_lever r2), and this one sits just outside the bore.
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if fence is None:
        raise RuntimeError("failed to create detail B's fence")
    arc = _early_bound(fence, "ISketchArc")
    placed = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    placed_centre = [float(adapter._get_attr_or_call(placed, coordinate)) for coordinate in "XY"]
    if math.dist(placed_centre, points[0][:2]) > 1e-9 or not math.isclose(
        float(arc.GetRadius()), math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError("detail B's fence moved from where it was placed")
    draw.ClearSelection2(True)
    if not _early_bound(fence, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select detail B's fence")
    detail = drawing.CreateDetailViewAt4(
        *BORE_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *spec.BORE_VIEW_SCALE,
        BORE_DETAIL_LETTER,
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("CreateDetailViewAt4 returned no detail B")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in spec.BORE_VIEW_SCALE])
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="collar detail B")
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], spec.BORE_VIEW_SCALE[0] / spec.BORE_VIEW_SCALE[1]
    ):
        raise RuntimeError(f"detail B scale {ratio!r}, expected {spec.BORE_VIEW_SCALE!r}")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("detail B has invalid bounds")
    span = 2.0 * bore_detail_radius_m()
    if min(outline[2] - outline[0], outline[3] - outline[1]) < 0.95 * span:
        raise RuntimeError(f"detail B is smaller than its fence: {outline}")
    target = [
        position[axis_index] + BORE_CENTER[axis_index]
        - (outline[axis_index] + outline[axis_index + 2]) / 2.0
        for axis_index in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position detail B")
    rebuild_drawing(adapter, label="collar detail B position")
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail B label, found {len(notes)}")
    label = _early_bound(_read_member(_early_bound(notes[0], "INote"), "GetAnnotation"), "IAnnotation")
    label_xyz = (BORE_CENTER[0], BORE_CENTER[1] - bore_detail_radius_m() - 0.005, 0.0)
    if not label.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position detail B's label")
    rebuild_drawing(adapter, label="collar detail B label")
    actual = tuple(float(value) for value in _read_member(label, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"detail B's label position did not persist: {actual}")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one detail circle on the end view, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    letter_xy = (axis[0] + BORE_LETTER_OFFSET[0], axis[1] + BORE_LETTER_OFFSET[1])
    circle.SetLabelPosition(*letter_xy)
    rebuild_drawing(adapter, label="collar detail B letter")
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, letter_xy) > 1e-8:
        raise RuntimeError(f"detail B's letter did not persist: {letter}")
    set_hidden_lines_removed(adapter, detail)
    marks = curate_view_dimensions(
        adapter, detail, keep=BORE_KEEP, view_label="collar bore detail B",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, marks, _precision(BORE_KEEP))
    set_dimension_callouts(adapter, marks, {"BoreDia": BORE_CALLOUT})
    return detail, _note_name(label)


def _view_a_arrow(adapter, side) -> str:
    """VIEW A's letter and arrow: a leader note owned by the turning view, its
    arrow on the mounting flat at the tap station (the tap view looks up at
    the flat). Returns its annotation name."""
    tip = model_point_in_view(
        adapter, side, (spec.FLAT_DISTANCE / 1000.0, spec.TAP_STATION / 1000.0, 0.0),
        label="VIEW A arrow tip on the mounting flat",
    )
    note = add_leader_note(
        adapter, VIEW_A_LETTER,
        text_xy=(tip[0] - VIEW_LETTER_HALF_WIDTH, tip[1] - VIEW_ARROW_RUN),
        attach_xy=tuple(tip[:2]), view=side, label=f"view {VIEW_A_LETTER} viewing arrow",
    )
    annotation = _early_bound(note, "INote").GetAnnotation()
    if annotation is None:
        raise RuntimeError("VIEW A's arrow note has no annotation")
    return _note_name(annotation)


def _supplier_dimension(adapter, annotation):
    name = dimension_name(adapter, annotation)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    return supplier_reference_dimension(
        adapter, display, label=f"McMaster {spec.SET_SCREW_SKU} {name}",
        units=spec.SET_SCREW_SUPPLIER_UNITS, precision=spec.SET_SCREW_SUPPLIER_PRECISION,
        expected_mm=spec.SET_SCREW_SUPPLIER_SIZES_MM[name],
        presentation="diameter" if name == "ScrewMajorDia" else "length",
        callout=spec.SET_SCREW_THREAD if name == "ScrewMajorDia" else (
            "HEX SOCKET AF" if name == "SocketAF" else None
        ),
    )


def _stock_reference_sheet(adapter):
    """The purchased screw's three published dimensions, never collar dimensions."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate stock set-screw reference sheet")
    side = place_view(adapter, str(SOURCE), "*Front", *STOCK_SIDE_CENTER, scale=STOCK_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *STOCK_END_CENTER, scale=STOCK_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *STOCK_ISO_CENTER, scale=STOCK_SCALE)
    _configuration(adapter, (side, end, iso), "SetScrew")
    middle = (spec.SET_SCREW_SEAT_RADIUS + spec.SET_SCREW_END_RADIUS) / 2.0
    for view, xyz, centre, label in (
        (side, (middle, spec.TAP_STATION, 0.0), STOCK_SIDE_CENTER, "stock screw side"),
        (end, (spec.SET_SCREW_END_RADIUS, spec.TAP_STATION, 0.0),
         STOCK_END_CENTER, "stock screw socket"),
        (iso, (middle, spec.TAP_STATION, 0.0), STOCK_ISO_CENTER, "stock screw isometric"),
    ):
        _centre_view(adapter, view, xyz, centre, label=label)
        set_hidden_lines_removed(adapter, view)
    side_marks = curate_view_dimensions(
        adapter, side, keep=STOCK_SIDE_KEEP, view_label="stock screw supplier side sizes",
        dimensions_by_feature=spec.SET_SCREW_SUPPLIER_DIMENSIONS,
    )
    end_marks = hidden_sketches.curate_view_dimensions(
        adapter, end, keep=STOCK_END_KEEP, view_label="stock screw supplier socket AF",
        dimensions_by_feature=spec.SET_SCREW_SUPPLIER_DIMENSIONS,
    )
    identities = {}
    for annotation in side_marks + end_marks:
        display = _supplier_dimension(adapter, annotation)
        name = dimension_name(adapter, annotation)
        if name in identities:
            raise RuntimeError(f"duplicate stock set-screw dimension {name}")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        identities[name] = (
            str(_early_bound(display.GetDimension2(0), "IDimension").FullName),
            view_name(adapter, annotation.Owner),
            tuple(annotation.GetAttachedEntities3() or ()),
            tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ())),
        )
    placed = frozenset({_literal_note(adapter, STOCK_TITLE, 0.016, 0.252)})
    _delete_unplaced_notes(adapter, placed, sheet_name=SHEET_NAMES[1])
    return placed, identities, frozenset(view_name(adapter, v) for v in (side, end, iso))


def _assert_stock_references(adapter, placed, identities, expected_views):
    """Re-enumerate native dimensions after final rebuild; never repair source state."""
    notes = _sheet_notes(adapter, SHEET_NAMES[1])
    if set(notes) != placed or any(
        _note_text(annotation).replace("\r", "") != STOCK_TITLE
        for _owner, annotation in notes.values()
    ):
        raise RuntimeError("stock set-screw reference title notes changed")
    if set(identities) != set(spec.SET_SCREW_SUPPLIER_SIZES_MM):
        raise RuntimeError("stock set-screw reference identities are incomplete")
    expected_owners = {
        name: feature
        for feature, names in spec.SET_SCREW_SUPPLIER_DIMENSIONS.items()
        for name in names
    }
    found = set()
    found_views = set()
    for view in _sheet_views(adapter, SHEET_NAMES[1])[1:]:
        owner = view_name(adapter, view)
        found_views.add(owner)
        if str(view.ReferencedConfiguration) != "SetScrew":
            raise RuntimeError("supplier view does not isolate the stock set screw")
        for raw in view.GetDisplayDimensions() or ():
            display = _early_bound(raw, "IDisplayDimension")
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            name = dimension_name(adapter, annotation)
            if name in found or name not in identities:
                raise RuntimeError(f"unexpected stock set-screw supplier dimension {name}")
            full_name, expected_view, entities, kinds = identities[name]
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            if (
                str(dimension.FullName) != full_name
                or full_name.split("@")[:2] != [name, expected_owners[name]]
                or owner != expected_view
                or view_name(adapter, annotation.Owner) != owner
            ):
                raise RuntimeError(f"{name}: stock reference model/view identity changed")
            assert_supplier_reference_dimension(
                adapter, display, label=f"stock set-screw {name}",
                units=spec.SET_SCREW_SUPPLIER_UNITS,
                precision=spec.SET_SCREW_SUPPLIER_PRECISION,
                expected_mm=spec.SET_SCREW_SUPPLIER_SIZES_MM[name],
                presentation="diameter" if name == "ScrewMajorDia" else "length",
                callout={"ScrewMajorDia": spec.SET_SCREW_THREAD, "SocketAF": "HEX SOCKET AF"}.get(name),
            )
            if int(_early_bound(dimension.Tolerance, "IDimensionTolerance").Type) != 0:
                raise RuntimeError(f"{name}: an unpublished set-screw supplier band was added")
            attached = tuple(annotation.GetAttachedEntities3() or ())
            actual_kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
            if len(attached) != len(entities) or actual_kinds != kinds or any(
                not _is_same_attachment(
                    adapter, actual, expected, "SILHOUETTE" if kind == 46 else "EDGE"
                )
                for actual, expected, kind in zip(attached, entities, kinds, strict=True)
            ):
                raise RuntimeError(f"{name}: stock reference attachment changed")
            found.add(name)
    if found != set(identities) or found_views != expected_views:
        raise RuntimeError(f"stock set-screw supplier coverage changed: {sorted(found)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part missing: {SOURCE}")
    check("open custom collar", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, (
        "Number", "Revision", "Title", "Material Specification", "Finish",
        "Quantity", "Isometric View Note",
    ), required=("Number", "Material Specification", "Isometric View Note"))
    drawing, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="collar and stock set screw")
    if not _early_bound(drawing, "IDrawingDoc").ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate collar manufacturing sheet")
    stamp_drawing_summary(adapter, drawing, {
        0: "Cone Tip Collar Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist drawing",
        2: "Harmonic Analyzer Project", 3: "Custom steel collar and stock set screw",
        4: "Project-owned ASME B drawing standard",
    })
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=SHEET_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=SHEET_SCALE)
    tap = place_view(adapter, str(SOURCE), "*Right", *TAP_CENTER, scale=TAP_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    _configuration(adapter, (end, side, tap, iso), "Collar")
    for view, label in ((end, "end view"), (side, "turning view"), (tap, "radial tap view")):
        _quarter_turn(adapter, view, label)
    for view in (end, side, tap, iso):
        set_hidden_lines_removed(adapter, view)
    # Detail B first: a native detail imports nothing after its parent's
    # import and deletions (draw_dt_crank_handle_pivot_screw), and the end
    # view's import then skips the bore size the detail already shows.
    _bore, bore_label = _bore_detail(adapter, end)
    end_marks = curate_view_dimensions(adapter, end, keep=END_KEEP,
                                      view_label="collar end", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    side_marks = curate_view_dimensions(adapter, side, keep=SIDE_KEEP,
                                       view_label="collar turning view", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    end_marks, nose_dia = _nose_dia_onto_side(adapter, end_marks, end, side)
    marks = [*end_marks, *side_marks, nose_dia]
    assert_imported_precision(adapter, marks, _precision(END_KEEP | SIDE_KEEP))
    _assert_functional_dimension_types(adapter, side_marks, SIDE_DIMENSION_TYPES)
    side_callouts, above = _side_callouts()
    set_dimension_callouts(adapter, side_marks, side_callouts)
    set_dimension_callouts(adapter, side_marks, above, location="above")
    # TapRootGauge is a blanked sketch: the hidden-owner importer shows it in
    # this view for the import (draw_ch_rocker_arm_tl_pivot_screw).
    tap_marks = hidden_sketches.curate_view_dimensions(
        adapter, tap, keep=TAP_KEEP, view_label="collar radial process controls",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, tap_marks, _precision(TAP_KEEP))
    _assert_functional_dimension_types(adapter, tap_marks, TAP_DIMENSION_TYPES)
    set_dimension_callouts(
        adapter, tap_marks, {**_wall_flags(TAP_KEEP), "TapRootLimit": TAP_ROOT_CALLOUT}
    )
    # Source geometry is asymmetric and the views are rotated: use the native
    # model-to-sheet transform rather than assuming the view's box centre is
    # the bore origin or that world +Y still projects vertically.
    def point(view, xyz_mm, label):
        return model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in xyz_mm), label=label,
        )

    tap_rim = point(
        tap, (spec.FLAT_DISTANCE, spec.TAP_STATION, spec.TAP_DRILL_DIA / 2.0),
        "collar tap outer mouth",
    )
    view_a_arrow = _view_a_arrow(adapter, side)
    _sheet_context(adapter)
    placed = frozenset({
        _literal_note(adapter, NOTES_TEXT, *NOTES_XY),
        _placed_note(adapter, "Isometric View Note", 0.310, 0.160),
        _literal_note(adapter, VIEW_A_CAPTION, *TAP_NOTE_XY),
        view_a_arrow,
        bore_label,
    })
    if len(placed) != 5:
        raise RuntimeError(
            f"collar notes do not have five distinct names: {sorted(placed)}"
        )
    # In the radial projection the tap mouth is a real circle on the flat.
    callout = add_native_hole_callout(
        adapter, tap,
        edge_xy=tap_rim,
        callout_xy=TAP_CALLOUT_XY, label="custom collar through set screw tap",
    )
    set_hole_callout_precision(
        callout, TAP_CALLOUT_PRECISION, label="custom collar through set screw tap",
    )
    callout_name = str(_early_bound(
        _early_bound(callout, "IDisplayDimension").GetAnnotation(), "IAnnotation",
    ).GetName() or "")
    if not callout_name:
        raise RuntimeError("collar tap callout has no annotation name")
    _delete_unplaced_notes(adapter, placed)
    stock_notes, stock_identities, stock_views = _stock_reference_sheet(adapter)
    findings = audit_document(adapter)
    if findings:
        raise RuntimeError("collar manufacturing layout:\n" + format_findings(findings))
    return await finalize_drawing(
        adapter, OUTPUTS,
        pdf_title="Cone Tip Collar Manufacturing and McMaster 94355A213 Stock Reference",
        scale=SHEET_SCALE, layout=SPEC.layout, expected_sheet_names=SHEET_NAMES,
        sheet_scales=SHEET_SCALES,
        settled_checks=(
            lambda: _assert_settled_annotations(adapter, placed, callout_name),
            lambda: _assert_stock_references(adapter, stock_notes, stock_identities, stock_views),
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
