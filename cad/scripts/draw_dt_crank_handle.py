r"""Create the curated machinist drawing for the crank handle.

A turned, ebonized oak pear grip (book ch. 11).  User ruling 2026-09-29: the
brass ferrule MHA-DT-34 and the steel butt cup MHA-DT-35 are separate parts, so
this sheet prints only the oak -- a tenon for the ferrule at the crank end, a
flared waist, an S-curve swell to the maximum, and a domed butt whose end
round crests on a flat oak end round the cup bonded into its counterbore
(user rulings 2026-09-30, concept v4).

The sheet is plain (user ruling 2026-09-29): no datums, feature-control frames
or basic dimensions, and no general notes (MHA-DT-08 machinist review of
2026-10-18).  The longitudinal section A-A, taken on the end view's vertical
centre line, is the handle's length view (drawing-guidelines.md rule 11
(turned parts read like the lathe)): the profile, the reamed bore and the
counterbore all sketch on the Front plane the section lies in, so nearly every
size prints there.  The stations stack above it in a baseline from the tenon
end face, with the tangency-fixed radii as references beneath them; the
diameters are dimensioned across their own cut, their text on shelves clear of
the section; the fitted tenon and counterbore carry their mates and clearances
as callouts, and the counterbore's floor corner its R.012 MAX single limit with
the cup that seats on it.  The tenon root's relief cut into the ferrule
shoulder (owner ruling 2026-10-24, #1900) prints in detail B, an 8:1 native
detail of the section: the 45-degree relief's band with the ferrule it serves
and the root's R.012 MAX, each on its own leader (MHA-DT-08 machinist review of
3de09b959: at 4:1 the two crowded one tiny corner).  The end view stands on
the section's axis and carries the cutting plane.  The sheet prints decimal
inch (#290, ``drawing_unit: in``).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle.py dt-crank-handle
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
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
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import create_section_axis_centerline, position_section_caption
from _session import run_build
import _telemetry
from dt_crank_handle_spec import (
    COUNTERBORE_DEPTH,
    COUNTERBORE_FIT_NOTE,
    COUNTERBORE_FLOOR_CALLOUT,
    COUNTERBORE_FLOOR_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    END_ROUND_CENTER,
    FLARE_CENTER,
    HANDLE_MAX_DIA,
    INFLECTION,
    INSIDE_CORNER_R_MAX,
    INSIDE_CORNER_R_TOL_TYPE,
    OAK_END_X,
    PEAK_X,
    REFERENCE_DIMENSIONS,
    REFERENCE_RADII,
    S_CONCAVE_CENTER,
    S_CONVEX_CENTER,
    S_CONVEX_R,
    SCREW_NUMBER,
    SHOULDER_R,
    SHOULDER_X,
    TANGENT_POINT_DIAMETERS,
    TENON_FIT_NOTE,
    TENON_R,
    TENON_ROOT_CALLOUT,
    TENON_ROOT_RELIEF,
    TENON_ROOT_RELIEF_CALLOUT,
    TENON_ROOT_ROUND_REACH,
    TENON_X0,
    WAIST_X,
    UNIT,
    inch_text,
)
from dt_crank_handle_pivot_screw_spec import (
    DIAMETRAL_CLEARANCE_MAX,
    DIAMETRAL_CLEARANCE_MIN,
)

# The reamed bore prints as a reference over the running clearance its model
# band gives on the MHA-DT-32 shoulder's band, at the places that hold it
# exactly (#290 fit F12: .0050-.0075).
PIVOT_BORE_CALLOUT = (
    f"REAM THRU; {inch_text(DIAMETRAL_CLEARANCE_MIN, 4)}-"
    f"{inch_text(DIAMETRAL_CLEARANCE_MAX, 4)}\n"
    f"DIAMETRAL CLEARANCE ON\n{SCREW_NUMBER} SHOULDER"
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_handle"]
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

# 4:1 gives the five-arc profile room for its stations, diameters and radii:
# the section reads 224 x 84 on the sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / 1000.0

# The section lays the handle axis horizontal, tenon at the left and butt at
# the right (the part's +X to the right, as MHA-DT-35's section shows), centred
# on the oak's extent.  The end view stands on the same axis height.  The axis
# sits low enough that the S-curve's concave centre (26.4 above it) falls
# under the long station rows, so its radius line crosses none of them.
FRONT_BBOX_CX = (TENON_X0 + OAK_END_X) / 2.0
FRONT_CENTER = (0.162, 0.130)
RIGHT_CENTER = (0.362, FRONT_CENTER[1])
# Detail B took the upper right, so the isometric, its note and the section's
# caption share the lower left, under the fitted tenon's callout (bottom y
# ~0.069, x 0.056..0.116) and left of the reamed bore's (x >= 0.152 down to y
# ~0.055).  The 1:1 isometric reads about 53 x 39 mm: x ~0.087..0.140, y
# ~0.020..0.059; the caption (top-centre anchored, ~44 x 16 mm) and the note
# (top-left anchored, ~59 x 5 mm) stand left of it.
ISO_CENTER = (0.112, 0.040)
ISO_NOTE_POS = (0.016, 0.034)
CAPTION_XY = (0.045, 0.061)

END_R = HANDLE_MAX_DIA * _S / 2.0


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model station (x from the arm face) on the section."""
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * _S


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model height (up from the axis) on the section."""
    return FRONT_CENTER[1] + model_y_mm * _S


def _on_radius(
    center: tuple[float, float], distance_mm: float, degrees: float
) -> tuple[float, float]:
    """Sheet point ``distance_mm`` from a model arc centre at ``degrees`` CCW."""
    angle = math.radians(degrees)
    return (
        _front_x(center[0] + distance_mm * math.cos(angle)),
        _front_y(center[1] + distance_mm * math.sin(angle)),
    )


# Rows above the section, the stations in a baseline from the tenon end face,
# shortest nearest: the two that end left of the waist below the S-curve's
# concave centre, the three that run past it above it; the counterbore depth
# from the oak end on the second row.
_ROW = (0.195, 0.205, 0.242, 0.250, 0.258)
# A diameter's text hangs on a shelf off its dimension line, on the side the
# text stands from the point it measures to (a line's END point; r2/r3 sheets):
# each stands right of it, so every shelf runs right.
_SHELF = 0.0015
_BELOW = 0.098
_CALLOUT_ROW = 0.080
FRONT_KEEP = {
    "TenonLength": (_front_x((TENON_X0 + SHOULDER_X) / 2.0), _ROW[0]),
    "WaistStation": (_front_x((TENON_X0 + WAIST_X) / 2.0), _ROW[1]),
    "InflectionStation": (_front_x((TENON_X0 + INFLECTION[0]) / 2.0), _ROW[2]),
    "PeakStation": (_front_x((TENON_X0 + PEAK_X) / 2.0), _ROW[3]),
    "OverallLength": (_front_x(FRONT_BBOX_CX), _ROW[4]),
    "CounterboreDepth": (_front_x(OAK_END_X - COUNTERBORE_DEPTH / 2.0), _ROW[1]),
    # The radii stand between the station extension lines, below the rows:
    # the convex ones outside their arcs (a short leader to the arc), the
    # concave ones between centre and arc.
    "FlareR": _on_radius(FLARE_CENTER, 5.3, 245.0),
    "SConcaveR": _on_radius(S_CONCAVE_CENTER, 15.5, 285.0),
    "SConvexR": _on_radius(S_CONVEX_CENTER, S_CONVEX_R + 5.0, 100.0),
    # Ruling-B native audit: the R77.3 text is 14.2 mm wide.  Its former
    # radial keep straddled the oak-end extension at x 0.274; this left-side
    # keep leaves 5.4 mm of air and separates it from the end-round callout.
    "DomeR": (_front_x(OAK_END_X) - 0.0125, 0.185),
    "EndRoundR": _on_radius(END_ROUND_CENTER, 8.1, 42.5),
    # Diameters across their own cut.  The shoulder and waist shelves sit
    # under the section; the fitted tenon's and the counterbore's callout
    # blocks stand below them, above the title block, and the reamed bore's
    # lower still between them, clear of the swell.  The counterbore's
    # five-line block stands near its floor, clear of the end view.
    "ShoulderDia": (_front_x(SHOULDER_X) + _SHELF, _BELOW),
    "WaistDia": (_front_x(WAIST_X) + _SHELF, _BELOW),
    # The S-curve's tangent point: its "( Ø12.6)" text (about 17 mm wide)
    # runs right under the swell, where the outline drops to y ~0.0968 by
    # its end (farm r1 of c1b463872 had the outline through the "6)" at the
    # waist row), so its shelf hangs 7 mm lower, 8 mm right of the fitted
    # tenon's block.
    "InflectionDia": (_front_x(INFLECTION[0]) + _SHELF, _BELOW - 0.007),
    "TenonDia": (_front_x(TENON_X0) + 4.0 * _SHELF, _CALLOUT_ROW),
    # The reamed bore's dimension line stands 22 mm right of the tangent
    # point's, 5 mm clear of its text; the four-line block and its leader
    # shoulder end about 6 mm left of the title block (machinist review of
    # 4cde83cb6: at 0.152 the shoulder touched the title block's edge).
    "PivotBoreDia": (0.146, 0.068),
    "CounterboreDia": (
        _front_x(OAK_END_X - COUNTERBORE_DEPTH) + 0.0055,
        _CALLOUT_ROW + 0.0015,
    ),
    # The swell's diameter reads above the section, clear of the bore's
    # callout, beside the 40.0 station's extension line.
    "PeakDia": (_front_x(PEAK_X) + 2.0 * _SHELF, 0.225),
    # Ruling-B's longer diameter tail ends at y 0.09325, beside the fitted
    # bore's text (right edge x 0.295).  Put the crest line at x 0.299:
    # 4 mm clear of that text, with another 4 mm from its own text to the
    # end view's x 0.320 outline.
    "CrestDia": (_front_x(OAK_END_X) + 0.025, 0.165),
    # The counterbore floor corner's three-row block (R0.3 MAX / mate / SEAT),
    # 8 x 2.75 = 22.0 mm wide and 2 x 5.55 + 3.5 = 14.6 mm tall, centred on
    # the keep (were the rows to hang from the keep instead, the box drops
    # ~7 mm and stays clear):
    #   Counterbore floor, above the section between the swell diameter's
    #   dimension line (x 0.213) and the 8.1's floor extension line (x
    #   0.2416): box x 0.2163..0.2383 (3.3 mm clear of each), y 0.1877..0.2023
    #   -- 15.8 above the silhouette (y <= 0.1719 there), 19.9 under the
    #   swell diameter's text (y 0.2222).  Its leader drops ~23 mm through the
    #   oak to the corner (under the corner's 25.4 approach to the section's
    #   top edge) and crosses the 8.1's floor extension line at y ~0.157,
    #   31 mm from either text.
    "CounterboreFloorRadius": (_front_x(COUNTERBORE_FLOOR_X) - 0.0143, 0.195),
}

# DETAIL B (MHA-DT-08 machinist review of 3de09b959): at 4:1 the root relief
# is a few millimetres of sheet, and its leg, its R0.3 MAX root and their two
# blocks all met one tiny corner, so a reader could not tell the 45-degree
# wall runs back into the shoulder.  An 8:1 native detail of section A-A
# carries both, each on its own leader, cut and hatched like its parent.  The
# leg's model dimension runs from the tenon end's corner (the dimension leaves
# the part's left end), and a detail imports only a dimension whose
# references it shows, so the fence takes in that corner as well as the
# relief, its root round, the shoulder face up to the ferrule's OD corner and
# the reamed bore under the tenon.
DETAIL_LETTER = "B"
DETAIL_SCALE = (8, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
DETAIL_FOCUS_MM = (4.9, 4.5)
DETAIL_RADIUS_MM = 3.4
_TENON_END_CORNER = (TENON_X0, TENON_R)
_RELIEF_TOP = (SHOULDER_X, TENON_R + TENON_ROOT_RELIEF)
_ROOT_CENTER = (
    SHOULDER_X + TENON_ROOT_RELIEF - TENON_ROOT_ROUND_REACH,
    TENON_R + INSIDE_CORNER_R_MAX,
)
_ROOT_EXTENT = (_ROOT_CENTER[0] + INSIDE_CORNER_R_MAX, _ROOT_CENTER[1])
_FENCE_MARGIN_MM = 0.3
if any(
    math.dist(DETAIL_FOCUS_MM, point) > DETAIL_RADIUS_MM - _FENCE_MARGIN_MM
    for point in (
        _TENON_END_CORNER,
        _RELIEF_TOP,
        _ROOT_EXTENT,
        (SHOULDER_X, SHOULDER_R),
    )
):
    raise AssertionError(
        "detail B's fence must take in the tenon end's corner, the relief, its "
        "root round and the ferrule shoulder's OD corner"
    )
# Upper right, where the isometric stood: the circle spans x 0.318..0.372, y
# 0.201..0.255, 11.7 mm under the top border, 15 mm right of the 56.0 row's
# end (x 0.274) and 13 mm over the end view's cutting-plane arrow (y ~0.182).
DETAIL_CENTER = (0.345, 0.228)
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS
# The label hangs from its top centre under the circle's lower left, left of
# the end view's "A" arrow (x >= 0.363) and right of the 15.2's text (x
# <= 0.315 at y ~0.165).
DETAIL_LABEL_XY = (0.333, 0.197)
# The fence on section A-A spans x 0.048..0.075, y 0.134..0.162; its letter
# stands up-left of it in the gutter the two blocks used to fill.
DETAIL_LETTER_XY = (0.036, 0.166)


def _detail_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    """Sheet point of a model point in detail B (as the section: +X right)."""
    return (
        DETAIL_CENTER[0] + (model_x_mm - DETAIL_FOCUS_MM[0]) * _DS,
        DETAIL_CENTER[1] + (model_y_mm - DETAIL_FOCUS_MM[1]) * _DS,
    )


DETAIL_KEEP = {
    # The relief's leg (owner ruling 2026-10-24, #1900): a vertical linear
    # dimension, so its dimension line sits on the keep and its "0.9 ±0.1"
    # plus four callout rows (23 mm wide on farm r3 of 8abe1a641) stand left
    # of it on a shelf, centred on the keep's y, as they did on the section.
    # The line stands 10 mm left of the tenon end's corner (x 0.3218), outside
    # the circle; the block spans x 0.289..0.312, y 0.233..0.261 -- above the
    # relief's upper extension line (y 0.2296), 6 mm under the top border and
    # 15 mm right of the 56.0 row's end.
    "TenonRootRelief": (
        _detail_xy(*_TENON_END_CORNER)[0] - 0.010,
        _detail_xy(*_RELIEF_TOP)[1] + 0.0173,
    ),
    # The root's R0.3 MAX block (22.0 x 14.6 mm, centred on the keep) right of
    # the circle, x 0.383..0.405: its leader runs left, inside the round's
    # span, onto the arc (x 0.3656), 14 mm inside the right border.
    "TenonRootRadius": (0.394, _detail_xy(*_ROOT_CENTER)[1]),
}
# Every band renders from its model dimension; the callouts carry the reamed
# bore's mate, the fitted tenon's and counterbore's mates and clearances, and
# the part seating on each inside corner (drawing-guidelines.md rules 4 and 7).
DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "TenonDia": TENON_FIT_NOTE,
    "CounterboreDia": COUNTERBORE_FIT_NOTE,
    "TenonRootRadius": TENON_ROOT_CALLOUT,
    "TenonRootRelief": TENON_ROOT_RELIEF_CALLOUT,
    "CounterboreFloorRadius": COUNTERBORE_FLOOR_CALLOUT,
}
# Each inside corner's text stands inside its arc's span, so its leader lands
# on the arc itself: the tenon root's right of its centre in detail B (the
# round turns from the tenon OD at -90 degrees to the relief at 45), the
# counterbore floor's up-left of its centre (its upper-left quarter).
INSIDE_CORNER_ARC_EXTENSION = {
    "TenonRootRadius": False,
    "CounterboreFloorRadius": False,
}
RADII = (*sorted(REFERENCE_RADII), "EndRoundR")
CUT_START = (RIGHT_CENTER[0], RIGHT_CENTER[1] - END_R - 0.006)
CUT_END = (RIGHT_CENTER[0], RIGHT_CENTER[1] + END_R + 0.006)
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


def _style_radius(adapter: Any, annotation: Any, *, name: str, reference: bool) -> None:
    """Arrow outside, no solid leader: the convex arcs' leaders run from the
    text to the arc and stop there, since the swell and dome centres lie off
    the sheet (draw_ch_fulcrum_keeper._set_crown_reference).
    A tangency-fixed radius prints as the reference "(R59.5)"; the bare "("
    prefix of set_reference_dimension would replace SolidWorks' own radius
    glyph, so whatever prefix the display carries stays behind it."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError(f"MHA-DT-08 {name} imported as a diameter")
    if reference:
        existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
        prefix = "(" + existing
        display.SetText(1, prefix)
        display.SetText(2, ")")  # swDimensionTextSuffix
        applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        _telemetry.info(f"{name}: radial reference prefix {existing!r} -> {applied[0]!r}")
        if applied != (prefix, ")"):
            raise RuntimeError(f"failed to mark MHA-DT-08 {name} as a reference: {applied}")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = _ARROWS_OUTSIDE
    display.SolidLeader = False
    if (
        bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != _ARROWS_OUTSIDE
        or bool(display.SolidLeader)
    ):
        raise RuntimeError(f"MHA-DT-08 {name} kept its leader to the arc's centre")


def _dress_inside_corner(adapter: Any, annotation: Any, *, name: str) -> None:
    """Prove an imported inside-corner radius prints the part's R0.3 MAX with
    its mate callout, and land its leader on the corner
    (draw_mg_magnifying_vertical_rod._dress_relief_roots).

    Read back: radial (not a diameter), measuring INSIDE_CORNER_R_MAX, the
    native swTolMAX the part set, and the callout under the value.
    SolidWorks ends a radial leader at the circle point facing its text, so a
    text standing off the arc's span takes ``ArcExtensionLineOrOppositeSide``
    True to draw the arc's extension out to that point (farm r4 of the
    magnifying rod); one inside the span lands on the arc itself."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError(f"MHA-DT-08 {name} imported as a diameter")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != INSIDE_CORNER_R_TOL_TYPE:
        raise RuntimeError(
            f"MHA-DT-08 {name} lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), INSIDE_CORNER_R_MAX / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(f"MHA-DT-08 {name} does not measure the inside corner")
    callout = str(display.GetText(4) or "")  # swDimensionTextCalloutBelow
    if callout != DIMENSION_CALLOUTS[name]:
        raise RuntimeError(f"MHA-DT-08 {name} callout did not persist: {callout!r}")
    extension = INSIDE_CORNER_ARC_EXTENSION[name]
    display.ArcExtensionLineOrOppositeSide = extension
    if bool(display.ArcExtensionLineOrOppositeSide) is not extension:
        raise RuntimeError(f"MHA-DT-08 {name} refused its arc extension setting")
    _telemetry.info(
        f"{name}: text {display.GetText(1)!r}, MAX type, callout {callout!r}"
    )


def _ferrule_seat_detail(adapter: Any, section: Any) -> Any:
    """Native 8:1 detail B of the tenon root's relief in section A-A
    (draw_dt_pinion_lever._hub_detail): fence, scale, outline, label and
    letter each read back."""
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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle; turned oak pear grip; ferrule tenon and cup counterbore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    front = create_section_view(
        adapter,
        right,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=FRONT_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="crank handle longitudinal section",
    )
    position_section_caption(adapter, front, CAPTION_XY, label="crank handle")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    detail = _ferrule_seat_detail(adapter, front)
    set_hidden_lines_removed(adapter, detail)
    for view, label in ((front, "section A-A"), (detail, "detail B")):
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide crank-handle {label} tangent edges")
        view.UpdateViewDisplayGeometry()

    # Detail B is dimensioned FIRST: its two dimensions live in HandleProfile
    # with the section's, a dimension already on the sheet is never imported
    # again while a deleted one is, and a native detail imported nothing after
    # its parent's import and deletions (draw_ch_amplitude_bar r743-6).  The
    # detail keeps its two and deletes the rest; the section's import then
    # takes those back and skips the two the detail holds.
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="ferrule seat detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    by_name = {dimension_name(adapter, a): a for a in annotations}
    # The tenon and the counterbore are fitted to the ferrule and cup (their
    # to-suit callouts), and the S-curve's tangent point is fixed by its
    # arcs, so their sizes print as references.
    for name in sorted(REFERENCE_DIMENSIONS | TANGENT_POINT_DIAMETERS):
        set_reference_dimension(
            adapter,
            by_name[name],
            label=f"MHA-DT-08 {name}",
            diameter=name.endswith("Dia"),
        )
    for name in RADII:
        _style_radius(
            adapter, by_name[name], name=name, reference=name in REFERENCE_RADII
        )
    for name in sorted(INSIDE_CORNER_ARC_EXTENSION):
        _dress_inside_corner(adapter, by_name[name], name=name)
    rebuild_drawing(adapter, label="crank-handle radii")
    create_section_axis_centerline(
        adapter, front, length_mm=OAK_END_X - TENON_X0, label="crank handle axis"
    )
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to crank-handle end view")

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Manufacturing Drawing",
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
