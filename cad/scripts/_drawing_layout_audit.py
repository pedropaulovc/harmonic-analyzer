"""Live collection for the unified drawing layout audit (``_layout_audit``).

``finalize_drawing`` calls :func:`run_layout_audit` once the PDF is exported,
with the finished document still open. For every sheet it records, WITHOUT
activating the sheet (``IDrawingDoc::GetViews`` returns one row per sheet, led
by the sheet's own view):

* every annotation's rendered primitives (``IAnnotation::GetDisplayData``:
  lines, arcs, arrowheads, polylines, polygons, triangles, text runs with
  their lower-left positions, heights, angles, fonts), its registered leaders,
  and per type: a note's text/extent/balloon flag, a display dimension's
  hole-callout flag and its own ``IDisplayDimension::GetDisplayData``, a datum
  origin's ``GetAxisPoints2`` and labels;
* every view's outline, orientation, ``ModelToViewTransform`` and visible
  model edges (``IView::GetPolylines7``, crosshatch excluded), plus one model
  vertex per view for the coordinate-space round trip;
* section lines (``IDrSection`` line, arrows, label origins, text height) and
  detail circles (``IView::GetDetailCircleInfo2``);
* tables, boxed from anchor + row/column spans (as ``_drawing_common`` does);
* the sheet size, zone margins and title-block keep-out.

That dump is logged verbatim (chunked, see ``_layout_audit.encode_dump_lines``)
so the offline calibration and tests replay exactly what the leaf saw, then
audited by the SolidWorks-free ``_layout_audit.audit_dump``.
"""

from __future__ import annotations

import json
import time
import traceback
from typing import Any, Callable, Mapping, Sequence

import _telemetry
from _common import _early_bound
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from _layout_audit import (
    DUMP_SCHEMA,
    FINDING_PREFIX,
    LAYOUT_AUDIT_MODE,
    SUMMARY_PREFIX,
    FindingSeverity,
    LayoutAuditMode,
    audit_dump,
    encode_dump_lines,
    finding_record,
    severity,
)

_ANNOT_DIM = 4
_ANNOT_NOTE = 6
_ANNOT_DATUM_ORIGIN = 16
# swZoneMargin_e
_ZONE_MARGINS = {"top": 0, "bottom": 1, "right": 2, "left": 3}
# IView::GetPolylines7 CrossHatchOption: 1 = exclude crosshatch lines.
_EXCLUDE_CROSSHATCH = 1

_DISPLAY_PRIMITIVES = (
    ("lines", "GetLineCount", ("GetLineAtIndex3", "GetLineAtIndex2")),
    ("arcs", "GetArcCount", ("GetArcAtIndex2",)),
    ("arrows", "GetArrowHeadCount", ("GetArrowHeadAtIndex2",)),
    ("polylines", "GetPolyLineCount", ("GetPolylineAtIndex2",)),
    ("polygons", "GetPolygonCount", ("GetPolygonAtIndex",)),
    ("triangles", "GetTriangleCount", ("GetTriangleAtIndex",)),
    ("ellipses", "GetEllipseCount", ("GetEllipseAtIndex2",)),
)


def _round(values: Any) -> list[float]:
    """Floats rounded to 0.1 um -- far below ink, and a third of the JSON."""
    return [round(float(value), 7) for value in (values or ())]


class _Reader:
    """Tolerant COM reads: an accessor that does not apply returns ``default``."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.errors = 0

    def call(self, fn: Callable[[], Any], default: Any = None) -> Any:
        try:
            value = fn()
        except Exception:
            self.errors += 1
            return default
        return default if value is None else value

    def bind(self, obj: Any, interface: str) -> Any:
        if obj is None:
            return None
        try:
            return _early_bound(obj, interface)
        except Exception:
            self.errors += 1
            return None


def _dump_display(reader: _Reader, data: Any) -> dict[str, Any]:
    data = reader.bind(data, "IDisplayData")
    if data is None:
        return {}
    out: dict[str, Any] = {}
    for key, count_name, getters in _DISPLAY_PRIMITIVES:
        count = int(reader.call(lambda c=count_name: getattr(data, c)(), 0) or 0)
        rows = []
        for index in range(count):
            raw = None
            for getter in getters:
                raw = reader.call(lambda g=getter, i=index: getattr(data, g)(i))
                if raw:
                    break
            if raw:
                rows.append(_round(raw))
        if rows:
            out[key] = rows
    texts = []
    for index in range(int(reader.call(lambda: data.GetTextCount(), 0) or 0)):
        texts.append(
            {
                "t": str(reader.call(lambda i=index: data.GetTextAtIndex(i), "")),
                "pos": _round(reader.call(lambda i=index: data.GetTextPositionAtIndex(i), ())),
                "h": round(float(reader.call(lambda i=index: data.GetTextHeightAtIndex(i), 0.0)), 7),
                "ref": int(reader.call(lambda i=index: data.GetTextRefPositionAtIndex(i), -1)),
                "ang": round(float(reader.call(lambda i=index: data.GetTextAngleAtIndex(i), 0.0)), 7),
                "font": str(reader.call(lambda i=index: data.GetTextFontAtIndex(i), "")),
                "ls": round(float(reader.call(lambda i=index: data.GetTextLineSpacingAtIndex(i), 0.0)), 7),
            }
        )
    if texts:
        out["texts"] = texts
    return out


def _dump_annotation(reader: _Reader, raw: Any) -> dict[str, Any] | None:
    annotation = reader.bind(raw, "IAnnotation")
    if annotation is None:
        return None
    kind = int(reader.call(lambda: annotation.GetType(), 0))
    record: dict[str, Any] = {
        "type": kind,
        "name": str(reader.call(lambda: annotation.GetName(), "")),
        "visible": int(reader.call(lambda: annotation.Visible, 1)),
        "owner_type": int(reader.call(lambda: annotation.OwnerType, -1)),
        "pos": _round(reader.call(lambda: annotation.GetPosition(), ())),
        "layer": str(reader.call(lambda: annotation.Layer, "")),
    }
    leaders = []
    for index in range(int(reader.call(lambda: annotation.GetLeaderCount(), 0) or 0)):
        points = reader.call(lambda i=index: annotation.GetLeaderPointsAtIndex(i))
        if points:
            leaders.append(_round(points))
    if leaders:
        record["leaders"] = leaders
    record["display"] = _dump_display(reader, reader.call(lambda: annotation.GetDisplayData()))
    specific = reader.call(lambda: annotation.GetSpecificAnnotation())
    if kind == _ANNOT_NOTE:
        note = reader.bind(specific, "INote")
        if note is not None:
            record["note"] = {
                "text": str(reader.call(lambda: note.GetText(), "")),
                "extent": _round(reader.call(lambda: note.GetExtent(), ())),
                "balloon": bool(reader.call(lambda: note.IsBomBalloon(), False)),
            }
    elif kind == _ANNOT_DIM:
        display = reader.bind(specific, "IDisplayDimension")
        if display is not None:
            record["dim"] = {
                "hole_callout": bool(reader.call(lambda: display.IsHoleCallout(), False)),
                # Calibration only: does the dimension's own display data
                # differ from IAnnotation's? (hole callouts were measured on it)
                "display": _dump_display(reader, reader.call(lambda: display.GetDisplayData())),
            }
    elif kind == _ANNOT_DATUM_ORIGIN:
        origin = reader.bind(specific, "IDatumOrigin")
        if origin is not None:
            record["datum_origin"] = {
                "axis": _round(reader.call(lambda: origin.GetAxisPoints2(), ())),
                "x_label": str(reader.call(lambda: origin.XLabel, "")),
                "y_label": str(reader.call(lambda: origin.YLabel, "")),
            }
    return record


def _table_record(reader: _Reader, raw: Any) -> dict[str, Any] | None:
    """A table's box: top-left anchor, then visible rows down and columns right."""
    table = reader.bind(raw, "ITableAnnotation")
    if table is None:
        return None
    inner = reader.bind(reader.call(lambda: table.GetAnnotation()), "IAnnotation")
    if inner is None:
        return None
    position = _round(reader.call(lambda: inner.GetPosition(), ()))
    if len(position) < 2:
        return None
    rows = int(reader.call(lambda: table.RowCount, 0) or 0)
    columns = int(reader.call(lambda: table.ColumnCount, 0) or 0)
    row_indices = list(range(rows))
    split = reader.call(lambda: table.GetSplitInformation(0, 0, 0, 0))
    if split and len(split) >= 5 and int(split[0]) == 1:
        _direction, _index, count, first, last = (int(value) for value in split[:5])
        if count > 1 and 0 <= first <= last < rows:
            row_indices = list(range(first, last + 1))
            if first > 0:
                row_indices.insert(0, 0)
    width = sum(float(reader.call(lambda i=i: table.GetColumnWidth(i), 0.0)) for i in range(columns))
    height = sum(float(reader.call(lambda i=i: table.GetRowHeight(i), 0.0)) for i in row_indices)
    x, y = position[0], position[1]
    return {
        "name": str(reader.call(lambda: inner.GetName(), "table")),
        "box": _round((x, y - height, x + width, y)),
    }


def _round_trip(reader: _Reader, edges: Sequence[Any]) -> dict[str, Any] | None:
    """One model vertex and the index of the polyline its edge drew.

    Offline, projecting ``model`` through the view transform must land on that
    polyline's points -- the coordinate-space proof for ``GetPolylines7``.
    """
    for index, edge in enumerate(edges or ()):
        edge = reader.bind(edge, "IEdge")
        if edge is None:
            continue
        vertex = reader.bind(reader.call(lambda e=edge: e.GetStartVertex()), "IVertex")
        if vertex is None:
            continue
        point = reader.call(lambda v=vertex: v.GetPoint())
        if point:
            return {"polyline_index": index, "model": _round(point)}
    return None


def _dump_view(
    reader: _Reader, view: Any, *, is_pictorial: Callable[[str], bool]
) -> dict[str, Any]:
    view = reader.bind(view, "IView")
    orientation = str(reader.call(lambda: view.GetOrientationName(), ""))
    record: dict[str, Any] = {
        "name": str(reader.call(lambda: view.GetName2(), "")),
        "type": int(reader.call(lambda: view.Type, -1)),
        "orientation": orientation,
        "pictorial": bool(is_pictorial(orientation)),
        "outline": _round(reader.call(lambda: view.GetOutline(), ())),
        "scale": _round(reader.call(lambda: view.ScaleRatio, ())),
        "display_mode": int(reader.call(lambda: view.GetDisplayMode2(), -1)),
    }
    transform = reader.bind(reader.call(lambda: view.ModelToViewTransform), "IMathTransform")
    if transform is not None:
        record["transform"] = _round(reader.call(lambda: transform.ArrayData, ()))
    result = reader.call(lambda: view.GetPolylines7(_EXCLUDE_CROSSHATCH))
    edges, polylines = (), ()
    if isinstance(result, tuple) and len(result) == 2:
        edges, polylines = result
    if polylines:
        record["polylines"] = _round(polylines)
    trip = _round_trip(reader, edges)
    if trip is not None:
        record["round_trip"] = trip
    record["annotations"] = [
        item
        for item in (
            _dump_annotation(reader, annotation)
            for annotation in (reader.call(lambda: view.GetAnnotations(), ()) or ())
        )
        if item is not None
    ]
    sections = []
    for raw in reader.call(lambda: view.GetSectionLines(), ()) or ():
        section = reader.bind(raw, "IDrSection")
        if section is None:
            continue
        text_format = reader.bind(reader.call(lambda s=section: s.GetTextFormat()), "ITextFormat")
        sections.append(
            {
                "label": str(reader.call(lambda s=section: s.GetLabel(), "")),
                "line": _round(reader.call(lambda s=section: s.GetLineInfo(), ())),
                "arrows": _round(reader.call(lambda s=section: s.GetArrowInfo(), ())),
                "texts": _round(reader.call(lambda s=section: s.GetTextInfo(), ())),
                "text_height": round(
                    float(reader.call(lambda: text_format.CharHeight, 0.0)) if text_format else 0.0, 7
                ),
            }
        )
    if sections:
        record["sections"] = sections
    detail = reader.call(lambda: view.GetDetailCircleInfo2())
    if detail:
        record["detail_circles_info"] = _round(detail)
    return record


def collect_sheet_dumps(
    adapter: Any,
    *,
    stem: str,
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> list[dict[str, Any]]:
    """One dump per sheet of the adapter's open drawing, no sheet activated."""
    reader = _Reader(adapter)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # GetViews' sheet order is undetermined; the PDF prints GetSheetNames order.
    page_of = {
        str(name): page for page, name in enumerate(reader.call(lambda: ddoc.GetSheetNames(), ()) or ())
    }
    rows = reader.call(lambda: ddoc.GetViews(), ()) or ()
    dumps = []
    for index, row in enumerate(rows):
        entries = list(row or ())
        if not entries:
            continue
        sheet_view = reader.bind(entries[0], "IView")
        name = str(reader.call(lambda: sheet_view.GetName2(), "") or reader.call(lambda: sheet_view.Name, ""))
        sheet = reader.bind(reader.call(lambda n=name: ddoc.Sheet(n)), "ISheet")
        if sheet is None:
            raise RuntimeError(f"layout audit cannot reach sheet {name!r}")
        properties = _round(reader.call(lambda: sheet.GetProperties2(), ()))
        layout = sheet_layouts.get(name)
        template = DRAWING_TEMPLATES[layout] if layout is not None else None
        width, height = properties[5], properties[6]
        zone = {
            side: float(reader.call(lambda c=code: sheet.GetZoneMargin(c), 0.0))
            for side, code in _ZONE_MARGINS.items()
        }
        dump: dict[str, Any] = {
            "schema": DUMP_SCHEMA,
            "stem": stem,
            "sheet": name,
            "index": index,
            "page": page_of.get(name, -1),
            "layout": layout.value if layout is not None else "",
            "width": width,
            "height": height,
            "zone": zone,
            "views": [_dump_view(reader, view, is_pictorial=is_pictorial) for view in entries[1:]],
            "sheet_annotations": [
                item
                for item in (
                    _dump_annotation(reader, annotation)
                    for annotation in (reader.call(lambda: sheet_view.GetAnnotations(), ()) or ())
                )
                if item is not None
            ],
        }
        if template is not None:
            dump["title_block"] = _round(
                (template.title_block_left_m, 0.0, width, template.title_block_top_m)
            )
        tables: dict[str, dict[str, Any]] = {}
        for view in entries:
            view = reader.bind(view, "IView")
            for raw in reader.call(lambda v=view: v.GetTableAnnotations(), ()) or ():
                record = _table_record(reader, raw)
                if record is not None:
                    tables[record["name"]] = record
        dump["tables"] = list(tables.values())
        dump["read_errors"] = reader.errors
        dumps.append(dump)
    return dumps


# A view's polylines are logged only up to this many values (~30k points):
# an assembly view can carry millions, which no log line should. The in-process
# audit always reads the full array; only the logged replay copy is trimmed.
_LOGGED_POLYLINE_VALUES = 300_000


def loggable_dump(dump: Mapping[str, Any]) -> dict[str, Any]:
    """``dump`` with oversized view polylines replaced by their size."""
    views = []
    for view in dump.get("views", ()):
        polylines = view.get("polylines") or ()
        if len(polylines) > _LOGGED_POLYLINE_VALUES:
            view = {k: v for k, v in view.items() if k != "polylines"}
            view["polylines_omitted"] = len(polylines)
        views.append(view)
    return {**dump, "views": views}


def run_layout_audit(
    adapter: Any,
    *,
    stem: str,
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
    mode: LayoutAuditMode = LAYOUT_AUDIT_MODE,
) -> None:
    """Dump, audit and report every sheet; under GATE, raise on a gating finding.

    REPORT never fails the drawing, not even on a collector fault: the fleet
    run it exists for must finish, and a fault is logged with its traceback
    for the calibration to see.
    """
    with _telemetry.span("drawing.layout_audit", stem=stem, mode=mode.value):
        started = time.perf_counter()
        try:
            dumps = collect_sheet_dumps(
                adapter, stem=stem, sheet_layouts=sheet_layouts, is_pictorial=is_pictorial
            )
        except Exception:
            if mode is LayoutAuditMode.GATE:
                raise
            _telemetry.error(f"layout-audit-error {stem} collect\n{traceback.format_exc()}")
            return
        collected = time.perf_counter() - started
        gating = []
        counts: dict[str, int] = {}
        for dump in dumps:
            for line in encode_dump_lines(stem, loggable_dump(dump)):
                _telemetry.info(line)
            try:
                findings = audit_dump(dump)
            except Exception:
                if mode is LayoutAuditMode.GATE:
                    raise
                _telemetry.error(
                    f"layout-audit-error {stem} audit {dump.get('sheet')}\n{traceback.format_exc()}"
                )
                continue
            for finding in findings:
                record = finding_record(stem, finding)
                counts[finding.kind] = counts.get(finding.kind, 0) + 1
                _telemetry.info(f"{FINDING_PREFIX} {json.dumps(record, separators=(',', ':'))}")
                if severity(finding) is FindingSeverity.GATING:
                    gating.append(finding)
        summary = {
            "stem": stem,
            "mode": mode.value,
            "sheets": len(dumps),
            "collect_s": round(collected, 3),
            "total_s": round(time.perf_counter() - started, 3),
            "findings": counts,
            "gating": len(gating),
        }
        _telemetry.info(f"{SUMMARY_PREFIX} {json.dumps(summary, separators=(',', ':'))}")
        if gating and mode is LayoutAuditMode.GATE:
            raise RuntimeError(
                f"drawing layout audit failed for {stem}: {len(gating)} gating finding(s):\n"
                + "\n".join(f"  - {finding.format()}" for finding in gating)
            )
