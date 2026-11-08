"""Experiment-only qualification of the final PD visibility helper.

Consume the separately built drawing, show the same hidden chain-link occurrence,
restore it, then prove a no-op. Never run a builder from inside this native leaf.
Raw observation is independent of production inventory/validation helpers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _com import _early_bound
from _session import run_build
import _seat_forensics
import _telemetry
import _drawing_balloons as visibility
import draw_pd_paper_drive_assembly as recipe

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "cad/out"
DIRECTORY = OUT / "reports/section-visibility-probe"
REPORT = DIRECTORY / "report.json"
JOURNAL = DIRECTORY / "calls.jsonl"
PRODUCTION_COMMIT = "3b8d009b6ee853afb14808025a7228037f6e120a"
SOURCE_HASHES = {
    "_drawing_balloons.py": "7db3e6bfb9293abdf99f720b3a2331ff36b82cfa6e87a2ad757d3608dbb50146",
    "draw_pd_paper_drive_assembly.py": "d4759508bc652979508e2e245be70cb64b45e6d5b982632c9a9cb3f06425cec5",
}
MODEL_HASHES = {
    "sldasm/pd-paper-drive.SLDASM": "bd55e967cd2957e028330c157cebfb37aa6d014e1d3f4420fd646ec8c1fae128",
    "sldprt/sh-vn-chain-link.SLDPRT": "14fca2a7c0d4ce1a632efe4d5649c090c2299a41be123d24a4930bb87b8609c7",
}
DRAWING = OUT / "slddrw/pd-paper-drive-assembly.SLDDRW"
INPUT_NAMES = (DRAWING.relative_to(OUT).as_posix(), *MODEL_HASHES)
TARGET_NAME = "sh-vn-chain-link-11"
HIDDEN_TARGET_NAME = "pd-paper-drive-1/sh-vn-chain-link-11"
TARGET_CONFIGURATION = "InnerLink"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Journal:
    def __init__(self, paths):
        self.streams = []
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.streams.append(path.open("w", encoding="utf-8"))
        self.sequence = 0

    def record(self, phase, member, **fields):
        value = {"sequence": self.sequence, "phase": phase, "member": member,
                 "monotonic": time.perf_counter(), **fields}
        encoded = json.dumps(value, ensure_ascii=False) + "\n"
        for stream in self.streams:
            stream.write(encoded)
            stream.flush()
        return value

    def call(self, member, action, encode=lambda value: value):
        self.sequence += 1
        self.record("before", member)
        _telemetry.info(f"section probe native {self.sequence}: {member}")
        try:
            result = action()
            self.record("after", member, value=encode(result))
            return result
        except Exception as error:
            self.record("error", member, error=repr(error))
            raise

    def close(self):
        for stream in self.streams:
            stream.close()


def checkpoint(report, failure_directory):
    text = json.dumps(report, indent=2)
    REPORT.write_text(text, encoding="utf-8")
    (failure_directory / "report.json").write_text(text, encoding="utf-8")


def field(journal, row, key, member, action):
    try:
        row[key] = journal.call(member, action)
    except Exception as error:
        row.setdefault("errors", {})[key] = repr(error)


def native_owner(journal, native, prefix):
    result = {}
    field(journal, result, "name", f"{prefix}.Name2", lambda: native.Name2)
    field(journal, result, "path", f"{prefix}.GetPathName", lambda: native.GetPathName())
    field(journal, result, "configuration", f"{prefix}.ReferencedConfiguration", lambda: native.ReferencedConfiguration)
    return result


def fresh_section(app, journal, expected=None):
    model = journal.call("ISldWorks.GetOpenDocumentByName", lambda: _early_bound(app.GetOpenDocumentByName(str(DRAWING)), "IModelDoc2"), lambda value: value is not None)
    if model is None or journal.call("fresh document.GetType", lambda: model.GetType()) != 3:
        raise RuntimeError("fresh drawing document unavailable")
    path = journal.call("fresh document.GetPathName", lambda: model.GetPathName())
    if Path(path).resolve() != DRAWING.resolve():
        raise RuntimeError(f"fresh document path changed: {path}")
    draw = _early_bound(model, "IDrawingDoc")
    sheet = journal.call("IDrawingDoc.GetCurrentSheet", lambda: _early_bound(draw.GetCurrentSheet(), "ISheet"), lambda value: value is not None)
    active_sheet = journal.call("active ISheet.GetName", lambda: sheet.GetName())
    sheets = journal.call("fresh IDrawingDoc.GetViews", lambda: draw.GetViews(), lambda value: len(value))
    candidates = []
    for sheet_index, raw_views in enumerate(sheets):
        sheet_view = _early_bound(raw_views[0], "IView")
        sheet_name = journal.call(f"sheets[{sheet_index}].GetName2", lambda: sheet_view.GetName2())
        for view_index, raw in enumerate(raw_views[1:]):
            view = _early_bound(raw, "IView")
            kind = journal.call(f"sheets[{sheet_index}].views[{view_index}].Type", lambda: view.Type)
            if kind != 2:
                continue
            name = journal.call(f"sheets[{sheet_index}].views[{view_index}].GetName2", lambda: view.GetName2())
            identity = {"sheet": sheet_name, "view": name}
            if expected is None or identity == expected:
                candidates.append((identity, view))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one exact section, found {len(candidates)}")
    identity, view = candidates[0]
    return model, view, identity, active_sheet


def observe_section(journal, view, phase):
    state = {}
    for name, action in (
        ("configuration", lambda: view.ReferencedConfiguration),
        ("use_parent", lambda: view.GetUseParentDisplayMode()),
        ("display_mode", lambda: view.GetDisplayMode2()),
        ("faceted_hlr", lambda: view.GetFacettedHlrDisplay()),
        ("edges_shaded", lambda: view.GetDisplayEdgesInShadedMode()),
        ("thread_quality", lambda: view.GetCThreadQuality()),
    ):
        field(journal, state, name, f"{phase}.view.{name}", action)
    root = journal.call(f"{phase}.RootDrawingComponent2(False)", lambda: _early_bound(view.RootDrawingComponent2(False), "IDrawingComponent"), lambda value: value is not None)
    if root is None:
        raise RuntimeError("section root unavailable")

    def children():
        member = root.GetChildren
        return member() if callable(member) else member

    raw_children = journal.call(f"{phase}.root.GetChildren", children, lambda value: None if value is None else len(value))
    if not isinstance(raw_children, (tuple, list)):
        raise RuntimeError("section direct-child array unreadable")
    rows = []
    components = []
    owners = []
    for index, raw in enumerate(raw_children):
        prefix = f"{phase}.rows[{index}]"
        component = _early_bound(raw, "IDrawingComponent")
        row = {"index": index}
        rows.append(row)
        components.append(component)
        field(journal, row, "drawing_name", prefix + ".Name", lambda: component.Name)
        field(journal, row, "own_visible", prefix + ".Visible", lambda: component.Visible)
        try:
            native = journal.call(prefix + ".Component", lambda: _early_bound(component.Component, "IComponent2"), lambda value: value is not None)
            row["owner"] = native_owner(journal, native, prefix + ".owner")
        except Exception as error:
            native = None
            row["owner_error"] = repr(error)
        owners.append(native)
    hidden = journal.call(f"{phase}.GetHiddenComponents", lambda: view.GetHiddenComponents(), lambda value: {"returned_none": value is None, "count": 0 if value is None else len(value)})
    if hidden is not None and not isinstance(hidden, (tuple, list)):
        raise RuntimeError("hidden-owner array unreadable")
    hidden_rows = [native_owner(journal, _early_bound(raw, "IComponent2"), f"{phase}.hidden[{index}]") for index, raw in enumerate(() if hidden is None else hidden)]
    return {"state": state, "rows": rows, "hidden_returned_none": hidden is None, "hidden": hidden_rows}, components, owners


def row_inventory(snapshot):
    result = {}
    owners = set()
    for row in snapshot["rows"]:
        if row.get("errors") or row.get("owner_error") or row["owner"].get("errors"):
            raise RuntimeError("raw section observation contains unreadable fields")
        key = tuple(row["owner"][name] for name in ("name", "path", "configuration"))
        name = row["drawing_name"]
        if name in result or key in owners or type(row["own_visible"]) is not bool:
            raise RuntimeError("raw section observation has ambiguous occurrences")
        owners.add(key)
        result[name] = (row["own_visible"], key)
    return result


def hidden_inventory(snapshot):
    rows = snapshot["hidden"]
    if any(row.get("errors") for row in rows):
        raise RuntimeError("raw hidden owner observation contains unreadable fields")
    values = [tuple(row[name] for name in ("name", "path", "configuration")) for row in rows]
    if len(set(values)) != len(values):
        raise RuntimeError("raw hidden owner observation contains duplicates")
    return set(values)


def qualify(adapter, journal, report, persist):
    app = adapter.swApp
    model, view, identity, active_sheet = fresh_section(app, journal)
    adapter.currentModel = model
    before, components, owners = observe_section(journal, view, "before")
    del components, owners
    report.update(view_identity=identity, active_sheet_before=active_sheet, before=before, phases=[])
    persist()
    rows_before = row_inventory(before)
    hidden_before = hidden_inventory(before)
    target = [row for row in before["rows"] if row["owner"]["name"] == TARGET_NAME and row["owner"]["configuration"] == TARGET_CONFIGURATION]
    target_hidden = [owner for owner in hidden_before if owner[0] == HIDDEN_TARGET_NAME and owner[2] == TARGET_CONFIGURATION]
    if len(target) != 1 or len(target_hidden) != 1 or len(rows_before) != 147 or len(hidden_before) != 142:
        raise RuntimeError("section differs from the previously failing exact occurrence/census")
    for path in (target[0]["owner"]["path"], target_hidden[0][1]):
        if digest(path) != MODEL_HASHES["sldprt/sh-vn-chain-link.SLDPRT"]:
            raise RuntimeError("target owner points at different native bytes")
    expected_hidden = {
        ("pd-paper-drive-1/" + owner[0], owner[1], owner[2])
        for _, owner in rows_before.values() if owner[0] not in recipe.PIVOT_VIEW_INSTANCES
    }
    if expected_hidden != hidden_before:
        raise RuntimeError("initial raw inventory differs from the exact authored five-instance set")

    for phase, names, expected, counts in (
        ("show", recipe.PIVOT_VIEW_INSTANCES | {TARGET_NAME}, hidden_before - set(target_hidden), (1, 0)),
        ("restore", recipe.PIVOT_VIEW_INSTANCES, hidden_before, (0, 1)),
        ("noop", recipe.PIVOT_VIEW_INSTANCES, hidden_before, (0, 0)),
    ):
        record = {"phase": phase, "expected_hidden": sorted(expected), "events": []}
        report["phases"].append(record)
        persist()
        original_event = visibility._telemetry.event

        def capture_event(name, **fields):
            if name.startswith("drawing.visibility."):
                record["events"].append({"name": name, **fields})
            original_event(name, **fields)

        visibility._telemetry.event = capture_event
        try:
            view = journal.call(
                f"{phase}: final visibility helper",
                lambda: visibility.set_drawing_view_instance_visibility(
                    adapter, view, frozenset(names), mode="show", label=f"section control {phase}"
                ),
                lambda value: value is not None,
            )
        except Exception as error:
            record["helper_error"] = repr(error)
            persist()
            try:
                _, observed_view, _, _ = fresh_section(app, journal, expected=identity)
                record["after_failure"], _, _ = observe_section(journal, observed_view, phase + ".failure-fresh")
                persist()
            except Exception as capture_error:
                record["capture_error"] = repr(capture_error)
                error.add_note(f"fresh failure observation also failed: {capture_error!r}")
                persist()
            raise
        finally:
            visibility._telemetry.event = original_event
        # Consume the RETURNED proxy directly; another lookup must not mask a bad return.
        after, components, owners = observe_section(journal, view, phase + ".returned")
        record["after"] = after
        record["adapter_document_path"] = journal.call(
            phase + ".adapter.currentModel.GetPathName", lambda: adapter.currentModel.GetPathName()
        )
        manager = journal.call(
            phase + ".adapter.currentModel.SelectionManager",
            lambda: _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr"),
            lambda value: value is not None,
        )
        record["selected_count_after"] = journal.call(
            phase + ".GetSelectedObjectCount2", lambda: manager.GetSelectedObjectCount2(-1)
        )
        persist()
        if record["selected_count_after"] != 0:
            raise RuntimeError(f"{phase}: selection remained after helper rebuild/readback")
        record["duplicate_owner_identity"] = duplicate_owner_identity(app, journal, after, owners)
        del components, owners
        persist()
        if row_inventory(after) != rows_before or hidden_inventory(after) != expected or after["state"] != before["state"]:
            raise RuntimeError(f"{phase}: exact raw section identity/visibility/state mismatch")
        timings = [event for event in record["events"] if event["name"] == "drawing.visibility.timings"]
        if len(timings) != 1 or timings[0]["outcome"] != "verified" or (timings[0]["show"], timings[0]["hide"]) != counts:
            raise RuntimeError(f"{phase}: helper timing/count outcome differs from the positive control")
        if phase == "noop" and any(timings[0][key] != 0 for key in ("changed", "selection_seconds", "apply_seconds", "rebuild_seconds")):
            raise RuntimeError("no-op selected, mutated or rebuilt the section")
        record["status"] = "passed"
        persist()
    report["status"] = "passed"
    report["qualification"] = "final helper show, restore and no-op; exact raw section readback"
    persist()


def duplicate_owner_identity(app, journal, snapshot, owners):
    """Compare only fresh owners sharing a drawing-wrapper name, linearly."""
    groups = {}
    for row in snapshot["rows"]:
        name = row.get("drawing_name")
        if isinstance(name, str):
            groups.setdefault(name, []).append(row["index"])
    result = []
    for name, indices in groups.items():
        if len(indices) < 2:
            continue
        group = {"drawing_name": name, "indices": indices, "pairs": []}
        result.append(group)
        first = indices[0]
        for index in indices[1:]:
            if owners[first] is None or owners[index] is None:
                group["pairs"].append({"first": first, "other": index, "error": "owner unavailable"})
                continue
            same = journal.call(
                f"fresh duplicate owners[{first},{index}].IsSame",
                lambda first=first, index=index: app.IsSame(owners[first], owners[index]),
            )
            group["pairs"].append({"first": first, "other": index, "native_is_same": same})
    return result


async def build(adapter):
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    failure_directory = _seat_forensics.OUT_FAILURES / "section-visibility-probe"
    failure_directory.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "running", "production_commit": PRODUCTION_COMMIT,
        "source_sha256": {name: digest(ROOT / "cad/scripts" / name) for name in SOURCE_HASHES},
        "input_sha256": {name: digest(OUT / name) for name in INPUT_NAMES},
    }
    journal = Journal((JOURNAL, failure_directory / "calls.jsonl"))
    persist = lambda: checkpoint(report, failure_directory)
    persist()
    title = None
    try:
        if report["source_sha256"] != SOURCE_HASHES:
            raise RuntimeError("qualification source differs from the exact final production code")
        if {name: report["input_sha256"][name] for name in MODEL_HASHES} != MODEL_HASHES:
            raise RuntimeError("native model inputs differ from the pinned dc892 artifacts")
        opened = journal.call("OpenDoc6 silent+read-only drawing", lambda: adapter.swApp.OpenDoc6(str(DRAWING), 3, 1 | 2, "", 0, 0), lambda value: {"tuple_length": len(value)} if isinstance(value, tuple) else {"unexpected_type": type(value).__name__})
        if not isinstance(opened, tuple) or len(opened) != 3:
            raise RuntimeError("unexpected OpenDoc6 binding shape")
        document, errors, warnings = opened
        report["open_errors"] = errors
        report["open_warnings"] = warnings
        if document is None or errors or warnings:
            raise RuntimeError(f"cached drawing open refused: errors={errors}, warnings={warnings}")
        title = journal.call("opened drawing.GetTitle", lambda document=document: _early_bound(document, "IModelDoc2").GetTitle())
        del document, opened
        qualify(adapter, journal, report, persist)
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        persist()
        raise
    finally:
        try:
            if title is not None:
                journal.call("CloseDoc without saving", lambda: adapter.swApp.CloseDoc(title), lambda value: None)
            report["input_sha256_after"] = {name: digest(OUT / name) for name in INPUT_NAMES}
            persist()
            if report["input_sha256_after"] != report["input_sha256"]:
                report["status"] = "failed"
                report["error"] = "read-only probe changed native input files"
                persist()
                raise RuntimeError(report["error"])
        finally:
            journal.close()
    return {"report": str(REPORT), "journal": str(JOURNAL)}


if __name__ == "__main__":
    sys.exit(run_build(build))
