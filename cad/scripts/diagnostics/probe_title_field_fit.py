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
  slug, and an untouched overlong negative that must breach its cells and
  actually wrap the owner-2 Title on multiple native/display/PDF rows;
* ``wrapped-landscape``: historical capture key for a 29-character Title's
  LineLength-only control. An exact-descriptor/font/style owner-1 note must
  physically wrap in its auto box; the original owner-2 template must retain
  its fixed box and one actual row. Its persisted narrow LineLength causes
  only a wrap-width refusal and is explicitly NOT a physical template wrap;
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

``probe_title_link_discovery.py`` is the smaller observational route: one
v39 scratch part, one landscape view, :data:`DISCOVERY_REPORT` and
:data:`DISCOVERY_PDF`. Success means a raw native catalog and PDF were
captured, NOT that the Title reader passed. Both native enumeration paths
(``IView.GetAnnotations`` and ``IView.GetNotes``) are logged before the
contract runs. The full probe stops at the first failed legacy baseline,
before creating qualified, overlong or wrapped cases.

``probe_title_wrap_control.py`` is the independent two-part/two-view calibration:
an untouched registry Title passes natively before the exact-style auto-box
decoy and inert fixed-box width control, then an untouched overlong source
must show a real physical template wrap. It has three dedicated outputs and
does not claim the full matrix, portrait, or configuration controls.

Delete this script and its dodo task once the proof is recorded.
"""

from __future__ import annotations

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
from _pdf_ink import ROW_BASELINE_FRACTION, Span, page_ink, read_pdf_ink  # noqa: E402
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
        return [
            item if isinstance(item, dict) else float(item) if isinstance(item, (int, float)) else str(item)
            for item in value
        ]
    if value is None or isinstance(value, (bool, int, float, str, dict)):
        return value
    return str(value)


def _observe_construction(observations: list[dict[str, Any]], stage: str, **values: Any) -> None:
    record = {"stage": stage, **values}
    observations.append(record)
    _telemetry.info(f"title construction: {json.dumps(record, default=str)}")


def _drawing_state(adapter: Any, draw: Any) -> dict[str, Any]:
    ddoc = _early_bound(draw, "IDrawingDoc")
    return {
        "application_document": _read(lambda: _early_bound(adapter.swApp.ActiveDoc, "IModelDoc2").GetTitle()),
        "adapter_document": _read(lambda: adapter.currentModel.GetTitle()),
        "active_sheet": _read(lambda: _active_sheet(ddoc)),
        "sheet_mode": _read(ddoc.GetEditSheet),
        "drawing_dirty": _read(_early_bound(draw, "IModelDoc2").GetSaveFlag),
    }


def _activate_probe_drawing(adapter: Any, target: Any, observations: list[dict[str, Any]]) -> Any:
    """Rebind the adapter too: new_project_drawing made the donor current."""
    target = _early_bound(target, "IModelDoc2")
    _observe_construction(observations, "drawing.activate.before", state=_drawing_state(adapter, target))
    activation = adapter.swApp.ActivateDoc3(str(target.GetTitle()), False, 2, 0)
    if not isinstance(activation, tuple) or len(activation) != 2:
        raise RuntimeError(f"probe drawing activation returned {activation!r}, not (document, errors)")
    activated, errors = activation
    if activated is None or int(errors) != 0:
        raise RuntimeError(f"probe drawing activation failed (document={activated!r}, errors={errors!r})")
    activated = _early_bound(activated, "IModelDoc2")
    active = _early_bound(adapter.swApp.ActiveDoc, "IModelDoc2")
    same_target = int(adapter.swApp.IsSame(activated, target))
    same_active = int(adapter.swApp.IsSame(active, target)) if active is not None else 0
    _observe_construction(observations, "drawing.activate.identity", errors=int(errors),
                          returned_is_target=same_target, active_is_target=same_active)
    if same_target != 1 or same_active != 1:
        raise RuntimeError("probe drawing activation did not return and activate the target drawing")
    adapter.currentModel = activated
    _observe_construction(observations, "drawing.activate.after", state=_drawing_state(adapter, activated))
    return activated


def _text_format(annotation: Any) -> dict[str, Any]:
    raw = annotation.GetTextFormat(0)
    if raw is None:
        return {}
    text_format = _early_bound(raw, "ITextFormat")
    return _text_format_values(text_format)


def _text_format_values(text_format: Any) -> dict[str, Any]:
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
    record = {
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
    if record["parsed_property"] in title_fields.TITLE_FIELD_PROPERTIES["Title"]:
        record["wrap_diagnostics"] = _read(lambda: _wrap_state(annotation, note))
    return record


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


def _add_donor_sheet(
    adapter: Any, target: Any, layout: DrawingLayout, name: str, observations: list[dict[str, Any]]
) -> None:
    """Copy a blank template sheet, restoring both application and adapter."""
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
        target = _activate_probe_drawing(adapter, target, observations)
        ddoc = _early_bound(target, "IDrawingDoc")
        before = tuple(ddoc.GetSheetNames() or ())
        ddoc.PasteSheet(2, 2)
        added = [sheet for sheet in ddoc.GetSheetNames() or () if sheet not in before]
        if len(added) != 1:
            raise RuntimeError(f"sheet paste added {added!r}")
        if not ddoc.ActivateSheet(added[0]):
            raise RuntimeError(f"failed to activate pasted sheet {added[0]!r}")
        _early_bound(ddoc.GetCurrentSheet(), "ISheet").SetName(name)
        if _active_sheet(ddoc) != name:
            raise RuntimeError(f"pasted sheet did not take name {name!r}")
        _observe_construction(observations, "drawing.donor.pasted", sheet=name,
                              state=_drawing_state(adapter, target))
    finally:
        adapter.swApp.CloseDoc(donor_title)
        _activate_probe_drawing(adapter, target, observations)


def _insert_linked_note(draw: Any, link: str, xy: tuple[float, float]) -> dict[str, Any]:
    """A drawing-owned link control which must never be taken as a source."""
    draw.ClearSelection2(True)
    raw = draw.InsertNote(link)
    if raw is None:
        return {"inserted": False}
    annotation = _early_bound(_early_bound(raw, "INote").GetAnnotation(), "IAnnotation")
    result: dict[str, Any] = {"inserted": True, "positioned": _read(lambda: annotation.SetPosition2(xy[0], xy[1], 0.0))}
    return result


def _paragraph_state(annotation: Any) -> list[dict[str, Any]]:
    """Observe SDK paragraph/segment properties without committing changes.
    GetParagraphs is documented as an array but the official VBA example
    receives one IParagraphs object. Preserve that actual binding shape and
    restore its paragraph selector; never call Set* or UpdateParagraph."""
    raw = annotation.GetParagraphs()
    if raw is None:
        return []
    entries = list(raw) if isinstance(raw, (tuple, list)) else [raw]
    records = []
    for index, entry in enumerate(entries):
        record: dict[str, Any] = {"interface_index": index, "binding_shape": "array" if isinstance(raw, (tuple, list)) else "scalar"}
        records.append(record)
        try:
            paragraphs = _early_bound(entry, "IParagraphs")
            count = _read(lambda: paragraphs.Count)
            original = _read(lambda: paragraphs.CurrentParagraph)
            record.update({"count": count, "current_paragraph": original, "paragraphs": []})
            if not isinstance(count, int) or not isinstance(original, int) or not 0 <= original < count:
                record["read_error"] = "paragraph count/current selector is unreadable or unselected"
                continue
            try:
                for paragraph_index in range(count):
                    paragraphs.CurrentParagraph = paragraph_index
                    segment_count = _read(paragraphs.GetTextSegmentCount)
                    paragraph = {
                        "index": paragraph_index,
                        "text_with_wrap": _read(lambda: paragraphs.GetText(True)),
                        "text_without_wrap": _read(lambda: paragraphs.GetText(False)),
                        "indentation": _read(paragraphs.GetIndentation),
                        "formatting": _read(paragraphs.GetFormatting),
                        "segment_count": segment_count,
                        "segments": [],
                    }
                    record["paragraphs"].append(paragraph)
                    if isinstance(segment_count, int):
                        for segment_index in range(segment_count):
                            paragraph["segments"].append({
                                "index": segment_index,
                                "text": _read(lambda i=segment_index: paragraphs.GetTextSegmentText(i)),
                                "format": _read(lambda i=segment_index: _text_format_values(
                                    _early_bound(paragraphs.GetTextSegmentFormat(i), "ITextFormat")
                                )),
                            })
            finally:
                paragraphs.CurrentParagraph = original
                record["current_paragraph_after"] = _read(lambda: paragraphs.CurrentParagraph)
        except Exception as exc:  # noqa: BLE001 - raw refusal is diagnostic evidence
            record["read_error"] = f"{type(exc).__name__}: {exc}"
    return records


def _display_state(annotation: Any) -> dict[str, Any]:
    raw = annotation.GetDisplayData()
    if raw is None:
        return {"count": None, "items": []}
    display = _early_bound(raw, "IDisplayData")
    count = _read(display.GetTextCount)
    items = [
        {
            "index": index,
            "text": _read(lambda i=index: display.GetTextAtIndex(i)),
            "position_offset": _read(lambda i=index: display.GetTextPositionAtIndex(i)),
        }
        for index in range(count)
    ] if isinstance(count, int) else []
    return {"count": count, "items": items}


def _display_rows(display: Any, char_height: Any) -> dict[str, Any]:
    """Physical rows of this horizontal Title, from actual display baselines.
    R7's linked auto-box note has one logical INote text/paragraph item but
    six displayed rows. Display runs alone are not rows: merge runs sharing
    a baseline using the PDF glyph grouping's existing height fraction."""
    if not isinstance(display, dict) or not isinstance(char_height, (int, float)) or char_height <= 0:
        return {"count": None, "error": "display data or native character height is unreadable"}
    count, items = display.get("count"), display.get("items")
    if not isinstance(count, int) or not isinstance(items, list) or len(items) != count:
        return {"count": None, "error": "native display item count/array is incomplete"}
    baselines = []
    for item in items:
        text, position = item.get("text"), item.get("position_offset")
        if (
            not isinstance(text, str) or text.startswith("<error:")
            or not isinstance(position, list) or len(position) != 3
            or not all(isinstance(value, (int, float)) for value in position)
        ):
            return {"count": None, "error": "a native display text/baseline read was refused"}
        if text.strip():
            baselines.append((position[1], item["index"]))
    tolerance = ROW_BASELINE_FRACTION * char_height
    groups: list[dict[str, Any]] = []
    last = float("-inf")
    for baseline, index in sorted(baselines):
        if baseline - last > tolerance:
            groups.append({"baseline_y": baseline, "display_indices": []})
        groups[-1]["display_indices"].append(index)
        last = baseline
    return {
        "count": len(groups),
        "groups": groups,
        "tolerance_m": tolerance,
        "metric": "grouped nonempty IDisplayData text-position Y baselines; not logical text/paragraph count",
    }


def _template_title(sheet_view: Any) -> tuple[Any, Any]:
    found = []
    for raw in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.OwnerType) != 2 or int(annotation.GetType()) != _ANNOT_NOTE:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        if title_fields._linked_name(str(note.PropertyLinkedText or "")) in title_fields.TITLE_FIELD_PROPERTIES["Title"]:
            found.append((annotation, note))
    if len(found) != 1:
        raise RuntimeError(f"template control needs one native PART cell, found {len(found)}")
    return found[0]


def _wrap_state(annotation: Any, note: Any) -> dict[str, Any]:
    state = {
        "name": _read(annotation.GetName),
        "owner": _read(lambda: annotation.OwnerType),
        "link": _read(lambda: note.PropertyLinkedText),
        "text": _read(note.GetText),
        "height": _read(note.GetHeight),
        "height_points": _read(note.GetHeightInPoints),
        "all_upper_case": _read(lambda: note.AllUpperCase),
        "justification": _read(note.GetTextJustification),
        "position": _read(annotation.GetPosition),
        "extent": _read(note.GetExtent),
        "text_point": _read(note.GetTextPoint2),
        "upper_right": _read(note.GetUpperRight),
        "line_segment_count": _read(note.GetLineCount),
        "text_count": _read(note.GetTextCount),
        "display_count": _read(lambda: title_fields._display_count(annotation)),
        "use_doc_format": _read(lambda: annotation.GetUseDocTextFormat(0)),
        "text_format": _read(lambda: _text_format(annotation)),
    }
    count = state["text_count"]
    state["text_items_1_based"] = [
        {"index": index, "text": _read(lambda i=index: note.GetTextAtIndex(i))}
        for index in range(1, count + 1)
    ] if isinstance(count, int) else []
    state["display_data"] = _read(lambda: _display_state(annotation))
    state["native_rows"] = _display_rows(state["display_data"], state["height"])
    state["paragraphs"] = _read(lambda: _paragraph_state(annotation))
    point, upper, extent = state["text_point"], state["upper_right"], state["extent"]
    if (
        isinstance(point, list) and len(point) == 3
        and isinstance(upper, list) and len(upper) == 3
        and isinstance(extent, list) and len(extent) >= 6
        and all(isinstance(value, (int, float)) for value in [*point, *upper, *extent])
    ):
        state["box_width"] = upper[0] - point[0]
        state["ink_width"] = extent[3] - extent[0]
        # GetUpperRight on R7's moved owner-1 note retained its insertion
        # coordinates. Do not classify a box from those inconsistent corners.
        state["box_geometry_consistent"] = abs(upper[1] - extent[4]) <= TITLE_FIELD_CLEARANCE_M
        state["fixed_box"] = (
            state["justification"] == 1 and upper[0] - extent[3] > 0.0001
            if state["box_geometry_consistent"] else None
        )
    else:
        state["fixed_box"] = None
    return state


def _wrap_template_title(
    adapter: Any, ddoc: Any, sheet_view: Any, observations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Persist a LineLength-only control without changing the template style.
    Its fixed-width note box is not settable through the documented SDK.
    A one-row readback is explicitly classified as inert, never as a wrap."""
    result: dict[str, Any] = {}
    ddoc.EditTemplate()
    if bool(ddoc.GetEditSheet()):
        raise RuntimeError("EditTemplate left the drawing in sheet mode")
    result["template_mode"] = True
    try:
        annotation, note = _template_title(sheet_view)
        before = _wrap_state(annotation, note)
        result["before"] = before
        result["link"] = before["link"]
        _observe_construction(observations, "wrap.template.before", state=before)
        if not isinstance(before["text_format"], dict) or not before["text_format"]:
            raise RuntimeError("template PART original font/style was unreadable")
        original_values = [before["height"], before["height_points"], *before["text_format"].values()]
        if any(value is None or (isinstance(value, str) and value.startswith("<error:")) for value in original_values):
            raise RuntimeError("template PART original font/style has refused fields")
        text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
        result["clear_set"] = _read(lambda: annotation.SetTextFormat(0, True, None))
        _observe_construction(observations, "wrap.template.clear", returned=result["clear_set"],
                              state=_wrap_state(annotation, note))
        if not _is_true(result["clear_set"]):
            raise RuntimeError("template PART rich-format clear was refused")
        text_format.LineLength = WRAP_M
        result["wrap_set"] = _read(lambda: annotation.SetTextFormat(0, False, text_format))
        _observe_construction(observations, "wrap.template.restore", returned=result["wrap_set"],
                              state=_wrap_state(annotation, note))
        if not _is_true(result["wrap_set"]):
            raise RuntimeError("template PART original-format restoration was refused")
    finally:
        ddoc.EditSheet()
        if not bool(ddoc.GetEditSheet()):
            raise RuntimeError("EditSheet left the drawing in template mode")
    result["sheet_mode"] = True
    rebuild_drawing(adapter, label="title fit template wrap readback")
    after = _wrap_state(annotation, note)
    result["after"] = after
    _observe_construction(observations, "wrap.template.after", state=after,
                          drawing_state=_drawing_state(adapter, adapter.currentModel))
    for key in (
        "name", "owner", "text", "height", "height_points", "all_upper_case",
        "justification", "position", "use_doc_format", "text_point", "upper_right", "box_width",
    ):
        if after[key] != before[key]:
            raise RuntimeError(f"template wrap changed {key}: {before[key]!r} -> {after[key]!r}")
    if title_fields._linked_name(str(after["link"])) != title_fields._linked_name(str(before["link"])):
        raise RuntimeError("template wrap changed the source property link")
    if not isinstance(before["text_format"], dict) or not isinstance(after["text_format"], dict):
        raise RuntimeError("template wrap could not read both font/style snapshots")
    old_style = {key: value for key, value in before["text_format"].items() if key != "LineLength"}
    new_style = {key: value for key, value in after["text_format"].items() if key != "LineLength"}
    if new_style != old_style:
        raise RuntimeError(f"template wrap changed original font/style: {old_style!r} -> {new_style!r}")
    if after["text_format"].get("LineLength") != WRAP_M:
        raise RuntimeError("template PART wrap width did not persist")
    if not (
        before.get("fixed_box") is True and after.get("fixed_box") is True
        and before.get("box_width") == after.get("box_width")
        and before["text_count"] == before["display_count"] == 1
        and after["text_count"] == after["display_count"] == 1
        and before["native_rows"].get("count") == after["native_rows"].get("count") == 1
        and before["extent"] == after["extent"]
    ):
        raise RuntimeError("LineLength-only control did not preserve an observed one-row fixed template box")
    result["inert_under_fixed_box"] = True
    result["evidence_kind"] = "persisted-width-only; not a physical template wrap"
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
        decoy = _drawing_title_control(sheet)
        if decoy is not None:
            sheet["drawing_title_control_pdf"] = _note_pdf_rows(pages[index], decoy)
    _telemetry.info(f"title fit {key}: {json.dumps(capture['contract'], default=str)[:2000]}")
    return capture


def _note_pdf_rows(page: Any, note: Mapping[str, Any]) -> dict[str, Any]:
    """Measure the actual glyph baselines in an independently placed note's
    native extent, not in the title-block cells or by text-object count."""
    extent = note.get("extent")
    if not isinstance(extent, list) or len(extent) < 6 or not all(
        isinstance(value, (float, int)) for value in extent
    ):
        return {"native_extent": extent, "error": "native extent is unreadable"}
    xmin, ymin, xmax, ymax = extent[0], extent[1], extent[3], extent[4]
    clearance = TITLE_FIELD_CLEARANCE_M
    pieces = []
    glyphs = []
    for span in page.spans:
        inside = tuple(
            glyph
            for glyph in span.glyphs
            if xmin - clearance <= (glyph.xmin + glyph.xmax) / 2 <= xmax + clearance
            and ymin - clearance <= (glyph.ymin + glyph.ymax) / 2 <= ymax + clearance
        )
        if inside:
            glyphs.extend(inside)
            pieces.append({
                "text": span.text,
                "glyphs": [
                    [glyph.char, glyph.xmin, glyph.ymin, glyph.xmax, glyph.ymax, glyph.baseline]
                    for glyph in inside
                ],
            })
    measured = Span(str(note.get("text") or ""), xmin, ymin, xmax, ymax, tuple(glyphs))
    return {"native_extent": extent, "rows": measured.rows, "pieces": pieces}


def _drawing_title_control(sheet: Mapping[str, Any]) -> Mapping[str, Any] | None:
    notes = [
        note for note in sheet["notes"]
        if note.get("owner") == 1
        and note.get("parsed_property") in title_fields.TITLE_FIELD_PROPERTIES["Title"]
    ]
    return notes[0] if len(notes) == 1 else None


def _template_title_catalog(sheet: Mapping[str, Any]) -> Mapping[str, Any]:
    notes = [
        note for note in sheet["notes"]
        if note.get("owner") == 2
        and note.get("parsed_property") in title_fields.TITLE_FIELD_PROPERTIES["Title"]
    ]
    if len(notes) != 1:
        raise RuntimeError("native catalog does not contain exactly one template Title baseline")
    return notes[0]


def _physical_rows(page: Any, template: Any, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each identity's printed pieces in the title block -- text objects
    spelling a run of it, wrapped remainders included -- and the distinct
    glyph baselines they stand on together (``Span.rows``' rule). A whole
    one-line print is one piece on one baseline; the wrapped case must read
    multiple rows."""
    measured = []
    for record in records:
        text = record["text"]
        pieces = []
        normalizations = []
        for span in page.spans:
            if span.xmin < template.title_block_left_m or span.ymax > 0.066:
                continue
            fragment = span.text
            normalized = False
            # Actual overlong PDFs emit one terminal U+FFFE at a source
            # wrap-break hyphen. Match only that known source boundary; keep
            # the raw text/glyphs below, and never substitute other characters.
            if fragment.endswith("\ufffe") and fragment.count("\ufffe") == 1:
                candidate = fragment.rstrip("\ufffe")
                if candidate + "-" in text:
                    fragment = candidate
                    normalized = True
            if len(fragment) >= 3 and fragment in text:
                pieces.append(span)
                if normalized:
                    normalizations.append({
                        "raw": span.text,
                        "source_fragment": fragment,
                        "rule": "single terminal U+FFFE stripped at an exact source hyphen boundary",
                    })
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
                "normalizations": normalizations,
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
    mutate: Callable[[Any, Any, Any, TitleSource], dict[str, Any]] | None = None,
    *,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    template = DRAWING_TEMPLATES[layout]
    draw, _sheet = new_project_drawing(adapter, layout=layout)
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = place_view(adapter, str(part), "*Front", template.width_m * 0.3, template.height_m * 0.6)
    sheet_name = str(ddoc.GetSheetNames()[0])
    _link_property_view(adapter, ddoc, sheet_name, view)
    configuration = str(view.ReferencedConfiguration or "")
    source = TitleSource(view.ReferencedDocument, configuration, number, title)
    source_before = title_fields._model_state(source.model)
    extra = mutate(draw, ddoc, _sheet_views(ddoc)[sheet_name], source) if mutate else {}
    rebuild_drawing(adapter, label=f"title fit {key}")
    source_after = title_fields._model_state(source.model)
    if source_after != source_before or str(view.ReferencedConfiguration or "") != configuration:
        _telemetry.info(f"title fit {key}: construction source changed {source_before!r} -> {source_after!r}")
        raise RuntimeError(f"title fit {key}: drawing construction changed its source/configuration state")
    sources = {sheet_name: source}
    return _capture(adapter, key, draw, sources, {sheet_name: layout}, {"mutations": extra}, pdf_path=pdf_path)


def _configs_two_sheets(adapter: Any, part: Path, observations: list[dict[str, Any]]) -> dict[str, Any]:
    names = list(CONFIGS)
    first_layout = CONFIGS[names[0]][0]
    draw, sheet = new_project_drawing(adapter, layout=first_layout)
    ddoc = _early_bound(draw, "IDrawingDoc")
    _early_bound(sheet, "ISheet").SetName(names[0])
    if _active_sheet(ddoc) != names[0]:
        raise RuntimeError("configs-2sheet: first sheet rename did not take")
    for name in names[1:]:
        _add_donor_sheet(adapter, draw, CONFIGS[name][0], name, observations)
    draw = _activate_probe_drawing(adapter, draw, observations)
    ddoc = _early_bound(draw, "IDrawingDoc")
    sources, layouts = {}, {}
    model_before = None
    for name in names:
        layout, number = CONFIGS[name]
        template = DRAWING_TEMPLATES[layout]
        if not ddoc.ActivateSheet(name) or _active_sheet(ddoc) != name:
            raise RuntimeError(f"failed to activate {name!r}")
        _observe_construction(observations, "configs.view.before", sheet=name, model_path=str(part),
                              state=_drawing_state(adapter, draw))
        view = place_view(adapter, str(part), "*Front", template.width_m * 0.3, template.height_m * 0.6)
        model = _early_bound(view.ReferencedDocument, "IModelDoc2")
        model_path = Path(str(model.GetPathName() or ""))
        if not title_fields._same_file(model_path, part):
            raise RuntimeError(f"configs-2sheet {name}: view references {model_path}, not {part}")
        before = title_fields._model_state(model)
        if model_before is None:
            model_before = before
        _observe_construction(observations, "configs.configuration.before", sheet=name,
                              view=str(view.GetName2()), referenced_configuration=str(view.ReferencedConfiguration),
                              source_model_state=list(before))
        view.ReferencedConfiguration = name
        _link_property_view(adapter, ddoc, name, view)
        # The SDK requires EditRebuild3 after a view configuration changes.
        rebuild_drawing(adapter, label=f"title fit configs-2sheet {name}")
        configuration = str(view.ReferencedConfiguration or "")
        _observe_construction(observations, "configs.configuration.after", sheet=name,
                              view=str(view.GetName2()), referenced_configuration=configuration,
                              source_model_state=list(title_fields._model_state(model)),
                              state=_drawing_state(adapter, draw))
        if configuration != name:
            raise RuntimeError(f"configs-2sheet {name}: view configuration is {configuration!r}")
        sources[name] = (view, number)
        layouts[name] = layout
    model = _early_bound(sources[names[0]][0].ReferencedDocument, "IModelDoc2")
    # Authoring view configurations must not leave this scratch source on one
    # of them: the read contract is exercised with its original Default active.
    state = title_fields._model_state(model)
    if state[0] != "Default":
        switched = _read(lambda: model.ShowConfiguration2("Default"))
        _observe_construction(observations, "configs.source.restore-default", returned=switched,
                              before=list(state), after=list(title_fields._model_state(model)))
        if not _is_true(switched):
            raise RuntimeError("configs-2sheet: source Default configuration restoration was refused")
    final_state = title_fields._model_state(model)
    _observe_construction(observations, "configs.source.before-capture",
                          original_state=list(model_before), current_state=list(final_state))
    if model_before != final_state or final_state[0] != "Default":
        raise RuntimeError(f"configs-2sheet construction changed source state {model_before!r} -> {final_state!r}")
    # The drawing-owned control note lands on the active sheet: T006.
    if not ddoc.ActivateSheet(names[0]) or _active_sheet(ddoc) != names[0]:
        raise RuntimeError(f"configs-2sheet: {names[0]!r} is not the active sheet ({_active_sheet(ddoc)!r})")
    control = _insert_linked_note(draw, '$PRPSHEET:"Number"', (0.05, 0.20))
    rebuild_drawing(adapter, label="title fit configs-2sheet")
    resolved = {
        name: TitleSource(view.ReferencedDocument, str(view.ReferencedConfiguration or ""), number, CONFIG_TITLE)
        for name, (view, number) in sources.items()
    }
    extra = {
        "configurations": {name: str(view.ReferencedConfiguration or "") for name, (view, _n) in sources.items()},
        "drawing_note_control": control,
    }
    _observe_construction(observations, "configs.capture.before", state=_drawing_state(adapter, draw),
                          source_model_state=list(title_fields._model_state(model)), **extra)
    return _capture(adapter, "configs-2sheet", draw, resolved, layouts, extra)


def _force_wraps(
    adapter: Any, draw: Any, ddoc: Any, sheet_view: Any, observations: list[dict[str, Any]], source: TitleSource
) -> dict[str, Any]:
    """Observe a true native positive, then bisect identical text/font/style
    under a drawing-owned auto box versus the template's original fixed box."""
    annotation, note = _template_title(sheet_view)
    template_original = _wrap_state(annotation, note)
    sheet_name = _active_sheet(ddoc)
    source_before = title_fields._model_state(source.model)
    drawing_before = _drawing_state(adapter, draw)
    baseline = {
        "native_catalog": _native_catalog(adapter, sheet_view, key="wrapped-landscape.before", sheet=sheet_name),
        "contract": _contract(ddoc, {sheet_name: source}, {sheet_name: DrawingLayout.LANDSCAPE}),
        "source_model_state": list(source_before),
        "drawing_state": drawing_before,
        "template_title": template_original,
    }
    _observe_construction(observations, "wrap.native-positive-baseline", **baseline)
    if (
        baseline["contract"].get("breaches") != []
        or "read_error" in baseline["contract"]
        or "read_breaches" in baseline["contract"]
    ):
        raise RuntimeError("untouched registry Title did not pass the native positive baseline")
    if title_fields._model_state(source.model) != source_before or _drawing_state(adapter, draw) != drawing_before:
        raise RuntimeError("native positive baseline reads changed source/drawing state")
    if (
        template_original["text_count"] != 1 or template_original["display_count"] != 1
        or template_original["native_rows"].get("count") != 1
        or template_original.get("fixed_box") is not True
    ):
        raise RuntimeError("native positive baseline did not observe a one-row fixed template Title")

    # Use the original unresolved link, including its observed 15PT rich tag,
    # and the same ITextFormat object values. No shorthand descriptor,
    # smaller document font, literal newline, or fallback can be the control.
    text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    draw.ClearSelection2(True)
    raw = draw.InsertNote(str(template_original["link"]))
    if raw is None:
        raise RuntimeError("matched drawing-owned Title control insertion failed")
    decoy_note = _early_bound(raw, "INote")
    decoy_annotation = _early_bound(decoy_note.GetAnnotation(), "IAnnotation")
    decoy = {"inserted": True, "before": _wrap_state(decoy_annotation, decoy_note)}
    _observe_construction(observations, "wrap.drawing-decoy.before", state=decoy["before"])
    decoy["positioned"] = _read(lambda: decoy_annotation.SetPosition2(0.05, 0.20, 0.0))
    decoy["clear_set"] = _read(lambda: decoy_annotation.SetTextFormat(0, True, None))
    _observe_construction(observations, "wrap.drawing-decoy.clear", returned=decoy["clear_set"],
                          state=_wrap_state(decoy_annotation, decoy_note))
    if not _is_true(decoy["positioned"]) or not _is_true(decoy["clear_set"]):
        raise RuntimeError("matched drawing-owned Title position/rich-format clear failed")
    text_format.LineLength = WRAP_M
    decoy["wrap_set"] = _read(lambda: decoy_annotation.SetTextFormat(0, False, text_format))
    _observe_construction(observations, "wrap.drawing-decoy.restore", returned=decoy["wrap_set"],
                          state=_wrap_state(decoy_annotation, decoy_note))
    if not _is_true(decoy["wrap_set"]):
        raise RuntimeError("matched drawing-owned Title original-format copy was refused")
    template_control = _wrap_template_title(adapter, ddoc, sheet_view, observations)
    decoy["after"] = _wrap_state(decoy_annotation, decoy_note)
    _observe_construction(observations, "wrap.drawing-decoy.after", state=decoy["after"])
    if decoy["after"]["owner"] != 1:
        raise RuntimeError("matched positive control is not drawing-owned")
    for field in ("text", "height", "height_points", "all_upper_case", "justification", "use_doc_format"):
        if decoy["after"][field] != template_original[field]:
            raise RuntimeError(f"matched positive control changed original template {field}")
    if title_fields._linked_name(str(decoy["after"]["link"])) != title_fields._linked_name(str(template_original["link"])):
        raise RuntimeError("matched positive control changed the exact source-link descriptor")
    expected_style = {key: value for key, value in template_original["text_format"].items() if key != "LineLength"}
    actual_style = {key: value for key, value in decoy["after"]["text_format"].items() if key != "LineLength"}
    if actual_style != expected_style or decoy["after"]["text_format"].get("LineLength") != WRAP_M:
        raise RuntimeError("matched positive control did not preserve the original font/style and imposed width")
    if not (
        isinstance(decoy["after"]["native_rows"].get("count"), int)
        and decoy["after"]["native_rows"]["count"] >= 2
    ):
        raise RuntimeError("matched drawing-owned positive control did not really wrap natively")
    if title_fields._model_state(source.model) != source_before:
        raise RuntimeError("wrap-control construction changed the source model's state")
    return {
        "native_positive_baseline": baseline,
        "template_original": template_original,
        "drawing_note": decoy,
        "template_title": template_control,
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


def _physical_wrap_failures(capture: Mapping[str, Any], baseline: Mapping[str, Any]) -> list[str]:
    """An untouched overlong source must really wrap the original owner-2
    template note, not merely persist an inert format width."""
    failures: list[str] = []
    name, sheet = _only_sheet(capture)
    reading = _readings(capture, failures).get((name, "Title"))
    expected = sheet["source"]["expected"]["Title"]
    if reading is None or (
        reading["expected"], reading["model_value"], reading["printed"]
    ) != (expected, expected, expected):
        failures.append(f"{capture['key']}: physical-wrap Title is not its exact source: {reading!r}")
    if reading is None or not (
        "multi-line" in reading["problem_kinds"] and "outside-cell" in reading["problem_kinds"]
        and reading["display_count"] >= 2
    ):
        failures.append(f"{capture['key']}: no real native/display multiline outside-cell refusal: {reading!r}")
    rows = next((row["rows"] for row in sheet["physical_rows"] if row["source"] == "Title"), None)
    if not isinstance(rows, int) or rows < 2:
        failures.append(f"{capture['key']}: real template negative has {rows!r} PDF baselines, not multiple")
    notes = [
        note for note in sheet["notes"]
        if note.get("owner") == 2
        and note.get("parsed_property") in title_fields.TITLE_FIELD_PROPERTIES["Title"]
    ]
    if len(notes) != 1:
        failures.append(f"{capture['key']}: not exactly one physical template Title: {notes!r}")
    else:
        note = notes[0]
        diagnostics = note.get("wrap_diagnostics")
        native_rows = diagnostics.get("native_rows") if isinstance(diagnostics, dict) else None
        if (
            not isinstance(native_rows, dict) or not isinstance(native_rows.get("count"), int)
            or native_rows["count"] < 2
        ):
            failures.append(
                f"{capture['key']}: real template negative lacks multiple measured native baselines: {native_rows!r}"
            )
        for field in (
            "link", "height", "height_points", "all_upper_case", "justification",
            "position", "use_doc_format", "text_format",
        ):
            if note.get(field) != baseline.get(field):
                failures.append(
                    f"{capture['key']}: untouched template {field}: {note.get(field)!r} != {baseline.get(field)!r}"
                )
    states = capture["observation_state"]
    if not all(state == states[0] for state in states[1:]):
        failures.append(f"{capture['key']}: physical-wrap reads changed document state {states!r}")
    return failures


def _wrapped_failures(wrapped: Mapping[str, Any]) -> list[str]:
    """Prove the actual native baseline and matched auto-box positive, while
    explicitly refusing to call an inert fixed-box width change a physical wrap."""
    failures: list[str] = []

    def need(ok: bool, message: str) -> None:
        if not ok:
            failures.append(message)

    name, sheet = _only_sheet(wrapped)
    mutation = wrapped["mutations"].get("template_title") or {}
    need(
        mutation.get("template_mode") is True and mutation.get("sheet_mode") is True
        and _is_true(mutation.get("clear_set")) and _is_true(mutation.get("wrap_set"))
        and mutation.get("inert_under_fixed_box") is True,
        f"wrapped-landscape: not a strictly observed inert fixed-box control: {mutation!r}",
    )
    positive = wrapped["mutations"].get("native_positive_baseline") or {}
    need(
        positive.get("contract", {}).get("breaches") == []
        and "read_error" not in positive.get("contract", {})
        and "read_breaches" not in positive.get("contract", {}),
        f"wrapped-landscape: original template did not pass the native positive baseline: {positive!r}",
    )
    readings = _readings(wrapped, failures)
    reading = readings.get((name, "Title"))
    kinds = None if reading is None else reading["problem_kinds"]
    need(
        kinds == ["wrap-width"] and reading["text_count"] == 1 and reading["display_count"] == 1,
        f"wrapped-landscape Title: expected only wrap-width, with one actual native/display row: {reading!r}",
    )
    need(
        mutation.get("after", {}).get("native_rows", {}).get("count") == 1,
        f"wrapped-landscape Title: inert control has more than one measured native baseline: {mutation!r}",
    )
    number = readings.get((name, "Number"))
    need(number is not None and number["problem_kinds"] == [], f"wrapped-landscape Number: {number!r}")
    fit = next((fit for fit in sheet["printed_fits"] if fit["source"] == "Title"), None)
    need(
        fit is not None and fit["printed"] is not None and fit["rows"] == 1,
        f"wrapped-landscape Title: inert control is not printed whole on one PDF row: {fit!r}",
    )
    rows = next((row["rows"] for row in sheet["physical_rows"] if row["source"] == "Title"), None)
    need(rows == 1, f"wrapped-landscape Title: inert control has {rows!r} physical baseline rows, not one")

    decoy = _drawing_title_control(sheet)
    need(decoy is not None, "wrapped-landscape: not exactly one drawing-owned Title positive control")
    if decoy is not None:
        baseline = mutation.get("before") or {}
        need(
            decoy.get("parsed_property") == title_fields._linked_name(str(baseline.get("link") or "")),
            "wrapped-landscape: drawing-owned control uses a different source-link descriptor",
        )
        for field in ("text", "height", "height_points", "all_upper_case", "justification", "use_doc_format"):
            need(
                decoy.get(field) == baseline.get(field),
                f"wrapped-landscape: drawing-owned control {field}: {decoy.get(field)!r} != {baseline.get(field)!r}",
            )
        native_style = {key: value for key, value in (decoy.get("text_format") or {}).items() if key != "LineLength"}
        baseline_style = {key: value for key, value in (baseline.get("text_format") or {}).items() if key != "LineLength"}
        need(
            bool(native_style) and native_style == baseline_style,
            f"wrapped-landscape: drawing-owned control font/style {native_style!r} != {baseline_style!r}",
        )
        need(
            isinstance(decoy.get("wrap_diagnostics"), dict)
            and isinstance(decoy["wrap_diagnostics"].get("native_rows", {}).get("count"), int)
            and decoy["wrap_diagnostics"]["native_rows"]["count"] >= 2,
            f"wrapped-landscape: drawing-owned positive control is not natively multiline: {decoy!r}",
        )
        printed = sheet.get("drawing_title_control_pdf") or {}
        need(
            isinstance(printed.get("rows"), int) and printed["rows"] >= 2,
            f"wrapped-landscape: drawing-owned positive control has no multiple PDF baselines: {printed!r}",
        )
        extent = decoy.get("extent")
        box = [extent[0], extent[1], extent[3], extent[4]] if isinstance(extent, list) and len(extent) >= 6 else None
        cells = sheet["cells"].values()
        need(
            box is not None and all(
                box[2] < cell[0] or box[0] > cell[2] or box[3] < cell[1] or box[1] > cell[3]
                for cell in cells
            ),
            f"wrapped-landscape: drawing-owned control {box!r} overlaps an identity cell",
        )
        need(
            reading is not None and reading["extent"] != box,
            "wrapped-landscape: the Title reading took the drawing-owned control's extent",
        )
    states = wrapped["observation_state"]
    need(
        all(state == states[0] for state in states[1:]),
        f"wrapped-landscape: native observations changed document state {states!r}",
    )
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
        failures.extend(_physical_wrap_failures(capture, _template_title_catalog(control_sheet)))

    failures.extend(_wrapped_failures(by_key["wrapped-landscape"]))

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
    observations: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "mode": "native-link-discovery" if legacy_only else "full-title-field-proof",
        "success_means": "raw observations captured, not Title fit passed" if legacy_only else "all controls passed",
        "cases": {case: list(value) for case, value in CASES.items()},
        "configs": {name: [layout.value, value] for name, (layout, value) in CONFIGS.items()},
        "wrap_m": WRAP_M,
        "captures": captures,
        "construction_observations": observations,
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
        # Exercise the mixed-sheet constructor before a wrapped-note failure
        # can prevent its independent source/configuration control from running.
        configs_part = await _scratch_part(
            adapter, "configs", CONFIG_FILE_NUMBER, CONFIG_TITLE, {name: value for name, (_l, value) in CONFIGS.items()}
        )
        captures.append(_configs_two_sheets(adapter, configs_part, observations))
        parts = {}
        for case, (number, title) in CASES.items():
            if case == "control-v39":
                continue
            parts[case] = await _scratch_part(adapter, case, number, title)
            for layout in LAYOUTS:
                capture = _single_sheet(adapter, f"{case}-{layout.value}", parts[case], layout, number, title)
                captures.append(capture)
                if case == "overlong":
                    control = next(item for item in captures if item["key"] == f"control-v39-{layout.value}")
                    _name, control_sheet = _only_sheet(control)
                    failures = _physical_wrap_failures(capture, _template_title_catalog(control_sheet))
                    if failures:
                        report["control_failures"] = failures
                        raise RuntimeError("real template physical-wrap negative failed:\n" + "\n".join(failures))
        number, title = CASES[WRAPPED_CASE]
        captures.append(
            _single_sheet(
                adapter, "wrapped-landscape", parts[WRAPPED_CASE], DrawingLayout.LANDSCAPE, number, title,
                lambda draw, ddoc, sheet_view, source: _force_wraps(adapter, draw, ddoc, sheet_view, observations, source),
            )
        )
        discard_open_documents(adapter)
        report["control_failures"] = _check_controls(captures)
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        # Failed leaves do not publish normal outputs. Keep completed native/PDF
        # controls and fatal-construction observations in task.log as well.
        partial = {
            "error": report["error"],
            "construction_observations": observations,
            "captures": [
                {
                    "key": capture["key"],
                    "mutations": capture.get("mutations"),
                    "contract": capture["contract"],
                    "active_sheet": capture["active_sheet"],
                    "observation_state": capture["observation_state"],
                    "pdf": capture["pdf"],
                    "sheets": {
                        name: {key: sheet[key] for key in ("source", "printed_fits", "printed_misfits", "physical_rows")}
                        for name, sheet in capture["sheets"].items()
                    },
                }
                for capture in captures
            ],
        }
        _telemetry.info(f"title partial proof after fatal construction: {json.dumps(partial, default=str)}")
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
    sys.exit(run_build(probe))
