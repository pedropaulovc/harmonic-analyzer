r"""Create the pinion-handle manufacturing drawing under the simplicity policy.

The turned body is shown horizontally, with baseline lengths from the flat
socket end. An axial section exposes the blind socket; the body-only top view
exposes the transverse reamed hole before the rod is pressed. The assembled
front view is rotated so the cross rod lies horizontally. Source geometry and
native model fits remain authoritative; no drawing text substitutes for them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_handle.py pinion-handle
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
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_handle_spec import (
    CAP_SAG,
    GRIP_DIA,
    GRIP_LEN,
    ROD_DOWN,
    ROD_HOLE_DIA,
    ROD_SPAN,
    TUBE_LEN,
    TUBE_OD,
    WALL_T,
)
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
SECTION_CENTER = (0.295, 0.140)
ASSEMBLED_CENTER = (0.115, 0.058)
ROD_END_CENTER = (0.220, 0.050)
ISO_CENTER = (0.355, 0.225)
SECTION_SCALE = (3, 1)

# Import in the actual authoring planes, then MOVE the native dimensions to
# their manufacturing views. Importing these names directly into *Right gives
# no dimensions: the circle sketches were authored normal to the arbor axis.
FRONT_KEEP = {
    "GripDia": (0.035, 0.175),
    "TubeOd": (0.035, 0.155),
}
TOP_KEEP = {"RodHoleDia": (0.120, 0.255), "CapR": (0.035, 0.235)}
SECTION_KEEP = {"TubeLen": (0.310, 0.179), "TubeId": (0.355, 0.140)}
ASSEMBLED_KEEP = {"RodSpan": (0.115, 0.024)}
ROD_END_KEEP = {"RodDia": (0.220, 0.078)}
SIDE_DIAMETERS = {"GripDia": (0.228, 0.173), "TubeOd": (0.140, 0.178)}
ROD_DIAMETER_XY = (0.168, 0.081)
DIMENSION_CALLOUTS = {
    "TubeId": "REAM",
    "TubeLen": "BORE DEPTH",
    "RodHoleDia": "REAM THRU",
    "RodSpan": "OAL",
}
DIMENSION_PRECISION = {
    "GripDia": 2,
    "TubeOd": 2,
    "TubeId": 3,
    "TubeLen": 2,
    "CapR": 2,
    "RodHoleDia": 3,
    "RodDia": 4,
    "RodSpan": 2,
}

HUB_END_Z = GRIP_LEN / 2.0 + WALL_T + TUBE_LEN
CROWN_ROOT_Z = -GRIP_LEN / 2.0
CROWN_TIP_Z = CROWN_ROOT_Z - CAP_SAG
SHOULDER_Z = GRIP_LEN / 2.0
BODY_OVERALL = HUB_END_Z - CROWN_TIP_Z


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


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    orientation: str,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    center: bool = False,
    maximum: bool = False,
) -> Any:
    display = add_edge_dimension(
        adapter,
        view,
        p0=_point(adapter, view, p0),
        p1=_point(adapter, view, p1),
        text_xy=text_xy,
        label=label,
        orientation=orientation,
        entity_types=entity_types,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    if maximum:
        set_arc_endpoints_to_max(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    measured_mm = (
        float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    )
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    return display


def _add_body_centerline(adapter: Any, view: Any) -> None:
    """Use the two visible socket flanks, as in the pen-marker recipe."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate body centerline view")
    draw.ClearSelection2(True)
    station = SHOULDER_Z + WALL_T + TUBE_LEN / 2.0
    for index, side in enumerate((-1.0, 1.0)):
        x, y = _point(adapter, view, (0.0, side * TUBE_OD / 2.0, station))
        if not draw.Extension.SelectByID2(
            "", "SILHOUETTE", x, y, 0.0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError("failed to select body centerline socket flank")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError("failed to insert centerline between socket flanks")
    # SOLIDWORKS also generates axes for the omitted rod and coaxial body faces.
    # Retain one native turning axis by its sheet geometry, never annotation IDs.
    native_view = _early_bound(view, "IView")
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
    for view, label in (
        (front, "body end"),
        (right, "body side"),
        (top, "body cross-hole"),
    ):
        _isolate_body(adapter, view, body, label=label)
        set_hidden_lines_visible(adapter, view)

    # Cut the turned body through the arbor axis, without sectioning a pressed
    # rod across the socket. The section replaces dimensions to hidden bore edges.
    cut_center = _point(adapter, front, (0.0, 0.0, 0.0))
    section = create_section_view(
        adapter,
        front,
        line_start=(cut_center[0], cut_center[1] - 0.023),
        line_end=(cut_center[0], cut_center[1] + 0.023),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="turned-body axial socket section",
    )
    set_hidden_lines_visible(adapter, section)
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
    assembled_annotations = curate_view_dimensions(
        adapter, assembled, keep=ASSEMBLED_KEEP, view_label="assembled rod"
    )
    rod_annotations = curate_view_dimensions(
        adapter, rod_end, keep=ROD_END_KEEP, view_label="rod end"
    )
    annotations = [*top_annotations, *section_annotations, *assembled_annotations]
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
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)

    # Visible shoulders and crown root, all measured from the flat socket end.
    end = (0.0, TUBE_OD / 4.0, HUB_END_Z)
    for station, y, expected, label in (
        (SHOULDER_Z, 0.188, HUB_END_Z - SHOULDER_Z, "hub projection"),
        (CROWN_ROOT_Z, 0.202, HUB_END_Z - CROWN_ROOT_Z, "socket end to crown root"),
    ):
        _checked_dimension(
            adapter,
            right,
            p0=end,
            p1=(0.0, (TUBE_OD + GRIP_DIA) / 4.0, station),
            text_xy=(RIGHT_CENTER[0], y),
            label=label,
            expected_mm=expected,
            orientation="horizontal",
        )
    _checked_dimension(
        adapter,
        right,
        p0=end,
        p1=(0.0, 0.0, CROWN_TIP_Z),
        text_xy=(RIGHT_CENTER[0], 0.219),
        label="body overall length",
        expected_mm=BODY_OVERALL,
        orientation="horizontal",
        entity_types=("EDGE", "SILHOUETTE"),
        maximum=True,
    )
    _checked_dimension(
        adapter,
        top,
        p0=(TUBE_OD / 4.0, 0.0, HUB_END_Z),
        p1=(0.0, 0.0, ROD_HOLE_DIA / 2.0),
        text_xy=(0.122, 0.223),
        label="socket end to cross-hole axis",
        expected_mm=HUB_END_Z,
        orientation="vertical",
        center=True,
    )
    _checked_dimension(
        adapter,
        assembled,
        p0=(GRIP_DIA / 2.0, 0.0, CROWN_ROOT_Z),
        p1=(0.0, -ROD_DOWN, 0.0),
        text_xy=(0.080, 0.093),
        label="rod placement from body axis",
        expected_mm=ROD_DOWN,
        orientation="horizontal",
        center=True,
    )

    for view, label in ((front, "body end"), (top, "cross-hole")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add center marks to {label}")
    _add_body_centerline(adapter, right)
    for text, xy in (
        ("BODY", (0.158, 0.120)),
        ("BODY CROSS-HOLE", (0.047, 0.195)),
        ("ASSEMBLED", (0.092, 0.038)),
    ):
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to add {text} view caption")
    add_property_linked_note(adapter, "Manufacturing Notes", 0.240, 0.087)
    add_property_linked_note(adapter, "Isometric View Note", 0.322, 0.196)
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
