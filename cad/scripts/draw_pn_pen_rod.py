r"""Create the curated machinist drawing for the pen square rod.

The SLDPRT remains authoritative.  This recipe supplies only the rod's views,
the placement of its imported model dimensions, the stud-tap callout, the
overall-length reference and the property-linked view notes; sheet/template
and export behavior lives in ``_drawing_common``.  Places, bands and mate
callouts are authored on the part (``pn_pen_rod_spec``).

The front view (1:1) carries the square's width and length, the pivot length
and the (122.5) end-to-end reference; the top view (4:1) looks down on the
tapped top face and carries the square's depth and the native Hole Wizard
callout of the #0-80 stud tap; the bottom view (4:1) shows the turned pivot
end-on inside the square and carries its banded diameter; DETAIL A (10:1) of
the front view's right shoulder carries the shoulder root's R MAX; the shaded
isometric sits right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_rod.py pn-pen-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
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
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_rod_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    PIVOT_DIA,
    PIVOT_LENGTH,
    ROD_SECTION,
    SHOULDER_FILLET_R,
    SHOULDER_FILLET_TOL_TYPE,
    SQUARE_LENGTH,
    STUD_TAP_DRILL_DIA,
    STUD_TAP_SPEC,
    TOTAL_LENGTH,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_rod"]
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

SHEET_SCALE = (1.0, 1.0)  # the 122.5-long rod fits the sheet at full size
FRONT_SCALE = (1, 1)
END_SCALE = (4, 1)  # the 5 mm square's ends: tap callout and pivot band need room
ISO_SCALE = (1, 1)

# Front-view model extents (local mm): the square's width in X, pivot end to
# top face in Y.  The top and bottom views are centred on the rod axis.
_CY = (SQUARE_LENGTH - PIVOT_LENGTH) / 2.0

# Sheet layout (meters).  The tall front view hugs the left margin; the two
# 4:1 end views stack to its right (top face above, pivot end below), each
# with its scale note under it; the shoulder detail sits in the free field
# below the bottom view, left of the title block (x >= 0.2155, y <= 0.0655);
# the isometric to the right.
FRONT_CENTER = (0.070, 0.150)
TOP_CENTER = (0.200, 0.215)
BOTTOM_CENTER = (0.200, 0.140)
ISO_CENTER = (0.340, 0.180)
TOP_NOTE_XY = (0.180, 0.198)
BOTTOM_NOTE_XY = (0.180, 0.123)
TAP_CALLOUT_XY = (0.222, 0.248)
DETAIL_CENTER = (0.130, 0.062)
DETAIL_SCALE = (10, 1)  # the R0.2 arc draws 2 mm on the sheet


def _fx(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0


def _fy(model_y_mm: float) -> float:
    return (
        FRONT_CENTER[1] + (model_y_mm - _CY) * FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0
    )


def _end_x(center: tuple[float, float], model_x_mm: float) -> float:
    return center[0] + model_x_mm * END_SCALE[0] / END_SCALE[1] / 1000.0


_HALF = ROD_SECTION / 2.0
_END_HALF_M = _HALF * END_SCALE[0] / END_SCALE[1] / 1000.0

# DETAIL A fences the RIGHT shoulder root only, so the fillet face shows ONE
# arc in it and its imported radius has one place to attach: centred
# between the arc's ends (2.2, -0.1), r 1.5 reaches 0.7 <= x <= 3.7, clear of
# the left root at x -2.2.  Inside it: the pivot side (x 2.0) below, the
# 0.3-wide seat face and the square's side (x 2.5) above, open air right.
DETAIL_FENCE_MM = (PIVOT_DIA / 2.0 + SHOULDER_FILLET_R, -SHOULDER_FILLET_R / 2.0)
DETAIL_FENCE_RADIUS_MM = 1.5
_DETAIL_K = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_DETAIL_RADIUS_M = DETAIL_FENCE_RADIUS_MM * _DETAIL_K  # 0.015 on the sheet


def _detail_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    """Sheet point of a front-plane model point in DETAIL A (fence centre on
    DETAIL_CENTER; the detail keeps the front view's +X right, +Y up)."""
    return (
        DETAIL_CENTER[0] + (model_x_mm - DETAIL_FENCE_MM[0]) * _DETAIL_K,
        DETAIL_CENTER[1] + (model_y_mm - DETAIL_FENCE_MM[1]) * _DETAIL_K,
    )


# The fillet arc's centre (2.2, -0.2) lands at (0.130, 0.061); the arc runs
# from (0.128, 0.061) on the pivot side to (0.130, 0.063) on the seat face, so
# the open air of the detail is everything right of x 0.128 below y 0.063.
_SHOULDER_ARC_CENTRE_XY = _detail_xy(
    PIVOT_DIA / 2.0 + SHOULDER_FILLET_R, -SHOULDER_FILLET_R
)
# The native detail label anchors at its top centre and prints DETAIL A over
# SCALE 10 : 1, about 32 x 15 mm (dt-pinion-lift-rod's 5:1 label on the
# farm PNG).  Left of the fence (left edge x 0.115): x 0.079..0.111,
# y 0.0545..0.0695 -- below the front view's pivot end (y 0.089), clear of
# the radius callout's lower-right field.
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0] - _DETAIL_RADIUS_M - 0.020,
    DETAIL_CENTER[1] + 0.0075,
)
# The front view's fence (r 1.5 about (0.0722, 0.0992)) takes its letter up and
# right: 5 mm right of the square's side, 5 mm above the shoulder, so clear of
# the 10.5 pivot length's upper extension line (y 0.0993) and its text
# (y 0.094).
DETAIL_LETTER_XY = (_fx(_HALF + 5.0), _fy(5.0))

# Front view: the length left of the square, the pivot length right of the
# pivot, the banded width (and its mate callout) above the top face, offset
# right so neither extension line runs through the toleranced text.
FRONT_KEEP = {
    "Length": (_fx(-_HALF) - 0.012, _fy(SQUARE_LENGTH / 2.0)),
    "PivotLength": (_fx(_HALF) + 0.012, _fy(-PIVOT_LENGTH / 2.0)),
    "Section": (_fx(0.0) + 0.040, _fy(SQUARE_LENGTH) + 0.010),
}
# The (122.5) end-to-end reference stands OUTSIDE the 112.0 (dimension line
# x 0.0555): its line at x 0.0415, about 20 mm of text centred there
# (0.0315..0.0515, inside the 0.0127 border), a quarter of the way up the
# square (y 0.127) so it sits 28 mm below the 112.0 text (y 0.155).  Its
# witness lines leave the top face and the pivot end at their left ends; the
# upper one runs along the 112.0's own, the lower one passes under the
# 112.0's (which stops at the shoulder, y 0.0993).
OVERALL_REF_XY = (_fx(-_HALF) - 0.026, _fy(SQUARE_LENGTH / 4.0))
# Picks: the top face's edge 1.0 in from the left corner (the tap mouth and
# its cosmetic thread stop at x 0.76), and the pivot end's edge 1.0 in from
# its left silhouette -- each the only edge at that point.
OVERALL_TOP_PICK_MM = (-_HALF + 1.0, SQUARE_LENGTH, _HALF)
OVERALL_END_PICK_MM = (
    -PIVOT_DIA / 2.0 + 1.0,
    -PIVOT_LENGTH,
    math.sqrt((PIVOT_DIA / 2.0) ** 2 - (PIVOT_DIA / 2.0 - 1.0) ** 2),
)
# Top view: the banded depth (and its mate callout) right of the square.
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + _END_HALF_M + 0.035, TOP_CENTER[1]),
}
# Bottom view: the pivot's banded diameter (and its mate callout) out to the
# right of the square.  The four-line block (~20 mm tall) centres on its
# anchor; at +0.008 its MHA-PN-005 line sat on the view's horizontal
# centreline (y 0.140, ending x ~0.217), so +0.014 lifts the block's bottom
# to ~0.1445, 4.5 mm clear, and its top (~0.164) stays under the top view's
# note (0.198).
BOTTOM_KEEP = {
    "PivotDia": (BOTTOM_CENTER[0] + _END_HALF_M + 0.035, BOTTOM_CENTER[1] + 0.014),
}
# DETAIL A: the R MAX callout (R0.2 MAX / SEATS ON PEN V-BLOCK / MHA-PN-005,
# ~57 x 17 mm) out in the open air down-right of the arc centre: x
# 0.1465..0.2035, y 0.029..0.046, its nearest corner 23 mm from the fence
# centre (r 15), 12 mm left of the title block.  The leader runs from it at
# -28 deg toward the arc centre through the open air only and lands on the
# arc from its concave side.
DETAIL_KEEP = {
    "ShoulderRadius": (
        _SHOULDER_ARC_CENTRE_XY[0] + 0.045,
        _SHOULDER_ARC_CENTRE_XY[1] - 0.024,
    ),
}
_DETAIL_PLACE_TOL_M = 1e-4


def _mm_to_m(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)  # type: ignore[return-value]


@_telemetry.traced("drawing.pen_rod.shoulder_detail")
def _shoulder_detail(adapter: Any, front: Any) -> Any:
    """DETAIL A: the right shoulder root at DETAIL_SCALE, fenced on the front
    view (dt-pinion-lift-rod's full-outline circle detail, sketched with
    AddToDB as dt-cone-gear-shaft's so the centre 0.2 mm off the pivot's edge
    cannot snap onto it), placed by its outline and proved by projection."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate the shoulder detail's parent view")
    draw.ClearSelection2(True)
    centre = _mm_to_m((*DETAIL_FENCE_MM, 0.0))
    rim = _mm_to_m(
        (DETAIL_FENCE_MM[0] + DETAIL_FENCE_RADIUS_MM, DETAIL_FENCE_MM[1], 0.0)
    )
    sheet = [
        model_point_in_view(adapter, front, point, label=f"shoulder detail {name}")
        for name, point in (("centre", centre), ("rim", rim))
    ]
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet:
        point = _early_bound(
            utility.CreatePoint(double_array([float(x), float(y), 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError("failed to sketch the shoulder detail circle")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = front
    selectable = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError("failed to select the shoulder detail circle")
    detail = ddoc.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        float(DETAIL_SCALE[0]),
        float(DETAIL_SCALE[1]),
        "A",
        1,  # swDetCircleCIRCLE
        True,  # FullOutline: the circle prints, and the outline is its box
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError("CreateDetailViewAt4 returned no shoulder detail")
    detail = _sw_type_info.early_bound_or_flag(
        detail, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label="create shoulder detail")
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1]):
        raise RuntimeError(f"shoulder detail scale is {ratio}, not {DETAIL_SCALE}")
    for attempt in range(4):
        outline = tuple(float(value) for value in detail.GetOutline())
        landed = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        anchor = tuple(float(value) for value in detail.Position)
        _telemetry.info(
            f"shoulder detail pass {attempt}: anchor={anchor} outline={outline}"
        )
        if math.dist(landed, DETAIL_CENTER) < _DETAIL_PLACE_TOL_M:
            break
        moved = [anchor[axis] + DETAIL_CENTER[axis] - landed[axis] for axis in range(2)]
        if not detail.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to position the shoulder detail")
        rebuild_drawing(adapter, label="place shoulder detail")
    else:
        raise RuntimeError(
            f"shoulder detail outline centre stayed at {landed}, "
            f"requested {DETAIL_CENTER}"
        )
    # DETAIL_KEEP's radius text is laid out from the fence centre landing on
    # DETAIL_CENTER: prove it once the detail's transform has caught up.
    settle_detail_projection(
        adapter,
        detail,
        centre,
        ink_xy=landed,
        tolerance_xy=(0.0005, 0.0005),
        label="shoulder detail",
    )
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the shoulder detail label")
    rebuild_drawing(adapter, label="place shoulder detail label")
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"shoulder detail label did not persist: {actual}")
    return detail


def _place_detail_letter(adapter: Any, front: Any) -> None:
    """Stand the front view's circle letter where DETAIL_LETTER_XY says."""
    circles = tuple(
        _read_member(_early_bound(front, "IView"), "GetDetailCircles") or ()
    )
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail circle on the front view, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    rebuild_drawing(adapter, label="place shoulder detail letter")
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"shoulder detail letter position did not persist: {actual}")


def _dress_shoulder_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove the imported ShoulderRadius is the radial R MAX and route its
    leader through the arc centre onto the concave side of the arc.

    The text stands in the open air on the far side of the arc centre (no
    part of the arc faces it), so the leader must extend to the OPPOSITE side
    to reach the arc: ``ArcExtensionLineOrOppositeSide`` True
    (types/IDisplayDimension/ArcExtensionLineOrOppositeSide.md).
    """
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ShoulderRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one ShoulderRadius on DETAIL A, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported shoulder radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE:
        raise RuntimeError(
            f"ShoulderRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), SHOULDER_FILLET_R / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("ShoulderRadius does not measure the shoulder fillet")
    display.ArcExtensionLineOrOppositeSide = True
    if display.ArcExtensionLineOrOppositeSide is not True:
        raise RuntimeError("ShoulderRadius leader did not keep its opposite-side run")


@_telemetry.traced("drawing.pen_rod.overall_reference")
def _overall_reference(adapter: Any, front: Any) -> None:
    """(122.5): top face to pivot end, a reference the square and pivot
    lengths own (rule 10); a drawing-added edge dimension, readback-proved."""
    label = "pen-rod overall length reference"
    display = add_edge_dimension(
        adapter,
        front,
        p0=model_point_in_view(
            adapter, front, _mm_to_m(OVERALL_TOP_PICK_MM), label=f"{label} top pick"
        ),
        p1=model_point_in_view(
            adapter, front, _mm_to_m(OVERALL_END_PICK_MM), label=f"{label} end pick"
        ),
        text_xy=OVERALL_REF_XY,
        label=label,
        orientation="vertical",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    # swLinearDimension, swVertLinearDimension
    if dimension_type not in (2, 12):
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    # Only the top face and the pivot end are TOTAL_LENGTH apart (the
    # shoulder is 112.0 from one, 10.5 from the other): the value proves the
    # picks.
    measured_mm = abs(
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    )
    if abs(measured_mm - TOTAL_LENGTH) > 1e-3:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {TOTAL_LENGTH:g}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Top View Note",
            "Bottom View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Top View Note",
            "Bottom View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; turned pivot end; tapped top",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=FRONT_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=END_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=END_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False).
    # From HLR the shading call really changes the mode and takes precision.
    for view in (front, top, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            bottom,
            keep=BOTTOM_KEEP,
            view_label="bottom",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    detail = _shoulder_detail(adapter, front)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="shoulder detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _dress_shoulder_radius(adapter, detail_annotations)
    annotations += detail_annotations
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the stud tap")

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre.
    stud_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(_end_x(TOP_CENTER, STUD_TAP_DRILL_DIA / 2.0), TOP_CENTER[1]),
        callout_xy=TAP_CALLOUT_XY,
        label="adjuster stud blind tap",
        process="TAP",
    )
    # The title block's THREADS row owns the general thread class (rule 2).
    omit_title_block_thread_class(stud_callout, label="adjuster stud blind tap")

    _overall_reference(adapter, front)
    _place_detail_letter(adapter, front)

    add_property_linked_note(adapter, "Top View Note", *TOP_NOTE_XY)
    add_property_linked_note(adapter, "Bottom View Note", *BOTTOM_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(f"{STUD_TAP_SPEC.size} Tapped Hole",),
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
