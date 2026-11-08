"""Experiment-only, admitted cached-drawing probe; never runs the PD builder.

Show the previously failing chain-link occurrence once, then abandon every
pre-change view/component proxy and observe only a freshly resolved section.
Every native call is journaled and flushed before execution, including errors.
A successful diagnostic means observations completed, not that production's
old-name readback contract passed.
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

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "cad/out"
DIRECTORY = OUT / "reports/section-visibility-probe"
REPORT = DIRECTORY / "report.json"
JOURNAL = DIRECTORY / "calls.jsonl"
INPUT_HASHES = {
    "slddrw/pd-paper-drive-assembly.SLDDRW": "81551b5bf360b87fe858fbad96cbcc2a648afc90bd6dd9fc2b2ff425cf9a9b80",
    "sldasm/pd-paper-drive.SLDASM": "bd55e967cd2957e028330c157cebfb37aa6d014e1d3f4420fd646ec8c1fae128",
    "sldprt/sh-vn-chain-link.SLDPRT": "14fca2a7c0d4ce1a632efe4d5649c090c2299a41be123d24a4930bb87b8609c7",
}
DRAWING = OUT / "slddrw/pd-paper-drive-assembly.SLDDRW"
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


def show_once(app, journal, report, persist):
    model, view, identity, active_sheet = fresh_section(app, journal)
    before, components, owners = observe_section(journal, view, "before")
    report.update(view_identity=identity, active_sheet_before=active_sheet, before=before)
    persist()
    matches = [row["index"] for row in before["rows"] if row.get("owner", {}).get("name") == TARGET_NAME and row["owner"].get("configuration") == TARGET_CONFIGURATION]
    hidden_matches = [row for row in before["hidden"] if row.get("name") == HIDDEN_TARGET_NAME and row.get("configuration") == TARGET_CONFIGURATION]
    if len(matches) != 1 or len(hidden_matches) != 1 or len(before["rows"]) != 147 or len(before["hidden"]) != 142:
        raise RuntimeError("cached section differs from the previously failing exact occurrence/census")
    index = matches[0]
    if digest(before["rows"][index]["owner"]["path"]) != INPUT_HASHES["sldprt/sh-vn-chain-link.SLDPRT"] or digest(hidden_matches[0]["path"]) != INPUT_HASHES["sldprt/sh-vn-chain-link.SLDPRT"]:
        raise RuntimeError("target owner points at different native bytes")
    journal.call("before.ClearSelection2", lambda: model.ClearSelection2(True))
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    data = journal.call("SelectionManager.CreateSelectData", lambda: manager.CreateSelectData(), lambda value: value is not None)
    journal.call("SelectData.View=set exact section", lambda: setattr(data, "View", view), lambda value: None)
    if not journal.call("target DrawingComponent.Select", lambda: components[index].Select(True, data)):
        raise RuntimeError("hidden target selection failed")
    if journal.call("GetSelectedObjectCount2", lambda: manager.GetSelectedObjectCount2(-1)) != 1 or journal.call("GetSelectedObjectType3", lambda: manager.GetSelectedObjectType3(1, -1)) != 20:
        raise RuntimeError("selection count/type mismatch")
    selected_view = journal.call("GetSelectedObjectsDrawingView2", lambda: manager.GetSelectedObjectsDrawingView2(1, -1), lambda value: value is not None)
    selected = journal.call("GetSelectedObjectsComponent4", lambda: _early_bound(manager.GetSelectedObjectsComponent4(1, -1), "IDrawingComponent"), lambda value: value is not None)
    selected_owner = journal.call("selected DrawingComponent.Component", lambda: _early_bound(selected.Component, "IComponent2"), lambda value: value is not None)
    for name, left, right in (("view", selected_view, view), ("owner", selected_owner, owners[index])):
        same = journal.call(f"before IsSame selected {name}", lambda: app.IsSame(left, right))
        if type(same) is not int or same != 1:
            raise RuntimeError(f"selection {name} identity unproved: {same!r}")
    journal.call("IModelDoc2.ShowComponent2", lambda: model.ShowComponent2(), lambda value: None)
    journal.call("after-command.ClearSelection2", lambda: model.ClearSelection2(True))
    if not journal.call("IModelDoc2.EditRebuild3", lambda: model.EditRebuild3()):
        raise RuntimeError("final rebuild failed")
    report["command_completed"] = True
    persist()
    # All view/component/selection proxies die with this frame. None are returned.
    return identity


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
    report = {"status": "running", "input_commit": "dc892b2dd10026db0a1918080b5cdf7b16563323", "drawing_cache_key": "f2bdecebc7e542ea47d7212951c67e9950bb2168a7409371eee02affa31bf8de", "input_sha256": {name: digest(OUT / name) for name in INPUT_HASHES}}
    journal = Journal((JOURNAL, failure_directory / "calls.jsonl"))
    persist = lambda: checkpoint(report, failure_directory)
    persist()
    title = None
    try:
        if report["input_sha256"] != INPUT_HASHES:
            raise RuntimeError("cached native inputs differ from the pinned dc892 artifacts")
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
        identity = show_once(adapter.swApp, journal, report, persist)
        fresh_model, fresh_view, _, active_sheet = fresh_section(adapter.swApp, journal, expected=identity)
        report["active_sheet_after"] = active_sheet
        after, fresh_components, fresh_owners = observe_section(journal, fresh_view, "after-fresh")
        report["after"] = after
        persist()
        report["duplicate_owner_identity"] = duplicate_owner_identity(
            adapter.swApp, journal, after, fresh_owners
        )
        persist()
        report["status"] = "observation_complete"
        report["qualification"] = "diagnostic only; raw names/owners require interpretation"
        del fresh_components, fresh_owners, fresh_view, fresh_model
        persist()
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        persist()
        raise
    finally:
        try:
            if title is not None:
                journal.call("CloseDoc without saving", lambda: adapter.swApp.CloseDoc(title), lambda value: None)
            report["input_sha256_after"] = {name: digest(OUT / name) for name in INPUT_HASHES}
            persist()
            if report["input_sha256_after"] != INPUT_HASHES:
                raise RuntimeError("read-only probe changed native input files")
        finally:
            journal.close()
    return {"report": str(REPORT), "journal": str(JOURNAL)}


if __name__ == "__main__":
    sys.exit(run_build(build))
