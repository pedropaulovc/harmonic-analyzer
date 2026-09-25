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
* every view's outline and orientation;
* section lines (``IDrSection`` line, arrows, label origins, text height) and
  detail circles (``IView::GetDetailCircleInfo2``);
* tables, boxed from anchor + row/column spans (as ``_drawing_common`` does);
* the sheet size, zone margins and title-block keep-out;
* the sheet's page of the exported PDF (``_pdf_ink``): every text object with
  its tight glyph box, and every black stroke with its width and dash. The
  PDF is where text and model edges are measured; COM says what each is.

The dumps are audited by the SolidWorks-free ``_layout_audit.audit_dump`` and
written, with every finding, to the drawing's report
(``_drawing_registry.layout_report_path``), a declared task target that rides
the remote cache: the offline calibration and tests replay exactly what the
building seat saw, whether the leaf was built or restored.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping

import _telemetry
from _common import _early_bound
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from _pdf_ink import PageInk, page_ink, read_pdf_ink
from _layout_audit import (
    DUMP_SCHEMA,
    LAYOUT_AUDIT_MODE,
    LayoutAuditMode,
    audit_report,
)

_ANNOT_DIM = 4
_ANNOT_NOTE = 6
_ANNOT_DATUM_ORIGIN = 16
# How far a PDF page may differ from its sheet's GetProperties2 size.
PAGE_SIZE_TOL_M = 0.0005
# swZoneMargin_e
_ZONE_MARGINS = {"top": 0, "bottom": 1, "right": 2, "left": 3}

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
    """Tolerant COM reads: an accessor that does not apply returns ``default``.

    Every refusal is counted per sheet under the accessor's name. A refused
    read can drop an annotation's ink or text from the audit, so any count is
    a gating ``com-read-errors`` finding. A read the audit cannot do without
    (``need``) also counts a ``None`` answer: SolidWorks often fails that way
    instead of raising.
    """

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.errors: dict[str, int] = {}

    def _count(self, name: str) -> None:
        self.errors[name] = self.errors.get(name, 0) + 1

    def call(self, fn: Callable[[], Any], default: Any = None, *, name: str = "", required: bool = False) -> Any:
        try:
            value = fn()
        except Exception:
            self._count(name or _accessor(fn))
            return default
        if value is None and required:
            self._count(name or _accessor(fn))
        return default if value is None else value

    def need(self, fn: Callable[[], Any], default: Any = None, *, name: str = "") -> Any:
        """``call`` for a read whose ``None`` loses ink or text."""
        return self.call(fn, default, name=name, required=True)

    def first(self, fns: list[Callable[[], Any]], *, name: str) -> Any:
        """The first of some ARRAY-returning overloads that answers (a scalar 0
        or False would read as empty: never route a scalar getter here); one
        refusal counted only when all do
        (``GetLineAtIndex3`` refusing before ``GetLineAtIndex2`` answers is the
        expected path, not a lost primitive). An empty answer falls through to
        the next overload, but is returned, uncounted, when none answers with
        data; only raising or None from every overload is a refusal."""
        empty = None
        for fn in fns:
            try:
                value = fn()
            except Exception:
                continue
            if value:
                return value
            if value is not None and empty is None:
                empty = value
        if empty is None:
            self._count(name)
        return empty

    def bind(self, obj: Any, interface: str) -> Any:
        if obj is None:
            return None
        try:
            return _early_bound(obj, interface)
        except Exception:
            self._count(f"bind {interface}")
            return None

    def take_errors(self) -> dict[str, int]:
        errors, self.errors = self.errors, {}
        return dict(sorted(errors.items()))


def _accessor(fn: Callable[[], Any]) -> str:
    return fn.__code__.co_names[-1] if fn.__code__.co_names else "?"


def _dump_display(reader: _Reader, data: Any) -> dict[str, Any]:
    data = reader.bind(data, "IDisplayData")
    if data is None:
        return {}
    out: dict[str, Any] = {}
    for key, count_name, getters in _DISPLAY_PRIMITIVES:
        count = int(reader.call(lambda c=count_name: getattr(data, c)(), 0, name=count_name) or 0)
        rows = []
        for index in range(count):
            raw = reader.first(
                [lambda g=getter, i=index: getattr(data, g)(i) for getter in getters], name="/".join(getters)
            )
            if raw:
                rows.append(_round(raw))
        if rows:
            out[key] = rows
    texts = []
    for index in range(int(reader.call(lambda: data.GetTextCount(), 0) or 0)):
        texts.append(
            {
                "t": str(reader.need(lambda i=index: data.GetTextAtIndex(i), "")),
                "pos": _round(reader.need(lambda i=index: data.GetTextPositionAtIndex(i), ())),
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
        points = reader.need(lambda i=index: annotation.GetLeaderPointsAtIndex(i))
        if points:
            leaders.append(_round(points))
    if leaders:
        record["leaders"] = leaders
    record["display"] = _dump_display(reader, reader.need(lambda: annotation.GetDisplayData()))
    specific = (
        reader.need(lambda: annotation.GetSpecificAnnotation())
        if kind in (_ANNOT_NOTE, _ANNOT_DIM, _ANNOT_DATUM_ORIGIN)
        else None
    )
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
            # IDisplayDimension::GetDisplayData is not read: on the d09c2b9eb
            # calibration leaves it equalled IAnnotation's for all 72 dimensions.
            record["dim"] = {"hole_callout": bool(reader.call(lambda: display.IsHoleCallout(), False))}
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
        "outline": _round(reader.need(lambda: view.GetOutline(), ())),
        "scale": _round(reader.call(lambda: view.ScaleRatio, ())),
        "display_mode": int(reader.call(lambda: view.GetDisplayMode2(), -1)),
    }
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
                "line": _round(reader.need(lambda s=section: s.GetLineInfo(), ())),
                "arrows": _round(reader.need(lambda s=section: s.GetArrowInfo(), ())),
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
    pdf: Path,
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> list[dict[str, Any]]:
    """One dump per sheet of the adapter's open drawing, no sheet activated,
    each carrying its page of the exported ``pdf``."""
    with _telemetry.span("layout.read_pdf", pdf=pdf.name) as span:
        pages = read_pdf_ink(pdf)
        span.set_attribute("pages", len(pages))
    with _telemetry.span("layout.collect_com", stem=stem) as span:
        dumps = _collect_com(adapter, stem=stem, pdf=pdf, pages=pages, sheet_layouts=sheet_layouts, is_pictorial=is_pictorial)
        span.set_attribute("sheets", len(dumps))
    return dumps


def _collect_com(
    adapter: Any,
    *,
    stem: str,
    pdf: Path,
    pages: list[PageInk],
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> list[dict[str, Any]]:
    reader = _Reader(adapter)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # GetViews' sheet order is undetermined; the PDF prints GetSheetNames order.
    # Both are read strictly: a tolerant empty answer would audit no sheet and
    # cache a clean report.
    page_of = {str(name): page for page, name in enumerate(ddoc.GetSheetNames() or ())}
    if not page_of or len(pages) != len(page_of):
        raise RuntimeError(
            f"layout audit: {len(page_of)} sheet(s) but {len(pages)} page(s) in {pdf.name}"
        )
    rows = ddoc.GetViews() or ()
    dumps = []
    for index, row in enumerate(rows):
        entries = list(row or ())
        if not entries:
            continue
        try:
            dump = _dump_sheet(
                reader, ddoc, entries, index=index, stem=stem, pdf=pdf, pages=pages, page_of=page_of,
                sheet_layouts=sheet_layouts, is_pictorial=is_pictorial,
            )
        except Exception as exc:
            raise _collector_fault(stem, dumps, reader, exc) from exc
        dumps.append(dump)
    audited = sorted(str(dump["sheet"]) for dump in dumps)
    if audited != sorted(page_of):
        raise RuntimeError(f"layout audit: dumped sheets {audited}, drawing has {sorted(page_of)}")
    return dumps


def _collector_fault(stem: str, dumps: list[dict[str, Any]], reader: _Reader, exc: Exception) -> RuntimeError:
    """The error a collector fault raises, and a warn saying how far it got.

    Fail loud: no report is written. What was collected up to the fault
    (the sheets dumped, each one's refused reads, and the refusals on the
    sheet it died in) rides the error and the warn instead.
    """
    done = {str(dump["sheet"]): dump["read_errors"] for dump in dumps}
    progress = f"{len(done)} sheet(s) dumped {done}; refused reads on the failing sheet {dict(reader.errors)}"
    _telemetry.warn(f"layout audit {stem}: collector fault after {progress}: {exc}")
    return RuntimeError(f"layout audit {stem}: collector fault after {progress}: {exc}")


def _dump_sheet(
    reader: _Reader,
    ddoc: Any,
    entries: list[Any],
    *,
    index: int,
    stem: str,
    pdf: Path,
    pages: list[PageInk],
    page_of: Mapping[str, int],
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> dict[str, Any]:
    """One sheet's dump: ``entries`` is its ``GetViews`` row (sheet view first)."""
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
    page = dump["page"]
    if not 0 <= page < len(pages):
        raise RuntimeError(
            f"layout audit: sheet {name!r} is page {page} of {pdf.name}, which has {len(pages)}"
        )
    # A page of another size, or an origin/scale mismatch, would place all
    # the ink wrong; the size is checked here, placement by the text match
    # rate in _layout_audit.sheet_model.
    ink = pages[page]
    if abs(ink.width - width) > PAGE_SIZE_TOL_M or abs(ink.height - height) > PAGE_SIZE_TOL_M:
        raise RuntimeError(
            f"layout audit: sheet {name!r} is {width * 1000:.1f} x {height * 1000:.1f} mm but page "
            f"{page} of {pdf.name} is {ink.width * 1000:.1f} x {ink.height * 1000:.1f} mm"
        )
    dump["ink"] = page_ink(ink)
    dump["read_errors"] = reader.take_errors()
    return dump


def run_layout_audit(
    adapter: Any,
    *,
    stem: str,
    pdf: Path,
    report: Path,
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
    mode: LayoutAuditMode = LAYOUT_AUDIT_MODE,
) -> None:
    """Dump and audit every sheet, write ``report``; under GATE, raise on a gating finding.

    A collector or audit fault fails the drawing in every mode: a report that
    silently skipped a sheet would under-count the fleet calibration.
    """
    with _telemetry.span(f"layout.audit {stem}", stem=stem, mode=mode.value) as span:
        started = time.perf_counter()
        dumps = collect_sheet_dumps(
            adapter, stem=stem, pdf=pdf, sheet_layouts=sheet_layouts, is_pictorial=is_pictorial
        )
        collected = time.perf_counter() - started
        with _telemetry.span("layout.findings", stem=stem) as child:
            finding_started = time.perf_counter()
            content, gating = audit_report(stem, mode, dumps)
            child.set_attribute("findings_s", round(time.perf_counter() - finding_started, 3))
            for kind, count in content["summary"]["findings"].items():
                child.set_attribute(f"findings.{kind}", count)
        summary = content["summary"]
        summary["collect_s"] = round(collected, 3)
        summary["total_s"] = round(time.perf_counter() - started, 3)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(content, separators=(",", ":")), encoding="utf-8")
        for record in content["findings"]:
            _telemetry.debug(f"layout finding {stem}: {record['kind']}: {record['detail']}")
        span.set_attribute("sheets", summary["sheets"])
        span.set_attribute("gating", summary["gating"])
        span.set_attribute("collect_s", summary["collect_s"])
        read_errors = sum(sum(d["read_errors"].values()) for d in dumps)
        span.set_attribute("read_errors", read_errors)
        if read_errors:
            _telemetry.warn(
                f"layout audit {stem}: {read_errors} refused COM read(s): "
                + "; ".join(f"{d['sheet']}: {d['read_errors']}" for d in dumps if d["read_errors"])
            )
        for kind, count in summary["findings"].items():
            span.set_attribute(f"findings.{kind}", count)
        _telemetry.info(
            f"layout audit {stem}: {summary['sheets']} sheet(s), {summary['gating']} gating, "
            f"{summary['findings']} -> {report}"
        )
        if gating and mode is LayoutAuditMode.GATE:
            raise RuntimeError(
                f"drawing layout audit failed for {stem}: {len(gating)} gating finding(s):\n"
                + "\n".join(f"  - {finding.format()}" for finding in gating)
            )
