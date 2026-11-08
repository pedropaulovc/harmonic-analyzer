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


@pytest.mark.parametrize("scenario", ["matching", "mismatched"])
def test_build_reacquires_document_after_show_and_exports_duplicates(tmp_path, monkeypatch, scenario):
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    out = tmp_path / "out"
    directory = out / "reports/section-visibility-probe"
    drawing = out / "slddrw/pd-paper-drive-assembly.SLDDRW"
    monkeypatch.setattr(probe, "OUT", out)
    monkeypatch.setattr(probe, "DIRECTORY", directory)
    monkeypatch.setattr(probe, "REPORT", directory / "report.json")
    monkeypatch.setattr(probe, "JOURNAL", directory / "calls.jsonl")
    monkeypatch.setattr(probe, "DRAWING", drawing)
    monkeypatch.setattr(probe._seat_forensics, "OUT_FAILURES", out / "failures")
    observed_hashes = dict(probe.INPUT_HASHES)
    if scenario == "mismatched":
        observed_hashes["slddrw/pd-paper-drive-assembly.SLDDRW"] = "different cached drawing"
    monkeypatch.setattr(probe, "digest", lambda path: observed_hashes[Path(path).relative_to(out).as_posix()])
    fresh_owners = [owner("first"), owner("second")]
    fresh_view = section(fresh_owners)
    identity = {"sheet": "PLATEN AND SUPPORT", "view": "Section A-A"}
    show_completed = False
    calls = []

    class StaleDocument:
        def GetTitle(self):
            return "pd-paper-drive-assembly.SLDDRW"

        def __getattr__(self, name):
            raise AssertionError(f"retained pre-rebuild document used: {name}")

    fresh_document = SimpleNamespace(
        GetType=lambda: 3, GetPathName=lambda: str(drawing),
        GetCurrentSheet=lambda: SimpleNamespace(GetName=lambda: identity["sheet"]),
        GetViews=lambda: ((SimpleNamespace(GetName2=lambda: identity["sheet"]), fresh_view),),
    )

    def get_open_document(path):
        assert show_completed
        assert path == str(drawing)
        calls.append("fresh document")
        return fresh_document

    def show_once(app, journal, report, persist):
        nonlocal show_completed
        show_completed = True
        report["command_completed"] = True
        persist()
        return identity

    def same(left, right):
        assert left is fresh_owners[0] and right is fresh_owners[1]
        calls.append("fresh owners")
        return 0

    monkeypatch.setattr(probe, "show_once", show_once)
    app = SimpleNamespace(
        OpenDoc6=lambda *args: (StaleDocument(), 0, 0),
        GetOpenDocumentByName=get_open_document, IsSame=same,
        CloseDoc=lambda title: calls.append("close without save"),
    )
    if scenario == "mismatched":
        with pytest.raises(RuntimeError, match="differ from the pinned dc892 artifacts"):
            asyncio.run(probe.build(SimpleNamespace(swApp=app)))
    else:
        asyncio.run(probe.build(SimpleNamespace(swApp=app)))
    canonical = json.loads(probe.REPORT.read_text())
    failure = json.loads((out / "failures/section-visibility-probe/report.json").read_text())
    assert canonical == failure
    if scenario == "mismatched":
        assert canonical["status"] == "failed"
        assert canonical["input_sha256_after"] == observed_hashes
        assert calls == []
        return
    assert canonical["status"] == "observation_complete"
    assert len(canonical["after"]["rows"]) == 2
    assert canonical["duplicate_owner_identity"][0]["pairs"][0]["native_is_same"] == 0
    assert canonical["input_sha256_after"] == probe.INPUT_HASHES
    assert calls == ["fresh document", "fresh owners", "close without save"]


def test_cached_probe_has_exact_native_prerequisites_and_report_targets():
    import dodo

    task = dodo._verify_task("pd_section_visibility_probe")
    assert task["task_dep"] == ["drawing:pd_paper_drive_assembly", "assembly:pd_paper_drive"]
    assert task["targets"] == dodo._canonical_targets("verify:pd_section_visibility_probe")
    assert {Path(path).name for path in task["targets"]} == {"report.json", "calls.jsonl"}
    assert any(Path(path).name == "pd-paper-drive-assembly.SLDDRW" for path in task["file_dep"])
    assert "pd_section_visibility_probe" in dodo._VERIFY_NAMES
