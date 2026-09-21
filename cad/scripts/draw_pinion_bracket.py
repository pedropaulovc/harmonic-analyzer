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
    create_blank_drawing_sheets,
    create_section_view,
    check_drawing_layout,
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
    PIN_DROP,
    PIN_SEAT,
    DRAWING_REFERENCE_PRECISION,
    OVERALL_LENGTH,
    PIVOT_BORE,
    R_END,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    add_note,
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
SHEET_NAMES = ("MAIN", "RELIEF")
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters). The third-angle left view belongs to the LEFT of the
# front view. That leaves the lane between them for the follower-seat location,
# while the bore sizes and radii remain outside the front silhouette.
FRONT_BBOX_CY = (C2C + 2.0 * R_END) / 2.0 - R_END
FRONT_CENTER = (0.210, 0.150)
LEFT_CENTER = (0.080, 0.150)
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
# bites.  5:1 separates the near-coincident PARK and ENGAGED X witness lines
# while keeping the coordinate and radius labels inside its native boundary.
# The native caption goes to the detail's right (the sheet border is too close
# underneath), and the fence's own letter stays clear of the follower seat on
# the parent view.
DETAIL_SCALE = (5.0, 1.0)
DETAIL_CENTER = (0.160, 0.145)
DETAIL_FENCE_CENTER_MM = (-7.0, -1.5)
DETAIL_FENCE_RADIUS_MM = 11.5
DETAIL_CAPTION_XY = (0.270, 0.085)
DETAIL_LETTER_XY = (0.225, 0.100)


def _detail_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the native detail."""
    return (
        DETAIL_CENTER[0]
        + (model_x_mm - DETAIL_FENCE_CENTER_MM[0]) * DETAIL_SCALE[0] / 1000.0
    )


def _detail_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the native detail."""
    return (
        DETAIL_CENTER[1]
        + (model_y_mm - DETAIL_FENCE_CENTER_MM[1]) * DETAIL_SCALE[0] / 1000.0
    )


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position. The front view carries the upper bore and end radii. The side view
# owns every follower-seat dimension so that its axis is located from visible
# geometry; the relief detail owns the lower pivot bore, and the seat section
# owns depth.
FRONT_KEEP = {
    "ArborBoreDia": (0.256, 0.214),
    "ArborBoreCz": (0.240, 0.151),
    "BottomCapRadius": (0.250, 0.080),
    "TopCapRadius": (0.188, 0.245),
}
# The scallop pair is dimensioned in the enlarged detail the way it is cut:
# each centre from the pivot axis (X stacked above the fence, the shorter one
# inside; Y beside it on the open left) and each cutter radius leadered from
# its own visible bite, the park bite above the crossover and the engaged bite
# below it, so neither leader lands on the virtual circle in the air the way
# both did at 2:1.
DETAIL_KEEP = {
    "PivotBoreDia": (0.240, 0.155),
    "CamReliefParkR": (0.165, 0.195),
    "CamReliefParkX": (0.080, 0.235),
    "CamReliefParkY": (0.065, 0.175),
    "CamReliefEngagedR": (0.145, 0.075),
    "CamReliefEngagedX": (0.080, 0.220),
    "CamReliefEngagedY": (0.065, 0.125),
}
# The seat's own plane: its mouth circle is solid here, so its size and its
# station through the bar are dimensioned on real geometry.
LEFT_KEEP = {
    "Depth": (0.080, 0.212),
    "PinSeatCz": (0.060, 0.090),
    "PinSeatCy": (0.130, 0.125),
    "PinSeatDia": (0.040, 0.160),
}
SECTION_CENTER = (0.350, 0.115)
SECTION_KEEP = {"PinSeatDepth": (SECTION_CENTER[0], 0.145)}
# The flank's top and bottom edges are the strap's two extreme lines. Put the
# overall on its clear right, between the third-angle left and front views.
OVERALL_XY = (0.112, 0.168)
# The arbor symbol has a short leader to the bore's unobstructed left edge.
ARBOR_FINISH_EDGE = (_front_x(-ARBOR_BORE / 2.0), _front_y(C2C))
ARBOR_FINISH_XY = (0.155, 0.205)
# A callout says only what a dimension cannot: how the feature is made, where
# it stops, and -- for the one dimension held finer than the general grade --
# why it is held there.  Naming both follower-seat annotations ties the native
# diameter and native depth together without copying either model value into
# note text; the depth then reads explicitly from the depicted entry face.
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "REAM THRU",
    "ArborBoreDia": "REAM THRU",
    "PinSeatDia": "FOLLOWER SEAT\nBLIND FLAT-BOTTOM\nREAM",
    "CamReliefParkX": "PARK X",
    "CamReliefParkY": "PARK +Y",
    "CamReliefEngagedX": "ENGAGED X",
    "CamReliefEngagedY": "ENGAGED -Y",
}
PIN_SEAT_DEPTH_CALLOUT = "FOLLOWER SEAT\nREAM DEPTH FROM\nCAM NOTCH FACE"


def _cam_relief_detail(adapter: Any, front: Any) -> Any:
    """Enlarge the scallops as a native detail in the parent's sketch space."""
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
    """Move the native detail caption without replacing its linked fields;
    SolidWorks drops it under the view, below the border here."""
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
    extent = tuple(float(value) for value in note.GetExtent())
    outline = tuple(float(value) for value in view.GetOutline())
    if len(extent) != 6 or len(outline) != 4:
        raise RuntimeError(
            f"cannot measure detail caption clearance: extent={extent!r}, "
            f"outline={outline!r}"
        )
    caption_left = min(extent[0], extent[3])
    view_right = max(outline[0], outline[2])
    gap = caption_left - view_right
    if gap < 0.003:
        raise RuntimeError(
            f"detail caption is not outboard of its view: {gap * 1000:.1f} mm gap"
        )
    _telemetry.info(
        f"detail caption measured outboard: {gap * 1000:.1f} mm gap; "
        f"caption=[{min(extent[0], extent[3]) * 1000:.1f}, "
        f"{min(extent[1], extent[4]) * 1000:.1f}, "
        f"{max(extent[0], extent[3]) * 1000:.1f}, "
        f"{max(extent[1], extent[4]) * 1000:.1f}] mm; "
        f"view=[{min(outline[0], outline[2]) * 1000:.1f}, "
        f"{min(outline[1], outline[3]) * 1000:.1f}, "
        f"{max(outline[0], outline[2]) * 1000:.1f}, "
        f"{max(outline[1], outline[3]) * 1000:.1f}] mm"
    )


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

def _seat_depth_dimension(adapter: Any, section: Any) -> Any:
    """Dimension the visible entry face to blind floor in Section B-B."""
    entry_x = SECTION_CENTER[0] - R_END * 3.0 / 1000.0
    floor_x = entry_x + PIN_SEAT * 3.0 / 1000.0
    display = add_edge_dimension(
        adapter,
        section,
        p0=(entry_x, SECTION_CENTER[1] + 0.009),
        p1=(floor_x, SECTION_CENTER[1]),
        text_xy=SECTION_KEEP["PinSeatDepth"],
        label="follower seat depth",
        orientation="horizontal",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - PIN_SEAT) > 1e-5:
        raise RuntimeError(
            f"follower seat depth measured {measured_mm:g}, expected {PIN_SEAT:g} mm"
        )
    digits = DRAWING_PRECISION_BY_NAME["PinSeatDepth"]
    display.SetPrecision3(digits, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != digits:
        raise RuntimeError("follower seat depth precision did not persist")
    display.SetText(3, PIN_SEAT_DEPTH_CALLOUT)
    return display.GetAnnotation()


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
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="pinion bracket drawing package"
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
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate pinion bracket main sheet")
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, left):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="strap face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="seat flank",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _overall_reference(adapter, left)
    for view, label in ((front, "strap face"), (left, "seat flank")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    add_surface_finish(
        adapter,
        front,
        edge_xy=ARBOR_FINISH_EDGE,
        symbol_xy=ARBOR_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
    )

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate pinion bracket relief sheet")
    detail_parent = place_view(
        adapter, str(SOURCE), "*Front", 0.270, 0.155, scale=(2, 1)
    )
    seat_axis_y = 0.155 + (-PIN_DROP - FRONT_BBOX_CY) * 2.0 / 1000.0
    seat_section = create_section_view(
        adapter,
        detail_parent,
        line_start=(0.230, seat_axis_y),
        line_end=(0.315, seat_axis_y),
        view_xy=SECTION_CENTER,
        section_label="B",
        scale=(3.0, 1.0),
        label="follower seat depth section",
    )
    detail = _cam_relief_detail(adapter, detail_parent)
    for view in (detail_parent, detail, seat_section):
        set_hidden_lines_removed(adapter, view)
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to mark pivot-bore origin in scallop detail")
    if (
        add_note(
            adapter,
            "ALL RELIEF X/Y COORDINATES\nFROM Ø6.35 PIVOT BORE AXIS",
            0.250,
            0.255,
            height=0.0035,
        )
        is None
    ):
        raise RuntimeError("failed to identify relief coordinate origin")
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="scallop detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _seat_depth_dimension(adapter, seat_section)
    if (
        add_note(
            adapter,
            "FOLLOWER SEAT BREAK-OUT\nINTO CAM RELIEF IS INTENDED",
            0.350,
            0.185,
            height=0.0035,
        )
        is None
    ):
        raise RuntimeError("failed to state intended follower-seat break-out")
    add_surface_finish(
        adapter,
        detail,
        edge_xy=(_detail_x(0.0), _detail_y(-PIVOT_BORE / 2.0)),
        symbol_xy=(0.185, 0.110),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )

    annotations = [*front_annotations, *left_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    imported_precision = {
        name: digits
        for name, digits in DRAWING_PRECISION_BY_NAME.items()
        if name != "PinSeatDepth"
    }
    assert_imported_precision(adapter, annotations, imported_precision)

    for index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate sheet {sheet_name!r} for audit")
        if add_note(adapter, f"SHEET {index} OF {len(SHEET_NAMES)}", 0.380, 0.260) is None:
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name!r}")
        rebuild_drawing(adapter, label=f"pinion bracket {sheet_name} layout")
        check_drawing_layout(adapter, layout=SPEC.layout, stem=sheet_name)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Swing Bracket Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
