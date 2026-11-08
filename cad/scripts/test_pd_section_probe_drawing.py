"""Offline safety checks for the disposable cached PD section diagnostic."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import probe_pd_section_visibility as probe


def test_journal_flushes_both_copies_before_native_call(tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(probe._telemetry, "info", messages.append)
    paths = (tmp_path / "canonical/calls.jsonl", tmp_path / "failures/calls.jsonl")
    journal = probe.Journal(paths)

    def fail_after_observing_disk():
        for path in paths:
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            assert rows[-1]["phase"] == "before"
            assert rows[-1]["member"] == "fresh.GetChildren"
        assert messages == ["section probe native 1: fresh.GetChildren"]
        raise RuntimeError("native failure")

    try:
        with pytest.raises(RuntimeError, match="native failure"):
            journal.call("fresh.GetChildren", fail_after_observing_disk)
        assert paths[0].read_bytes() == paths[1].read_bytes()
        assert json.loads(paths[1].read_text().splitlines()[-1])["phase"] == "error"
    finally:
        journal.close()


def owner(name):
    return SimpleNamespace(Name2=name, GetPathName=lambda: "C:/fixture/part.SLDPRT", ReferencedConfiguration="InnerLink")


def section(owners):
    components = [SimpleNamespace(Name="duplicate<1>", Visible=True, Component=value) for value in owners]
    return SimpleNamespace(
        Type=2, GetName2=lambda: "Section A-A", ReferencedConfiguration="Default",
        GetUseParentDisplayMode=lambda: False, GetDisplayMode2=lambda: 1,
        GetFacettedHlrDisplay=lambda: False, GetDisplayEdgesInShadedMode=lambda: False,
        GetCThreadQuality=lambda: 0,
        RootDrawingComponent2=lambda unused: SimpleNamespace(GetChildren=components),
        GetHiddenComponents=lambda: (owners[0],),
    )


def test_observation_keeps_duplicate_names_and_owner_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    journal = probe.Journal((tmp_path / "calls.jsonl",))
    try:
        state, components, owners = probe.observe_section(journal, section([owner("first"), None]), "after-fresh")
        assert [row["drawing_name"] for row in state["rows"]] == ["duplicate<1>"] * 2
        assert state["rows"][0]["owner"]["name"] == "first"
        assert set(state["rows"][1]["owner"]["errors"]) == {"name", "path", "configuration"}
        assert len(components) == len(owners) == 2
        assert state["hidden_returned_none"] is False
        assert len(state["hidden"]) == 1
    finally:
        journal.close()


def test_duplicate_comparison_is_linear_and_fresh_only(tmp_path, monkeypatch):
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    fresh = [object() for _ in range(4)]
    pairs = []
    app = SimpleNamespace(IsSame=lambda left, right: pairs.append((left, right)) or 0)
    state = {"rows": [{"index": index, "drawing_name": "duplicate"} for index in range(4)]}
    journal = probe.Journal((tmp_path / "calls.jsonl",))
    try:
        result = probe.duplicate_owner_identity(app, journal, state, fresh)
        assert pairs == [(fresh[0], fresh[index]) for index in (1, 2, 3)]
        assert len(result[0]["pairs"]) == 3
    finally:
        journal.close()


@pytest.mark.parametrize("scenario", ["matching", "mismatched-model", "mismatched-source", "helper-failure"])
def test_build_pins_source_and_models_and_exports_refusal(tmp_path, monkeypatch, scenario):
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    out = tmp_path / "out"
    directory = out / "reports/section-visibility-probe"
    monkeypatch.setattr(probe, "OUT", out)
    monkeypatch.setattr(probe, "DIRECTORY", directory)
    monkeypatch.setattr(probe, "REPORT", directory / "report.json")
    monkeypatch.setattr(probe, "JOURNAL", directory / "calls.jsonl")
    monkeypatch.setattr(probe, "DRAWING", out / probe.INPUT_NAMES[0])
    monkeypatch.setattr(probe._seat_forensics, "OUT_FAILURES", out / "failures")
    hashes = {probe.INPUT_NAMES[0]: "new final drawing bytes", **probe.MODEL_HASHES}
    sources = dict(probe.SOURCE_HASHES)
    if scenario == "mismatched-model":
        hashes["sldasm/pd-paper-drive.SLDASM"] = "wrong model"
    if scenario == "mismatched-source":
        sources["_drawing_balloons.py"] = "wrong helper"

    def digest(path):
        path = Path(path)
        return sources[path.name] if path.name in sources else hashes[path.relative_to(out).as_posix()]

    monkeypatch.setattr(probe, "digest", digest)
    calls = []

    def qualify(adapter, journal, report, persist):
        calls.append("qualify")
        report["phases"] = [{"phase": "show", "witness": "persisted before refusal"}]
        persist()
        if scenario == "helper-failure":
            raise RuntimeError("helper refused")
        report["status"] = "passed"
        persist()

    monkeypatch.setattr(probe, "qualify", qualify)
    app = SimpleNamespace(
        OpenDoc6=lambda *args: (SimpleNamespace(GetTitle=lambda: "drawing.SLDDRW"), 0, 0),
        CloseDoc=lambda title: calls.append("close without save"),
    )
    if scenario == "matching":
        asyncio.run(probe.build(SimpleNamespace(swApp=app)))
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(probe.build(SimpleNamespace(swApp=app)))
    canonical = json.loads(probe.REPORT.read_text())
    failure = json.loads((out / "failures/section-visibility-probe/report.json").read_text())
    assert canonical == failure
    assert canonical["input_sha256_after"] == hashes
    assert canonical["status"] == ("passed" if scenario == "matching" else "failed")
    assert calls == ([] if scenario.startswith("mismatched") else ["qualify", "close without save"])
    if scenario == "helper-failure":
        assert canonical["phases"][0]["witness"] == "persisted before refusal"


@pytest.mark.parametrize("fault", ["none", "ineffective-show", "bad-return", "helper-error", "selection-left"])
def test_final_control_uses_returned_view_and_independent_raw_sets(tmp_path, monkeypatch, fault):
    import copy
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)

    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    monkeypatch.setattr(probe._telemetry, "event", lambda name, **fields: None)
    monkeypatch.setattr(probe, "digest", lambda path: probe.MODEL_HASHES["sldprt/sh-vn-chain-link.SLDPRT"])
    names = [*sorted(probe.recipe.PIVOT_VIEW_INSTANCES), probe.TARGET_NAME, *[f"other-{i}" for i in range(141)]]
    rows = [
        {"index": index, "drawing_name": "section/" + name, "own_visible": True,
         "owner": {"name": name, "path": f"C:/fixture/{name}.SLDPRT",
                   "configuration": "InnerLink" if name == probe.TARGET_NAME else "Default"}}
        for index, name in enumerate(names)
    ]
    hidden = set(names) - probe.recipe.PIVOT_VIEW_INSTANCES
    current = [object()]
    model = SimpleNamespace(
        GetPathName=lambda: "C:/fixture/drawing.SLDDRW",
        SelectionManager=SimpleNamespace(GetSelectedObjectCount2=lambda mark: int(fault == "selection-left")),
    )
    adapter = SimpleNamespace(swApp=object(), currentModel=None)
    identity = {"sheet": "Sheet1", "view": "Section A-A"}
    monkeypatch.setattr(probe, "fresh_section", lambda *args, **kwargs: (model, current[0], identity, "Sheet1"))

    def observe(journal, view, phase):
        assert view is current[0], "caller used an unusable helper return"
        owners = [
            {**row["owner"], "name": "pd-paper-drive-1/" + row["owner"]["name"]}
            for row in rows if row["owner"]["name"] in hidden
        ]
        return {"rows": copy.deepcopy(rows), "hidden": owners, "state": {"configuration": "Default"}}, [], []

    monkeypatch.setattr(probe, "observe_section", observe)
    helper_calls = []

    def helper(adapter, view, shown, *, mode, label):
        assert view is current[0] and mode == "show"
        phase = label.rsplit(" ", 1)[-1]
        helper_calls.append(phase)
        if fault != "ineffective-show":
            hidden.clear()
            hidden.update(set(names) - shown)
        if phase != "noop":
            current[0] = object()
        if fault == "helper-error":
            raise RuntimeError("helper refused after command")
        adapter.currentModel = model
        show, hide = {"show": (1, 0), "restore": (0, 1), "noop": (0, 0)}[phase]
        probe.visibility._telemetry.event(
            "drawing.visibility.timings", outcome="verified", show=show, hide=hide,
            changed=show + hide, selection_seconds=show + hide, apply_seconds=show + hide,
            rebuild_seconds=show + hide,
        )
        return object() if fault == "bad-return" else current[0]

    monkeypatch.setattr(probe.visibility, "set_drawing_view_instance_visibility", helper)
    report = {}
    checkpoints = []
    journal = probe.Journal((tmp_path / "calls.jsonl",))
    try:
        if fault == "none":
            probe.qualify(adapter, journal, report, lambda: checkpoints.append(copy.deepcopy(report)))
            assert report["status"] == "passed"
            assert helper_calls == ["show", "restore", "noop"]
            assert [len(phase["after"]["hidden"]) for phase in report["phases"]] == [141, 142, 142]
        else:
            with pytest.raises((RuntimeError, AssertionError)):
                probe.qualify(adapter, journal, report, lambda: checkpoints.append(copy.deepcopy(report)))
            assert helper_calls == ["show"]
            if fault == "helper-error":
                assert len(report["phases"][0]["after_failure"]["hidden"]) == 141
                assert checkpoints[-1]["phases"][0]["helper_error"]
    finally:
        journal.close()


def test_cached_probe_has_exact_native_prerequisites_and_report_targets():
    import dodo

    task = dodo._verify_task("pd_section_visibility_probe")
    assert task["task_dep"] == ["drawing:pd_paper_drive_assembly", "assembly:pd_paper_drive"]
    assert task["targets"] == dodo._canonical_targets("verify:pd_section_visibility_probe")
    assert {Path(path).name for path in task["targets"]} == {"report.json", "calls.jsonl"}
    assert any(Path(path).name == "pd-paper-drive-assembly.SLDDRW" for path in task["file_dep"])
    assert "pd_section_visibility_probe" in dodo._VERIFY_NAMES
