r"""THROWAWAY route-B probe: do the title block's identity cells take the
cut-over identities natively, in both templates, and does the contract
(``_drawing_title_fields`` + ``_layout_audit.find_title_field_misfits``)
catch what must fail?

The identity cutover prints a 10-character ``MHA-XX-###`` (cone-gear sheets a
15-character ``MHA-DT-003-T###``) in DWG. NO. and a slug of up to 29
characters in PART, where v39 printed 7-character Numbers. On drawings from
the checked-in templates (neither file is modified or saved) it records what
SolidWorks itself reports for every sheet note (owner, ``PropertyLinkedText``,
``GetText``, ``AllUpperCase``, ``GetExtent``, position, text point, heights,
text-item and display-data counts, text format), the contract's readings and
structured breaches, the linked model's (configuration, dirty) state around
the reads, and the exported PDF's title-block glyph runs with the
printed-fit measure (rows included):

* ``CASES`` x both templates: the v39 shape (positive control of the
  identity-shape gate), both 29-character slugs with their 10-character
  registry Numbers, cone-gear's 15-character configuration Number with its
  slug, and an overlong negative that must breach its cells;
* ``wrapped-landscape``: a 29-character Title forced to wrap -- a
  drawing-owned note with the same link and a narrow wrap width, and the
  template's own PART note given that wrap width on this drawing copy only --
  to calibrate how SolidWorks reports a wrapped note (text items, display
  data, extent, PDF rows);
* ``configs-2sheet``: one scratch part whose configurations T006/T120 stamp
  their own Number over the file-level one, on a landscape sheet and a
  portrait sheet pasted from the portrait template (fr-frame-assembly's
  mixed package), read with sheet T006 active, plus a drawing-owned note
  carrying the same ``$PRPSHEET`` link that the contract must ignore.

Outputs (all under ``cad/out/probe/title-field-fit/``): :data:`REPORT` and
:data:`PDFS`. Scratch parts and drawings land in ``scratch/`` beside them,
undeclared. The report is written whatever happens; then every control
(:func:`_check_controls`) must hold or the probe fails, its
``control_failures`` saying which.

``--legacy-only`` is the smaller observational discovery route: one v39
scratch part, one landscape view, :data:`DISCOVERY_REPORT` and
:data:`DISCOVERY_PDF`. Success means a raw native catalog and PDF were
captured, NOT that the Title reader passed. Both native enumeration paths
(``IView.GetAnnotations`` and ``IView.GetNotes``) are logged before the
contract runs. The full probe stops at the first failed legacy baseline,
before creating qualified, overlong or wrapped cases.

Delete this script and its dodo task once the proof is recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _config  # noqa: E402
import _drawing_title_fields as title_fields  # noqa: E402
import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    CAD_ROOT,
    _early_bound,
    _read_member,
    apply_custom_properties,
    apply_summary_info,
    check,
    discard_open_documents,
    run_build,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402
from _drawing_common import new_project_drawing, rebuild_drawing  # noqa: E402
from _drawing_layout_audit import annotation_display  # noqa: E402
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout  # noqa: E402
from _drawing_title_fields import TitleFieldContractError, TitleSource, assert_title_fields  # noqa: E402
from _layout_audit import TITLE_FIELD_CLEARANCE_M, find_title_field_misfits, title_field_fits  # noqa: E402
from _pdf_ink import Span, page_ink, read_pdf_ink  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import place_view, save_drawing  # noqa: E402

OUT = CAD_ROOT / "out" / "probe" / "title-field-fit"
SCRATCH = OUT / "scratch"
REPORT = OUT / "title-field-fit.json"
# case -> (Number, Title)
CASES = {
    # v39's cone-gear sheet 1 printed exactly these.
    "control-v39": ("MHA-013", "cone-gear"),
    # The registry rows of the two 29-character slugs.
    "number10-title29": ("MHA-PD-015", "pd-transgear-knob-thrust-ring"),
    "number10-title29-vn": ("MHA-VN-037", "vn-transgear-collar-cross-pin"),
    # The widest Number any sheet prints: cone-gear's configuration Number.
    "number15-cone-gear": ("MHA-DT-003-T006", "dt-cone-gear"),
    # Must breach both cells in both templates.
    "overlong": (
        "MHA-DT-003-T006-MHA-DT-003-T006",
        "vn-transgear-collar-cross-pin-with-a-title-far-longer-than-any-part-cell-holds",
    ),
}
# The cases the contract must pass whole, natively and on the PDF.
NORMAL_CASES = ("number10-title29", "number10-title29-vn", "number15-cone-gear")
# The case the wrapped capture forces to wrap.
WRAPPED_CASE = "number10-title29-vn"
SOURCES = ("Number", "Title")
# The template note's style a longer value must print in: v39's.
STYLE = ("TypeFaceName", "CharHeight", "WidthFactor", "CharSpacingFactor")
LAYOUTS = (DrawingLayout.LANDSCAPE, DrawingLayout.PORTRAIT)
# configs-2sheet: configuration -> (sheet layout, its own Number)
CONFIG_FILE_NUMBER = "MHA-DT-003"
CONFIG_TITLE = "dt-cone-gear"
CONFIGS = {
    "T006": (DrawingLayout.LANDSCAPE, "MHA-DT-003-T006"),
    "T120": (DrawingLayout.PORTRAIT, "MHA-DT-003-T120"),
}
# A wrap width far inside the PART cell (106.6 mm landscape, 103.5 portrait).
WRAP_M = 0.020
PDFS = {
    **{f"{case}-{layout.value}": OUT / f"{case}-{layout.value}.pdf" for case in CASES for layout in LAYOUTS},
    "wrapped-landscape": OUT / "wrapped-landscape.pdf",
    "configs-2sheet": OUT / "configs-2sheet.pdf",
}
DISCOVERY_REPORT = OUT / "title-link-discovery.json"
DISCOVERY_PDF = OUT / "discovery" / "control-v39-landscape.pdf"
_SW_CUSTOM_TEXT = 30  # swCustomInfoType_e.swCustomInfoText
_SW_PROP_REPLACE = 2  # swCustomPropertyAddOption_e.swCustomPropertyReplaceValue
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
        name: _read(lambda n=name: _read_member(text_format, n))
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


def _note_record(adapter: Any, annotation: Any, note: Any, *, link: Any, text: Any) -> dict[str, Any]:
    """SDK getters only: unresolved PropertyLinkedText and evaluated GetText."""
    display, refused = annotation_display(adapter, annotation)
    return {
        "note_interface": type(note).__name__,
        "link": link,
        "parsed_property": title_fields._linked_name(link) if isinstance(link, str) else None,
        "text": text,
        "all_upper_case": _read(lambda: note.AllUpperCase),
        "extent": _read(note.GetExtent),
        "position": _read(annotation.GetPosition),
        "text_point": _read(note.GetTextPoint2),
        "upper_right": _read(note.GetUpperRight),
        "height": _read(note.GetHeight),
        "height_points": _read(note.GetHeightInPoints),
        "text_count": _read(note.GetTextCount),
        "display_count": _read(lambda: title_fields._display_count(annotation)),
        "justification": _read(note.GetTextJustification),
        "use_doc_format": _read(lambda: annotation.GetUseDocTextFormat(0)),
        "text_format": _read(lambda: _text_format(annotation)),
        "display_texts": display.get("texts", []),
        "display_refused": refused,
    }


def _native_catalog(adapter: Any, sheet_view: Any, *, key: str, sheet: str) -> dict[str, Any]:
    """Observe both SDK enumeration paths without changing sheet/edit mode.

    Keep every annotation type and every getter refusal, not just notes the
    current link parser already recognizes. Each record reaches task.log
    BEFORE the reader is called, so a fatal later control cannot hide it.
    """
    catalog: dict[str, Any] = {"annotations": [], "notes": []}
    for method, collection, interface in (
        ("GetAnnotations", "annotations", "IAnnotation"),
        ("GetNotes", "notes", "INote"),
    ):
        path = f"IDrawingDoc.GetViews[sheet={sheet!r}][0].{method}()"
        try:
            entries = getattr(sheet_view, method)()
        except Exception as exc:  # noqa: BLE001 - traversal refusal is evidence
            catalog[f"{collection}_error"] = f"{type(exc).__name__}: {exc}"
            _telemetry.info(f"title native catalog {key}: {path}: {catalog[f'{collection}_error']}")
            continue
        for index, raw in enumerate(entries or ()):
            record: dict[str, Any] = {"path": f"{path}[{index}]"}
            try:
                bound = _early_bound(raw, interface)
                annotation = bound if interface == "IAnnotation" else _early_bound(bound.GetAnnotation(), "IAnnotation")
                record.update(
                    {
                        "annotation_interface": type(annotation).__name__,
                        "type": _read(annotation.GetType),
                        "owner": _read(lambda: annotation.OwnerType),
                        "name": _read(annotation.GetName),
                    }
                )
                if interface == "INote" or record["type"] == _ANNOT_NOTE:
                    note = bound if interface == "INote" else _early_bound(annotation.GetSpecificAnnotation(), "INote")
                    record.update(
                        {
                            "note_interface": type(note).__name__,
                            "link": _read(lambda: note.PropertyLinkedText),
                            "text": _read(note.GetText),
                        }
                    )
                    # Publish raw links/text before geometry/display reads too.
                    _telemetry.info(f"title native raw note {key}: {json.dumps(record, default=str)}")
                    record.update(_note_record(adapter, annotation, note, link=record["link"], text=record["text"]))
            except Exception as exc:  # noqa: BLE001 - preserve partial raw record
                record["read_error"] = f"{type(exc).__name__}: {exc}"
            catalog[collection].append(record)
            _telemetry.info(f"title native catalog {key}: {json.dumps(record, default=str)}")
        _telemetry.info(f"title native catalog {key}: {path}: count={len(catalog[collection])}")
    return catalog


def _sheet_views(ddoc: Any) -> dict[str, Any]:
    views = {}
    for row in ddoc.GetViews() or ():
        entries = list(row or ())
        if entries:
            sheet_view = _early_bound(entries[0], "IView")
            views[str(sheet_view.GetName2() or "")] = sheet_view
    return views


def _active_sheet(ddoc: Any) -> str:
    return str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").GetName() or "")


def _link_property_view(adapter: Any, ddoc: Any, sheet_name: str, view: Any) -> None:
    """``finalize_drawing``'s per-sheet link: explicit property source, then
    the sheet's ``CustomPropertyView`` on ``view``, read back."""
    if not ddoc.ActivateSheet(sheet_name):
        raise RuntimeError(f"failed to activate {sheet_name!r}")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    properties = list(sheet.GetProperties2() or ())
    if len(properties) >= 8 and bool(properties[7]):
        sheet.SetProperties2(
            int(properties[0]),
            int(properties[1]),
            float(properties[2]),
            float(properties[3]),
            bool(properties[4]),
            float(properties[5]),
            float(properties[6]),
            False,
        )
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    name = str(view.GetName2())
    sheet.CustomPropertyView = name
    linked = str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").CustomPropertyView or "")
    if linked != name:
        raise RuntimeError(f"{sheet_name}: CustomPropertyView {linked!r} != {name!r}")


def _add_donor_sheet(adapter: Any, target: Any, layout: DrawingLayout, name: str) -> None:
    """A blank sheet of ``layout`` pasted into ``target`` from a donor drawing
    of that template (``draw_fr_frame_assembly._insert_template_sheet``)."""
    target = _early_bound(target, "IModelDoc2")
    donor, donor_sheet = new_project_drawing(adapter, layout=layout)
    donor = _early_bound(donor, "IModelDoc2")
    donor_title = str(donor.GetTitle())
    try:
        donor.ClearSelection2(True)
        donor_name = str(_early_bound(donor_sheet, "ISheet").GetName())
        if not donor.Extension.SelectByID2(donor_name, "SHEET", 0.0, 0.0, 0.0, False, 0, null_callout(), 0):
            raise RuntimeError(f"failed to select donor sheet {donor_name!r}")
        donor.EditCopy()
        adapter.swApp.ActivateDoc3(str(target.GetTitle()), False, 2, 0)
        ddoc = _early_bound(target, "IDrawingDoc")
        before = tuple(ddoc.GetSheetNames() or ())
        ddoc.PasteSheet(2, 2)
        added = [sheet for sheet in ddoc.GetSheetNames() or () if sheet not in before]
        if len(added) != 1:
            raise RuntimeError(f"sheet paste added {added!r}")
        if not ddoc.ActivateSheet(added[0]):
            raise RuntimeError(f"failed to activate pasted sheet {added[0]!r}")
        _early_bound(ddoc.GetCurrentSheet(), "ISheet").SetName(name)
    finally:
        adapter.swApp.CloseDoc(donor_title)
        adapter.swApp.ActivateDoc3(str(target.GetTitle()), False, 2, 0)


def _insert_linked_note(draw: Any, link: str, xy: tuple[float, float], *, wrap: float | None) -> dict[str, Any]:
    """A drawing-owned note carrying ``link`` -- the contract must ignore it --
    optionally given a narrow wrap width."""
    draw.ClearSelection2(True)
    raw = draw.InsertNote(link)
    if raw is None:
        return {"inserted": False}
    annotation = _early_bound(_early_bound(raw, "INote").GetAnnotation(), "IAnnotation")
    result: dict[str, Any] = {"inserted": True, "positioned": _read(lambda: annotation.SetPosition2(xy[0], xy[1], 0.0))}
    if wrap is not None:
        text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
        text_format.LineLength = wrap
        result["wrap_set"] = _read(lambda: annotation.SetTextFormat(0, False, text_format))
    return result


def _wrap_template_title(ddoc: Any, sheet_view: Any) -> dict[str, Any]:
    """Give the template's own PART note a narrow wrap width on THIS drawing
    (the DRWDOT is never saved). ``EditTemplate``/``EditSheet`` return
    nothing, so each mode change is read back through ``GetEditSheet``
    (False in template mode, True in sheet mode) and a mode not entered
    raises."""
    result: dict[str, Any] = {}
    ddoc.EditTemplate()
    if bool(ddoc.GetEditSheet()):
        raise RuntimeError("EditTemplate left the drawing in sheet mode")
    result["template_mode"] = True
    try:
        for raw in sheet_view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.OwnerType) != 2 or int(annotation.GetType()) != _ANNOT_NOTE:
                continue
            note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
            name = title_fields._linked_name(str(note.PropertyLinkedText or ""))
            if name not in title_fields.TITLE_FIELD_PROPERTIES["Title"]:
                continue
            text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
            text_format.LineLength = WRAP_M
            result["wrap_set"] = _read(lambda: annotation.SetTextFormat(0, False, text_format))
        if "wrap_set" not in result:
            raise RuntimeError("no template note links the PART cell")
    finally:
        ddoc.EditSheet()
        if not bool(ddoc.GetEditSheet()):
            raise RuntimeError("EditSheet left the drawing in template mode")
    result["sheet_mode"] = True
    return result


async def _scratch_part(
    adapter: Any, name: str, number: str, title: str, configs: Mapping[str, str] | None = None
) -> Path:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(f"create_part {name}", await adapter.create_part())
    check(f"sketch {name}", await adapter.create_sketch("Front"))
    check(f"rectangle {name}", await adapter.add_rectangle(-40.0, -20.0, 40.0, 20.0))
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    check(f"extrude {name}", await adapter.create_extrusion(ExtrusionParameters(depth=10.0)))
    apply_custom_properties(adapter, {"Number": number, "Title": title, "Revision": _config.release_revision()})
    apply_summary_info(adapter, title=title)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for configuration, value in (configs or {}).items():
        manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
        if manager.AddConfiguration2(configuration, "", "", 0, "", "", False) is None:
            raise RuntimeError(f"AddConfiguration2({configuration!r}) failed")
        properties = _early_bound(model.Extension.CustomPropertyManager(configuration), "ICustomPropertyManager")
        properties.Add3("Number", _SW_CUSTOM_TEXT, value, _SW_PROP_REPLACE)
        if str(model.GetCustomInfoValue(configuration, "Number")) != value:
            raise RuntimeError(f"{configuration}: Number did not take")
    if configs:
        # The configs capture reads with the model on Default: hold it there.
        if not model.ShowConfiguration2("Default"):
            raise RuntimeError(f"ShowConfiguration2('Default') failed on {name}")
        active = title_fields._model_state(model)[0]
        if active != "Default":
            raise RuntimeError(f"{name}: active configuration {active!r} after ShowConfiguration2('Default')")
    path = SCRATCH / f"title-fit-{name}.SLDPRT"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    check(f"save {name}", await adapter.save_file(str(path)))
    if not path.is_file():
        raise RuntimeError(f"scratch part {path} was not saved")
    adapter.swApp.CloseDoc(str(model.GetTitle()))
    return path


def _contract(ddoc: Any, sources: Mapping[str, TitleSource], layouts: Mapping[str, DrawingLayout]) -> dict[str, Any]:
    """The permanent contract's readings and structured verdict. Scratch
    models have no registry row, so the probe hands the private measurement
    the identity each sheet must print; production always takes the
    registry's (``read_title_fields``)."""
    states = {sheet: _read(lambda s=source: list(title_fields._model_state(s.model))) for sheet, source in sources.items()}
    result: dict[str, Any] = {"model_state_before": states}
    try:
        readings = title_fields._measure_title_fields(ddoc, sources, layouts)
    except TitleFieldContractError as exc:
        result["read_breaches"] = [vars(breach) for breach in exc.breaches]
        return result
    except Exception as exc:  # noqa: BLE001 - the contract's own refusal is evidence
        result["read_error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        result["model_state_after"] = {
            sheet: _read(lambda s=source: list(title_fields._model_state(s.model))) for sheet, source in sources.items()
        }
    result["readings"] = [
        {
            "sheet": r.sheet,
            "source": r.source,
            "identity": list(r.identity),
            "expected": r.expected,
            "model_value": r.model_value,
            "printed": r.printed,
            "all_upper_case": r.all_upper_case,
            "cell": list(r.cell),
            "extent": list(r.extent),
            "height_mm": (r.extent[3] - r.extent[1]) * 1000,
            "height_per_char_height": (r.extent[3] - r.extent[1]) / r.char_height if r.char_height else None,
            "clearance_mm": r.clearance * 1000,
            "char_height_mm": r.char_height * 1000,
            "typeface": r.typeface,
            "line_length_mm": r.line_length * 1000,
            "text_count": r.text_count,
            "display_count": r.display_count,
            "problem_kinds": [kind for kind, _detail in r.problems()],
        }
        for r in readings
    ]
    try:
        assert_title_fields(readings)
    except TitleFieldContractError as exc:
        result["breaches"] = [vars(breach) for breach in exc.breaches]
    else:
        result["breaches"] = []
    return result


def _capture(
    adapter: Any,
    key: str,
    draw: Any,
    sources: Mapping[str, TitleSource],
    layouts: Mapping[str, DrawingLayout],
    extra: Mapping[str, Any],
    *,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet_names = [str(name) for name in ddoc.GetSheetNames() or ()]
    # Read with the first sheet active: every other sheet is read unactivated.
    if not ddoc.ActivateSheet(sheet_names[0]):
        raise RuntimeError(f"title fit {key}: failed to activate {sheet_names[0]!r}")
    active_before = _active_sheet(ddoc)
    if active_before != sheet_names[0]:
        raise RuntimeError(f"title fit {key}: sheet {active_before!r} active after activating {sheet_names[0]!r}")
    views = _sheet_views(ddoc)
    model = _early_bound(draw, "IModelDoc2")

    def observation_state() -> dict[str, Any]:
        return {
            "active_sheet": _active_sheet(ddoc),
            "sheet_mode": _read(ddoc.GetEditSheet),
            "drawing_dirty": _read(model.GetSaveFlag),
            "models": {
                name: _read(lambda s=source: list(title_fields._model_state(s.model))) for name, source in sources.items()
            },
        }

    state_before = observation_state()
    sheets: dict[str, Any] = {}
    for name in sheet_names:
        catalog = _native_catalog(adapter, views[name], key=key, sheet=name)
        sheet = _early_bound(ddoc.Sheet(name), "ISheet")
        source = sources[name]
        source_record = {
            "custom_property_view": _read(lambda: sheet.CustomPropertyView),
            "sheet_properties": _read(sheet.GetProperties2),
            "model_path": _read(_early_bound(source.model, "IModelDoc2").GetPathName),
            "configuration": source.configuration,
            "expected": {prop: source.expected(prop) for prop in SOURCES},
            "stored": {
                prop: _read(lambda p=prop: title_fields.linked_property(source.model, source.configuration, p))
                for prop in ("Number", "Title", "SW-Title")
            },
        }
        _telemetry.info(f"title native source {key} {name}: {json.dumps(source_record, default=str)}")
        sheets[name] = {
            "layout": layouts[name].value,
            "cells": {prop: list(box) for prop, box in DRAWING_TEMPLATES[layouts[name]].title_cells_m},
            "source": source_record,
            "native_catalog": catalog,
            "notes": [record for record in catalog["annotations"] if record.get("type") == _ANNOT_NOTE],
        }
    state_after_catalog = observation_state()
    capture: dict[str, Any] = {
        "key": key,
        **extra,
        "sheets": sheets,
        "contract": _contract(ddoc, sources, layouts),
    }
    capture["observation_state"] = [state_before, state_after_catalog, observation_state()]
    # The sheet the contract read with active, before and after the reads.
    capture["active_sheet"] = [active_before, _active_sheet(ddoc)]
    pdf = pdf_path if pdf_path is not None else PDFS[key]
    pdf.parent.mkdir(parents=True, exist_ok=True)
    saved = save_drawing(adapter, str(SCRATCH / f"title-fit-{key}.SLDDRW"), pdf_path=str(pdf))
    if set(saved) != {"drawing", "pdf"}:
        raise RuntimeError(f"title fit {key}: save incomplete {saved!r}")
    adapter.swApp.CloseDoc(str(draw.GetTitle()))
    pages = read_pdf_ink(pdf)
    capture["pdf"] = pdf.name
    for index, name in enumerate(sheet_names):
        template = DRAWING_TEMPLATES[layouts[name]]
        ink = page_ink(pages[index])
        cells = dict(template.title_cells_m)
        records = [
            {"source": source, "text": sources[name].expected(source), "cell": list(cells[source])}
            for source in ("Number", "Title")
        ]
        dump = {"sheet": name, "ink": ink, "title_fields": records}
        sheet = capture["sheets"][name]
        sheet["title_block_spans"] = [
            span for span in ink["spans"] if float(span[1]) >= template.title_block_left_m and float(span[2]) <= 0.066
        ]
        sheet["printed_fits"] = [
            {
                "source": fit.source,
                "text": fit.text,
                "printed": None
                if fit.printed is None
                else [fit.printed.xmin, fit.printed.ymin, fit.printed.xmax, fit.printed.ymax],
                "rows": fit.rows,
                "clearance_mm": fit.clearance * 1000,
            }
            for fit in title_field_fits(dump)
        ]
        sheet["printed_misfits"] = [
            {"kind": f.kind, "a": f.a, "extra": dict(f.extra), "text": f.format()} for f in find_title_field_misfits(dump)
        ]
        sheet["physical_rows"] = _physical_rows(pages[index], template, records)
    _telemetry.info(f"title fit {key}: {json.dumps(capture['contract'], default=str)[:2000]}")
    return capture


def _physical_rows(page: Any, template: Any, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each identity's printed pieces in the title block -- text objects
    spelling a run of it, wrapped remainders included -- and the distinct
    glyph baselines they stand on together (``Span.rows``' rule). A whole
    one-line print is one piece on one baseline; the wrapped case must read
    two."""
    measured = []
    for record in records:
        text = record["text"]
        pieces = [
            span
            for span in page.spans
            if len(span.text) >= 3
            and span.text in text
            and span.xmin >= template.title_block_left_m
            and span.ymax <= 0.066
        ]
        glyphs = tuple(glyph for span in pieces for glyph in span.glyphs)
        union = Span(text, 0.0, 0.0, 0.0, 0.0, glyphs)
        measured.append(
            {
                "source": record["source"],
                "pieces": [
                    [span.text, span.xmin, span.ymin, span.xmax, span.ymax, sorted({g.baseline for g in span.glyphs})]
                    for span in pieces
                ],
                "rows": union.rows,
            }
        )
    return measured


def _single_sheet(
    adapter: Any,
    key: str,
    part: Path,
    layout: DrawingLayout,
    number: str,
    title: str,
    mutate: Callable[[Any, Any, Any], dict[str, Any]] | None = None,
    *,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    template = DRAWING_TEMPLATES[layout]
    draw, _sheet = new_project_drawing(adapter, layout=layout)
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = place_view(adapter, str(part), "*Front", template.width_m * 0.3, template.height_m * 0.6)
    sheet_name = str(ddoc.GetSheetNames()[0])
    _link_property_view(adapter, ddoc, sheet_name, view)
    extra = mutate(draw, ddoc, _sheet_views(ddoc)[sheet_name]) if mutate else {}
    rebuild_drawing(adapter, label=f"title fit {key}")
    configuration = str(view.ReferencedConfiguration or "")
    sources = {sheet_name: TitleSource(view.ReferencedDocument, configuration, number, title)}
    return _capture(adapter, key, draw, sources, {sheet_name: layout}, {"mutations": extra}, pdf_path=pdf_path)


def _configs_two_sheets(adapter: Any, part: Path) -> dict[str, Any]:
    names = list(CONFIGS)
    first_layout = CONFIGS[names[0]][0]
    draw, sheet = new_project_drawing(adapter, layout=first_layout)
    ddoc = _early_bound(draw, "IDrawingDoc")
    _early_bound(sheet, "ISheet").SetName(names[0])
    for name in names[1:]:
        _add_donor_sheet(adapter, draw, CONFIGS[name][0], name)
    sources, layouts = {}, {}
    for name in names:
        layout, number = CONFIGS[name]
        template = DRAWING_TEMPLATES[layout]
        if not ddoc.ActivateSheet(name):
            raise RuntimeError(f"failed to activate {name!r}")
        view = place_view(adapter, str(part), "*Front", template.width_m * 0.3, template.height_m * 0.6)
        view.ReferencedConfiguration = name
        _link_property_view(adapter, ddoc, name, view)
        sources[name] = (view, number)
        layouts[name] = layout
    # The drawing-owned control note lands on the active sheet: T006.
    if not ddoc.ActivateSheet(names[0]) or _active_sheet(ddoc) != names[0]:
        raise RuntimeError(f"configs-2sheet: {names[0]!r} is not the active sheet ({_active_sheet(ddoc)!r})")
    control = _insert_linked_note(draw, '$PRPSHEET:"Number"', (0.05, 0.20), wrap=None)
    rebuild_drawing(adapter, label="title fit configs-2sheet")
    resolved = {
        name: TitleSource(view.ReferencedDocument, str(view.ReferencedConfiguration or ""), number, CONFIG_TITLE)
        for name, (view, number) in sources.items()
    }
    extra = {
        "configurations": {name: str(view.ReferencedConfiguration or "") for name, (view, _n) in sources.items()},
        "drawing_note_control": control,
    }
    return _capture(adapter, "configs-2sheet", draw, resolved, layouts, extra)


def _force_wraps(draw: Any, ddoc: Any, sheet_view: Any) -> dict[str, Any]:
    return {
        "drawing_note": _insert_linked_note(draw, '$PRPSHEET:"SW-Title"', (0.05, 0.20), wrap=WRAP_M),
        "template_title": _wrap_template_title(ddoc, sheet_view),
    }


def _only_sheet(capture: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    sheets = capture["sheets"]
    if len(sheets) != 1:
        raise RuntimeError(f"{capture['key']}: expected one sheet, captured {sorted(sheets)}")
    return next(iter(sheets.items()))


def _readings(capture: Mapping[str, Any], failures: list[str]) -> dict[tuple[str, str], Mapping[str, Any]]:
    """The capture's contract readings by (sheet, source); a refused read is a
    failure."""
    contract = capture["contract"]
    for refusal in ("read_breaches", "read_error"):
        if refusal in contract:
            failures.append(f"{capture['key']}: the contract refused the read: {contract[refusal]!r}")
    return {(reading["sheet"], reading["source"]): reading for reading in contract.get("readings", ())}


def _style(sheet: Mapping[str, Any], source: str) -> dict[str, Any] | None:
    """The template note's height and text-format style for ``source``'s cell,
    or None when the note is not exactly one or a value was refused."""
    notes = [
        note
        for note in sheet["notes"]
        if note.get("owner") == 2
        and title_fields._linked_name(str(note.get("link") or "")) in title_fields.TITLE_FIELD_PROPERTIES[source]
    ]
    if len(notes) != 1 or not isinstance(notes[0].get("text_format"), dict):
        return None
    style = {"height": notes[0].get("height"), **{name: notes[0]["text_format"].get(name) for name in STYLE}}
    if any(value is None or (isinstance(value, str) and value.startswith("<error")) for value in style.values()):
        return None
    return style


def _is_true(value: Any) -> bool:
    """A COM BOOL as JSON: true, and not a refused read's error string."""
    return isinstance(value, (bool, int)) and bool(value)


def _legacy_failures(capture: Mapping[str, Any]) -> list[str]:
    """Require a working native/PDF baseline before interpreting later cases."""
    failures: list[str] = []
    name, sheet = _only_sheet(capture)
    readings = _readings(capture, failures)
    for source in SOURCES:
        reading = readings.get((name, source))
        kinds = None if reading is None else sorted(set(reading["problem_kinds"]))
        if kinds != ["not-identity"]:
            failures.append(f"{capture['key']} {source}: expected only not-identity, read {kinds!r}")
    if sheet["printed_misfits"]:
        failures.append(f"{capture['key']}: legacy PDF misfits {sheet['printed_misfits']!r}")
    rows = {row["source"]: row["rows"] for row in sheet["physical_rows"]}
    for source in SOURCES:
        if rows.get(source) != 1:
            failures.append(f"{capture['key']} {source}: legacy PDF physical rows {rows.get(source)!r}, not 1")
    states = capture["observation_state"]
    if not all(state == states[0] for state in states[1:]):
        failures.append(f"{capture['key']}: native observations changed document state {states!r}")
    return failures


def _check_controls(captures: list[Mapping[str, Any]]) -> list[str]:
    """Every positive and negative control the captures must show; each
    failure says what was observed."""
    by_key = {capture["key"]: capture for capture in captures}
    failures: list[str] = []

    def need(ok: bool, message: str) -> None:
        if not ok:
            failures.append(message)

    clearance_mm = TITLE_FIELD_CLEARANCE_M * 1000
    for layout in LAYOUTS:
        # control-v39: only its pre-cutover shapes breach -- nothing about fit.
        control = by_key[f"control-v39-{layout.value}"]
        _control_name, control_sheet = _only_sheet(control)
        failures.extend(_legacy_failures(control))
        for case in NORMAL_CASES:
            key = f"{case}-{layout.value}"
            capture = by_key[key]
            name, sheet = _only_sheet(capture)
            readings = _readings(capture, failures)
            need(capture["contract"].get("breaches") == [], f"{key}: breaches {capture['contract'].get('breaches')!r}")
            need(sheet["printed_misfits"] == [], f"{key}: PDF misfits {sheet['printed_misfits']!r}")
            fits = {fit["source"]: fit for fit in sheet["printed_fits"]}
            rows = {row["source"]: row["rows"] for row in sheet["physical_rows"]}
            for source in SOURCES:
                reading = readings.get((name, source))
                if reading is None:
                    failures.append(f"{key} {source}: no native reading")
                    continue
                x0, _y0, x1, _y1 = sheet["cells"][source]
                width_mm = (x1 - x0) * 1000
                line_length = reading["line_length_mm"]
                need(
                    line_length == 0 or line_length >= width_mm,
                    f"{key} {source}: LineLength {line_length:.3f} mm inside its {width_mm:.3f} mm cell",
                )
                need(
                    reading["text_count"] == 1 and reading["display_count"] == 1,
                    f"{key} {source}: text items {reading['text_count']}, display {reading['display_count']}",
                )
                need(
                    reading["clearance_mm"] >= clearance_mm,
                    f"{key} {source}: native clearance {reading['clearance_mm']:.3f} mm",
                )
                fit = fits.get(source)
                need(
                    fit is not None
                    and fit["printed"] is not None
                    and fit["rows"] == 1
                    and fit["clearance_mm"] >= clearance_mm,
                    f"{key} {source}: PDF fit {fit!r}",
                )
                need(rows.get(source) == 1, f"{key} {source}: {rows.get(source)!r} physical baseline rows")
                style, control_style = _style(sheet, source), _style(control_sheet, source)
                need(
                    style is not None and style == control_style,
                    f"{key} {source}: style {style!r} differs from control-v39's {control_style!r}",
                )
            title = CASES[case][1]
            need(
                any(str(span[0]).strip() == title for span in sheet["title_block_spans"]),
                f"{key}: no title-block span prints {title!r} in its exact case",
            )
        # overlong: both cells breach natively and on the PDF.
        key = f"overlong-{layout.value}"
        capture = by_key[key]
        name, sheet = _only_sheet(capture)
        readings = _readings(capture, failures)
        misfits = {misfit["a"] for misfit in sheet["printed_misfits"]}
        for source in SOURCES:
            reading = readings.get((name, source))
            kinds = None if reading is None else reading["problem_kinds"]
            need(kinds is not None and "outside-cell" in kinds, f"{key} {source}: no outside-cell in {kinds!r}")
            need(f"title {source}" in misfits, f"{key} {source}: no PDF misfit in {sorted(misfits)!r}")

    # wrapped-landscape: the template PART note really took the narrow wrap.
    wrapped = by_key["wrapped-landscape"]
    name, sheet = _only_sheet(wrapped)
    mutation = wrapped["mutations"].get("template_title") or {}
    need(
        mutation.get("template_mode") is True and mutation.get("sheet_mode") is True and _is_true(mutation.get("wrap_set")),
        f"wrapped-landscape: template mutation {mutation!r}",
    )
    reading = _readings(wrapped, failures).get((name, "Title"))
    kinds = None if reading is None else reading["problem_kinds"]
    need(kinds is not None and "wrap-width" in kinds, f"wrapped-landscape Title: no wrap-width in {kinds!r}")
    fit = next((fit for fit in sheet["printed_fits"] if fit["source"] == "Title"), None)
    need(
        fit is not None and (fit["printed"] is None or fit["rows"] >= 2),
        f"wrapped-landscape Title: PDF prints it whole on one row ({fit!r})",
    )
    rows = next((row["rows"] for row in sheet["physical_rows"] if row["source"] == "Title"), None)
    need(rows == 2, f"wrapped-landscape Title: {rows!r} physical baseline rows, not 2")

    # configs-2sheet: per-sheet configuration Numbers, read without moving the
    # model, with T006 active and the portrait T120 sheet never activated.
    configs = by_key["configs-2sheet"]
    contract = configs["contract"]
    readings = _readings(configs, failures)
    names = list(CONFIGS)
    need(
        "model_state_after" in contract and contract["model_state_before"] == contract["model_state_after"],
        f"configs-2sheet: model state {contract.get('model_state_before')!r} -> {contract.get('model_state_after')!r}",
    )
    need(list(configs["sheets"]) == names, f"configs-2sheet: sheets {list(configs['sheets'])!r}")
    need(configs["active_sheet"] == [names[0], names[0]], f"configs-2sheet: active sheet {configs['active_sheet']!r}")
    for name, (layout, number) in CONFIGS.items():
        need(
            configs["sheets"].get(name, {}).get("layout") == layout.value,
            f"configs-2sheet {name}: layout {configs['sheets'].get(name, {}).get('layout')!r}",
        )
        reading = readings.get((name, "Number"))
        observed = None if reading is None else (reading["expected"], reading["model_value"], reading["printed"])
        need(observed == (number, number, number), f"configs-2sheet {name} Number: {observed!r}, not its own {number!r}")
    control = configs["drawing_note_control"]
    need(control.get("inserted") is True, f"configs-2sheet: drawing-owned note {control!r}")
    owned = [
        note
        for note in configs["sheets"].get(names[0], {}).get("notes", ())
        if note.get("owner") != 2 and title_fields._linked_name(str(note.get("link") or "")) == "Number"
    ]
    need(len(owned) == 1, f"configs-2sheet: {len(owned)} drawing-owned Number note(s)")
    taken = [reading["extent"] for reading in readings.values()]
    for note in owned:
        extent = note.get("extent")
        box = [extent[0], extent[1], extent[3], extent[4]] if isinstance(extent, list) and len(extent) >= 6 else None
        need(box is not None and box not in taken, f"configs-2sheet: a reading took the drawing-owned note {extent!r}")
    return failures


async def probe(adapter: Any, *, legacy_only: bool = False) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = DISCOVERY_REPORT if legacy_only else REPORT
    captures: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "mode": "native-link-discovery" if legacy_only else "full-title-field-proof",
        "success_means": "raw observations captured, not Title fit passed" if legacy_only else "all controls passed",
        "cases": {case: list(value) for case, value in CASES.items()},
        "configs": {name: [layout.value, value] for name, (layout, value) in CONFIGS.items()},
        "wrap_m": WRAP_M,
        "captures": captures,
    }
    try:
        number, title = CASES["control-v39"]
        legacy_part = await _scratch_part(adapter, "control-v39", number, title)
        for layout in (DrawingLayout.LANDSCAPE,) if legacy_only else LAYOUTS:
            capture = _single_sheet(
                adapter,
                f"control-v39-{layout.value}",
                legacy_part,
                layout,
                number,
                title,
                pdf_path=DISCOVERY_PDF if legacy_only else None,
            )
            captures.append(capture)
            failures = _legacy_failures(capture)
            report["legacy_baseline_failures"] = failures
            report["legacy_baseline_passed"] = not failures
            if legacy_only:
                catalogs = [sheet["native_catalog"] for sheet in capture["sheets"].values()]
                if not all(
                    any(
                        isinstance(record.get("link"), str)
                        and not record["link"].startswith("<error:")
                        and isinstance(record.get("text"), str)
                        and not record["text"].startswith("<error:")
                        for collection in ("annotations", "notes")
                        for record in catalog[collection]
                    )
                    for catalog in catalogs
                ):
                    raise RuntimeError("native link discovery captured no readable raw note link/text records")
                discard_open_documents(adapter)
                return {"report": str(report_path), "control-v39-landscape": str(DISCOVERY_PDF)}
            if failures:
                report["control_failures"] = failures
                raise RuntimeError("legacy baseline failed; no later cases run:\n" + "\n".join(failures))
        parts = {}
        for case, (number, title) in CASES.items():
            if case == "control-v39":
                continue
            parts[case] = await _scratch_part(adapter, case, number, title)
            for layout in LAYOUTS:
                captures.append(_single_sheet(adapter, f"{case}-{layout.value}", parts[case], layout, number, title))
        number, title = CASES[WRAPPED_CASE]
        captures.append(
            _single_sheet(
                adapter, "wrapped-landscape", parts[WRAPPED_CASE], DrawingLayout.LANDSCAPE, number, title, _force_wraps
            )
        )
        configs_part = await _scratch_part(
            adapter, "configs", CONFIG_FILE_NUMBER, CONFIG_TITLE, {name: value for name, (_l, value) in CONFIGS.items()}
        )
        captures.append(_configs_two_sheets(adapter, configs_part))
        discard_open_documents(adapter)
        report["control_failures"] = _check_controls(captures)
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        # Written whatever happened: a failed probe's evidence is the point.
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if report["control_failures"]:
        raise RuntimeError(
            f"title field probe: {len(report['control_failures'])} control(s) failed "
            f"(see {report_path}):\n" + "\n".join(report["control_failures"])
        )
    return {"report": str(report_path), **{key: str(path) for key, path in PDFS.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--legacy-only", action="store_true", help="capture one landscape legacy catalog, not fit proof")
    arguments = parser.parse_args()
    sys.exit(run_build(lambda adapter: probe(adapter, legacy_only=arguments.legacy_only)))
