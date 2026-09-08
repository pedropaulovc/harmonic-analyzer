"""Pack the base's unchanged native table and views on two checked sheets.

This is deliberately recipe-local: the general annotation reader does not
support tables. Native row/column spans bound this exact, unsplit 18x4 table;
every displayed cell and text-format field remains a separate content witness.
No table text, font, padding, column width, view scale or source entity is edited.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
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
SHEET_NAMES = ("PLAN AND HOLE TABLE", "MANUFACTURING")


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


def activate_harmonic_base_sheet(adapter, name):
    """Activate an exact member of this two-sheet drawing, with native readback."""
    app = _early_bound(adapter.swApp, "ISldWorks")
    active = app.ActiveDoc  # Object-valued PROPERTY; never invoke its COM dispatch.
    if active is None or int(app.IsSame(active, adapter.currentModel)) != 1:
        raise RuntimeError("harmonic-base table owner is not the active drawing")
    if int(adapter.currentModel.GetType()) != 3:
        raise RuntimeError("harmonic-base print layout requires an active drawing")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if name not in SHEET_NAMES or tuple(drawing.GetSheetNames() or ()) != SHEET_NAMES:
        raise RuntimeError("harmonic-base sheet names/order differ from two-sheet plan")
    if not drawing.ActivateSheet(name):
        raise RuntimeError(f"harmonic-base failed to activate sheet {name!r}")
    sheet = drawing.GetCurrentSheet()
    if sheet is None or _early_bound(sheet, "ISheet").GetName() != name:
        raise RuntimeError(f"harmonic-base active sheet readback differs: {name!r}")


def _inventory(adapter, view, table=None, expected_annotation=None):
    """Prove this sheet has exactly its one view and its declared table, if any."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    expected_view = view
    view = drawing.GetFirstView()
    if view is None:
        raise RuntimeError("harmonic-base sheet has no native sheet view")
    seen = []
    table_count = annotation_count = 0
    while view is not None:
        view = _early_bound(view, "IView")
        if any(int(adapter.swApp.IsSame(view, prior)) == 1 for prior in seen):
            raise RuntimeError("harmonic-base table inventory repeats a native view")
        seen.append(view)
        for raw in view.GetTableAnnotations() or ():
            if (
                table is None
                or raw is None
                or int(adapter.swApp.IsSame(table, raw)) != 1
            ):
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
            if (
                expected_annotation is None
                or int(adapter.swApp.IsSame(expected_annotation, actual)) != 1
            ):
                raise RuntimeError("harmonic-base has an unexpected table annotation")
            annotation_count += 1
        view = view.GetNextView()
    if len(seen) != 2 or int(adapter.swApp.IsSame(seen[1], expected_view)) != 1:
        raise RuntimeError("harmonic-base sheet view ownership differs from plan")
    if table is not None and (table_count == 0 or annotation_count == 0):
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


class TableReadbackError(RuntimeError):
    """Retain exact native table evidence; never normalize text to hide a change."""

    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence
        self.add_note("Native table readback: " + json.dumps(evidence))


def _changed_fields(expected, actual):
    return [
        field.name
        for field in fields(expected)
        if getattr(expected, field.name) != getattr(actual, field.name)
    ]


def _table_evidence(expected, actual, position, actual_position, position_error=None):
    changed = _changed_fields(expected, actual)
    if actual_position != position:
        changed.append("position")
    return {
        "changed_fields": changed,
        "expected_state": asdict(expected),
        "actual_state": asdict(actual),
        "expected_position": position,
        "actual_position": actual_position,
        "position_read_error": position_error,
        "actual_heights": actual.heights,
        "text_changes": [
            {"row": old[0], "column": old[1], "before": old[2], "after": new[2]}
            for old, new in zip(expected.cells, actual.cells, strict=True)
            if old[2] != new[2]
        ],
    }


def _reject_table(message, evidence):
    failure = TableReadbackError(message, evidence)
    try:
        _telemetry.error(
            str(failure),
            changed_fields=evidence["changed_fields"],
            actual_heights=evidence["actual_heights"],
            expected_position=evidence["expected_position"],
            actual_position=evidence["actual_position"],
            expected_state=json.dumps(evidence["expected_state"]),
            actual_state=json.dumps(evidence["actual_state"]),
            position_read_error=evidence["position_read_error"],
        )
    except Exception as error:
        failure.add_note(f"Native table readback telemetry failed: {error!r}")
    raise failure


def _preserve_table(
    table, annotation, expected, position, *, phase, position_tolerance_m=0.0
):
    actual = _table_state(table)
    actual_position, error = None, None
    try:
        actual_position = _position(annotation)
    except Exception as failure:
        error = repr(failure)
    evidence = _table_evidence(expected, actual, position, actual_position, error)
    if (
        error is None
        and "position" in evidence["changed_fields"]
        and math.dist(position, actual_position) <= position_tolerance_m
    ):
        evidence["changed_fields"].remove("position")
    if evidence["changed_fields"]:
        _reject_table(f"harmonic-base table changed during {phase}", evidence)
    return actual_position


@_telemetry.traced("drawing.harmonic_base.resolve_table")
def _resolve_table(adapter, table, annotation):
    """Observe native rebuild resolution before freezing the exact display."""
    before, position = _table_state(table), _position(annotation)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("harmonic-base table resolution rebuild failed")
    after, actual_position = _table_state(table), _position(annotation)
    evidence = _table_evidence(before, after, position, actual_position)
    _telemetry.info(
        "harmonic-base native table display resolved before preservation witness",
        changed_fields=evidence["changed_fields"],
        text_changes=json.dumps(evidence["text_changes"]),
        before_state=json.dumps(evidence["expected_state"]),
        resolved_state=json.dumps(evidence["actual_state"]),
        before_position=position,
        resolved_position=actual_position,
    )

    # Only the native text display may resolve in this explicit pre-witness
    # phase. Log its exact spelling/precision, never numeric-equate it away.
    # Fonts, row geometry, use-doc flags, widths, padding and anchor stay fixed.
    def cell_metadata(state):
        return tuple(cell[:2] + cell[3:] for cell in state.cells)

    if set(evidence["changed_fields"]) - {"cells"} or cell_metadata(
        before
    ) != cell_metadata(after):
        _reject_table(
            "harmonic-base rebuild changed table formatting/geometry", evidence
        )
    return after, actual_position


@_telemetry.traced("drawing.harmonic_base.place_table")
def _place_table(table, annotation, expected, position, drawable, title_block):
    target = (drawable.xmin + _HEADROOM_M, drawable.ymax - _HEADROOM_M, position[2])
    bounds = _box(expected, target)
    _telemetry.info(
        "harmonic-base unchanged native table placement",
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
            f"harmonic-base unchanged table no_fit: {bounds.bounds}, drawable={drawable.bounds}"
        )
    if not annotation.SetPosition2(*target):
        raise RuntimeError("harmonic-base table rejected measured upper-left position")
    # Exact table text/geometry plus strict position: no formatted equivalence.
    return _preserve_table(
        table,
        annotation,
        expected,
        target,
        phase="table placement",
        position_tolerance_m=_POSITION_TOLERANCE_M,
    )


@_telemetry.traced("drawing.harmonic_base.native_layout")
def repair_harmonic_base_layout(
    adapter: Any,
    *,
    table: Any,
    views: dict[str, Any],
    manufacturing_note: Any,
    side_note: Any,
):
    """Pack both original-size sheets, rejecting any missing owner or failed fit."""
    if set(views) != {"top", "side"}:
        raise ValueError("harmonic-base layout requires exactly top and side views")
    table = _early_bound(table, "ITableAnnotation")
    annotation = _annotation(table)
    activate_harmonic_base_sheet(adapter, SHEET_NAMES[0])
    _inventory(adapter, views["top"], table, annotation)
    activate_harmonic_base_sheet(adapter, SHEET_NAMES[1])
    _inventory(adapter, views["side"])
    activate_harmonic_base_sheet(adapter, SHEET_NAMES[0])
    expected, position = _resolve_table(adapter, table, annotation)
    _inventory(adapter, views["top"], table, annotation)
    drawable, title_block = _sheet_bounds(adapter)
    position = _place_table(
        table, annotation, expected, position, drawable, title_block
    )

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
        _preserve_table(table, actual_annotation, expected, position, phase="packing")
        state = expected
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
    plan_report = repair_native_layout(
        adapter,
        views={"top": views["top"]},
        title_block=title_block,
        measure_annotation=measure,
        gap_m=_GAP_M,
        planning_headroom_m=_HEADROOM_M,
        final_annotation_validation=validate_gtol_leader_clearance,
    )
    _require_fit(plan_report, SHEET_NAMES[0])
    _inventory(adapter, views["top"], table, annotation)
    _preserve_table(table, annotation, expected, position, phase="plan final readback")
    activate_harmonic_base_sheet(adapter, SHEET_NAMES[1])
    _inventory(adapter, views["side"])
    _, manufacturing_title = _sheet_bounds(adapter)
    manufacturing_report = repair_native_layout(
        adapter,
        views={"side": views["side"]},
        notes=notes,
        title_block=manufacturing_title,
        measure_annotation=annotation_box,
        gap_m=_GAP_M,
        planning_headroom_m=_HEADROOM_M,
        final_annotation_validation=validate_gtol_leader_clearance,
    )
    _require_fit(manufacturing_report, SHEET_NAMES[1])
    _inventory(adapter, views["side"])
    activate_harmonic_base_sheet(adapter, SHEET_NAMES[0])
    _inventory(adapter, views["top"], table, annotation)
    _preserve_table(
        table, annotation, expected, position, phase="both sheets final readback"
    )
    return {SHEET_NAMES[0]: plan_report, SHEET_NAMES[1]: manufacturing_report}


def _require_fit(report, sheet_name):
    _telemetry.info(
        "harmonic-base native print sheet measured",
        sheet=sheet_name,
        layout_report=json.dumps(asdict(report), default=lambda value: value.value),
    )
    if report.status in (NativeLayoutStatus.NO_FIT, NativeLayoutStatus.SEARCH_LIMIT):
        raise RuntimeError(
            f"harmonic-base native print {report.status.value} ({sheet_name}): {report.reason}"
        )
