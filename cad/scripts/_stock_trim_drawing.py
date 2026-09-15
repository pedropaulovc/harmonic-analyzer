"""Shared sheet machinery for the modified-purchased-stock (trim) drawings.

Both stock anchors take the SAME sheet recipe: a Front view carrying the
finished overall length, a magnified detail of the real cut end carrying the
restored 45 deg deburr, and an isometric. Only the sheet constants and the
acceptance bands differ per part, so the COM machinery lives here and each
``draw_*`` script owns its layout (``TrimSheet``) and its expected controls.

Nothing here opens or saves a document; the caller drives the sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from _common import _early_bound, _read_member
from _drawing_common import dimension_name, model_point_in_view
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import view_name


@dataclass(frozen=True)
class TrimSheet:
    """Per-part sheet constants for one modified-stock manufacturing drawing."""

    sheet_scale: tuple[float, float]
    detail_center: tuple[float, float]
    detail_scale: tuple[float, float]
    fence_radius_mm: float
    cut_end_y_mm: float
    detail_offset_mm: float
    detail_label_xy: tuple[float, float]
    parent_letter_offset: tuple[float, float]

    @property
    def detail_reference_mm(self) -> tuple[float, float, float]:
        """Model point the detail fence and the parent letter both key on."""
        return (0.0, self.cut_end_y_mm + self.detail_offset_mm, 0.0)


def end_detail(adapter: Any, front: Any, sheet: TrimSheet) -> Any:
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
        tuple(value / 1000 for value in sheet.detail_reference_mm),
        label="cut end detail center",
    )
    radius = sheet.fence_radius_mm * sheet.sheet_scale[0] / sheet.sheet_scale[1] / 1000
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
        *sheet.detail_center, 0.0, 0, *sheet.detail_scale, "A", 1, True, False, False, 5
    )
    if detail is None:
        raise RuntimeError("cannot create native cut-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(sheet.detail_scale))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("invalid cut-end detail bounds")
    target = [
        position[i] + sheet.detail_center[i] - (outline[i] + outline[i + 2]) / 2
        for i in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("cannot position cut-end detail")
    draw.EditRebuild3()
    if tuple(float(value) for value in detail.ScaleRatio) != sheet.detail_scale:
        raise RuntimeError("cut-end detail scale did not persist")
    return detail


def position_detail_label(adapter: Any, detail: Any, sheet: TrimSheet) -> None:
    """Move the native dynamic label beside the detail, clear of the title block."""
    # Pin the final sheet scale before positioning a dynamic label; changing
    # it during finalization moves the label after its readback has passed.
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not current.SetScale(*sheet.sheet_scale, False, False):
        raise RuntimeError("cannot pin sheet scale before detail label placement")
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*sheet.detail_label_xy, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("cannot position native detail label")
    adapter.currentModel.EditRebuild3()
    if math.dist(tuple(_read_member(annotation, "GetPosition")), target) > 1e-8:
        raise RuntimeError("native detail label position did not persist")


def position_parent_detail_letter(adapter: Any, front: Any, sheet: TrimSheet) -> None:
    """Keep the native parent-circle A clear of the cut-end extension line."""
    circles = tuple(
        _read_member(_early_bound(front, "IView"), "GetDetailCircles") or ()
    )
    if len(circles) != 1:
        raise RuntimeError(f"expected one parent detail circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    center = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000 for value in sheet.detail_reference_mm),
        label="parent detail letter reference",
    )
    target = tuple(center[i] + sheet.parent_letter_offset[i] for i in range(2))
    circle.SetLabelPosition(*target)
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, target) > 1e-8:
        raise RuntimeError(
            f"parent detail-circle label position did not persist: {actual}"
        )


def verify_machining_controls(
    adapter: Any,
    annotations: list[Any],
    *,
    expected: dict[str, tuple[float, float, float]],
    tolerance_types: dict[str, int],
    precision: dict[str, int],
) -> None:
    """Re-read every cutting control: driving, nominal, band and printed digits.

    ``expected`` maps a dimension name to its (nominal, lower, upper) SI values
    -- signed deviations, so a unilateral trim band and a symmetric deburr band
    are checked by the same walk. A control that silently became reference-only,
    lost its band or moved is a drawing regression, never a cosmetic drift.
    """
    remaining = dict(expected)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        nominal, lower, upper = remaining.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(dimension.DrivenState) != 2 or "(" in str(display.GetText(1) or ""):
            raise RuntimeError(f"{name}: machining control became reference-only")
        if not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9):
            raise RuntimeError(f"{name}: native dimension nominal changed")
        if (
            int(tolerance.Type) != tolerance_types[name]
            or not math.isclose(float(tolerance.GetMinValue()), lower, abs_tol=1e-9)
            or not math.isclose(float(tolerance.GetMaxValue()), upper, abs_tol=1e-9)
        ):
            raise RuntimeError(f"{name}: native tolerance changed")
        if int(display.GetPrimaryPrecision2()) != precision[name]:
            raise RuntimeError(f"{name}: native display precision changed")
    if remaining:
        raise RuntimeError(f"missing machining controls: {sorted(remaining)}")
