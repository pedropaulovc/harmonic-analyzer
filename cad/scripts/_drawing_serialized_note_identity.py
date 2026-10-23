"""Capture a note's actual post-save name from its original native annotation.

Call after successful native/PDF saves and audits, before closing the drawing.
The caller retains physical attachment/landing/text proofs and uses the returned
exact name for fresh cold reads. This module proves only serialized identity:
no geometry lookup, text matching, assumed name persistence, rebuild or repair.

SDK: IDrawingDoc.GetViews returns unordered sheet rows, each led by its sheet
view. IAnnotation.GetName takes no arguments; ISldWorks.IsSame compares native
objects rather than Python wrappers or diagnostic names. Refusals retain the
reachable native inventory and chain the original getter exception.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import view_name

import _telemetry
from _com import _early_bound


@_telemetry.traced("drawing.serialized_note_identity_capture", label_param="label")
def capture_serialized_note_name(
    adapter: Any,
    original_annotation: Any,
    view: Any,
    *,
    drawing_path: Path,
    source_path: Path,
    sheet_names: tuple[str, ...],
    sheet_name: str,
    configuration: str,
    label: str,
) -> str:
    """Return the unique actual saved name of this exact original native note."""
    missing = object()
    errors = []
    problems = []
    inventory = []
    matches = []
    saved_path = Path(drawing_path).resolve()
    expected_source_path = Path(source_path).resolve()
    evidence = {
        "phase": "serialized_capture", "label": label,
        "expected_document_path": str(saved_path),
        "expected_source_path": str(expected_source_path),
        "expected_sheet": sheet_name, "expected_configuration": configuration,
        "inventory": inventory,
    }

    def observe(record, key, getter, *, native=False):
        try:
            value = getter()
        except Exception as error:
            errors.append(error)
            record.setdefault("errors", []).append({
                "field": key, "type": type(error).__name__, "error": str(error),
            })
            return missing
        if native:
            record[f"{key}_null"] = value is None
        else:
            record[key] = (
                value if value is None or isinstance(value, (str, bool, int, float, tuple, list))
                else {"type": type(value).__name__, "repr": repr(value)[:120]}
            )
        return value

    app = observe(evidence, "app_bind", lambda: _early_bound(adapter.swApp, "ISldWorks"), native=True)

    def same(record, key, left, right):
        value = observe(record, key, lambda: app.IsSame(left, right))
        if value is not missing and (
            isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1)
        ):
            problems.append(f"{key}: unknown native IsSame state {value!r}")
        return value

    model = observe(
        evidence, "model_bind", lambda: _early_bound(adapter.currentModel, "IModelDoc2"), native=True,
    )
    drawing = observe(evidence, "drawing_bind", lambda: _early_bound(model, "IDrawingDoc"), native=True)
    actual_path = observe(evidence, "document_path", lambda: model.GetPathName())
    actual_type = observe(evidence, "document_type", lambda: model.GetType())
    if (
        not isinstance(actual_path, str) or not actual_path
        or not Path(actual_path).is_absolute() or Path(actual_path).resolve() != saved_path
        or actual_type != 3
    ):
        problems.append("original note is not in the actual saved output drawing")
    for key, getter in (
        ("registered_document", lambda: app.GetOpenDocumentByName(str(saved_path))),
        ("active_document", lambda: app.ActiveDoc),
    ):
        document = observe(evidence, key, getter, native=True)
        if document is missing or document is None:
            problems.append(f"{key}: actual saved current drawing is unavailable")
        elif same(evidence, f"{key}_same", document, model) != 1:
            problems.append(f"{key}: actual saved current drawing changed")
    expected_view_name = observe(evidence, "expected_view_name", lambda: view_name(adapter, view))
    if original_annotation is None or view is None:
        problems.append("original native note annotation/view reference is null")
    else:
        owner = observe(evidence, "original_owner", lambda: original_annotation.Owner, native=True)
        if owner is missing or owner is None or same(evidence, "original_owner_same", owner, view) != 1:
            problems.append("original native note owner changed")
    actual_sheet_names = observe(evidence, "sheet_names", lambda: drawing.GetSheetNames())
    if not isinstance(actual_sheet_names, (tuple, list)) or tuple(actual_sheet_names) != sheet_names:
        problems.append("actual saved drawing sheet census changed")
    rows = observe(evidence, "view_rows", lambda: drawing.GetViews(), native=True)
    if not isinstance(rows, (tuple, list)):
        problems.append("actual all-sheet native view rows are unavailable")
    observed_sheets = []
    for row_index, row in enumerate(rows if isinstance(rows, (tuple, list)) else ()):
        sheet_record = {"row_index": row_index}
        if not isinstance(row, (tuple, list)) or not row:
            inventory.append(sheet_record)
            problems.append(f"row {row_index}: native sheet-view reference is unavailable")
            continue
        sheet_view = observe(
            sheet_record, "sheet_view", lambda: _early_bound(row[0], "IView"), native=True,
        )
        sheet = (
            observe(sheet_record, "sheet", lambda: view_name(adapter, sheet_view))
            if sheet_view is not missing and sheet_view is not None else missing
        )
        observed_sheets.append(sheet)
        for index, raw_view in enumerate(row):
            record = dict(sheet_record, is_sheet_view=index == 0, annotations=[])
            if "errors" in record:
                record["errors"] = list(record["errors"])
            inventory.append(record)
            native_view = observe(record, "view", lambda: _early_bound(raw_view, "IView"), native=True)
            if native_view is missing or native_view is None:
                problems.append(f"row {row_index} view {index}: native view reference is unavailable")
                continue
            observe(record, "view_name", lambda: view_name(adapter, native_view))
            if index:
                observe(record, "configuration", lambda: native_view.ReferencedConfiguration)
                source = observe(record, "source", lambda: native_view.ReferencedDocument, native=True)
                if source is missing or source is None:
                    problems.append(f"row {row_index} view {index}: native source reference is unavailable")
                else:
                    observe(record, "source_path", lambda: _early_bound(source, "IModelDoc2").GetPathName())
            annotations = observe(record, "annotations_array", lambda: native_view.GetAnnotations(), native=True)
            if annotations is missing:
                continue
            for raw in annotations or ():
                item = {}
                record["annotations"].append(item)
                annotation = observe(
                    item, "annotation", lambda: _early_bound(raw, "IAnnotation"), native=True,
                )
                if annotation is missing or annotation is None:
                    problems.append("actual native annotation reference is unavailable")
                    continue
                observe(item, "name", lambda: annotation.GetName())
                observe(item, "type", lambda: annotation.GetType())
                owner_type = observe(item, "owner_type", lambda: annotation.OwnerType)
                # Sheet/template annotations do not have a drawing-view Owner.
                if owner_type == 0:
                    owner = observe(item, "owner", lambda: annotation.Owner, native=True)
                    if owner is missing or owner is None:
                        problems.append("actual native annotation owner reference is unavailable")
                    else:
                        same(item, "owner_same", owner, native_view)
                if original_annotation is not None and same(
                    item, "original_same", annotation, original_annotation,
                ) == 1:
                    matches.append((record, item, native_view))
    if (
        len(observed_sheets) != len(sheet_names)
        or any(not isinstance(sheet, str) for sheet in observed_sheets)
        or set(observed_sheets) != set(sheet_names)
    ):
        problems.append("actual native sheet-view row census changed")
    evidence["match_count"] = len(matches)
    if len(matches) != 1:
        problems.append("original note must have exactly one actual IsSame=1 annotation")
    else:
        record, item, native_view = matches[0]
        native_source_path = record.get("source_path")
        if (
            record.get("sheet") != sheet_name or record["is_sheet_view"]
            or record.get("view_name") != expected_view_name
            or record.get("configuration") != configuration
            or not isinstance(native_source_path, str) or not native_source_path
            or not Path(native_source_path).is_absolute()
            or Path(native_source_path).resolve() != expected_source_path
            or same(record, "original_view_same", native_view, view) != 1
            or item.get("type") != 6 or item.get("owner_type") != 0 or item.get("owner_same") != 1
            or not isinstance(item.get("name"), str) or not item["name"]
        ):
            problems.append("original note's actual serialized source/owner/name changed")
        evidence["serialized_name"] = item.get("name")
        if isinstance(item.get("name"), str) and sum(
            annotation.get("name") == item["name"]
            for view_record in inventory for annotation in view_record.get("annotations", ())
        ) != 1:
            problems.append("actual serialized note name is not unique")
    evidence["problems"] = problems
    if errors or problems:
        _telemetry.event("drawing.serialized_note_identity", status="refused", **evidence)
        error = RuntimeError(f"{label}: serialized note identity capture refused; native_snapshot={evidence!r}")
        if errors:
            raise error from errors[0]
        raise error
    _telemetry.event("drawing.serialized_note_identity", status="captured", **evidence)
    return evidence["serialized_name"]
