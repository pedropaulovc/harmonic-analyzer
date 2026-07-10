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
from _common import run_build
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
TITLE_Y1 = 0.070


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


def _strip_native_template(adapter: Any) -> tuple[int, int, int]:
    """Retain only native border/zone segments; remove annotations and tables."""
    draw = adapter.currentModel
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    sheet = _sw_type_info.flagged(sheet, "ISheet")
    sketch = adapter._get_attr_or_call(sheet, "GetTemplateSketch")
    sketch = _sw_type_info.flagged(sketch, "ISketch")
    segments = list(adapter._get_attr_or_call(sketch, "GetSketchSegments") or [])
    delete_segments: list[Any] = []
    for segment in segments:
        segment = _sw_type_info.flagged(segment, "ISketchSegment")
        if not _is_native_border_segment(_segment_points(adapter, segment)):
            delete_segments.append(segment)

    draw.ClearSelection2(True)
    for segment in delete_segments:
        selected = adapter._attempt(
            lambda item=segment: item.Select4(True, null_callout()), default=False
        )
        if not selected:
            raise RuntimeError("failed to select native title-block segment")
    if delete_segments:
        draw.EditDelete()

    sheet_view = adapter._attempt(lambda: draw.GetFirstView())
    annotations: list[Any] = []
    if sheet_view is not None:
        annotation = adapter._attempt(lambda: sheet_view.GetFirstAnnotation3())
        while annotation is not None:
            annotation = _sw_type_info.flagged(annotation, "IAnnotation")
            next_annotation = adapter._attempt(lambda item=annotation: item.GetNext3())
            annotations.append(annotation)
            annotation = next_annotation
    removed_annotations = 0
    for annotation in annotations:
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select native sheet annotation")
        draw.EditDelete()
        removed_annotations += 1
    removed_tables = delete_all_tables(adapter)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return len(delete_segments), removed_annotations, removed_tables


def _line(adapter: Any, x0: float, y0: float, x1: float, y1: float) -> None:
    segment = adapter.currentModel.SketchManager.CreateLine(x0, y0, 0.0, x1, y1, 0.0)
    if segment is None:
        raise RuntimeError(f"failed to create title-block line ({x0}, {y0})-({x1}, {y1})")


def _draw_project_title_block(adapter: Any) -> None:
    for x0, y0, x1, y1 in (
        (TITLE_X0, TITLE_Y0, TITLE_X1, TITLE_Y0),
        (TITLE_X1, TITLE_Y0, TITLE_X1, TITLE_Y1),
        (TITLE_X1, TITLE_Y1, TITLE_X0, TITLE_Y1),
        (TITLE_X0, TITLE_Y1, TITLE_X0, TITLE_Y0),
    ):
        _line(adapter, x0, y0, x1, y1)
    for y in (0.017, 0.027, 0.037, 0.047, 0.057):
        _line(adapter, TITLE_X0, y, TITLE_X1, y)

    rows = (
        ('$PRPSHEET:"Title"', 0.064),
        ('DWG $PRPSHEET:"Number"    REV $PRPSHEET:"Revision"', 0.052),
        ('MATERIAL $PRPSHEET:"Material Specification"', 0.042),
        ('FINISH $PRPSHEET:"Finish"    QTY $PRPSHEET:"Quantity"', 0.032),
        ("SCALE 1:1 UNLESS NOTED    THIRD ANGLE", 0.022),
        ("SHEET 1 OF 1", 0.011),
    )
    for text, y in rows:
        if add_note(adapter, text, TITLE_X0 + 0.004, y) is None:
            raise RuntimeError(f"failed to add title-block note {text!r}")
    if not add_third_angle_symbol(adapter, 0.252, 0.027, size=0.007):
        raise RuntimeError("failed to create third-angle symbol in sheet format")


def _assert_no_banned_sheet_text(adapter: Any) -> None:
    draw = adapter.currentModel
    sheet_view = adapter._attempt(lambda: draw.GetFirstView())
    if sheet_view is None:
        raise RuntimeError("drawing has no sheet view")
    banned = ("proprietary", "confidential", "insert company", "approval")
    annotation = adapter._attempt(lambda: sheet_view.GetFirstAnnotation3())
    found: list[str] = []
    while annotation is not None:
        annotation = _sw_type_info.flagged(annotation, "IAnnotation")
        specific = adapter._attempt(lambda item=annotation: item.GetSpecificAnnotation())
        text = ""
        if specific is not None:
            specific = _sw_type_info.flagged(specific, "INote")
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
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("native drawing has no current sheet")
    sheet = _sw_type_info.flagged(sheet, "ISheet")
    assert_asme_b_sheet(adapter, sheet, phase="native B template")
    draw.EditTemplate()
    if draw.GetEditSheet():
        raise RuntimeError("failed to enter sheet-format edit mode")
    removed = _strip_native_template(adapter)
    _telemetry.info(
        f"native B cleanup: segments={removed[0]}, notes={removed[1]}, tables={removed[2]}"
    )
    _draw_project_title_block(adapter)
    _assert_no_banned_sheet_text(adapter)
    draw.EditSheet2()
    if not draw.GetEditSheet():
        raise RuntimeError("failed to leave sheet-format edit mode")
    draw.EditRebuild3()

    ASME_B_SLDDRT.parent.mkdir(parents=True, exist_ok=True)
    ASME_B_SLDDRT.unlink(missing_ok=True)
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name or not draw.ActivateSheet(sheet_name):
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
