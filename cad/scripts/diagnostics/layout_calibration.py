r"""Calibrate the unified layout audit against the ink each leaf actually printed.

WHY THIS EXISTS
---------------
``_layout_audit`` boxes text from COM display data and places model edges from
``IView::GetPolylines7``. Neither API documents what it needs: the text WIDTH
(no API returns it) and the polylines' coordinate SPACE. The drawing leaf's own
vector PDF answers both exactly -- SolidWorks exports text as real PDF text
objects (tight glyph boxes) and every line as a stroked path with its width --
so this tool replays each leaf's layout report against that PDF and reports:

* text: how often a COM text row matches a PDF text object 1:1 (by string and
  position), per annotation kind, and the COM-vs-PDF edge errors (left, right,
  bottom, top) in millimetres;
* model edges: which coordinate space each view's polylines resolved to, the
  model-vertex round trip, and how much of the COM geometry lies on a PDF
  stroke of the model-edge weight;
* findings: the COM-box audit next to the same audit run on PDF glyph boxes
  (attributed to the COM annotation they matched), per kind.

INPUTS
------
``--report``: one or more drawing layout reports
(cad/out/reports/layout-audit/<stem>.json, a cached drawing-task target, so a
restored leaf has one too). ``--pdf-dir``: where each drawing's ``<stem>.pdf``
lives (cad/out/pdf).

    uv run python cad/scripts/diagnostics/layout_calibration.py \
        --report cad/out/reports/layout-audit/*.json --pdf-dir cad/out/pdf --json calib.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _layout_audit import (  # noqa: E402
    ANNOTATION_KINDS,
    TextItem,
    _TOKEN,
    apply_transform,
    audit_dump,
    sheet_model,
    text_items,
)
from _layout_geometry import Box  # noqa: E402
from _pdf_ink import PageInk, Span, read_pdf_ink  # noqa: E402

MM = 1000.0
# How far (sheet metres) a PDF run may sit from a COM row and still be the
# same text: generous, because the question is identity, not accuracy.
MATCH_WINDOW_M = 0.003


def _normal(text: str) -> str:
    """Compare strings as printed: tokens are path glyphs, blanks carry no ink."""
    return re.sub(r"\s+", "", _TOKEN.sub("", text)).upper()


def _item_rows(dump: dict[str, Any]) -> list[tuple[str, str, list[TextItem]]]:
    """(kind, label, items) for every annotation, straight from display data."""
    out = []
    for view in dump.get("views", ()):
        for annotation in view.get("annotations", ()):
            kind = ANNOTATION_KINDS.get(int(annotation.get("type", 0)), "other")
            items = text_items(annotation.get("display") or {})
            if items:
                out.append((kind, str(annotation.get("name", "")), items))
    for annotation in dump.get("sheet_annotations", ()):
        if int(annotation.get("owner_type", 1)) != 1:
            continue
        kind = ANNOTATION_KINDS.get(int(annotation.get("type", 0)), "other")
        items = text_items(annotation.get("display") or {})
        if items:
            out.append((kind, str(annotation.get("name", "")), items))
    return out


def match_items(dump: dict[str, Any], page: PageInk) -> list[dict[str, Any]]:
    """Every COM text ITEM against the PDF text object that printed it.

    One display-data item is expected to be one PDF text object. The match is
    by normalised string within ``MATCH_WINDOW_M`` of the item's lower-left.
    """
    spans_by_text: dict[str, list[Span]] = defaultdict(list)
    for span in page.spans:
        spans_by_text[_normal(span.text)].append(span)
    records = []
    for kind, label, items in _item_rows(dump):
        for item in items:
            key = _normal(item.text)
            if not key:
                continue
            candidates = [
                span
                for span in spans_by_text.get(key, ())
                if abs(span.xmin - item.x) < MATCH_WINDOW_M + item.height
                and abs(span.ymin - item.y) < MATCH_WINDOW_M
            ]
            best = min(
                candidates,
                key=lambda s: abs(s.xmin - item.x) + abs(s.ymin - item.y),
                default=None,
            )
            record = {
                "kind": kind,
                "label": label,
                "text": item.text,
                "com_xy_mm": [item.x * MM, item.y * MM],
                "height_mm": item.height * MM,
                "ref": item.reference,
                "matched": best is not None,
            }
            if best is not None:
                record.update(
                    {
                        "pdf_box_mm": [best.xmin * MM, best.ymin * MM, best.xmax * MM, best.ymax * MM],
                        "d_left_mm": (best.xmin - item.x) * MM,
                        "d_bottom_mm": (best.ymin - item.y) * MM,
                        "ink_height_mm": (best.ymax - best.ymin) * MM,
                        "ink_width_per_glyph_h": (best.xmax - best.xmin)
                        / max(1, len(key))
                        / item.height,
                    }
                )
            records.append(record)
    return records


def row_errors(dump: dict[str, Any], page: PageInk) -> list[dict[str, Any]]:
    """Each COM ROW box against the union of PDF runs lying on it."""
    model = sheet_model(dump)
    out = []
    for annotation in model.geometry.annotations:
        if annotation.kind in ("geometry", "table") or annotation.exact:
            continue
        for box in annotation.text_boxes:
            grown = Box(box.xmin - 0.002, box.ymin - 0.001, box.xmax + 0.002, box.ymax + 0.001)
            inside = [
                span
                for span in page.spans
                if grown.xmin <= (span.xmin + span.xmax) / 2 <= grown.xmax
                and grown.ymin <= (span.ymin + span.ymax) / 2 <= grown.ymax
            ]
            if not inside:
                out.append({"kind": annotation.kind, "label": annotation.label, "matched": False})
                continue
            ink = Box(
                min(s.xmin for s in inside),
                min(s.ymin for s in inside),
                max(s.xmax for s in inside),
                max(s.ymax for s in inside),
            )
            out.append(
                {
                    "kind": annotation.kind,
                    "label": annotation.label,
                    "matched": True,
                    "d_left_mm": (box.xmin - ink.xmin) * MM,
                    "d_right_mm": (box.xmax - ink.xmax) * MM,
                    "d_bottom_mm": (box.ymin - ink.ymin) * MM,
                    "d_top_mm": (box.ymax - ink.ymax) * MM,
                }
            )
    return out


def view_space(dump: dict[str, Any], page: PageInk | None) -> list[dict[str, Any]]:
    """Per view: polyline space, round trip, and coverage by PDF model strokes."""
    model = sheet_model(dump)
    by_name = {ink.name: ink for ink in model.view_ink}
    out = []
    for view in dump.get("views", ()):
        name = str(view.get("name", ""))
        ink = by_name.get(name)
        record: dict[str, Any] = {
            "view": name,
            "space": ink.space if ink else "none",
            "inside_fraction": round(ink.inside_fraction, 3) if ink else 0.0,
            "segments": len(ink.segments) if ink else 0,
        }
        trip = view.get("round_trip")
        transform = view.get("transform")
        if trip and transform:
            model_xyz = trip["model"]
            projected = apply_transform(transform, *model_xyz[:3])
            records = _polyline_records(view.get("polylines") or [])
            index = int(trip["polyline_index"])
            if 0 <= index < len(records):
                points = records[index]
                nearest = min(
                    ((projected[0] - x) ** 2 + (projected[1] - y) ** 2) ** 0.5 for x, y in points
                )
                record["round_trip_mm"] = nearest * MM
        if page is not None and ink is not None and ink.segments:
            model_strokes = [s for s in page.strokes if s.stroked and not s.dashed and s.rgb == (0, 0, 0)]
            widths = Counter(round(s.width * MM, 2) for s in model_strokes)
            record["pdf_black_stroke_widths_mm"] = dict(widths)
            covered = 0
            for segment in ink.segments[:400]:
                mx, my = (segment.x0 + segment.x1) / 2, (segment.y0 + segment.y1) / 2
                if any(_point_segment(mx, my, s) < 1e-4 for s in model_strokes):
                    covered += 1
            record["covered_by_pdf_stroke"] = covered / min(400, len(ink.segments))
        out.append(record)
    return out


def _polyline_records(values: list[float]) -> list[list[tuple[float, float]]]:
    records = []
    index = 0
    while index + 2 <= len(values):
        size = int(values[index + 1])
        count_at = index + 2 + size + 6
        if count_at >= len(values):
            break
        count = int(values[count_at])
        points = values[count_at + 1 : count_at + 1 + 3 * count]
        records.append([(points[i], points[i + 1]) for i in range(0, len(points) - 2, 3)])
        index = count_at + 1 + 3 * count
    return records


def _point_segment(x: float, y: float, s: Any) -> float:
    dx, dy = s.x1 - s.x0, s.y1 - s.y0
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((x - s.x0) * dx + (y - s.y0) * dy) / length2))
    return ((x - s.x0 - t * dx) ** 2 + (y - s.y0 - t * dy) ** 2) ** 0.5


def _summarise(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": median(ordered),
        "p05": ordered[int(0.05 * (len(ordered) - 1))],
        "p95": ordered[int(0.95 * (len(ordered) - 1))],
        "min": ordered[0],
        "max": ordered[-1],
    }


def calibrate(reports: list[Path], pdf_dir: Path | None) -> dict[str, Any]:
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in reports]
    dumps = [dump for report in loaded for dump in report["sheets"]]
    summaries = [{"stem": report["stem"], **report["summary"]} for report in loaded]
    logged_findings = [finding for report in loaded for finding in report["findings"]]
    report: dict[str, Any] = {"sheets": [], "summaries": summaries}
    item_records: list[dict[str, Any]] = []
    row_records: list[dict[str, Any]] = []
    for dump in dumps:
        stem, page_index = str(dump.get("stem")), int(dump.get("page", dump.get("index", 0)))
        page = None
        pdf = (pdf_dir / f"{stem}.pdf") if pdf_dir else None
        if pdf is not None and pdf.is_file():
            pages = read_pdf_ink(pdf)
            if 0 <= page_index < len(pages):
                page = pages[page_index]
        findings = audit_dump(dump)
        sheet: dict[str, Any] = {
            "stem": stem,
            "sheet": dump.get("sheet"),
            "page": page_index,
            "pdf": str(pdf) if page is not None else None,
            "findings": dict(Counter(f.kind for f in findings)),
            "views": view_space(dump, page),
            "read_errors": dump.get("read_errors"),
        }
        if page is not None:
            items = match_items(dump, page)
            rows = row_errors(dump, page)
            item_records.extend({"stem": stem, **r} for r in items)
            row_records.extend({"stem": stem, **r} for r in rows)
            sheet["item_match_rate"] = (
                sum(r["matched"] for r in items) / len(items) if items else None
            )
        report["sheets"].append(sheet)
    by_kind: dict[str, dict[str, Any]] = {}
    for kind in sorted({r["kind"] for r in item_records}):
        subset = [r for r in item_records if r["kind"] == kind]
        matched = [r for r in subset if r["matched"]]
        rows = [r for r in row_records if r["kind"] == kind and r["matched"]]
        by_kind[kind] = {
            "items": len(subset),
            "item_match_rate": len(matched) / len(subset),
            "d_left_mm": _summarise([r["d_left_mm"] for r in matched]),
            "d_bottom_mm": _summarise([r["d_bottom_mm"] for r in matched]),
            "ink_height_over_h": _summarise([r["ink_height_mm"] / r["height_mm"] for r in matched]),
            "ref_positions": dict(Counter(r["ref"] for r in subset)),
            "row_d_right_mm": _summarise([r["d_right_mm"] for r in rows]),
            "row_d_left_mm": _summarise([r["d_left_mm"] for r in rows]),
            "row_d_top_mm": _summarise([r["d_top_mm"] for r in rows]),
        }
    report["text_by_kind"] = by_kind
    report["unmatched_items"] = [r for r in item_records if not r["matched"]][:200]
    report["logged_findings"] = dict(Counter(f["kind"] for f in logged_findings))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, nargs="+", required=True)
    parser.add_argument("--pdf-dir", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = calibrate(args.report, args.pdf_dir)
    text = json.dumps(report, indent=2, default=str)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    for sheet in report["sheets"]:
        print(
            f"{sheet['stem']} / {sheet['sheet']} (page {sheet['page']}): "
            f"findings={sheet['findings']} match={sheet.get('item_match_rate')} "
            f"views={[(v['view'], v['space'], v.get('round_trip_mm'), v.get('covered_by_pdf_stroke')) for v in sheet['views']]}"
        )
    for kind, stats in report["text_by_kind"].items():
        print(f"  {kind}: {json.dumps(stats, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
