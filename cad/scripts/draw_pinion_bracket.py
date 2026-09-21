r"""Create the curated machinist drawing for the pinion swing bracket.

The SLDPRT remains authoritative.  This recipe supplies only the strap's
views and its dimension/callout placement; every shared sheet/template,
import, curation and export behaviour lives in ``_drawing_common``, and every
nominal, decimal place and tolerance band is imported from the model.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
bracket carries no datums and no feature-control frames, and it carries no
manufacturing-note block either -- the outline, the four hole/scallop
callouts, two roughness symbols and the title block say everything.  Three
bands survive, one per fitted bore, each from a named fit class.

Two orthographic views at the 2:1 sheet scale, one enlarged detail, plus the
isometric:

* FRONT -- the strap face: both bores, both end radii, the follower-seat
  height and the seat's blind depth.  This is the only view carrying hidden
  lines, and the blind seat is the only feature that needs them: both bores
  and both scallops go clean through.
* DETAIL A (3:1) -- the two cam-relief scallops enlarged around the pivot
  bore, where their centres and cutter radius have room to read: at 2:1 the
  six scallop dimensions packed into one column and printed on top of each
  other.
* LEFT -- the seat flank, where the blind O4 seat mouth is a SOLID circle:
  its size, its station through the bar and the bar thickness; plus the
  (43.0) overall as a reference, so nobody saws the bar short of the two
  end radii the 28.00 centre distance does not include.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_bracket.py pinion-bracket
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_bracket_spec import (
    ARBOR_BORE,
    C2C,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    OVERALL_LENGTH,
    PIVOT_BORE,
    R_END,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_bracket"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The strap runs UP the sheet: the front view's model
# bbox is +/-7.5 in X and -7.5..35.5 in Y, so at 2:1 it is 30 x 86 mm and the
# left flank view beside it is 16 x 86.  The face view keeps the clear column
# to its LEFT for the two seat dimensions measured off the pivot axis and the
# column to its RIGHT for the leadered sizes, so no two dimension lanes cross.
# The scallop detail sits in the empty lower-left quarter, under that left
# column.  Each end radius is labelled almost straight below/above its own arc
# while that bore's roughness symbol leads away to the LEFT of it: the two
# leaders leave the same crowded corner on diverging paths and never cross,
# and the symbol's text ends before the radius label begins.
FRONT_BBOX_CY = (C2C + 2.0 * R_END) / 2.0 - R_END
FRONT_CENTER = (0.150, 0.150)
LEFT_CENTER = (0.240, 0.150)
ISO_CENTER = (0.350, 0.215)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


def _flank_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the left view (same bbox as the front)."""
    return LEFT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


# DETAIL A: a native detail of the face view, fenced around the pivot bore so
# it holds the COMPLETE pivot bore and its centre mark: that reachable bore
# axis is the common physical origin for every relief-centre coordinate.  The
# fence also holds both scallop centres (in the air beside the strap) and both
# bites.  3:1 turns the 6.90 radius into a 21 mm arc the two radius leaders can
# land on separately.  The native caption goes to the detail's right (the sheet
# border is too close underneath), and the fence's own letter stays clear of
# the follower seat on the parent view.
DETAIL_SCALE = (3.0, 1.0)
DETAIL_CENTER = (0.058, 0.072)
DETAIL_FENCE_CENTER_MM = (-7.0, -1.5)
DETAIL_FENCE_RADIUS_MM = 11.5
DETAIL_CAPTION_XY = (0.112, 0.075)
DETAIL_LETTER_XY = (0.116, 0.104)


def _detail_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the detail (3:1, fence-centred)."""
    return (
        DETAIL_CENTER[0]
        + (model_x_mm - DETAIL_FENCE_CENTER_MM[0]) * DETAIL_SCALE[0] / 1000.0
    )


def _detail_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the detail (3:1, fence-centred)."""
    return (
        DETAIL_CENTER[1]
        + (model_y_mm - DETAIL_FENCE_CENTER_MM[1]) * DETAIL_SCALE[0] / 1000.0
    )


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The face features and their locations stay on the front view; the
# two bore diameters and the end radii on its closed right side, the seat's
# height and depth on its open left side.
FRONT_KEEP = {
    "PivotBoreDia": (0.196, 0.086),
    "ArborBoreDia": (0.196, 0.214),
    "ArborBoreCz": (0.180, 0.151),
    "BottomCapRadius": (0.164, 0.062),
    "TopCapRadius": (0.164, 0.238),
    "PinSeatCy": (0.088, 0.134),
    "PinSeatDepth": (0.100, 0.158),
}
# The scallop pair is dimensioned in the enlarged detail the way it is cut:
# each centre from the pivot axis (X stacked above the fence, the shorter one
# inside; Y beside it on the open left) and each cutter radius leadered from
# its own visible bite, the park bite above the crossover and the engaged bite
# below it, so neither leader lands on the virtual circle in the air the way
# both did at 2:1.
DETAIL_KEEP = {
    "CamReliefParkR": (0.100, 0.090),
    "CamReliefParkX": (0.068, 0.115),
    "CamReliefParkY": (0.031, 0.084),
    "CamReliefEngagedR": (0.100, 0.048),
    "CamReliefEngagedX": (0.068, 0.106),
    "CamReliefEngagedY": (0.031, 0.064),
}
# The seat's own plane: its mouth circle is solid here, so its size and its
# station through the bar are dimensioned on real geometry.
LEFT_KEEP = {
    "Depth": (0.240, 0.212),
    "PinSeatCz": (0.240, 0.090),
    "PinSeatDia": (0.290, 0.140),
}
# The flank's top and bottom edges are the strap's two extreme lines.  Put the
# overall outside the flank on its clear LEFT, between the aligned views, so
# neither its dimension line nor its short witness lines cross the follower-
# seat size leader on the flank's right.
OVERALL_XY = (0.212, 0.168)
# Each bore's roughness symbol leads out to the upper/lower LEFT of its arc
# and that same bore's end-radius label sits to the upper/lower RIGHT, so the
# two leaders leaving the same crowded corner diverge instead of crossing and
# the symbol's "Ra" text stops short of the radius label.
PIVOT_FINISH_EDGE = (_front_x(0.0), _front_y(-PIVOT_BORE / 2.0))
PIVOT_FINISH_XY = (0.128, 0.086)
ARBOR_FINISH_EDGE = (_front_x(0.0), _front_y(C2C + ARBOR_BORE / 2.0))
ARBOR_FINISH_XY = (0.108, 0.222)
# A callout says only what a dimension cannot: how the feature is made, where
# it stops, and -- for the one dimension held finer than the general grade --
# why it is held there.  Naming both follower-seat annotations ties the native
# diameter and native depth together without copying either model value into
# note text; the depth then reads explicitly from the depicted entry face.
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU",
    "ArborBoreDia": "REAM THRU",
    "PinSeatDia": "FOLLOWER SEAT\nREAM; FLAT-BOTTOM BLIND",
    "PinSeatDepth": "FOLLOWER SEAT\nREAM DEPTH\nFROM ENTRY FACE",
    "PinSeatCy": "CAM ENGAGE CLEARANCE\nHOLD FINE GRADE",
}


def _cam_relief_detail(adapter: Any, front: Any) -> Any:
    """Enlarge the scallops as a native detail of the face view.

    The fence is sketched in the parent's own sketch space (its
    ``ModelToSketchTransform``), the way the cylinder-gear notch and the
    top-frame underside details are, and the detail is then re-centred on its
    OUTLINE because SolidWorks places a detail by its parent-relative origin,
    not by the fenced region.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate scallop detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        (DETAIL_FENCE_CENTER_MM[0] / 1000.0, DETAIL_FENCE_CENTER_MM[1] / 1000.0, 0.0),
        label="scallop detail centre",
    )
    radius = DETAIL_FENCE_RADIUS_MM * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
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
        raise RuntimeError("failed to create native scallop detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *DETAIL_CENTER, 0.0, 0, *DETAIL_SCALE, "A", 1, True, False, False, 5
    )
    if detail is None:
        raise RuntimeError("failed to create native scallop detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_cam_relief_detail")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("native scallop detail has invalid initial bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position native scallop detail")
    rebuild_drawing(adapter, label="_cam_relief_detail")
    outline = tuple(float(value) for value in detail.GetOutline())
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(outline) != 4 or len(ratio) != 2:
        raise RuntimeError("native scallop detail has invalid final bounds")
    center = tuple((outline[axis] + outline[axis + 2]) / 2 for axis in range(2))
    if not math.isclose(ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1]):
        raise RuntimeError("native scallop detail scale did not persist")
    if math.dist(center, DETAIL_CENTER) > 0.0001:
        raise RuntimeError(f"native scallop detail centre did not persist: {center}")
    _position_detail_caption(adapter, detail)
    _position_fence_letter(adapter, detail)
    return detail


def _position_detail_caption(adapter: Any, detail: Any) -> None:
    """Move the native "DETAIL A / SCALE 3:1" caption without replacing its
    linked fields; SolidWorks drops it under the view, below the border here."""
    view = _early_bound(detail, "IView")
    candidates = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        # GetText is blank at this point; the native view-label fields persist.
        if all(
            token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")
        ):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one native linked detail caption, found {len(candidates)}"
        )
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*DETAIL_CAPTION_XY, 0.0):
        raise RuntimeError("failed to position native detail caption")
    rebuild_drawing(adapter, label="_position_detail_caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], DETAIL_CAPTION_XY) > 1e-6:
        raise RuntimeError("native detail caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("detail caption lost its native view-label fields")


def _position_fence_letter(adapter: Any, detail: Any) -> None:
    """Keep the fence's A on the face view off the pivot bore and its leaders."""
    circle = _early_bound(_early_bound(detail, "IView").GetDetail(), "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    rebuild_drawing(adapter, label="_position_fence_letter")
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"fence letter position did not persist: {actual}")


def _overall_reference(adapter: Any, left: Any) -> None:
    """The (43.0) overall between the flank's top and bottom runs.

    Both end caps are half-cylinders whose axes run through the bar, so the
    flank shows each as a SILHOUETTE line, not a model edge (the cap's own
    edges are the two arcs on the faces): an EDGE pick there finds nothing
    (farm iter9).
    """
    display = add_edge_dimension(
        adapter,
        left,
        p0=(LEFT_CENTER[0], _flank_y(C2C + R_END)),
        p1=(LEFT_CENTER[0], _flank_y(-R_END)),
        text_xy=OVERALL_XY,
        label="overall length reference",
        orientation="vertical",
        entity_type="SILHOUETTE",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_LENGTH) > 1e-5:
        raise RuntimeError(
            f"overall length reference measured {measured_mm:g}, "
            f"expected {OVERALL_LENGTH:g} mm"
        )
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="overall length reference"
    )
    # A derived reference has no part-side precision to import; the spec owns
    # the digit (policy rule 2).
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall length reference precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-bracket source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Swing Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion swing bracket; manufacturing drawing; pivot strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    detail = _cam_relief_detail(adapter, front)
    # Only ONE feature on this strap is invisible in outline -- the blind
    # follower seat -- and only the face view sees it, so only the face view
    # carries hidden lines.  Both bores and both scallops go clean through,
    # so nothing else turns dashed; the flank and the scallop detail stay
    # clean (the seat's nick by the park scallop is a visible edge there).
    set_hidden_lines_visible(adapter, front)
    for view in (left, iso, detail):
        set_hidden_lines_removed(adapter, view)

    # The complete pivot bore is the relief coordinates' reachable physical
    # origin.  Mark its axis in the enlarged detail before importing the
    # origin-based scallop dimensions, so their common baseline is visible.
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to mark pivot-bore origin in scallop detail")

    # The detail claims the scallop dimensions before the parent import.
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="scallop detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="strap face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The seat profile is authored on a Right-parallel plane, so its size and
    # its station through the bar are native to this flank view; the face
    # import above rejects the two it does not place, which returns them to
    # the import pool.
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="seat flank",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*detail_annotations, *front_annotations, *left_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Decimal places are the tolerance statement and the part owns them; this
    # sheet only proves the import kept them (policy rule 2).
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _overall_reference(adapter, left)

    for view, label in ((front, "strap face"), (left, "seat flank")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Both bores run: the torque shaft in the lower one, the pinion arbor in
    # the upper one.  Nothing else on the strap slides, seats or locates.
    add_surface_finish(
        adapter,
        front,
        edge_xy=PIVOT_FINISH_EDGE,
        symbol_xy=PIVOT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=ARBOR_FINISH_EDGE,
        symbol_xy=ARBOR_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Swing Bracket Manufacturing Drawing",
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
