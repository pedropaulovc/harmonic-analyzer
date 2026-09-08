"""Compact the base's one native hole table and pack its unchanged print.

This is deliberately recipe-local: the general annotation reader does not
support tables. Native row/column spans bound this exact, unsplit 18x4 table;
every displayed cell and text-format field remains a separate content witness.
No table text, font, padding, column width, view scale or source entity is edited.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from typing import Any

from _common import _early_bound
from _drawing_annotation_bounds import AnnotationBounds, annotation_box
from _drawing_common import _TITLE_BLOCK_LEFT_M, _TITLE_BLOCK_TOP_M
from _drawing_leader_clearance import validate_gtol_leader_clearance
from _drawing_native_layout import LayoutNote, NativeLayoutStatus, repair_native_layout
from _drawing_view_packing import Rect
import _telemetry


_FORMAT_FIELDS = (
    "TypeFaceName",
    "CharHeight",
    "CharHeightInPts",
    "WidthFactor",
    "CharSpacingFactor",
    "LineLength",
    "LineSpacing",
    "Escapement",
    "ObliqueAngle",
    "Bold",
    "Italic",
    "Underline",
    "Strikeout",
    "BackWards",
    "UpsideDown",
    "Vertical",
)
_GAP_M = 0.002
_HEADROOM_M = 0.0005  # Same planning reserve as repair_project_drawing_layout.
_POSITION_TOLERANCE_M = 1e-8


def _format_signature(raw: Any) -> tuple:
    if raw is None:
        raise RuntimeError("harmonic-base table has no native text format")
    fmt = _early_bound(raw, "ITextFormat")
    values = tuple(getattr(fmt, name) for name in _FORMAT_FIELDS)
    if (
        not values[0]
        or any(not math.isfinite(value) for value in values[1:])
        or float(fmt.CharHeight) <= 0
    ):
        raise RuntimeError("harmonic-base table has invalid native text format")
    return (
        *zip(_FORMAT_FIELDS, values, strict=True),
        ("IsHeightSpecifiedInPts", int(fmt.IsHeightSpecifiedInPts())),
    )


def _positive_sizes(values, label):
    result = tuple(float(value) for value in values)
    if not result or any(not math.isfinite(value) or value <= 0 for value in result):
        raise RuntimeError(f"harmonic-base table has invalid {label}: {result}")
    return result


@dataclass(frozen=True)
class _TableState:
    cells: tuple
    table_format: tuple
    widths: tuple[float, ...]
    heights: tuple[float, ...]
    gaps: tuple[float, ...]
    locks: tuple[int, ...]


def _table_state(table: Any) -> _TableState:
    dimensions = tuple(
        int(getattr(table, name))
        for name in (
            "RowCount",
            "ColumnCount",
            "TotalRowCount",
            "TotalColumnCount",
        )
    )
    if dimensions != (18, 4, 18, 4):
        raise RuntimeError(
            f"harmonic-base table must retain visible 18x4 cells: {dimensions}"
        )
    split = tuple(table.GetSplitInformation(0, 0, 0, 0) or ())
    if len(split) != 5 or int(split[0]) != 0:
        raise RuntimeError(f"harmonic-base table must remain unsplit: {split}")
    if int(table.AnchorType) != 1 or table.Anchored:
        raise RuntimeError(
            "harmonic-base table must remain unanchored, top-left origin"
        )
    gaps = tuple(float(table.GetRowVerticalGap(row)) for row in range(18))
    if any(not math.isfinite(value) or value < 0 for value in gaps):
        raise RuntimeError(f"harmonic-base table has invalid row padding: {gaps}")
    cells = []
    for row in range(18):
        for column in range(4):
            text = table.DisplayedText(row, column)
            if text is None:
                raise RuntimeError(
                    f"harmonic-base table cell ({row}, {column}) has no text"
                )
            cells.append(
                (
                    row,
                    column,
                    str(text),
                    int(table.GetCellUseDocTextFormat(row, column)),
                    _format_signature(table.GetCellTextFormat(row, column)),
                )
            )
    return _TableState(
        tuple(cells),
        (int(table.GetUseDocTextFormat()), _format_signature(table.GetTextFormat())),
        _positive_sizes((table.GetColumnWidth(i) for i in range(4)), "column widths"),
        _positive_sizes((table.GetRowHeight(i) for i in range(18)), "row heights"),
        gaps,
        tuple(int(table.GetLockRowHeight(i)) for i in range(18)),
    )


def _annotation(table):
    raw = table.GetAnnotation()
    if raw is None:
        raise RuntimeError("harmonic-base table lost its annotation")
    annotation = _early_bound(raw, "IAnnotation")
    if (
        int(annotation.GetType()) != 14
        or int(annotation.Visible) != 1
        or int(annotation.OwnerType) == 2
        or not annotation.GetName()
    ):
        raise RuntimeError(
            "harmonic-base table needs a named visible native table annotation"
        )
    return annotation


def _position(annotation):
    result = tuple(float(value) for value in annotation.GetPosition() or ())
    if len(result) != 3 or not all(math.isfinite(value) for value in result):
        raise RuntimeError(f"harmonic-base table has invalid native position: {result}")
    return result


def _inventory(adapter, table, expected_annotation):
    """Prove both native enumerations contain only the exact returned table."""
    app = _early_bound(adapter.swApp, "ISldWorks")
    active = app.ActiveDoc  # Object-valued PROPERTY; never invoke its COM dispatch.
    if active is None or int(app.IsSame(active, adapter.currentModel)) != 1:
        raise RuntimeError("harmonic-base table owner is not the active drawing")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    view = drawing.GetFirstView()
    seen = []
    table_count = annotation_count = 0
    while view is not None:
        view = _early_bound(view, "IView")
        if any(int(adapter.swApp.IsSame(view, prior)) == 1 for prior in seen):
            raise RuntimeError("harmonic-base table inventory repeats a native view")
        seen.append(view)
        for raw in view.GetTableAnnotations() or ():
            if raw is None or int(adapter.swApp.IsSame(table, raw)) != 1:
                raise RuntimeError("harmonic-base has an unexpected native table")
            table_count += 1
        for raw in view.GetAnnotations() or ():
            if raw is None:
                raise RuntimeError(
                    "harmonic-base native annotation inventory contains null"
                )
            actual = _early_bound(raw, "IAnnotation")
            if int(actual.GetType()) != 14:
                continue
            if int(adapter.swApp.IsSame(expected_annotation, actual)) != 1:
                raise RuntimeError("harmonic-base has an unexpected table annotation")
            annotation_count += 1
        view = view.GetNextView()
    if table_count == 0 or annotation_count == 0:
        raise RuntimeError(
            "harmonic-base exact table is missing from native table/annotation inventory: "
            f"tables={table_count}, annotations={annotation_count}"
        )


def _sheet_bounds(adapter):
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(float(value) for value in sheet.GetProperties2() or ())
    margins = tuple(float(sheet.GetZoneMargin(i)) for i in range(4))
    if (
        len(properties) != 8
        or not all(math.isfinite(v) for v in properties)
        or any(not math.isfinite(v) or v < 0 for v in margins)
    ):
        raise RuntimeError("harmonic-base native sheet properties/margins are invalid")
    top, bottom, right, left = margins  # swZoneMargin_e.
    return (
        Rect(left, bottom, properties[5] - right, properties[6] - top),
        Rect(_TITLE_BLOCK_LEFT_M, 0.0, properties[5], _TITLE_BLOCK_TOP_M),
    )


def _box(state, position):
    # Same top-left row/column-span contract as _drawing_common._table_element,
    # but no _attempt(... or 0) may conceal a missing native measurement here.
    x, y, _z = position
    return Rect(x, y - sum(state.heights), x + sum(state.widths), y)


@_telemetry.traced("drawing.harmonic_base.compact_table")
def _compact_table(adapter, table, annotation, drawable, title_block):
    before = _table_state(table)
    position = _position(annotation)
    _telemetry.info(
        "harmonic-base native table before compaction",
        table_state=json.dumps(asdict(before)),
        position=position,
    )
    actual_heights = []
    for row, original in enumerate(before.heights):
        # SetRowHeight documents native minimum clamping. Zero requests that
        # minimum; option 0 permits the TABLE to shrink, not adjacent rows to grow.
        actual = float(table.SetRowHeight(row, 0.0, 0))
        if not math.isfinite(actual) or actual <= 0 or actual > original:
            raise RuntimeError(
                f"harmonic-base row {row} rejected minimum height: {actual}"
            )
        readback = float(table.GetRowHeight(row))
        if readback != actual:
            raise RuntimeError(
                f"harmonic-base row {row} height readback differs: {actual}, {readback}"
            )
        actual_heights.append(actual)
    expected = replace(before, heights=tuple(actual_heights))
    if _table_state(table) != expected or _position(annotation) != position:
        raise RuntimeError(
            "harmonic-base compaction changed table content/font/width/padding/anchor"
        )
    target = (
        drawable.xmax - sum(expected.widths) - _HEADROOM_M,
        drawable.ymax - _HEADROOM_M,
        position[2],
    )
    bounds = _box(expected, target)
    _telemetry.info(
        "harmonic-base native table minimum-height readback",
        row_heights=expected.heights,
        target=target,
        bounds=bounds.bounds,
        drawable=drawable.bounds,
    )
    if (
        bounds.xmin < drawable.xmin + _HEADROOM_M
        or bounds.ymin < drawable.ymin + _HEADROOM_M
        or (
            bounds.xmax > title_block.xmin - _GAP_M
            and bounds.ymin < title_block.ymax + _GAP_M
        )
    ):
        raise RuntimeError(
            f"harmonic-base compacted table no_fit: {bounds.bounds}, drawable={drawable.bounds}"
        )
    if not annotation.SetPosition2(*target):
        raise RuntimeError("harmonic-base table rejected measured upper-right position")
    if math.dist(_position(annotation), target) > _POSITION_TOLERANCE_M:
        raise RuntimeError(
            "harmonic-base table did not reach measured upper-right position"
        )
    if _table_state(table) != expected:
        raise RuntimeError(
            "harmonic-base table placement changed content/font/row geometry"
        )
    return expected


@_telemetry.traced("drawing.harmonic_base.native_layout")
def repair_harmonic_base_layout(
    adapter: Any,
    *,
    table: Any,
    views: dict[str, Any],
    manufacturing_note: Any,
    side_note: Any,
):
    """Place the complete original-size base print or reject before export."""
    if int(adapter.currentModel.GetType()) != 3:
        raise RuntimeError("harmonic-base print layout requires an active drawing")
    table = _early_bound(table, "ITableAnnotation")
    annotation = _annotation(table)
    _inventory(adapter, table, annotation)  # Before ANY native layout write.
    drawable, title_block = _sheet_bounds(adapter)
    expected = _compact_table(adapter, table, annotation, drawable, title_block)

    def measure(actual_adapter, actual_annotation):
        actual_annotation = _early_bound(actual_annotation, "IAnnotation")
        if int(actual_annotation.GetType()) != 14:
            return annotation_box(actual_adapter, actual_annotation)
        if (
            int(actual_adapter.swApp.IsSame(annotation, actual_annotation)) != 1
            or int(actual_adapter.swApp.IsSame(annotation, _annotation(table))) != 1
        ):
            raise RuntimeError(
                "harmonic-base measurement encountered a replaced/unknown table"
            )
        state = _table_state(table)
        if state != expected:
            raise RuntimeError(
                "harmonic-base table content/font/row geometry changed during packing"
            )
        position = _position(actual_annotation)
        bounds = _box(state, position)
        # The occupied table rectangle is native grid geometry, not fabricated
        # glyph metrics. All 72 cell values/fonts are in the immutable signature.
        return AnnotationBounds(
            name=str(actual_annotation.GetName()),
            kind=14,
            anchor=position[:2],
            body=bounds,
            envelope=bounds,
            text_boxes=(bounds,),
            text_runs=(),
            leader_segments=(),
            format_signature=(state,),
            native_strokes=(),
        )

    notes = (
        LayoutNote(
            "manufacturing", _early_bound(manufacturing_note, "INote").GetAnnotation()
        ),
        LayoutNote(
            "side-caption",
            _early_bound(side_note, "INote").GetAnnotation(),
            follows_view="side",
        ),
    )
    report = repair_native_layout(
        adapter,
        views=views,
        title_block=title_block,
        measure_annotation=measure,
        notes=notes,
        gap_m=_GAP_M,
        planning_headroom_m=_HEADROOM_M,
        final_annotation_validation=validate_gtol_leader_clearance,
    )
    _inventory(adapter, table, annotation)
    if _table_state(table) != expected:
        raise RuntimeError("harmonic-base final table witness changed")
    _telemetry.info(
        "harmonic-base native print layout measured",
        layout_report=json.dumps(asdict(report), default=lambda value: value.value),
    )
    if report.status in (NativeLayoutStatus.NO_FIT, NativeLayoutStatus.SEARCH_LIMIT):
        raise RuntimeError(
            f"harmonic-base native print {report.status.value}: {report.reason}"
        )
    return report
