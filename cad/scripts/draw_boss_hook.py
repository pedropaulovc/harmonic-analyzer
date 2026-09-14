"""Create the manufacturing drawing for the modified McMaster 9490T1 anchor."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_precision,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from boss_hook_spec import (
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    TRIM,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name

SPEC = DRAWINGS_BY_NAME["boss_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = (2.0, 1.0)
FRONT_CENTER = (0.100, 0.165)
ISO_CENTER = (0.310, 0.213)
DETAIL_CENTER = (0.280, 0.115)
DETAIL_SCALE = (12.0, 1.0)
FRONT_KEEP = {"FinishedOverall": (0.040, 0.165)}
DETAIL_KEEP = {"ChamferWidth": (0.235, 0.090), "ChamferAngle": (0.340, 0.115)}


def _end_detail(adapter: Any, front: Any) -> Any:
    """Crop the real cut end; transform the fence as in the cylinder-gear recipe."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("cannot activate cut-end detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        (0.0, (TRIM.shank_end_y_mm + 1.0) / 1000, 0.0),
        label="cut end detail center",
    )
    radius = 3.2 * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
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
        raise RuntimeError("cannot create native cut-end detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *DETAIL_CENTER, 0.0, 0, *DETAIL_SCALE, "A", 1, True, False, False, 5
    )
    if detail is None:
        raise RuntimeError("cannot create native cut-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(DETAIL_SCALE))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("invalid cut-end detail bounds")
    target = [
        position[i] + DETAIL_CENTER[i] - (outline[i] + outline[i + 2]) / 2
        for i in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("cannot position cut-end detail")
    draw.EditRebuild3()
    if tuple(float(value) for value in detail.ScaleRatio) != DETAIL_SCALE:
        raise RuntimeError("cut-end detail scale did not persist")
    return detail


def _position_detail_label(adapter: Any, detail: Any) -> None:
    """Move the native dynamic label beside the detail, clear of the title block."""
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (0.360, 0.085, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("cannot position native detail label")
    adapter.currentModel.EditRebuild3()
    if math.dist(tuple(_read_member(annotation, "GetPosition")), target) > 1e-8:
        raise RuntimeError("native detail label position did not persist")


def _position_parent_detail_letter(adapter: Any, front: Any) -> None:
    """Keep the native parent-circle A above/right of the cut-end extension."""
    circles = tuple(_read_member(_early_bound(front, "IView"), "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one parent detail circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    center = model_point_in_view(
        adapter, front, (0.0, (TRIM.shank_end_y_mm + 1.0) / 1000, 0.0),
        label="parent detail letter reference",
    )
    target = (center[0] + 0.020, center[1] + 0.014)
    circle.SetLabelPosition(*target)
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, target) > 1e-8:
        raise RuntimeError(f"parent detail-circle label position did not persist: {actual}")


def _verify_controls(adapter: Any, annotations: list[Any]) -> None:
    expected = {
        "FinishedOverall": (
            FINISHED_OVERALL_MM / 1000,
            FINISHED_OVERALL_TOLERANCE_MM / 1000,
        ),
        "ChamferWidth": (CHAMFER_WIDTH_MM / 1000, CHAMFER_WIDTH_TOLERANCE_MM / 1000),
        "ChamferAngle": (
            math.radians(CHAMFER_ANGLE_DEG),
            math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        ),
    }
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        nominal, band = expected.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(dimension.DrivenState) != 2 or "(" in str(display.GetText(1) or ""):
            raise RuntimeError(f"{name}: machining control became reference-only")
        if not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9):
            raise RuntimeError(f"{name}: native dimension nominal changed")
        if (
            int(tolerance.Type) != DIMENSION_TOLERANCE_TYPES[name]
            or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
            or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
        ):
            raise RuntimeError(f"{name}: native tolerance changed")
        if int(display.GetPrimaryPrecision2()) != DIMENSION_PRECISION[name]:
            raise RuntimeError(f"{name}: native display precision changed")
    if expected:
        raise RuntimeError(f"missing machining controls: {sorted(expected)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified anchor", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Counter Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-005; McMaster-Carr 9490T1",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_visible(adapter, front)
    detail = _end_detail(adapter, front)
    set_hidden_lines_visible(adapter, detail)
    # The detail claims its manufacturing dimensions before the parent import.
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="cut end detail"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="finished overall"
    )
    annotations = [*front_annotations, *detail_annotations]
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    _verify_controls(adapter, annotations)
    add_property_linked_note(adapter, "Supplier", 0.016, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.080, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.049, char_height=0.003)
    add_property_linked_note(adapter, "Isometric View Note", 0.275, 0.163)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.083, char_height=0.003
    )
    for view in (front, detail):
        set_hidden_lines_visible(adapter, view)
    _position_detail_label(adapter, detail)
    _position_parent_detail_letter(adapter, front)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Counter Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
