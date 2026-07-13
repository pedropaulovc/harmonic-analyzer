r"""Generate the project-owned ASME B drawing template and sheet format.

Starts from SolidWorks' native B-size drawing/format, retains its border and
zone geometry, removes the vendor title/legal/table content, and installs the
compact property-linked title block used by the hobby-machinist book drawings.

Run with SolidWorks open::

    uv run python cad\scripts\create_drawing_standards.py
"""

from __future__ import annotations

import sys
from typing import Any

import _telemetry
from _common import _early_bound, run_build
from _drawing_common import ASME_B_HEIGHT_M, ASME_B_WIDTH_M, assert_asme_b_sheet
from _drawing_registry import ASME_B_DRWDOT, ASME_B_SLDDRT
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    add_third_angle_symbol,
    delete_all_tables,
    new_drawing,
    save_as_template,
    setup_sheet,
)


TITLE_X0 = 0.278
TITLE_Y0 = 0.006
TITLE_X1 = ASME_B_WIDTH_M - 0.006
TITLE_Y1 = 0.080  # raised from 0.070 to fit the DRAWN/CHECKED production-control row


def _point_xy(adapter: Any, point: Any) -> tuple[float, float] | None:
    if point is None:
        return None
    x = adapter._get_attr_or_call(point, "X")
    y = adapter._get_attr_or_call(point, "Y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return float(x), float(y)


def _segment_points(adapter: Any, segment: Any) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for method in ("GetStartPoint2", "GetEndPoint2", "GetCenterPoint2"):
        point = adapter._attempt(lambda name=method: getattr(segment, name)())
        xy = _point_xy(adapter, point)
        if xy is not None:
            points.append(xy)
    return points


def _is_native_border_segment(points: list[tuple[float, float]]) -> bool:
    if len(points) < 2:
        return False
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width > 0.30 or height > 0.20:
        return True
    near_left = max(xs) < 0.018
    near_right = min(xs) > ASME_B_WIDTH_M - 0.018
    near_top = min(ys) > ASME_B_HEIGHT_M - 0.018
    near_bottom = max(ys) < 0.018
    short_tick = max(width, height) < 0.020
    return short_tick and (near_left or near_right or near_top or near_bottom)


def _delete_native_sheet_annotations(adapter: Any) -> int:
    """Delete stock notes before entering sheet-format edit mode."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")  # IDrawingDoc view for drawing-only methods (same dispatch)
    sheet_view = adapter._attempt(lambda: ddoc.GetFirstView())
    if sheet_view is None:
        raise RuntimeError("native drawing has no sheet view")
    sheet_view = _sw_type_info.early_bound_or_flag(
        sheet_view, "IView", "GetFirstAnnotation3"
    )
    annotations: list[Any] = []
    annotation = adapter._attempt(lambda: sheet_view.GetFirstAnnotation3())
    while annotation is not None:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetNext3", "Select2"
        )
        next_annotation = adapter._attempt(lambda item=annotation: item.GetNext3())
        annotations.append(annotation)
        annotation = next_annotation
    for annotation in annotations:
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select native sheet annotation")
        draw.EditDelete()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return len(annotations)


def _strip_native_template(adapter: Any) -> int:
    """Retain only native border/zone sketch segments."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")  # IDrawingDoc view for drawing-only methods (same dispatch)
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    sheet = _sw_type_info.early_bound_or_flag(sheet, "ISheet", "GetTemplateSketch")
    sheet.SheetFormatVisible = True
    sketch = adapter._get_attr_or_call(sheet, "GetTemplateSketch")
    sketch = _sw_type_info.early_bound_or_flag(sketch, "ISketch", "GetSketchSegments")
    segments = list(adapter._get_attr_or_call(sketch, "GetSketchSegments") or [])
    delete_segments: list[Any] = []
    for segment in segments:
        # Bind to the DERIVED ISketchLine/ISketchArc/... where the point accessors
        # (GetStartPoint2/GetEndPoint2/GetCenterPoint2) are declared. Binding to the
        # base ISketchSegment leaves them off-interface, so _segment_points reads
        # <2 points and a border segment is misclassified as interior -> DELETED.
        segment = _sw_type_info.concrete_sketch_segment(segment)
        if not _is_native_border_segment(_segment_points(adapter, segment)):
            delete_segments.append(segment)

    for segment in delete_segments:
        draw.ClearSelection2(True)
        selected = adapter._attempt(
            lambda item=segment: _early_bound(item, "IEntity").Select4(False, null_callout()),
            default=False,
        )
        if not selected:
            raise RuntimeError("failed to select native title-block segment")
        draw.EditDelete()

    remaining_segments = list(
        adapter._get_attr_or_call(sketch, "GetSketchSegments") or []
    )
    remaining_interior = []
    for segment in remaining_segments:
        segment = _sw_type_info.concrete_sketch_segment(segment)
        if not _is_native_border_segment(_segment_points(adapter, segment)):
            remaining_interior.append(segment)
    if remaining_interior:
        raise RuntimeError(
            "native title-block cleanup left "
            f"{len(remaining_interior)} interior sketch entities"
        )

    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return len(delete_segments)


def _line(adapter: Any, x0: float, y0: float, x1: float, y1: float) -> None:
    segment = adapter.currentModel.SketchManager.CreateLine(x0, y0, 0.0, x1, y1, 0.0)
    if segment is None:
        raise RuntimeError(f"failed to create title-block line ({x0}, {y0})-({x1}, {y1})")


def _draw_project_border(adapter: Any) -> None:
    margin = 0.006
    x0, y0 = margin, margin
    x1, y1 = ASME_B_WIDTH_M - margin, ASME_B_HEIGHT_M - margin
    for line in (
        (x0, y0, x1, y0),
        (x1, y0, x1, y1),
        (x1, y1, x0, y1),
        (x0, y1, x0, y0),
    ):
        _line(adapter, *line)
    for index in range(1, 4):
        x = x0 + (x1 - x0) * index / 4.0
        _line(adapter, x, y0, x, y0 + 0.004)
        _line(adapter, x, y1, x, y1 - 0.004)
    y_mid = (y0 + y1) / 2.0
    _line(adapter, x0, y_mid, x0 + 0.004, y_mid)
    _line(adapter, x1, y_mid, x1 - 0.004, y_mid)
    for index, label in enumerate(("4", "3", "2", "1")):
        x = x0 + (x1 - x0) * (index + 0.5) / 4.0
        add_note(adapter, label, x, y1 + 0.001)
    for y, label in (
        (y0 + 0.75 * (y1 - y0), "B"),
        (y0 + 0.25 * (y1 - y0), "A"),
    ):
        add_note(adapter, label, 0.001, y)
        add_note(adapter, label, x1 + 0.001, y)


def _draw_project_title_block(adapter: Any) -> None:
    for x0, y0, x1, y1 in (
        (TITLE_X0, TITLE_Y0, TITLE_X1, TITLE_Y0),
        (TITLE_X1, TITLE_Y0, TITLE_X1, TITLE_Y1),
        (TITLE_X1, TITLE_Y1, TITLE_X0, TITLE_Y1),
        (TITLE_X0, TITLE_Y1, TITLE_X0, TITLE_Y0),
    ):
        _line(adapter, x0, y0, x1, y1)
    for y in (0.017, 0.027, 0.037, 0.047, 0.057, 0.067):
        _line(adapter, TITLE_X0, y, TITLE_X1, y)

    # DRAWN carries the drafter ($PRPSHEET); CHECKED / DATE are blank fill-ins a
    # machinist signs on the printed copy. Revision Description rides the DWG/REV row.
    rows = (
        ('$PRPSHEET:"Title"', 0.074),
        ('DRAWN $PRPSHEET:"Drawn By"    CHECKED    DATE', 0.062),
        ('DWG $PRPSHEET:"Number"    REV $PRPSHEET:"Revision"    $PRPSHEET:"Revision Description"', 0.052),
        ('MATERIAL $PRPSHEET:"Material Specification"', 0.042),
        ('FINISH $PRPSHEET:"Finish"    QTY $PRPSHEET:"Quantity"', 0.032),
        ('SCALE $PRP:"SW-Sheet Scale"    THIRD ANGLE', 0.022),
        ("SHEET 1 OF 1", 0.011),
    )
    for text, y in rows:
        if add_note(adapter, text, TITLE_X0 + 0.004, y) is None:
            raise RuntimeError(f"failed to add title-block note {text!r}")
    if not add_third_angle_symbol(adapter, 0.252, 0.027, size=0.007):
        raise RuntimeError("failed to create third-angle symbol in sheet format")


def _assert_no_banned_sheet_text(adapter: Any) -> None:
    draw = _early_bound(adapter.currentModel, "IDrawingDoc")  # IDrawingDoc view: only GetFirstView used here
    sheet_view = adapter._attempt(lambda: draw.GetFirstView())
    if sheet_view is None:
        raise RuntimeError("drawing has no sheet view")
    banned = ("proprietary", "confidential", "insert company", "approval")
    sheet_view = _sw_type_info.early_bound_or_flag(
        sheet_view, "IView", "GetFirstAnnotation3"
    )
    annotation = adapter._attempt(lambda: sheet_view.GetFirstAnnotation3())
    found: list[str] = []
    while annotation is not None:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation", "GetNext3"
        )
        specific = adapter._attempt(lambda item=annotation: item.GetSpecificAnnotation())
        text = ""
        if specific is not None:
            specific = _sw_type_info.early_bound_or_flag(specific, "INote", "GetText")
            value = adapter._attempt(lambda item=specific: item.GetText())
            text = value if isinstance(value, str) else ""
        if any(token in text.lower() for token in banned):
            found.append(text)
        annotation = adapter._attempt(lambda item=annotation: item.GetNext3())
    if found:
        raise RuntimeError(f"book-irrelevant native sheet text remains: {found}")


async def build(adapter: Any) -> dict[str, str]:
    new_drawing(adapter, width=ASME_B_WIDTH_M, height=ASME_B_HEIGHT_M)
    if not setup_sheet(
        adapter,
        template=2,  # swDwgTemplateBsize: native B sheet is the provenance base
        scale=(1.0, 1.0),
        first_angle=False,
    ):
        raise RuntimeError("failed to create native SolidWorks B-size sheet")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")  # IDrawingDoc view for drawing-only methods (same dispatch)
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("native drawing has no current sheet")
    sheet = _sw_type_info.early_bound_or_flag(sheet, "ISheet")
    assert_asme_b_sheet(adapter, sheet, phase="native B template")
    sheet.SheetFormatVisible = True
    removed_annotations = _delete_native_sheet_annotations(adapter)
    removed_tables = delete_all_tables(adapter)
    draw.EditTemplate()
    if draw.GetEditSheet():
        raise RuntimeError("failed to enter sheet-format edit mode")
    removed_segments = _strip_native_template(adapter)
    _telemetry.info(
        "native B cleanup: "
        f"segments={removed_segments}, notes={removed_annotations}, "
        f"tables={removed_tables}"
    )
    _draw_project_border(adapter)
    _draw_project_title_block(adapter)
    _assert_no_banned_sheet_text(adapter)
    draw.EditSheet2()
    if not draw.GetEditSheet():
        raise RuntimeError("failed to leave sheet-format edit mode")
    draw.EditRebuild3()

    ASME_B_SLDDRT.parent.mkdir(parents=True, exist_ok=True)
    ASME_B_SLDDRT.unlink(missing_ok=True)
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name or not ddoc.ActivateSheet(sheet_name):
        raise RuntimeError("failed to activate project drawing sheet")
    if not sheet.SaveFormat(str(ASME_B_SLDDRT.resolve())):
        raise RuntimeError(f"ISheet.SaveFormat failed: {ASME_B_SLDDRT}")
    if not ASME_B_SLDDRT.is_file() or ASME_B_SLDDRT.stat().st_size == 0:
        raise RuntimeError(f"sheet format was not written: {ASME_B_SLDDRT}")

    save_as_template(adapter, str(ASME_B_DRWDOT))
    if not ASME_B_DRWDOT.is_file() or ASME_B_DRWDOT.stat().st_size == 0:
        raise RuntimeError(f"drawing template was not written: {ASME_B_DRWDOT}")
    _telemetry.success(f"created {ASME_B_DRWDOT}")
    _telemetry.success(f"created {ASME_B_SLDDRT}")
    return {
        "drwdot": str(ASME_B_DRWDOT.resolve()),
        "slddrt": str(ASME_B_SLDDRT.resolve()),
    }


if __name__ == "__main__":
    _telemetry.set_service("drawing-standards")
    sys.exit(run_build(build))
