r"""Create the curated machinist drawing for MHA-DT-35, the crank handle butt cup.

A plain steel cup (user rulings 2026-09-29 and 2026-09-30, ch11 p.14/p.15 and
ch30 eight-views-4).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A is the cup's length view (drawing-guidelines.md rule 9 (show internal shape in solid lines)) and takes every dimension, so
the pocket and the floor hole read on cut edges rather than hidden lines (the
MHA-DT-35 machinist review).  The body diameter and the pocket depth are the
bands; the pocket is bored to suit the MHA-DT-32 head (a reference size whose
callout states the fit), and the floor hole carries its drill callout.  Every
band names its mate at the callout (MHA-DT-35 machinist ENFORCE, r1).
The local radial MAX callout also names the MHA-DT-32 head and its floor
seating function; it does not change the model's corner or clearance.
DETAIL B, a 20:1 native detail of section A-A, carries the floor hole's
pocket-side mouth break, which takes the MHA-DT-32 under-head radius (#1757).
Owner ruling B on #1375 restores the pocket-wall floor in the model, so its
former shortfall note and property are not part of the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_butt_cup.py dt-crank-handle-butt-cup
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_layout_collect import check_drawing_layout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_butt_cup_notes import (
    BODY_CHAMFER_CALLOUT,
    FLOOR_HOLE_CALLOUT,
    FLOOR_HOLE_CHAMFER_CALLOUT,
    HANDLE_NUMBER,
    POCKET_FIT_CALLOUT,
    POCKET_FLAG,
    POCKET_NOTE,
    POCKET_NOTE_TEXT,
)
from dt_crank_handle_butt_cup_spec import (
    BODY_DIA,
    FLOOR_HOLE_DIA,
    OVERALL_LENGTH,
    POCKET_DEPTH,
    POCKET_FLOOR_CORNER_R_BAND,
    POCKET_FLOOR_CORNER_R_MAX,
    POCKET_FLOOR_CORNER_R_TOL_TYPE,
    REFERENCE_DIMENSIONS,
)
from dt_crank_handle_head_seat_spec import (
    CUP_DRAWING_DIMENSIONS as DRAWING_DIMENSIONS,
    CUP_DRAWING_PRECISION_BY_NAME as DRAWING_PRECISION_BY_NAME,
    FLOOR_HOLE_CHAMFER,
    FLOOR_HOLE_CHAMFER_LIMITS,
    LIMIT_TOL_TYPE,
)
from _fit_deviations import deviations
from dt_crank_handle_spec import COUNTERBORE_GLUE_LINE


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle_butt_cup"]
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

# Ø10.72 x 8.64 at 5:1 reads 54 x 43 on the sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
ISO_SCALE = (4, 1)
# Third angle: the end view left of the section looks at the chamfered
# floor face (*Left), not the counterbore mouth on the opposite end.
END_CENTER = (0.074, 0.165)
# 10 mm right of the r1 sheet: the body-fit callout needs the room between the
# floor-hole dimension and the section.
SECTION_CENTER = (0.225, 0.165)
ISO_CENTER = (0.368, 0.215)
# Below the floor end, clear of the floor-hole callout.
CAPTION_XY = (0.160, 0.114)
ISO_NOTE_POS = (0.335, 0.170)
# The pocket's numbered flag note: under the end view, left of the section's
# caption and above the title block.
POCKET_NOTE_POS = (0.030, 0.090)

_S = VIEW_SCALE[0] / 1000.0
BODY_R = BODY_DIA * _S / 2.0  # 0.0268
HALF_LENGTH = OVERALL_LENGTH * _S / 2.0  # 0.0216
# The section lays the part's +X to the right (the draw_crank_pinion
# convention), so the face is the right edge and the floor the left.
FACE_X = SECTION_CENTER[0] + HALF_LENGTH

# The pocket opens right; the smaller floor-hole dimension nests closest to
# the floor end, with the body diameter outboard.  Keep the overall below
# the section and the pocket-depth row: its upper witnesses otherwise strike
# the three-row functional radius callout.  The radius owns the open upper
# corridor, above the independent outer-chamfer block, with its native leader
# still pointing to the real quarter arc.  No model dimension or fit changes.
#
# Retained sheet-mm solve from the 22821a1d2 native r2 findings (2026-10-19):
# - PocketDepth's upper row [268.8,140.2]..[286.9,143.8] met PocketDia's
#   outside-arrow tail x284.2, y142.9..149.2.  Lower the whole depth block
#   3.5: its top is y140.3, 2.6 below the tail, including its far endpoint.
# - The 031202 native floor-hole keep (136.75,141) put DRILL THRU on a
#   shoulder at keep_y-5.583, with its main glyph top at keep_y+3.5267.
#   Keep the same below-witness/hung-text regime (keep_y <154.5), but nest
#   its column at x201.75, 3 left of the floor, instead of crossing BodyDia's
#   x166.75 column.  For 2 mm air above BodyDia's y144.5 lower witness and
#   3.57 mm below its r2 y160.4 text-break boundary, the keep-Y range is
#   152.083..153.3033; choose 152.5.  The shoulder is then y146.917 and the
#   main glyph top y156.0267, 4.3733 below BodyDia's lower row.  DRILL THRU's
#   full 24.0285 mm row hangs LEFT of keep X, so all text ends at x201.75,
#   3 mm from the actual floor silhouette x204.75, not on the section.
# Rounded r2 coordinates have 0.05 mm uncertainty; offline contracts retain it.
SECTION_KEEP = {
    "PocketDia": (FACE_X + 0.039, SECTION_CENTER[1] + 0.001),
    "BodyDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.038, SECTION_CENTER[1] + 0.001),
    # Smaller diameter closest to the floor; the complete two-row hung block
    # fits above the body witness without moving into the hole's witness span.
    "FloorHoleDia": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.003,
        SECTION_CENTER[1] - 0.0125,
    ),
    "OverallLength": (SECTION_CENTER[0], SECTION_CENTER[1] - BODY_R - 0.035),
    "PocketDepth": (FACE_X + 0.033, SECTION_CENTER[1] - BODY_R - 0.0115),
    "BodyChamfer": (
        SECTION_CENTER[0] - HALF_LENGTH - 0.0295,
        SECTION_CENTER[1] + BODY_R + 0.0161,
    ),
    "PocketFloorRadius": (
        FACE_X - POCKET_DEPTH * _S,
        SECTION_CENTER[1] + BODY_R + 0.041,
    ),
}
# The body is bonded in the MHA-DT-08 counterbore: a matched bonded fit,
# turned to the measured counterbore, whose diametral clearance is the
# handle's glue line, REF (rules 4 and 26; rule 23: epoxy, wood to metal).
# The fit lives on flag note 2: printed on the dimension (round 2) its two
# lines ran into the floor-hole dimension line, and the .XXX grade alone
# cannot give a .004-wide clearance, so the matched route must be printed.
_MM_PER_IN = 25.4
BODY_NOTE = POCKET_NOTE + 1
BODY_FLAG = f"SEE NOTE {BODY_NOTE}"
BODY_NOTE_TEXT = "\n".join(
    (
        f"{BODY_NOTE}. BODY: BONDED FIT IN {HANDLE_NUMBER} CRANK HANDLE, EPOXY:",
        "   TURN TO THE MEASURED COUNTERBORE (CLEARANCE "
        + "-".join(
            f"{value / _MM_PER_IN:.3f}".removeprefix("0")
            for value in COUNTERBORE_GLUE_LINE
        )
        + ").",
    )
)
NOTES_TEXT = f"{POCKET_NOTE_TEXT}\n{BODY_NOTE_TEXT}"
DIMENSION_CALLOUTS = {
    "BodyChamfer": BODY_CHAMFER_CALLOUT,
    "BodyDia": BODY_FLAG,
    "FloorHoleDia": FLOOR_HOLE_CALLOUT,
    "PocketDepth": POCKET_FLAG,
    "PocketDia": POCKET_FIT_CALLOUT,
    "PocketFloorRadius": POCKET_FLAG,
    "FloorHoleChamfer": FLOOR_HOLE_CHAMFER_CALLOUT,
}
# *Left reverses *Right's horizontal basis.  Reverse the cut as well to
# retain the section's physical viewing direction and +X-right orientation.
CUT_START = (END_CENTER[0], END_CENTER[1] + BODY_R + 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] - BODY_R - 0.006)

# DETAIL B (#1757): the floor hole's pocket-side mouth break is under 1 mm of
# sheet at 5:1, inside the section, so a 20:1 native detail of section A-A
# carries its model dimension.  The fence takes in both ends of the break.
DETAIL_LETTER = "B"
DETAIL_SCALE = (20, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_MOUTH_ON_HOLE = (-(POCKET_DEPTH + FLOOR_HOLE_CHAMFER), FLOOR_HOLE_DIA / 2.0)
_MOUTH_ON_FLOOR = (-POCKET_DEPTH, FLOOR_HOLE_DIA / 2.0 + FLOOR_HOLE_CHAMFER)
# (model x, y): just inside the pocket, a little above the hole wall.
DETAIL_FOCUS_MM = (-POCKET_DEPTH + 0.15, FLOOR_HOLE_DIA / 2.0 + 0.1)
DETAIL_RADIUS_MM = 0.6
_FENCE_MARGIN_MM = 0.2
if any(
    math.dist(DETAIL_FOCUS_MM, point) > DETAIL_RADIUS_MM - _FENCE_MARGIN_MM
    for point in (_MOUTH_ON_HOLE, _MOUTH_ON_FLOOR)
):
    raise AssertionError("detail B's fence must take in both ends of the mouth break")
# Right of the section, under the isometric's label: the circle spans
# x 0.333..0.357, y 0.103..0.127.
DETAIL_CENTER = (0.345, 0.115)
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS
DETAIL_LABEL_XY = (DETAIL_CENTER[0], DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - 0.005)
# The circle's letter on section A-A stands in the open pocket, up-right of
# the mouth corner and under the pocket-floor radius's leader.
DETAIL_LETTER_XY = (FACE_X - POCKET_DEPTH * _S + 0.007, SECTION_CENTER[1] + 0.011)


def _detail_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    """Sheet point of a model point in detail B (as the section: +X right)."""
    return (
        DETAIL_CENTER[0] + (model_x_mm - DETAIL_FOCUS_MM[0]) * _DS,
        DETAIL_CENTER[1] + (model_y_mm - DETAIL_FOCUS_MM[1]) * _DS,
    )


# The break's radial leg: a vertical dimension whose extension lines run
# right over the open pocket, its line 10 mm right of the circle, centred on
# the break, with its two limits and callout rows beside it.
DETAIL_KEEP = {
    "FloorHoleChamfer": (
        DETAIL_CENTER[0] + DETAIL_CROP_RADIUS + 0.010,
        (_detail_xy(*_MOUTH_ON_HOLE)[1] + _detail_xy(*_MOUTH_ON_FLOOR)[1]) / 2.0,
    ),
}


def _dress_floor_hole_chamfer(annotation: Any) -> None:
    """Prove the imported mouth break prints the model's two native limits."""
    label = "MHA-DT-35 FloorHoleChamfer"
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    nominal = float(dimension.SystemValue) * 1000.0
    limits = (
        nominal + float(tolerance.GetMinValue()) * 1000.0,
        nominal + float(tolerance.GetMaxValue()) * 1000.0,
    )
    if (
        not math.isclose(nominal, FLOOR_HOLE_CHAMFER, abs_tol=1e-6)
        or int(tolerance.Type) != LIMIT_TOL_TYPE
        or any(
            not math.isclose(actual, expected, abs_tol=1e-6)
            for actual, expected in zip(limits, FLOOR_HOLE_CHAMFER_LIMITS, strict=True)
        )
        or bool(dimension.IsReference())
    ):
        raise RuntimeError(f"{label}: imported break lost its model limits: {limits}")


def _mouth_break_detail(adapter: Any, section: Any) -> Any:
    """Native 20:1 detail B of the floor hole's mouth in section A-A
    (draw_dt_crank_handle._ferrule_seat_detail): fence, scale, outline, label
    and letter each read back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(section, "IView")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate detail B's parent section")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        section,
        (DETAIL_FOCUS_MM[0] / 1000.0, DETAIL_FOCUS_MM[1] / 1000.0, 0.0),
        label="detail B fence centre",
    )
    sheet_xy = [center[:2], (center[0] + DETAIL_RADIUS_MM * _S, center[1])]
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


def _dress_pocket_floor_radius(annotation: Any) -> None:
    """Keep the imported model radius controlling, MAX, and on its real arc."""
    label = "MHA-DT-35 PocketFloorRadius"
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric) or int(display.Type2) != 5:  # swRadialDimension
        raise RuntimeError(f"{label}: imported as a non-radial dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    lower, upper = deviations(POCKET_FLOOR_CORNER_R_BAND)
    if (
        not math.isclose(
            float(dimension.SystemValue),
            POCKET_FLOOR_CORNER_R_MAX / 1000.0,
            abs_tol=1e-9,
        )
        or int(tolerance.Type) != POCKET_FLOOR_CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: imported radius lost its model MAX limit")
    if (
        bool(dimension.IsReference())
        or bool(display.ShowParenthesis)
        or any(
            "(" in str(display.GetText(index) or "")
            or ")" in str(display.GetText(index) or "")
            for index in (1, 2)
        )
    ):
        raise RuntimeError(f"{label}: imported as a reference")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
    display.SolidLeader = False
    if (
        bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != 1
        or bool(display.SolidLeader)
    ):
        raise RuntimeError(f"{label}: radial leader style did not persist")


_CAPTION_SCALE_LINE = re.compile(r"[^\r\n]*<VLSCALE[^\r\n]*")


def _drop_section_caption_scale(adapter: Any, section: Any) -> None:
    """Remove the scale line from section A-A's native caption.

    ASME Y14.3 (drawing-guidelines.md rule 9): a view states its scale only
    when it differs from the sheet's.  The section is drawn at the sheet's
    5:1 (asserted here), yet its native caption printed SCALE 5 : 1 (fan-out
    screen); tying the view to the sheet scale read back 4:1 on the farm.
    So the caption keeps its label fields and loses only the scale line.
    """
    bound = _early_bound(section, "IView")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], SHEET_SCALE[0] / SHEET_SCALE[1]):
        raise RuntimeError(f"butt cup section is not at the sheet scale: {ratio}")
    notes = [_early_bound(raw, "INote") for raw in (bound.GetNotes() or ())]
    captions = [
        note for note in notes if "<VLLABEL>" in str(note.PropertyLinkedText or "")
    ]
    if len(captions) != 1:
        raise RuntimeError(
            f"butt cup section: expected one caption, found {len(captions)}"
        )
    note = captions[0]
    linked = str(note.PropertyLinkedText or "")
    if "<VLSCALE" not in linked:
        return
    stripped = _CAPTION_SCALE_LINE.sub("", linked).strip("\r\n")
    note.PropertyLinkedText = stripped
    rebuild_drawing(adapter, label="butt cup section caption without scale")
    after = str(note.PropertyLinkedText or "")
    if (
        after != stripped
        or "<VLLABEL>" not in after
        or "SCALE" in str(note.GetText() or "")
    ):
        raise RuntimeError(
            f"butt cup section caption kept its scale: {after!r} / {note.GetText()!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-butt-cup source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
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
            0: "Crank Handle Butt Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle butt cup; turned plain steel cup",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Left", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="butt cup longitudinal section",
    )
    _drop_section_caption_scale(adapter, section)
    position_section_caption(adapter, section, CAPTION_XY, label="butt cup")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, section, iso):
        set_hidden_lines_removed(adapter, view)

    # Detail B first (draw_dt_crank_handle): a native detail imports nothing
    # after its parent's import and deletions, and a dimension already on the
    # sheet is never imported again, so the section's import then skips the
    # mouth break the detail holds.
    detail = _mouth_break_detail(adapter, section)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="floor-hole mouth detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*section_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, by_name[name], label=f"MHA-DT-35 {name}", diameter=True
        )
    _dress_pocket_floor_radius(by_name["PocketFloorRadius"])
    _dress_floor_hole_chamfer(by_name["FloorHoleChamfer"])
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the cup end view")
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH, label="butt cup axis"
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    if add_note(adapter, NOTES_TEXT, *POCKET_NOTE_POS) is None:
        raise RuntimeError("failed to add the pocket and body flag notes")
    rebuild_drawing(adapter, label="crank-handle-butt-cup layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Butt Cup Manufacturing Drawing",
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
