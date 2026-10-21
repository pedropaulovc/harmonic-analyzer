"""Temporary Native2554 PD-only read/visibility/restore experiment; never saves.

The caller supplies the actual existing hide, not a reconstructed +1 oracle.
Raw property indices and True/False table indices remain separate evidence.
Remove this module and its explicit PD hook after the intentional failed leaf.
"""

from __future__ import annotations

from collections import Counter
from hashlib import file_digest
import json
from pathlib import Path
from typing import Any, Callable, NoReturn

from solidworks_mcp.adapters import sw_type_info

from _drawing_tables import bom_row_identities
import _telemetry


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError("PD visibility probe: " + message)


def _read(call: Callable[[], Any]) -> Any:
    """Keep independent accessor failures in evidence, including invalid controls."""
    try:
        value = call()
        _require(len(json.dumps(value, allow_nan=False)) <= 16384, "accessor payload overflow")
        return value
    except Exception as error:
        return {"error": type(error).__name__, "detail": str(error)[:768]}


def _count(value: Any, maximum: int, label: str) -> int:
    _require(type(value) is int and 0 <= value <= maximum, f"{label} outside 0..{maximum}: {value!r}")
    return value


def _text(value: Any) -> str:
    _require(type(value) is str and len(value) <= 4096, "missing/oversize native BSTR")
    return value


def _bind(value: Any, interface: str) -> Any:
    _require(value is not None, f"missing {interface}")
    return sw_type_info.early_bound_or_flag(value, interface)


def _kind(column: dict[str, Any]) -> int | None:
    value = column["type"]
    if (
        isinstance(value, (tuple, list)) and len(value) == 3
        and type(value[0]) is int and type(value[2]) is int
        and value[2] == 0 and (value[0] == 0 or 201 <= value[0] <= 211)
    ):
        return value[0]
    return None


def _columns(table: Any, bom: Any) -> dict[str, Any]:
    """Immediate census, before any source/native/render proof can refuse."""
    result = {
        "GetConfigurations(False,None)": _read(lambda: _bind(bom.BomFeature, "IBomFeature").GetConfigurations(False, None)),
        "ColumnCount": _read(lambda: table.ColumnCount),
        "TotalColumnCount": _read(lambda: table.TotalColumnCount),
        "RowCount": _read(lambda: table.RowCount),
        "TotalRowCount": _read(lambda: table.TotalRowCount),
        "raw_ColumnHidden": [], "True": [], "False": [],
    }
    # A bad count refuses traversal, rather than truncating an unknown table.
    try:
        total = _count(result["TotalColumnCount"], 16, "TotalColumnCount")
        _count(result["ColumnCount"], 16, "ColumnCount")
        rows = _count(result["TotalRowCount"], 64, "TotalRowCount")
        _count(result["RowCount"], 64, "RowCount")
    except Exception as error:
        result["bounds_error"] = str(error)
        return result
    result["raw_range_inclusive"] = [0, total + 1]
    for index in range(total + 2):
        result["raw_ColumnHidden"].append(_read(lambda i=index: table.ColumnHidden(i)))
        for hidden in (True, False):
            result[str(hidden)].append({
                "index": index,
                "type": _read(lambda i=index, h=hidden: table.GetColumnType3(i, h)),
                "title": _read(lambda i=index, h=hidden: table.GetColumnTitle2(i, h)),
                "header": _read(lambda i=index, h=hidden: table.DisplayedText2(0, i, h)),
            })
    # Complete metadata is captured before reading the rest of the cell matrix.
    result["RowHidden"] = [_read(lambda r=row: table.RowHidden(r)) for row in range(rows)]
    for hidden in (True, False):
        for column in result[str(hidden)]:
            index = column["index"]
            if _kind(column) is not None:
                column["cells"] = [
                    _read(lambda r=row, i=index, h=hidden: _text(table.DisplayedText2(r, i, h)))
                    for row in range(rows)
                ]
                if hidden and _kind(column) == 204:
                    column["custom_property"] = _read(lambda i=index: _text(bom.GetColumnCustomProperty(i)))
    return result


def _render(table: Any) -> dict[str, Any]:
    data = _bind(_bind(table.GetAnnotation(), "IAnnotation").GetDisplayData(), "IDisplayData")
    lines = _read(lambda: data.GetLineCount())
    texts = _read(lambda: data.GetTextCount())
    result: dict[str, Any] = {
        "frame": "raw display-data frame; sheet translation unknown",
        "line_count": lines, "text_count": texts, "lines": [], "texts": [],
    }
    # Independent limits: a line failure must not hide the text evidence.
    if type(lines) is int and 0 <= lines <= 1024:
        result["lines"] = [_read(lambda i=i: data.GetLineAtIndex3(i)) for i in range(lines)]
    else:
        result["line_error"] = "line count missing or exceeds 1024; not truncated"
    if type(texts) is int and 0 <= texts <= 512:
        result["texts"] = [{
            "index": i,
            "text": _read(lambda i=i: _text(data.GetTextAtIndex(i))),
            "position": _read(lambda i=i: data.GetTextPositionAtIndex(i)),
            "height": _read(lambda i=i: data.GetTextHeightAtIndex(i)),
            "angle": _read(lambda i=i: data.GetTextAngleAtIndex(i)),
            "reference": _read(lambda i=i: data.GetTextRefPositionAtIndex(i)),
        } for i in range(texts)]
    else:
        result["text_error"] = "text count missing or exceeds 512; not truncated"
    return result


def _remember_document(doc: Any, documents: dict[str, Any]) -> str:
    doc = _bind(doc, "IModelDoc2")
    path = _text(doc.GetPathName())
    _require(bool(path) and Path(path).is_absolute(), "source path is not absolute")
    _require(path in documents or len(documents) < 64, "source document count exceeds 64")
    documents[path] = doc
    return path


def _native(
    table: Any, bom: Any, columns: dict[str, Any], configuration: str,
    identities: dict[str, tuple[str, str | None]], documents: dict[str, Any],
) -> dict[str, Any]:
    _require(columns["RowCount"] == columns["TotalRowCount"] == 44, "native traversal requires exactly 43 rows")
    components_by_row = {}
    occurrences = 0
    for row in range(1, 44):
        components = tuple(bom.GetComponents2(row, configuration) or ())
        occurrences += len(components)
        _require(occurrences <= 256, "native component count exceeds 256")
        components_by_row[row] = components
    rows = bom_row_identities(table, configuration=configuration, component_identities=identities)
    _require(set(rows.values()) == set(range(1, 44)), "native mapping is not the complete 43 rows")
    result: dict[str, Any] = {"rows": {}, "configuration": configuration}
    for logical, row in sorted(rows.items()):
        components = components_by_row[row]
        members = []
        for component in components:
            component = _bind(component, "IComponent2")
            # Do not compare live COM proxies: persist declared native identity.
            members.append({
                "path": _read(lambda: _text(component.GetPathName())),
                "configuration": _read(lambda: _text(component.ReferencedConfiguration)),
                "reference": _read(lambda: _text(component.ComponentReference)),
                "name": _read(lambda: _text(component.Name2)),
                "document": _read(lambda: _remember_document(component.GetModelDoc2(), documents)),
            })
        # Native enumeration order is unspecified; retain the exact occurrence
        # multiset, including duplicates. Leave read errors intact for proof.
        if all(type(value) is str for member in members for value in member.values()):
            members.sort(key=lambda member: (
                member["path"], member["configuration"], member["reference"],
                member["name"], member["document"],
            ))
        number = [c for c in columns["True"] if _kind(c) == 204 and c.get("custom_property") == "Number"]
        item = [c for c in columns["True"] if _kind(c) == 202]
        result["rows"][logical] = {
            "row": row, "members": members,
            "Number": [c["cells"][row] for c in number],
            "item": [c["cells"][row] for c in item],
            "Qty": [{"column": c["index"], "text": c["cells"][row]} for c in columns["True"] if _kind(c) == 203],
        }
    return result


def _source_state(documents: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for path, doc in sorted(documents.items()):
        def disk_hash(path: str = path) -> str:
            with Path(path).open("rb") as stream:
                return file_digest(stream, "sha256").hexdigest()

        def active(doc: Any = doc) -> str:
            manager = _bind(doc.ConfigurationManager, "IConfigurationManager")
            return _text(_bind(manager.ActiveConfiguration, "IConfiguration").Name)

        result[path] = {
            "sha256": _read(disk_hash),
            "GetSaveFlag": _read(lambda doc=doc: doc.GetSaveFlag()),
            "active_configuration": _read(active),
            "current_path": _read(lambda doc=doc: _text(doc.GetPathName())),
        }
    return result


def _complete(value: Any) -> None:
    """Reject missing evidence; control-index errors are checked separately."""
    if isinstance(value, dict):
        _require("error" not in value and not any(k.endswith("_error") for k in value), f"accessor evidence failed: {value!r}"[:1024])
        for child in value.values():
            _complete(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _complete(child)


def _projection(columns: dict[str, Any], hidden: bool) -> list[dict[str, Any]]:
    prefix = []
    in_tail = False
    for column in columns[str(hidden)]:
        if column["index"] < columns["TotalColumnCount" if hidden else "ColumnCount"]:
            _complete(column)
        if _kind(column) is None:
            in_tail = True
            continue
        _require(not in_tail, "typed valid column follows invalid tail")
        _complete(column)
        prefix.append({key: column[key] for key in ("type", "title", "header", "cells")})
    _require(bool(prefix), "empty typed prefix")
    if not hidden:
        _require(len(prefix) == columns["ColumnCount"], "actual False prefix differs from ColumnCount")
    return prefix


def _prove_native(stage: dict[str, Any], counts: Counter[str], numbers: dict[str, str], *, quantities: bool) -> None:
    columns = stage["columns"]
    _require("bounds_error" not in columns, "column/row census bounds failed")
    _require(columns["RowCount"] == columns["TotalRowCount"] == 44, "expected complete 43 native rows")
    _require(len(columns["RowHidden"]) == 44 and all(v is False for v in columns["RowHidden"]), "rows are not exactly visible")
    native = stage["native"]
    _complete(native)
    _require(set(native["rows"]) == set(numbers) == set(counts) and len(numbers) == 43, "native row coverage changed")
    for key, expected in (
        ("pd-transgear-removable", 3),
        ("sh-vn-chain-link--InnerLink", 34),
        ("sh-vn-chain-link--OuterLink", 33),
    ):
        _require(counts[key] == expected, f"PD critical occurrence quantity changed: {key}")
    items = []
    for key, row in native["rows"].items():
        _require(len(row["members"]) == counts[key], f"native occurrence count changed: {key}")
        _require(row["Number"] == [numbers[key]], f"canonical Number changed: {key}")
        _require(len(row["item"]) == 1, f"nonunique item column: {key}")
        items.extend(row["item"])
        for member in row["members"]:
            _require(member["path"] == member["document"] and bool(member["configuration"]) and bool(member["name"]), f"unresolved native member: {key}")
        if quantities:
            _require(any(q["text"].strip() == str(counts[key]) for q in row["Qty"]), f"no actual Qty203 prints expected count: {key}")
    _require(set(items) == {str(i) for i in range(1, 44)}, "item sequence changed")
    _complete(stage["sources"])
    _require(bool(stage["sources"]), "source evidence empty")
    for path, source in stage["sources"].items():
        _require(type(source["GetSaveFlag"]) is bool, "GetSaveFlag not BOOL")
        _require(source["current_path"] == path and bool(source["active_configuration"]), "source identity/configuration missing")
    _require(type(stage["root_path"]) is str and stage["root_path"] in stage["sources"], "root source missing")


def _association(stage: dict[str, Any]) -> dict[str, Any]:
    return {key: {field: value for field, value in row.items() if field != "Qty"} for key, row in stage["native"]["rows"].items()}


def _prove_unchanged(
    stage: dict[str, Any], baseline: dict[str, Any], *,
    exact: bool, bom_configuration: bool = True,
) -> None:
    for key in ("root_path", "reference_configuration", "sources"):
        _require(stage[key] == baseline[key], f"{key} changed")
    _require(_association(stage) == _association(baseline), "native membership/Number/item association changed")
    if bom_configuration:
        _require(stage["columns"]["GetConfigurations(False,None)"] == baseline["columns"]["GetConfigurations(False,None)"], "BOM configurations changed")
    if exact:
        for key in ("columns", "native", "render"):
            _require(stage[key] == baseline[key], f"baseline {key} not exactly restored")


def _render_texts(stage: dict[str, Any]) -> Counter[str]:
    render = stage["render"]
    _complete(render)
    _require(render["text_count"] > 0, "empty native render")
    for line in render["lines"]:
        _require(isinstance(line, (list, tuple)) and len(line) == 10, "invalid native line record")
    for text in render["texts"]:
        _require(isinstance(text["position"], (list, tuple)) and len(text["position"]) == 3, "invalid native text position")
    return Counter(text["text"] for text in render["texts"] if text["text"])


def _prove_candidate(stage: dict[str, Any], baseline: dict[str, Any], p: int) -> None:
    before = _projection(baseline["columns"], False)
    expected = before[:p] + before[p + 1:]
    _require(_projection(stage["columns"], False) == expected, "candidate actual False projection is not baseline minus only native201")
    # No coordinate or split-text assumptions are silently accepted. If native
    # rendering splits/merges cell strings, record all primitives and refuse.
    cells_before = Counter(cell for column in before for cell in column["cells"] if cell)
    cells_after = Counter(cell for column in expected for cell in column["cells"] if cell)
    rendered_before = _render_texts(baseline)
    rendered_after = _render_texts(stage)
    _require(rendered_before == cells_before, "baseline render-to-cell multiplicity unproven")
    _require(rendered_after == cells_after, "candidate render-to-cell multiplicity unproven; Qty retention/201 loss not proven")
    removed = Counter(cell for cell in before[p]["cells"] if cell)
    _require(bool(removed) and rendered_before - rendered_after == removed, "actual rendered native201 text loss unproven")


def probe_visibility_domain(
    table: Any,
    native_column: int,
    existing_hide: Callable[[], None],
    *,
    reference: Any,
    configuration: str,
    component_identities: dict[str, tuple[str, str | None]],
    counts: Counter[str],
    part_numbers: dict[str, str],
) -> NoReturn:
    """Run original p+1 once, restore exactly, run raw p once, restore, STOP."""
    _require(configuration == "Default", "diagnostic is only approved for Default")
    _require(type(native_column) is int and native_column >= 0, "invalid native201 index")
    p = native_column
    original_raw, candidate_raw = p + 1, p
    bom = _bind(table, "IBomTableAnnotation")
    reference = _bind(reference, "IView")
    documents: dict[str, Any] = {}
    baseline: dict[str, Any] | None = None
    pending: list[int] = []
    baseline_flags: dict[int, bool] = {}
    primary: BaseException | None = None
    cleanup_errors: list[str] = []
    cleanup_setters: list[tuple[int, bool]] = []

    def capture(phase: str, setter: tuple[int, bool] | None) -> dict[str, Any]:
        # Each evidence family is independent, particularly during cleanup.
        stage: dict[str, Any] = {"columns": _columns(table, bom)}
        stage["root_path"] = _read(lambda: _remember_document(reference.ReferencedDocument, documents))
        stage["reference_configuration"] = _read(lambda: _text(reference.ReferencedConfiguration))
        # _read's small per-accessor cap does not apply to the complete 43 rows.
        try:
            stage["native"] = _native(table, bom, stage["columns"], configuration, component_identities, documents)
        except Exception as error:
            stage["native"] = {"error": type(error).__name__, "detail": str(error)[:768]}
        stage["sources"] = _source_state(documents)
        try:
            stage["render"] = _render(table)
        except Exception as error:
            stage["render"] = {"error": type(error).__name__, "detail": str(error)[:768]}
        evidence = dict(stage)
        if baseline is not None:
            evidence["native"] = {
                "exact_equal": stage["native"] == baseline["native"],
                "changed_rows": {
                    key: row for key, row in stage["native"].get("rows", {}).items()
                    if row != baseline["native"].get("rows", {}).get(key)
                },
                "read_error": stage["native"].get("error"),
                "detail": stage["native"].get("detail"),
                "rows_reread": len(stage["native"].get("rows", {})),
            }
            evidence["sources"] = {
                "exact_equal": stage["sources"] == baseline["sources"],
                "changed": {path: state for path, state in stage["sources"].items() if state != baseline["sources"].get(path)},
                "documents_reread": len(stage["sources"]),
            }
        _telemetry.info("drawing.pd_visibility_domain " + json.dumps({
            "phase": phase, "native201_typed_index": p,
            "original_raw": original_raw, "candidate_raw": candidate_raw,
            "setter": None if setter is None else {"member": "SetColumnHidden", "args": setter},
            "cleanup_setters": cleanup_setters, "cleanup_errors": cleanup_errors,
            "pending_raw_restores": pending[:], "evidence": evidence,
        }, separators=(",", ":"), allow_nan=False))
        return stage

    try:
        baseline = capture("BEFORE-EXISTING", None)
        _prove_native(baseline, counts, part_numbers, quantities=True)
        _complete(baseline["render"])
        _render_texts(baseline)
        columns = baseline["columns"]
        _complete(columns["GetConfigurations(False,None)"])
        names, visibility = columns["GetConfigurations(False,None)"]
        _require(
            isinstance(names, (tuple, list)) and isinstance(visibility, (tuple, list))
            and len(names) == len(visibility) and names.count(configuration) == 1
            and all(type(flag) is bool and flag is (name == configuration)
                    for name, flag in zip(names, visibility, strict=True)),
            "baseline BOM configuration selection is not exactly Default",
        )
        _require(
            all(type(flag) is bool for flag in columns["raw_ColumnHidden"][:columns["TotalColumnCount"]]),
            "baseline raw visibility prefix has missing BOOL evidence",
        )
        _require(type(baseline["reference_configuration"]) is str, "missing reference configuration")
        true_prefix = _projection(columns, True)
        false_prefix = _projection(columns, False)
        _require(true_prefix == false_prefix, "baseline is not actually all visible")
        _require([i for i, c in enumerate(true_prefix) if c["type"][0] == 201] == [p] and p == len(true_prefix) - 1, "actual pre-hide unique201 index changed")
        for index in (original_raw, candidate_raw):
            _require(index < len(columns["raw_ColumnHidden"]) and columns["raw_ColumnHidden"][index] is False, f"raw baseline {index} is not exactly BOOL False")
            baseline_flags[index] = columns["raw_ColumnHidden"][index]
        _require(original_raw != candidate_raw, "control indices must differ")

        pending.append(original_raw)  # BEFORE void setter: it can mutate then throw.
        try:
            existing_hide()
        except BaseException as error:
            try:
                capture("AFTER-EXISTING-SETTER-ERROR", (original_raw, True))
            except Exception as evidence_error:
                error.add_note(f"immediate evidence failed: {evidence_error}")
            raise
        existing = capture("AFTER-EXISTING", (original_raw, True))
        # Incorrect column/Qty visibility is the control outcome, not an oracle.
        _prove_native(existing, counts, part_numbers, quantities=False)
        # A configuration-owned Qty visibility change is also control evidence;
        # source active configurations and native associations still must match.
        _prove_unchanged(existing, baseline, exact=False, bom_configuration=False)

        # Consume the one undo BEFORE its void setter. A partial mutation or
        # failed proof must not cause a second, possibly materializing write.
        pending.remove(original_raw)
        cleanup_setters.append((original_raw, baseline_flags[original_raw]))
        table.SetColumnHidden(original_raw, baseline_flags[original_raw])
        restored = capture("RESTORED-ORIGINAL", (original_raw, baseline_flags[original_raw]))
        _prove_native(restored, counts, part_numbers, quantities=True)
        _prove_unchanged(restored, baseline, exact=True)

        pending.append(candidate_raw)  # BEFORE the only candidate void setter.
        try:
            table.SetColumnHidden(candidate_raw, True)
        except BaseException as error:
            try:
                capture("AFTER-CANDIDATE-SETTER-ERROR", (candidate_raw, True))
            except Exception as evidence_error:
                error.add_note(f"immediate evidence failed: {evidence_error}")
            raise
        candidate = capture("AFTER-CANDIDATE", (candidate_raw, True))
        _prove_native(candidate, counts, part_numbers, quantities=True)
        _prove_unchanged(candidate, baseline, exact=False)
        _prove_candidate(candidate, baseline, p)
        raise RuntimeError("PD visibility probe intentional STOP: raw p candidate proved; drawing UNSAVED; not production qualification")
    except BaseException as error:
        primary = error
        raise
    finally:
        # Reverse mutation order, deduplicated. Each setter/evidence/proof runs
        # independently so a failed restore cannot suppress source inspection.
        attempted: set[int] = set()
        for index in reversed(pending):
            if index in attempted:
                continue
            attempted.add(index)
            cleanup_setters.append((index, baseline_flags[index]))
            try:
                table.SetColumnHidden(index, baseline_flags[index])
            except BaseException as error:
                cleanup_errors.append(f"restore raw {index}: {type(error).__name__}: {str(error)[:768]}")
        try:
            final = capture("FINAL-RESTORED", None)
        except BaseException as error:
            cleanup_errors.append(f"final evidence: {type(error).__name__}: {str(error)[:768]}")
        else:
            if baseline is not None:
                try:
                    _prove_native(final, counts, part_numbers, quantities=True)
                except BaseException as error:
                    cleanup_errors.append(f"native/source proof: {type(error).__name__}: {str(error)[:768]}")
                for key in ("root_path", "reference_configuration", "sources", "columns", "native", "render"):
                    try:
                        _require(final[key] == baseline[key], f"final {key} differs from exact baseline")
                    except BaseException as error:
                        cleanup_errors.append(f"{key}: {type(error).__name__}: {str(error)[:768]}")
        for failure in cleanup_errors:
            if primary is not None:
                primary.add_note("PD visibility cleanup failure: " + failure)
        if cleanup_errors and primary is None:
            raise RuntimeError("PD visibility cleanup failed: " + "; ".join(cleanup_errors))
