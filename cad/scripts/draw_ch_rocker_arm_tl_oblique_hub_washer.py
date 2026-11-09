r"""Create the manufacturing drawing for the oblique-trammel hub washer (MHA-CH-06-TL-52).

The face view carries the 13/64 drilled bore with its DRILL THRU callout; the
side view reads like the lathe (drawing-guidelines.md rule 11): both turned
diameters, with the flange's O.D. naming the cutter its .XXX row clears
(rule 3) and the spigot's band naming the strap hole it locates in (rule 4).
Both lengths, from the seat face, read in DETAIL A, a 20:1 native detail of
the flange-to-spigot step: at 4:1 the .014 spigot is 1.4 mm of sheet and the
two chained lengths' arrowheads piled up on their shared extension line
(farm r1, run 20261107T221729532Z).  The flange thickness carries the
floored wall the owner's edge break leaves at the rims (machinist exception
RV-01).  The three local edge limits (the flange rims' .005 break, the sharp
spigot end edge and the R.003 inside corner) are leader notes in DETAIL A,
each arrow on the edge or corner it controls (rule 7: flag it where it
applies), not rows under the size dimensions.  Places and bands are
authored on the part (``ch_rocker_arm_tl_oblique_hub_washer_spec``).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_hub_washer.py ch-rocker-arm-tl-oblique-hub-washer
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name

import _telemetry
from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from ch_rocker_arm_tl_oblique_hub_washer_spec import (
    DIMENSION_CALLOUTS as SPEC_CALLOUTS,
)
from ch_rocker_arm_tl_oblique_hub_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_WALL_CALLOUT,
    JIG_NUMBER,
    OD,
    SPIGOT_DIA,
    SPIGOT_LENGTH,
    STEM,
    THICK,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_washer"]
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

# Drawing-owned callouts, so the wording stays off the part's cache key.
# Rule 7: at most two lines of words and at most one short reason; every
# mate by its drawing number (rule 4).  Rule 12: the bore says what to do;
# the title block's DRILLED HOLES row is its band.  The O.D.'s .XXX row names
# what it clears (rule 3), the 3/8 cutter on the jig; the holding proof and
# the jig's tooling-clearance check carry the 1.5 mm floor.  The flange
# thickness carries the floored wall the .005 rim breaks leave (machinist
# exception RV-01, owner ruling 2026-11-07, #2249; rule 20's plain fact).
# The spigot's band names its mate, the strap hole's limits REF (the strap's
# sheet controls them).  The spigot length prints bare.
DIMENSION_CALLOUTS: dict[str, str] = {
    "WasherBore": SPEC_CALLOUTS["WasherBore"],
    "WasherOd": f"CLEARS 3/8 CUTTER\nON {JIG_NUMBER}",
    "WasherThickness": FLANGE_WALL_CALLOUT,
    "SpigotDia": SPEC_CALLOUTS["SpigotDia"],
}
# The local edge limits, each overriding the title block where its default
# cannot serve: the .010 break would leave the flange no seat ring on the
# strap outside its hub hole (spec SEAT_RING_MIN), and the .010 break or the
# R.040 inside corner would each consume the shortest .014 spigot's locating
# land (spec SPIGOT_LAND_MIN).  The texts are the spec's own printed rows,
# less the narration that followed them, so the sheet authors no limit of
# its own (test_drawing_specification_purity); each note's leader names its
# edge or corner, so the ROOT label goes.
_BREAK_ROW = SPEC_CALLOUTS["WasherThickness"].splitlines()[0].removesuffix(":")
_END_ROW, _ROOT_ROW, _ = SPEC_CALLOUTS["SpigotLength"].splitlines()
RIM_BREAK_NOTE = f"{_BREAK_ROW}\nBOTH FLANGE RIMS"
SPIGOT_END_NOTE = _END_ROW.removesuffix(";")
ROOT_CORNER_NOTE = _ROOT_ROW.partition(":")[0].removeprefix("ROOT ")

# A Ø.433 x .074 top hat at 4:1 (44 mm across, 7.5 mm long): the face view,
# the side view and the isometric on one row midway between the top border
# and the title block (the mg-wheel-axle-spacer sheet's layout), no general
# note.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.090, 0.160)
RIGHT_CENTER = (0.215, 0.160)
ISO_CENTER = (0.345, 0.160)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# The side view (*Right) draws the Right-plane profile, sheet X = model -Z,
# centred on the part's z span -SPIGOT_LENGTH..THICK.
_U_MID = (SPIGOT_LENGTH - THICK) / 2.0


def _side_x(u_mm: float) -> float:
    """Sheet X of a profile station u = -z (mm) on the side view."""
    return RIGHT_CENTER[0] + (u_mm - _U_MID) * _S


HEAD_FACE_X = _side_x(-THICK)
SEAT_FACE_X = _side_x(0.0)
SPIGOT_END_X = _side_x(SPIGOT_LENGTH)
_OD_TOP_Y = RIGHT_CENTER[1] + OD / 2.0 * _S

# Face view: the bore alone, its callout up and left of the side view.
FRONT_KEEP = {
    "WasherBore": (0.105, 0.225),
}
# Side view: the two diameters.  The flange Ø stands left of the head-side
# face, where its extension lines leave the rims into open air and its rows
# sit between the face view and the part; the spigot Ø right of the spigot's
# end.  SolidWorks centres each Ø's whole text block (value and callout rows)
# on its requested point, so each block centres on the axis, midway between
# its arrows: set higher (run 9a1aa3a10e36) the Ø.433 value sat on its upper
# extension line and the spigot's upper arrowhead struck its value.
RIGHT_KEEP = {
    "WasherOd": (HEAD_FACE_X - 0.035, RIGHT_CENTER[1]),
    "SpigotDia": (SPIGOT_END_X + 0.040, RIGHT_CENTER[1]),
}

# DETAIL A: the flange-to-spigot step at 20:1, where the .06 thickness reads
# 30 mm and the .014 spigot 7 mm.  Both lengths run between the profile's +Y
# corners (build_ch_rocker_arm_tl_oblique_hub_washer: head-side and seat-face
# corners at the flange O.D., the spigot end's corner at the spigot O.D.),
# and a detail imports only a dimension whose references it shows, so the
# fence centres midway along the step, between the two O.D.s, and takes in
# all three corners; it stays well above the axis, so neither Ø (both
# measured from the axis) comes in.
DETAIL_LETTER = "A"
DETAIL_SCALE = (20, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_OD_R = OD / 2.0
_SPIGOT_R = SPIGOT_DIA / 2.0
# (profile station u = -z, radius) in mm.
DETAIL_FOCUS_MM = (_U_MID, (_OD_R + _SPIGOT_R) / 2.0)
DETAIL_RADIUS_MM = 1.3
_FENCE_MARGIN_MM = 0.3
_HEAD_CORNER = (-THICK, _OD_R)
_SEAT_CORNER = (0.0, _OD_R)
_SPIGOT_CORNER = (SPIGOT_LENGTH, _SPIGOT_R)
if (
    any(
        math.dist(DETAIL_FOCUS_MM, corner) > DETAIL_RADIUS_MM - _FENCE_MARGIN_MM
        for corner in (_HEAD_CORNER, _SEAT_CORNER, _SPIGOT_CORNER)
    )
    or DETAIL_FOCUS_MM[1] <= DETAIL_RADIUS_MM
):
    raise AssertionError(
        "detail A's fence must take in the three length corners and stay above "
        "the axis"
    )
# Lower left, the sheet's open field under the face view (its centre mark
# ends near y 0.128) and left of the title block (x 0.216): the 52 mm circle
# spans x 0.084..0.136, y 0.034..0.086.
DETAIL_CENTER = (0.110, 0.060)
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS
# The label hangs from its top centre 5 mm under the circle, above the
# bottom border (y 0.0127).
DETAIL_LABEL_XY = (DETAIL_CENTER[0], DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - 0.005)
# The circle's letter on the side view stands up-left of the 5.2 mm fence,
# above the flange Ø's upper extension line and left of the head-side face,
# in the field the two lengths left.
DETAIL_LETTER_XY = (HEAD_FACE_X - 0.010, _OD_TOP_Y + 0.009)


def _detail_xy(u_mm: float, radius_mm: float) -> tuple[float, float]:
    """Sheet point of a profile point in detail A (as the side view: +u right)."""
    return (
        DETAIL_CENTER[0] + (u_mm - DETAIL_FOCUS_MM[0]) * _DS,
        DETAIL_CENTER[1] + (radius_mm - DETAIL_FOCUS_MM[1]) * _DS,
    )


DETAIL_HEAD_X = _detail_xy(*_HEAD_CORNER)[0]
DETAIL_SEAT_X = _detail_xy(*_SEAT_CORNER)[0]
DETAIL_SPIGOT_X = _detail_xy(*_SPIGOT_CORNER)[0]
DETAIL_OD_TOP_Y = _detail_xy(*_SEAT_CORNER)[1]
DETAIL_SPIGOT_TOP_Y = _detail_xy(*_SPIGOT_CORNER)[1]
# The two lengths share the seat face's extension line, so they stand on two
# rows 10 mm apart and their arrowheads on that line never meet: the
# spigot's length nearer the part, the thickness above it.  Each text block
# leaves its span on a leader, the thickness's left of the head-side face's
# extension line and the spigot's right of the spigot end's, clear of the
# circle.  An offset text centres on its point, and SolidWorks runs the
# dimension line's outside stub level toward it: on the row (run
# 20261108T055431582Z) the .06 line struck the X of its text and the .014
# line the E of its own.  So each block stands above its row, its lowest
# line clear of the stub's height (5.5 mm row pitch: the .06's two lines
# reach 2.75 mm below its point plus the glyph's half height), and beyond
# the stub's end (about 3.3 mm past its extension line on that render).
_SPIGOT_ROW_Y = DETAIL_OD_TOP_Y + 0.008
_THICK_ROW_Y = _SPIGOT_ROW_Y + 0.010
TEXT_RISE = 0.009
DETAIL_KEEP = {
    "WasherThickness": ((DETAIL_HEAD_X + DETAIL_SEAT_X) / 2.0, _THICK_ROW_Y),
    "SpigotLength": ((DETAIL_SEAT_X + DETAIL_SPIGOT_X) / 2.0, _SPIGOT_ROW_Y),
}
DETAIL_TEXT_XY = {
    "WasherThickness": (DETAIL_HEAD_X - 0.032, _THICK_ROW_Y + TEXT_RISE),
    "SpigotLength": (DETAIL_SPIGOT_X + 0.016, _SPIGOT_ROW_Y + TEXT_RISE),
}
# The edge-limit leader notes, each arrow on the profile point where its
# edge or corner shows in the detail: the head-side flange rim (the
# outermost, reached from open air on the left), the spigot end edge and
# the inside corner where the spigot meets the flange.  A note anchors at its
# top-left and its leader leaves the side nearest the tip.  The rim note
# stands left of the circle, under the thickness's text and its leader; the
# two spigot notes stand right of the circle, under the .014's text, the
# corner's above the end edge's so their leaders never cross, and both stay
# below the .014 dimension line (a leader may cross an extension line, rule
# 14, not a dimension line).
RIM_TIP_XY = _detail_xy(*_HEAD_CORNER)
SPIGOT_END_TIP_XY = _detail_xy(*_SPIGOT_CORNER)
ROOT_CORNER_TIP_XY = (DETAIL_SEAT_X, DETAIL_SPIGOT_TOP_Y)
RIM_NOTE_XY = (0.024, DETAIL_OD_TOP_Y + 0.007)
ROOT_NOTE_XY = (0.140, DETAIL_OD_TOP_Y + 0.002)
SPIGOT_END_NOTE_XY = (0.140, DETAIL_SPIGOT_TOP_Y - 0.002)
DETAIL_NOTES = (
    ("flange rim break", RIM_BREAK_NOTE, RIM_NOTE_XY, RIM_TIP_XY),
    ("spigot root corner", ROOT_CORNER_NOTE, ROOT_NOTE_XY, ROOT_CORNER_TIP_XY),
    ("spigot end edge", SPIGOT_END_NOTE, SPIGOT_END_NOTE_XY, SPIGOT_END_TIP_XY),
)


@_telemetry.traced("hub_washer.step_detail")
def _step_detail(adapter: Any, side: Any) -> Any:
    """Native 20:1 detail A of the flange-to-spigot step on the side view
    (draw_dt_crank_handle_pivot_screw._relief_lead_detail): fence, scale,
    outline, label and letter each read back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(side, "IView")
    if not drawing.ActivateView(view_name(adapter, side)):
        raise RuntimeError("failed to activate detail A's parent side view")
    draw.ClearSelection2(True)
    # The profile lies on the Right plane: model (x, y, z) = (0, radius, -u).
    center = model_point_in_view(
        adapter,
        side,
        (0.0, DETAIL_FOCUS_MM[1] / 1000.0, -DETAIL_FOCUS_MM[0] / 1000.0),
        label="detail A fence centre",
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
    # Straight to the database: an inferred circle snaps onto nearby edges
    # (draw_dt_pinion_lever r2), and this one sits among the step's corners,
    # so the fence is read back before use.
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError("failed to create detail A's fence")
    arc = _early_bound(fence, "ISketchArc")
    placed = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    placed_centre = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XY"]
    if math.dist(placed_centre, points[0][:2]) > 1e-9 or not math.isclose(
        float(arc.GetRadius()), math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError("detail A's fence moved from where it was placed")
    draw.ClearSelection2(True)
    if not _early_bound(fence, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select detail A's fence")
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
        raise RuntimeError("CreateDetailViewAt4 returned no detail A")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1]
    ):
        raise RuntimeError(f"detail A scale {ratio!r}, expected {DETAIL_SCALE!r}")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("detail A has invalid bounds")
    span = 2.0 * DETAIL_CROP_RADIUS
    _telemetry.info(
        f"detail A outline {outline[2] - outline[0]:.5f} x "
        f"{outline[3] - outline[1]:.5f} m (fence {span:.5f})"
    )
    if min(outline[2] - outline[0], outline[3] - outline[1]) < 0.95 * span:
        raise RuntimeError(f"detail A is smaller than its fence: {outline}")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position detail A")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail A label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position detail A's label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"detail A's label position did not persist: {actual}")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail circle on the side view, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"detail A's letter did not persist: {letter}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub washer source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Oblique Trammel Hub Washer Manufacturing Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "hub clamp top-hat washer; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # Detail A first (draw_dt_crank_handle_pivot_screw, after
    # draw_ch_amplitude_bar r743-6): a dimension already on the sheet is
    # never imported again while a deleted one is, and a native detail
    # imported nothing after its parent's import and deletions.  The detail
    # keeps both lengths; the side view's import then takes the two
    # diameters and skips the lengths.
    detail = _step_detail(adapter, right)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="step detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations, *detail_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the spigot's band are authored on the part; the sheet only proves
    # the import kept the places.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    offset_dimension_text(adapter, detail_annotations, DETAIL_TEXT_XY)
    # Each edge limit at the edge or corner it controls, owned by detail A
    # (add_leader_note reads its tip back).
    for label, text, text_xy, tip_xy in DETAIL_NOTES:
        add_leader_note(
            adapter,
            text,
            text_xy=text_xy,
            attach_xy=tip_xy,
            label=f"hub washer {label}",
            view=detail,
        )
    # Re-assert the detail's hidden-lines-removed display once its
    # annotations have landed (draw_ch_pivot_shaft: left as placed, its 5:1
    # detail printed arcs as straight segments).
    set_hidden_lines_removed(adapter, detail)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Oblique Trammel Hub Washer Manufacturing Drawing",
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
