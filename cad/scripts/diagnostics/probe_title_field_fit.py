r"""THROWAWAY route-B probe: do the title block's identity cells take the
cut-over identities natively, in both templates?

The identity cutover prints a 10-character ``MHA-XX-###`` (cone-gear sheets a
15-character ``MHA-DT-003-T###``) in DWG. NO. and a slug of up to 29
characters in PART, where v39 printed 7-character Numbers. For three scratch
parts -- the v39 shape as positive control, a 10-character Number with a
29-character Title, the widest printed Number with the other 29-character
Title -- on a drawing from each checked-in template (neither is modified),
this records what SolidWorks itself reports for every title-block note
(``PropertyLinkedText``, ``GetText``, ``GetExtent``, ``GetExtentAtIndex``,
position, text point, upper right, heights, text format, display-data text
runs), the permanent contract's readings and verdicts
(``_drawing_title_fields``), and the exported PDF's glyph boxes with the
layout audit's printed-fit measure (``_layout_audit.title_field_fits``).

Outputs (all under ``cad/out/probe/title-field-fit/``): ``title-field-fit.json``
and one PDF per case and orientation (:data:`PDFS`). Scratch parts and
drawings land in ``scratch/`` beside them, undeclared.

Delete this script and its dodo task once the proof is recorded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _config  # noqa: E402
import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    CAD_ROOT,
    _early_bound,
    apply_custom_properties,
    apply_summary_info,
    check,
    run_build,
)
from _drawing_common import new_project_drawing, rebuild_drawing  # noqa: E402
from _drawing_layout_audit import annotation_display  # noqa: E402
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout  # noqa: E402
from _drawing_title_fields import audit_records, read_title_fields  # noqa: E402
from _layout_audit import find_title_field_misfits, title_field_fits  # noqa: E402
from _pdf_ink import page_ink, read_pdf_ink  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import place_view, save_drawing  # noqa: E402

OUT = CAD_ROOT / "out" / "probe" / "title-field-fit"
SCRATCH = OUT / "scratch"
REPORT = OUT / "title-field-fit.json"
# case -> (Number, Title)
CASES = {
    # v39's cone-gear sheet 1 printed exactly these.
    "control-v39": ("MHA-013", "cone-gear"),
    # The registry row of the 29-character pd slug.
    "number10-title29": ("MHA-PD-015", "pd-transgear-knob-thrust-ring"),
    # The widest Number any sheet prints (cone-gear's configuration Number)
    # beside the other 29-character slug.
    "number15-title29": ("MHA-DT-003-T006", "vn-transgear-collar-cross-pin"),
}
LAYOUTS = (DrawingLayout.LANDSCAPE, DrawingLayout.PORTRAIT)
PDFS = {(case, layout): OUT / f"{case}-{layout.value}.pdf" for case in CASES for layout in LAYOUTS}
# swAnnotationOwner_DrawingTemplate, swNote
_OWNER_DRAWING_TEMPLATE = 2
_ANNOT_NOTE = 6


def _read(read: Callable[[], Any]) -> Any:
    """One COM read as JSON: lists for arrays, an error string on refusal."""
    try:
        value = read()
    except Exception as exc:  # noqa: BLE001 - a refused read is evidence too
        return f"<error: {exc}>"
    if isinstance(value, (tuple, list)):
        return [float(item) if isinstance(item, (int, float)) else str(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str, dict)):
        return value
    return str(value)


def _text_format(annotation: Any) -> dict[str, Any]:
    raw = annotation.GetTextFormat(0)
    if raw is None:
        return {}
    text_format = _early_bound(raw, "ITextFormat")
    return {
        name: _read(lambda n=name: getattr(text_format, n))
        for name in (
            "TypeFaceName",
            "CharHeight",
            "CharHeightInPts",
            "IsHeightSpecifiedInPts",
            "LineLength",
            "LineSpacing",
            "WidthFactor",
            "CharSpacingFactor",
            "Bold",
            "Italic",
        )
    }


def _template_notes(adapter: Any, sheet_view: Any) -> list[dict[str, Any]]:
    """Every title-block/sheet-format note on the sheet, as SolidWorks reports it."""
    notes = []
    for raw in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.OwnerType) != _OWNER_DRAWING_TEMPLATE or int(annotation.GetType()) != _ANNOT_NOTE:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        display, refused = annotation_display(adapter, annotation)
        notes.append(
            {
                "name": _read(annotation.GetName),
                "link": _read(lambda: note.PropertyLinkedText),
                "text": _read(note.GetText),
                "extent": _read(note.GetExtent),
                "extent_at_1": _read(lambda: note.GetExtentAtIndex(1)),
                "position": _read(annotation.GetPosition),
                "text_point": _read(note.GetTextPoint2),
                "upper_right": _read(note.GetUpperRight),
                "height": _read(note.GetHeight),
                "height_points": _read(note.GetHeightInPoints),
                "text_count": _read(note.GetTextCount),
                "justification": _read(note.GetTextJustification),
                "multiple_fonts": _read(lambda: note.HasMultipleFonts),
                "use_doc_format": _read(lambda: annotation.GetUseDocTextFormat(0)),
                "text_format": _read(lambda: _text_format(annotation)),
                "display_texts": display.get("texts", []),
                "display_refused": refused,
            }
        )
    return notes


async def _scratch_part(adapter: Any, case: str, number: str, title: str) -> Path:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(f"create_part {case}", await adapter.create_part())
    check(f"sketch {case}", await adapter.create_sketch("Front"))
    check(f"rectangle {case}", await adapter.add_rectangle(-40.0, -20.0, 40.0, 20.0))
    check(f"exit_sketch {case}", await adapter.exit_sketch())
    check(f"extrude {case}", await adapter.create_extrusion(ExtrusionParameters(depth=10.0)))
    apply_custom_properties(
        adapter, {"Number": number, "Title": title, "Revision": _config.release_revision()}
    )
    apply_summary_info(adapter, title=title)
    path = SCRATCH / f"title-fit-{case}.SLDPRT"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    check(f"save {case}", await adapter.save_file(str(path)))
    if not path.is_file():
        raise RuntimeError(f"scratch part {path} was not saved")
    return path


def _drawing_capture(adapter: Any, case: str, part: Path, layout: DrawingLayout) -> dict[str, Any]:
    template = DRAWING_TEMPLATES[layout]
    draw, sheet = new_project_drawing(adapter, layout=layout)
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = place_view(adapter, str(part), "*Front", template.width_m * 0.3, template.height_m * 0.6)
    view_name = str(view.GetName2())
    sheet.CustomPropertyView = view_name
    rebuild_drawing(adapter, label=f"title fit {case} {layout.value}")
    sheet_name = str(ddoc.GetSheetNames()[0])
    linked = _early_bound(view.ReferencedDocument, "IModelDoc2")
    sheet_view = _early_bound(ddoc.GetViews()[0][0], "IView")
    capture: dict[str, Any] = {
        "case": case,
        "layout": layout.value,
        "sheet": sheet_name,
        "property_view": _read(lambda: _early_bound(ddoc.GetCurrentSheet(), "ISheet").CustomPropertyView),
        "cells": {source: list(box) for source, box in template.title_cells_m},
        "notes": _template_notes(adapter, sheet_view),
    }
    records: dict[str, list[dict[str, Any]]] = {}
    try:
        readings = read_title_fields(ddoc, {sheet_name: (linked, "")}, {sheet_name: layout})
    except Exception as exc:  # noqa: BLE001 - the contract's own failure is the evidence
        capture["contract"] = {"error": str(exc)}
    else:
        capture["contract"] = {
            "readings": [
                {
                    "source": r.source,
                    "link": r.link,
                    "expected": r.expected,
                    "printed": r.printed,
                    "extent": list(r.extent),
                    "clearance_mm": r.clearance * 1000,
                    "char_height_mm": r.char_height * 1000,
                    "typeface": r.typeface,
                    "line_length_mm": r.line_length * 1000,
                    "problems": r.problems(),
                }
                for r in readings
            ]
        }
        records = audit_records(readings)
    pdf = PDFS[(case, layout)]
    slddrw = SCRATCH / f"title-fit-{case}-{layout.value}.SLDDRW"
    saved = save_drawing(adapter, str(slddrw), pdf_path=str(pdf))
    if set(saved) != {"drawing", "pdf"}:
        raise RuntimeError(f"title fit {case} {layout.value}: save incomplete {saved!r}")
    adapter.swApp.CloseDoc(str(draw.GetTitle()))
    ink = page_ink(read_pdf_ink(pdf)[0])
    left = template.title_block_left_m
    capture["pdf"] = pdf.name
    capture["title_block_spans"] = [span for span in ink["spans"] if float(span[1]) >= left and float(span[2]) <= 0.066]
    dump = {"sheet": sheet_name, "ink": ink, "title_fields": records.get(sheet_name, [])}
    capture["printed_fits"] = [
        {
            "source": fit.source,
            "text": fit.text,
            "printed": None if fit.printed is None else [fit.printed.xmin, fit.printed.ymin, fit.printed.xmax, fit.printed.ymax],
            "clearance_mm": fit.clearance * 1000,
        }
        for fit in title_field_fits(dump)
    ]
    capture["printed_misfits"] = [finding.format() for finding in find_title_field_misfits(dump)]
    return capture


async def probe(adapter: Any) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    captures = []
    for case, (number, title) in CASES.items():
        part = await _scratch_part(adapter, case, number, title)
        part_title = str(adapter.currentModel.GetTitle())
        for layout in LAYOUTS:
            capture = _drawing_capture(adapter, case, part, layout)
            captures.append(capture)
            _telemetry.info(
                f"title fit {case} {layout.value}: contract={json.dumps(capture['contract'])} "
                f"printed={json.dumps(capture['printed_fits'])}"
            )
        adapter.swApp.CloseDoc(part_title)
    REPORT.write_text(
        json.dumps({"cases": {case: list(value) for case, value in CASES.items()}, "captures": captures}, indent=2),
        encoding="utf-8",
    )
    return {"report": str(REPORT), **{f"{case}-{layout.value}": str(path) for (case, layout), path in PDFS.items()}}


if __name__ == "__main__":
    sys.exit(run_build(probe))
