r"""Calibrate the unified layout audit: how COM's text model compares to the ink.

WHY THIS EXISTS
---------------
``_layout_audit`` measures text and model edges on the drawing's own vector
PDF (the page each sheet dump carries) and uses COM display data to say WHAT
each run of ink is. The two only agree when every COM text item finds the PDF
text object that printed it. This tool replays drawing layout reports and
reports, per annotation kind:

* how often a COM text item matched a PDF text object, in the audit's own
  assignment (``assign_sheet_text``, view labels included);
* the COM-vs-ink offsets of the matched items (left edge, baseline, ink
  height over COM height), in millimetres;
* the unmatched items (the audit reports each as ``text-unmatched``);
* per view, how many model edges (0.25 mm solid strokes) it owns;
* the findings, per kind.

INPUTS
------
``--report``: one or more drawing layout reports
(cad/out/reports/layout-audit/<stem>.json, a cached drawing-task target, so a
restored leaf has one too). A report keeps each page's text but only a count
of its strokes; ``--pdf-dir`` (cad/out/pdf, also cached) re-reads them, so
model-edge findings replay too.

    uv run python cad/scripts/diagnostics/layout_calibration.py \
        --report cad/out/reports/layout-audit/*.json --pdf-dir cad/out/pdf --json calib.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _layout_audit import (  # noqa: E402
    ANNOTATION_KINDS,
    assign_sheet_text,
    audit_dump,
    audited_annotations,
    ink_edges,
    ink_key,
    ink_spans,
    span_box,
    text_items,
    view_edges,
)
from _layout_geometry import Box  # noqa: E402
from _pdf_ink import page_ink, read_pdf_ink  # noqa: E402

MM = 1000.0


def _annotations(dump: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(kind, annotation) for every annotation the audit matches
    (``audited_annotations``): a hidden one is left out, so it cannot claim a
    visible annotation's printed text or count as unmatched."""
    return [(ANNOTATION_KINDS.get(int(a.get("type", 0)), "other"), a) for a in audited_annotations(dump)]


def match_items(dump: dict[str, Any]) -> list[dict[str, Any]]:
    """Every keyed COM text item against the PDF text object the audit
    matched: the sheet's one assignment (``assign_sheet_text``), in which the
    section and detail labels compete for the same spans. Only annotation
    runs are reported."""
    annotations = _annotations(dump)
    spans = ink_spans(dump)
    chosen = assign_sheet_text(dump, [annotation for _kind, annotation in annotations], spans)
    keyed = [
        ((id(annotation), index), (kind, annotation, item))
        for kind, annotation in annotations
        for index, item in enumerate(text_items(annotation.get("display") or {}))
        if ink_key(item.text)
    ]
    records = []
    for key, (kind, annotation, item) in keyed:
        box = span_box(spans, chosen[key]) if key in chosen else None
        record = {
            "kind": kind,
            "label": str(annotation.get("name", "")),
            "text": item.text,
            "com_xy_mm": [item.x * MM, item.y * MM],
            "height_mm": item.height * MM,
            "matched": box is not None,
        }
        if box is not None:
            record.update(
                {
                    "pdf_box_mm": [box.xmin * MM, box.ymin * MM, box.xmax * MM, box.ymax * MM],
                    "d_left_mm": (box.xmin - item.x) * MM,
                    "d_bottom_mm": (box.ymin - item.y) * MM,
                    "ink_height_mm": box.height * MM,
                }
            )
        records.append(record)
    return records


def view_edge_counts(dump: dict[str, Any]) -> dict[str, int]:
    outlines = [
        (str(view.get("name", "")), Box(*view["outline"][:4]))
        for view in dump.get("views", ())
        if len(view.get("outline") or ()) >= 4
    ]
    owned = view_edges(ink_edges(dump), outlines)
    return {name: len(owned.get(name, ())) for name, _box in outlines}


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


def with_strokes(dump: dict[str, Any], pdf_dir: Path | None) -> dict[str, Any]:
    """The dump with its page's strokes re-read from the drawing's PDF."""
    if "strokes" in (dump.get("ink") or {}):
        return dump
    if pdf_dir is None:
        raise SystemExit(f"{dump.get('stem')}: the report keeps no strokes; pass --pdf-dir")
    pages = read_pdf_ink(pdf_dir / f"{dump['stem']}.pdf")
    return {**dump, "ink": page_ink(pages[int(dump["page"])])}


def calibrate(reports: list[Path], pdf_dir: Path | None = None) -> dict[str, Any]:
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in reports]
    report: dict[str, Any] = {
        "sheets": [],
        "summaries": [{"stem": r["stem"], **r["summary"]} for r in loaded],
    }
    records: list[dict[str, Any]] = []
    for dump in (with_strokes(dump, pdf_dir) for r in loaded for dump in r["sheets"]):
        items = match_items(dump)
        records.extend({"stem": dump.get("stem"), **item} for item in items)
        report["sheets"].append(
            {
                "stem": dump.get("stem"),
                "sheet": dump.get("sheet"),
                "page": dump.get("page"),
                "findings": dict(Counter(f.kind for f in audit_dump(dump))),
                "item_match_rate": sum(i["matched"] for i in items) / len(items) if items else None,
                "view_edges": view_edge_counts(dump),
                "read_errors": dump.get("read_errors"),
            }
        )
    by_kind: dict[str, dict[str, Any]] = {}
    for kind in sorted({r["kind"] for r in records}):
        subset = [r for r in records if r["kind"] == kind]
        matched = [r for r in subset if r["matched"]]
        by_kind[kind] = {
            "items": len(subset),
            "item_match_rate": len(matched) / len(subset),
            "d_left_mm": _summarise([r["d_left_mm"] for r in matched]),
            "d_bottom_mm": _summarise([r["d_bottom_mm"] for r in matched]),
            "ink_height_over_h": _summarise([r["ink_height_mm"] / r["height_mm"] for r in matched]),
        }
    report["text_by_kind"] = by_kind
    report["unmatched_items"] = [r for r in records if not r["matched"]][:200]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, nargs="+", required=True)
    parser.add_argument("--pdf-dir", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = calibrate(args.report, args.pdf_dir)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    for sheet in report["sheets"]:
        print(
            f"{sheet['stem']} / {sheet['sheet']} (page {sheet['page']}): findings={sheet['findings']} "
            f"match={sheet['item_match_rate']} view_edges={sheet['view_edges']}"
        )
    for kind, stats in report["text_by_kind"].items():
        print(f"  {kind}: {json.dumps(stats, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
