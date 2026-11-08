"""Matched, unsaved three-case discriminator on the exact final PD drawing.

No production source changes. Each case reopens identical native bytes and closes
without saving. Cases vary raw-frame retention or the saved-document lookup only.
"""
from __future__ import annotations

import gc
import sys

if __package__:
    from . import probe_pd_section_visibility as probe
else:
    import probe_pd_section_visibility as probe

visibility = probe.visibility
FINAL_DRAWING_SHA = "3478420c8e40265ba4691cbcefe8d352f7f7ddcb8441af92325ecf682e4143e8"
SENTINEL = "pd-vn-guide-lock-screw-5"
CASES = ("raw_frame_ended", "raw_retained", "production_direct_lookup")


def direct_saved_resolver(app, identity, *, label):
    """The sole production override: document acquisition, not view enumeration."""
    if not identity.document_path:
        raise RuntimeError("this discriminator only qualifies a saved drawing")
    document = probe._early_bound(app.GetOpenDocumentByName(identity.document_path), "IModelDoc2")
    if document is None or int(document.GetType()) != 3 or (document.GetPathName(), document.GetTitle()) != (identity.document_path, identity.document_title):
        raise RuntimeError(f"{label}: direct saved drawing identity mismatch")
    views = [candidate for sheet, candidate in visibility._section_views(document, label=label)
             if sheet == identity.sheet_name and candidate.GetName2() == identity.view_name]
    if len(views) != 1:
        raise RuntimeError(f"{label}: expected one exact current section; found {len(views)}")
    return document, views[0]


def capture_before(app, journal, record, persist):
    model, view, identity, active = probe.fresh_section(app, journal)
    before, components, owners = probe.observe_section(journal, view, record["case"] + ".before")
    record.update(before=before, identity=identity, active_sheet=active)
    persist()
    matches = [row["index"] for row in before["rows"] if row.get("owner", {}).get("name") == probe.TARGET_NAME and row["owner"].get("configuration") == probe.TARGET_CONFIGURATION]
    hidden = probe.hidden_inventory(before)
    target_hidden = [owner for owner in hidden if owner[0] == probe.HIDDEN_TARGET_NAME and owner[2] == probe.TARGET_CONFIGURATION]
    if len(matches) != 1 or len(before["rows"]) != 147 or len(hidden) != 142 or len(target_hidden) != 1:
        raise RuntimeError("initial exact final-drawing occurrence/census differs")
    record["expected_hidden_after"] = sorted(hidden - set(target_hidden))
    persist()
    return model, view, components, owners, matches[0]


def raw_show(app, journal, record, persist):
    model, view, components, owners, index = capture_before(app, journal, record, persist)
    journal.call("raw.before.ClearSelection2", lambda: model.ClearSelection2(True))
    manager = probe._early_bound(model.SelectionManager, "ISelectionMgr")
    data = journal.call("raw.CreateSelectData", lambda: manager.CreateSelectData(), lambda value: value is not None)
    journal.call("raw.SelectData.View", lambda: setattr(data, "View", view), lambda value: None)
    if not journal.call("raw.target.Select", lambda: components[index].Select(True, data)):
        raise RuntimeError("hidden target selection failed")
    if journal.call("raw.selected_count", lambda: manager.GetSelectedObjectCount2(-1)) != 1 or journal.call("raw.selected_type", lambda: manager.GetSelectedObjectType3(1, -1)) != 20:
        raise RuntimeError("selection count/type mismatch")
    selected_view = journal.call("raw.selected_view", lambda: manager.GetSelectedObjectsDrawingView2(1, -1), lambda value: value is not None)
    selected = journal.call("raw.selected_component", lambda: probe._early_bound(manager.GetSelectedObjectsComponent4(1, -1), "IDrawingComponent"), lambda value: value is not None)
    selected_owner = journal.call("raw.selected_owner", lambda: probe._early_bound(selected.Component, "IComponent2"), lambda value: value is not None)
    for name, left, right in (("view", selected_view, view), ("owner", selected_owner, owners[index])):
        same = journal.call("raw.IsSame." + name, lambda: app.IsSame(left, right))
        if type(same) is not int or same != 1:
            raise RuntimeError("selected native identity mismatch")
    journal.call("raw.ShowComponent2", lambda: model.ShowComponent2(), lambda value: None)
    journal.call("raw.after.ClearSelection2", lambda: model.ClearSelection2(True))
    if not journal.call("raw.EditRebuild3", lambda: model.EditRebuild3()):
        raise RuntimeError("rebuild failed")
    record["command_completed"] = True
    persist()
    if record["case"] == "raw_retained":
        return {"model": model, "view": view, "components": components, "owners": owners,
                "manager": manager, "data": data, "selected": selected,
                "selected_view": selected_view, "selected_owner": selected_owner}
    return None


def production_show(adapter, journal, record, persist):
    model, view, components, owners, _ = capture_before(adapter.swApp, journal, record, persist)
    del components, owners
    adapter.currentModel = model
    original = visibility._resolve_section_visibility_view
    visibility._resolve_section_visibility_view = direct_saved_resolver
    try:
        current = journal.call(
            "production_direct_lookup.helper.show",
            lambda: visibility.set_drawing_view_instance_visibility(
                adapter, view, frozenset(probe.recipe.PIVOT_VIEW_INSTANCES | {probe.TARGET_NAME}),
                mode="show", label="lookup discriminator show"),
            lambda value: value is not None,
        )
        record["helper_outcome"] = "returned"
        persist()
        return {"returned_view": current}
    except Exception as error:
        record["helper_outcome"] = "refused"
        record["helper_error"] = repr(error)
        persist()
        # Match the previous negative capture: its exception kept native frames alive.
        return {"exception_with_traceback": error}
    finally:
        visibility._resolve_section_visibility_view = original


def sparse_after(app, journal, record, persist):
    model, view, _, _ = probe.fresh_section(app, journal, expected=record["identity"])
    root = journal.call("after.RootDrawingComponent2(False)", lambda: probe._early_bound(view.RootDrawingComponent2(False), "IDrawingComponent"), lambda value: value is not None)
    def children():
        value = root.GetChildren
        return value() if callable(value) else value
    components = journal.call("after.root.GetChildren", children, lambda value: None if value is None else len(value))
    if not isinstance(components, (list, tuple)):
        raise RuntimeError("post-command child array unreadable; stop discriminator")
    record["after"] = {"count": len(components), "names": [], "witnesses": [], "hidden": []}
    after = record["after"]
    spellings = {probe.TARGET_NAME: "target", "sh-vn-chain-link<11>": "target",
                 SENTINEL: "sentinel", "pd-vn-guide-lock-screw<5>": "sentinel"}
    after["witness_indices"] = {"target": [], "sentinel": []}
    for index, raw in enumerate(components):
        component = probe._early_bound(raw, "IDrawingComponent")
        name = journal.call(f"after.names[{index}]", lambda: component.Name)
        if not isinstance(name, str):
            raise RuntimeError("post-command drawing name unreadable; stop discriminator")
        after["names"].append(name)
        witness = spellings.get(name.rsplit("/", 1)[-1])
        if witness is not None:
            after["witness_indices"][witness].append(index)
            if len(after["witness_indices"][witness]) == 1:
                owner = journal.call(f"after.witness[{index}].Component", lambda: probe._early_bound(component.Component, "IComponent2"), lambda value: value is not None)
                row = {"index": index, "witness": witness, "drawing_name": name,
                       "owner": probe.native_owner(journal, owner, f"after.witness[{index}].owner")}
                row["own_visible"] = journal.call(f"after.witness[{index}].Visible", lambda: component.Visible)
                after["witnesses"].append(row)
        persist()
    hidden = journal.call("after.GetHiddenComponents", lambda: view.GetHiddenComponents(), lambda value: None if value is None else len(value))
    if hidden is not None and not isinstance(hidden, (list, tuple)):
        raise RuntimeError("post-command hidden array unreadable; stop discriminator")
    for index, raw in enumerate(hidden or ()):
        after["hidden"].append(probe.native_owner(journal, probe._early_bound(raw, "IComponent2"), f"after.hidden[{index}]"))
        persist()
    after["hidden_set_matches"] = probe.hidden_inventory(after) == {tuple(value) for value in record["expected_hidden_after"]}
    after["unique_drawing_names"] = len(set(after["names"]))
    if any(row["owner"].get("errors") for row in after["witnesses"]):
        raise RuntimeError("native witness getter failed; stop discriminator")
    record["status"] = "observed"
    persist()
    return model


async def build(adapter):
    probe.DIRECTORY.mkdir(parents=True, exist_ok=True)
    failure_directory = probe._seat_forensics.OUT_FAILURES / "section-visibility-probe"
    failure_directory.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "production_commit": probe.PRODUCTION_COMMIT,
              "fixture_sha256": FINAL_DRAWING_SHA, "case_definitions": list(CASES), "cases": [],
              "source_sha256": {name: probe.digest(probe.ROOT / "cad/scripts" / name) for name in probe.SOURCE_HASHES},
              "input_sha256": {name: probe.digest(probe.OUT / name) for name in probe.INPUT_NAMES}}
    journal = probe.Journal((probe.JOURNAL, failure_directory / "calls.jsonl"))
    persist = lambda: probe.checkpoint(report, failure_directory)
    persist()
    try:
        if report["source_sha256"] != probe.SOURCE_HASHES or report["input_sha256"][probe.INPUT_NAMES[0]] != FINAL_DRAWING_SHA or {name: report["input_sha256"][name] for name in probe.MODEL_HASHES} != probe.MODEL_HASHES:
            raise RuntimeError("exact production source or native fixture mismatch")
        for case in CASES:
            record = {"case": case, "status": "running"}
            report["cases"].append(record)
            persist()
            title = None
            retained = None
            try:
                opened = journal.call(case + ".OpenDoc6", lambda: adapter.swApp.OpenDoc6(str(probe.DRAWING), 3, 1 | 2, "", 0, 0), lambda value: len(value))
                document, errors, warnings = opened
                record.update(open_errors=errors, open_warnings=warnings)
                if document is None or errors or warnings:
                    raise RuntimeError("read-only fixture open refused")
                title = journal.call(case + ".GetTitle", lambda document=document: probe._early_bound(document, "IModelDoc2").GetTitle())
                del document, opened
                retained = production_show(adapter, journal, record, persist) if case == "production_direct_lookup" else raw_show(adapter.swApp, journal, record, persist)
                record["retained_proxy_groups"] = sorted(retained) if retained else []
                persist()
                sparse_after(adapter.swApp, journal, record, persist)
            finally:
                if retained and "exception_with_traceback" in retained:
                    retained["exception_with_traceback"].__traceback__ = None
                retained = None
                adapter.currentModel = None
                gc.collect()
                if title is not None:
                    journal.call(case + ".CloseDoc without saving", lambda: adapter.swApp.CloseDoc(title), lambda value: None)
                record["input_sha256_after"] = {name: probe.digest(probe.OUT / name) for name in probe.INPUT_NAMES}
                persist()
                if record["input_sha256_after"] != report["input_sha256"]:
                    raise RuntimeError("case changed immutable native files")
        report["status"] = "observations_complete"
        report["qualification"] = "differential observations only; no production acceptance from exit status"
        persist()
    except Exception as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        persist()
        raise
    finally:
        journal.close()
    return {"report": str(probe.REPORT), "journal": str(probe.JOURNAL)}


if __name__ == "__main__":
    sys.exit(probe.run_build(build))
