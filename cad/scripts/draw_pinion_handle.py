r"""Create the pinion-handle manufacturing drawing under the simplicity policy.

The turned body is shown horizontally, with baseline lengths from the flat
socket end. An axial section exposes the blind socket; the body-only top view
exposes the grip cross-hole and the separate handle-to-arbor retention hole.
The assembled front view is rotated so the cross rod lies horizontally. Source
geometry and native model fits remain authoritative; no drawing text
substitutes for them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_handle.py pinion-handle
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _config import title_block
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_arbor_spec import SHAFT_DIA as ARBOR_DIA
from pinion_arbor_spec import SHAFT_DIA_BAND as ARBOR_DIA_BAND
from pinion_handle_spec import (
    CAP_SAG,
    DRAWING_PRECISION_BY_NAME,
    GRIP_DIA,
    GRIP_LEN,
    RETENTION_HOLE_CALLOUT,
    ROD_SPAN,
    TUBE_ID,
    TUBE_LEN,
    TUBE_OD,
    WALL_T,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    delete_view,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_handle"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (2.0, 1.0)
ISO_SCALE = (1.0, 1.0)

# Landscape keeps the body orthographic group aligned and leaves separate lanes
# for the larger section, horizontal rod and standard assembled isometric.
FRONT_CENTER = (0.075, 0.150)
RIGHT_CENTER = (0.175, 0.150)
TOP_CENTER = (0.075, 0.230)
SECTION_CENTER = (0.270, 0.145)
ASSEMBLED_CENTER = (0.115, 0.090)
ROD_END_CENTER = (0.220, 0.050)
ISO_CENTER = (0.325, 0.210)
SECTION_SCALE = (3, 1)

# Import in the actual authoring planes, then MOVE the native dimensions to
# their manufacturing views. Importing these names directly into *Right gives
# no dimensions: the circle sketches were authored normal to the arbor axis.
# The axial stations (hub length, body overall, cross-hole axis, rod reach)
# are the part's reference-sketch dims, each authored on the plane of the
# view that prints it.
FRONT_KEEP = {
    "GripDia": (0.035, 0.175),
    "TubeOd": (0.035, 0.155),
}
RIGHT_KEEP = {
    "HubLen": (RIGHT_CENTER[0], 0.188),
    "BodyLen": (RIGHT_CENTER[0], 0.219),
}
TOP_KEEP = {
    "RodHoleDia": (0.104, 0.215),
    "CapR": (0.020, 0.255),
    "RodHoleZ": (0.122, 0.223),
    "RetentionHoleDia": (0.177, 0.250),
    "RetentionPinFromMouth": (0.145, 0.223),
}
# TubeId's text stands right of the section, under the seating-depth callout:
# its dimension line runs in the 13 mm between the socket mouth (sheet 0.120)
# and the SECTION A-A label (top 0.105); the four-line block clears the
# seating-depth callout above it.  Centred under the view it printed on top of
# that label and against the assembled view's (Ø6.0) rod reference.
SECTION_KEEP = {"TubeLen": (0.322, 0.135), "TubeId": (0.355, 0.116)}
SEATING_DEPTH_TEXT_XY = (0.353, 0.141)
ASSEMBLED_KEEP = {"RodSpan": (0.115, 0.032), "RodDown": (0.080, 0.125)}
ROD_END_KEEP = {"RodDia": (0.220, 0.078)}
SIDE_DIAMETERS = {"GripDia": (0.228, 0.173), "TubeOd": (0.140, 0.178)}
ROD_DIAMETER_XY = (0.202, 0.106)
_HOLE_TOLERANCE = title_block("drilled_hole")
_SOCKET_CLEARANCE_MIN = (
    TUBE_ID + float(_HOLE_TOLERANCE["minus_mm"])
) - (ARBOR_DIA + ARBOR_DIA_BAND[0])
_SOCKET_CLEARANCE_MAX = (
    TUBE_ID + float(_HOLE_TOLERANCE["plus_mm"])
) - (ARBOR_DIA + ARBOR_DIA_BAND[1])
if _SOCKET_CLEARANCE_MIN < 0.0:
    raise AssertionError("title-block socket range interferes with the arbor")
DIMENSION_CALLOUTS = {
    "TubeId": (
        f"REAM FOR {_SOCKET_CLEARANCE_MIN:.2f}-{_SOCKET_CLEARANCE_MAX:.2f}\n"
        "DIAMETRAL CLEARANCE ON\nPINION ARBOR MHA-102"
    ),
    "TubeLen": "SEATING DEPTH",
    "RodHoleDia": "REAM THRU",
    "RetentionHoleDia": RETENTION_HOLE_CALLOUT,
    "RodSpan": "OAL",
}
# Decimal places are the part's (pinion_handle_spec.DRAWING_PRECISION, applied
# by build_pinion_handle); the sheet only reads them back.

HUB_END_Z = GRIP_LEN / 2.0 + WALL_T + TUBE_LEN
CROWN_ROOT_Z = -GRIP_LEN / 2.0
CROWN_TIP_Z = CROWN_ROOT_Z - CAP_SAG


def _source_bodies(model: Any) -> tuple[Any, Any]:
    """Identify the two existing solids by their distinct axial spans."""
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 2:
        raise RuntimeError(f"pinion handle requires two solids, found {len(bodies)}")
    rod, body = [], []
    for raw in bodies:
        candidate = _early_bound(raw, "IBody2")
        box = tuple(float(value) * 1000.0 for value in candidate.GetBodyBox())
        # GetBodyBox is approximate; the rod is over four times the body width.
        (rod if box[4] - box[1] > (ROD_SPAN + GRIP_DIA) / 2.0 else body).append(raw)
    if len(rod) != 1 or len(body) != 1:
        raise RuntimeError("cannot uniquely identify turned body and cross rod")
    return body[0], rod[0]


def _isolate_body(adapter: Any, view: Any, body: Any, *, label: str) -> None:
    native = _early_bound(view, "IView")
    native.Bodies = dispatch_array([body])
    adapter.currentModel.EditRebuild3()
    if int(native.GetBodiesCount()) != 1:
        raise RuntimeError(f"{label}: body isolation did not persist")


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _point(
    adapter: Any, view: Any, xyz_mm: tuple[float, float, float]
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label="handle dimension pick",
    )

def _shorten_radius_leader(
    adapter: Any, annotation: Any, position: tuple[float, float]
) -> None:
    """Shorten the spherical-radius leader, then restore its curated position."""
    native_annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(
        native_annotation.GetSpecificAnnotation(), "IDisplayDimension"
    )
    display.ShortenedRadius = True
    # SolidWorks recentres radial text when ShortenedRadius changes.  Move it
    # only after that transition so the SR callout stays outside the crown.
    if native_annotation.SetPosition2(position[0], position[1], 0.0) is not True:
        raise RuntimeError("failed to restore handle crown-radius position")
    adapter.currentModel.GraphicsRedraw2()
    if display.ShortenedRadius is not True:
        raise RuntimeError("handle crown radius did not retain shortened leader")
    actual = tuple(float(value) for value in (native_annotation.GetPosition() or ()))
    if len(actual) < 2 or any(
        abs(measured - expected) > 1e-6
        for measured, expected in zip(actual[:2], position, strict=True)
    ):
        raise RuntimeError(
            f"handle crown radius position did not persist: {actual!r}"
        )







def _add_body_centerline(adapter: Any, view: Any) -> None:
    """Insert the socket axis from an opposite, overlapping OD-flank pair."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate body centerline view")
    native_view = _early_bound(view, "IView")
    native_view.UpdateViewDisplayGeometry()
    candidates: list[
        tuple[
            Any,
            tuple[float, float, float],
            tuple[float, float, float],
            tuple[float, float, float],
        ]
    ] = []
    components = adapter._attempt(native_view.GetVisibleComponents, default=()) or ()
    for component in components:
        silhouettes = (
            adapter._attempt(
                lambda c=component: native_view.GetVisibleEntities2(c, 4),
                default=(),
            )
            or ()
        )
        for raw_silhouette in silhouettes:
            silhouette = _early_bound(raw_silhouette, "ISilhouetteEdge")
            face = adapter._attempt(silhouette.GetFace)
            if face is None:
                continue
            surface = _early_bound(_early_bound(face, "IFace2").GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            parameters = surface.CylinderParams
            if abs(float(parameters[6]) - TUBE_OD / 2000.0) > 1e-7:
                continue
            start_point = adapter._attempt(silhouette.GetStartPoint)
            end_point = adapter._attempt(silhouette.GetEndPoint)
            if start_point is None or end_point is None:
                continue
            start_data = adapter._get_attr_or_call(start_point, "ArrayData")
            end_data = adapter._get_attr_or_call(end_point, "ArrayData")
            if start_data is None or end_data is None:
                continue
            start = tuple(float(value) for value in start_data[:3])
            end = tuple(float(value) for value in end_data[:3])
            length = math.dist(start, end)
            if length <= 1e-9:
                continue
            direction = tuple((b - a) / length for a, b in zip(start, end))
            candidates.append((silhouette, start, end, direction))
    pairs: list[tuple[float, float, Any, Any]] = []
    expected_separation = TUBE_OD / 1000.0
    for index, (first, first_start, first_end, first_direction) in enumerate(
        candidates
    ):
        for second, second_start, second_end, second_direction in candidates[index + 1 :]:
            alignment = abs(
                sum(a * b for a, b in zip(first_direction, second_direction))
            )
            if alignment < 1.0 - 1e-6:
                continue
            offset = tuple(b - a for a, b in zip(first_start, second_start))
            axial_offset = sum(
                value * axis for value, axis in zip(offset, first_direction)
            )
            radial_offset = tuple(
                value - axial_offset * axis
                for value, axis in zip(offset, first_direction)
            )
            separation = math.sqrt(sum(value * value for value in radial_offset))
            if separation < 0.8 * expected_separation:
                continue
            first_interval = sorted(
                (
                    sum(a * b for a, b in zip(first_start, first_direction)),
                    sum(a * b for a, b in zip(first_end, first_direction)),
                )
            )
            second_interval = sorted(
                (
                    sum(a * b for a, b in zip(second_start, first_direction)),
                    sum(a * b for a, b in zip(second_end, first_direction)),
                )
            )
            overlap = min(first_interval[1], second_interval[1]) - max(
                first_interval[0], second_interval[0]
            )
            if overlap > 1e-6:
                pairs.append(
                    (
                        overlap,
                        abs(separation - expected_separation),
                        first,
                        second,
                    )
                )
    if not pairs:
        raise RuntimeError("socket OD has no opposite overlapping silhouette pair")
    overlap, separation_error, first, second = max(
        pairs, key=lambda item: (item[0], -item[1])
    )
    if separation_error > 2e-4:
        raise RuntimeError(
            f"socket flank separation misses OD by {separation_error * 1000:g} mm"
        )
    if overlap < 1e-3:
        raise RuntimeError("socket flank pair has less than 1 mm axial overlap")
    flanks = (first, second)
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = _early_bound(selection_manager.CreateSelectData(), "ISelectData")
    selection_data.View = view
    for index, flank in enumerate(flanks):
        selectable = _sw_type_info.early_bound_or_flag(
            flank, "ISilhouetteEdge", "Select2"
        )
        if not bool(selectable.Select2(index > 0, selection_data)):
            raise RuntimeError(
                f"failed to select enumerated socket flank {index + 1}"
            )
    if int(selection_manager.GetSelectedObjectCount2(-1)) != 2:
        raise RuntimeError("body centerline socket-flank selection was not a pair")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError("failed to insert centerline between socket flanks")
    # SOLIDWORKS also generates axes for the omitted rod and coaxial body faces.
    axis_y = _point(adapter, view, (0.0, 0.0, 0.0))[1]
    body_x = sorted(
        _point(adapter, view, (0.0, 0.0, z))[0] for z in (CROWN_TIP_Z, HUB_END_Z)
    )
    centerlines = []
    candidates = []
    for item in native_view.GetCenterLines() or ():
        annotation = _early_bound(
            _early_bound(item, "ICenterLine").GetAnnotation(), "IAnnotation"
        )
        centerlines.append(annotation)
        data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
        lines = [data.GetLineAtIndex3(index) for index in range(data.GetLineCount())]
        if not lines or any(
            abs(line[5] - axis_y) > 1e-7 or abs(line[8] - axis_y) > 1e-7
            for line in lines
        ):
            continue
        left = min(min(line[4], line[7]) for line in lines)
        right = max(max(line[4], line[7]) for line in lines)
        if left < body_x[1] and right > body_x[0]:
            candidates.append((right - left, annotation))
    if not candidates:
        raise RuntimeError(
            "no native centerline follows the visible body's turning axis"
        )
    keeper = max(candidates, key=lambda candidate: candidate[0])[1]
    for annotation in centerlines:
        if annotation is keeper:
            continue
        selection_name = f"{annotation.GetName()}@{view_name(adapter, view)}"
        if not draw.Extension.SelectByID2(
            selection_name, "CENTERLINE", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(
                f"failed to select generated body-view axis {selection_name!r}"
            )
        if not draw.Extension.DeleteSelection2(0):
            raise RuntimeError("failed to delete extra generated body-view axis")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if native_view.GetCenterLineCount() != 1:
        raise RuntimeError("body view must contain only its horizontal turning axis")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open pinion-handle source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    body, rod = _source_bodies(source_model)
    properties = (
        "Number",
        "Revision",
        "Title",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        source_model,
        properties,
        required=tuple(
            name for name in properties if name not in {"Revision", "Title"}
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Turning Handle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion turning handle; turned body; press-fit cross rod; blind socket",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    # Hidden lines are removed from every orthographic view: section A-A
    # already shows the blind socket, while the body-only top view shows both
    # transverse holes directly as solid circles.  The assembled view below
    # keeps hidden lines because it is the only place the pressed grip rod's
    # engagement inside the body is shown.
    for view, label in (
        (front, "body end"),
        (right, "body side"),
        (top, "body cross-hole"),
    ):
        _isolate_body(adapter, view, body, label=label)
        set_hidden_lines_removed(adapter, view)

    # The XZ section contains the arbor axis and cuts normal to the omitted
    # cross rod, exposing its circular hole as well as the blind axial socket.
    cut_center = _point(adapter, front, (0.0, 0.0, 0.0))
    section = create_section_view(
        adapter,
        front,
        line_start=(cut_center[0] - 0.023, cut_center[1]),
        line_end=(cut_center[0] + 0.023, cut_center[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="turned-body axial socket section",
    )
    # Sections are always hidden-lines-removed: the dashed chord across the
    # hatched cap only said the cut had been drawn through it twice.
    set_hidden_lines_removed(adapter, section)
    assembled = place_view(
        adapter, str(SOURCE), "*Front", *ASSEMBLED_CENTER, scale=SHEET_SCALE
    )
    _early_bound(assembled, "IView").Angle = -math.pi / 2.0
    if (
        abs(
            math.remainder(
                float(_early_bound(assembled, "IView").Angle) + math.pi / 2.0,
                2.0 * math.pi,
            )
        )
        > 1e-9
    ):
        raise RuntimeError("failed to orient the cross rod horizontally")
    adapter.currentModel.EditRebuild3()
    set_hidden_lines_visible(adapter, assembled)
    rod_end = place_view(
        adapter, str(SOURCE), "*Top", *ROD_END_CENTER, scale=SHEET_SCALE
    )
    _isolate_body(adapter, rod_end, rod, label="cross-rod end")
    set_hidden_lines_visible(adapter, rod_end)
    # The shared finalizer sets and verifies precision Shaded With Edges and
    # high-quality cosmetic threads for every standard isometric.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="body end"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="body cross-hole"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="socket section"
    )
    # After the section has claimed TubeLen: the body side view imports only
    # the Right-plane reference sketch's hub length and body overall.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="body side"
    )
    assembled_annotations = curate_view_dimensions(
        adapter, assembled, keep=ASSEMBLED_KEEP, view_label="assembled rod"
    )
    rod_annotations = curate_view_dimensions(
        adapter, rod_end, keep=ROD_END_KEEP, view_label="rod end"
    )
    annotations = [
        *top_annotations,
        *section_annotations,
        *right_annotations,
        *assembled_annotations,
    ]
    for annotation in front_annotations:
        name = dimension_name(adapter, annotation)
        annotations.append(
            _move_dimension(
                adapter, annotation, right, SIDE_DIAMETERS[name], source_view=front
            )
        )
    annotations.append(
        _move_dimension(
            adapter, rod_annotations[0], assembled, ROD_DIAMETER_XY, source_view=rod_end
        )
    )
    # Its diameter is now native to the assembled side view; a blank rod-end
    # donor supplies no manufacturing information and is not part of the sheet.
    donor_name = view_name(adapter, rod_end)
    # The vendor helper currently casts void EditDelete() to false. Verify
    # deletion against the native sheet view collection, not that return value.
    delete_view(adapter, rod_end)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty rod-dimension donor view")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    cap_radius = [
        annotation
        for annotation in top_annotations
        if dimension_name(adapter, annotation) == "CapR"
    ]
    if len(cap_radius) != 1:
        raise RuntimeError("expected one handle crown-radius dimension")
    _shorten_radius_leader(adapter, cap_radius[0], TOP_KEEP["CapR"])
    # Every place the part authored (policy rule 2) must have survived the
    # import and the moves: a dimension that fell back to the sheet default
    # would print a band nobody specified.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, {"RodDia"})
    offset_dimension_text(adapter, annotations, {"TubeLen": SEATING_DEPTH_TEXT_XY})


    for view, label in ((front, "body end"), (top, "cross-hole")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add center marks to {label}")
    _add_body_centerline(adapter, right)
    for text, xy in (
        ("BODY", (0.158, 0.120)),
        ("BODY CROSS-HOLES", (0.047, 0.195)),
        ("CROSS ROD IN BODY", (0.058, 0.068)),
    ):
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to add {text} view caption")
    add_property_linked_note(adapter, "Manufacturing Notes", 0.058, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.292, 0.181)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Turning Handle Manufacturing Drawing",
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
