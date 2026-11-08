"""Offline controls for the disposable reference-subset discriminator."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import weakref

import pytest

from diagnostics import probe_pd_section_lifetime as experiment
from test_drawing_visibility import visibility_fixture


@pytest.mark.parametrize("case", experiment.CASES)
def test_raw_show_only_varies_retained_graph(tmp_path, monkeypatch, case):
    probe = experiment.probe
    adapter, view, components, calls, selected = visibility_fixture()
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    monkeypatch.setattr(experiment, "capture_before", lambda *args: (adapter.currentModel, view, components, [c.Component for c in components], 2))
    record = {"case": case}
    journal = probe.Journal((tmp_path / "calls.jsonl",))
    try:
        retained = experiment.raw_show(adapter.swApp, journal, record, lambda: None)
        assert components[2].Visible and selected == []
        assert calls == [("show", (components[2].Name,)), ("rebuild",)]
        assert record["command_completed"]
        if case == "raw_frame_ended":
            assert retained is None
        else:
            assert set(retained) == {
                "doc_view_retained": {"model", "view"},
                "components_retained": {"components", "owners", "selected", "selected_owner"},
                "selection_retained": {"manager", "data", "selected_view"},
            }[case]
    finally:
        journal.close()


def test_sparse_capture_limits_owner_reads_when_names_alias(tmp_path, monkeypatch):
    probe = experiment.probe
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    owner_reads = []
    owner = SimpleNamespace(Name2="assembly", GetPathName=lambda: "C:/assembly.SLDASM", ReferencedConfiguration="")

    class Component:
        Visible = True
        def __init__(self, name):
            self.Name = "root/" + name
        @property
        def Component(self):
            owner_reads.append(self.Name)
            return owner

    components = [Component("sh-vn-chain-link<11>"), *[Component("pd-vn-guide-lock-screw<5>") for _ in range(146)]]
    view = SimpleNamespace(RootDrawingComponent2=lambda value: SimpleNamespace(GetChildren=components), GetHiddenComponents=lambda: ())
    monkeypatch.setattr(probe, "fresh_section", lambda *args, **kwargs: (object(), view, {}, "Sheet"))
    record = {"identity": {}, "expected_hidden_after": []}
    journal = probe.Journal((tmp_path / "calls.jsonl",))
    try:
        experiment.sparse_after(object(), journal, record, lambda: None)
        assert len(owner_reads) == 2
        assert len(record["after"]["names"]) == 147
        assert len(record["after"]["witness_indices"]["sentinel"]) == 146
        assert record["after"]["unique_drawing_names"] == 2
    finally:
        journal.close()


@pytest.mark.parametrize("outcome", ["complete", "getter-error"])
def test_cases_reopen_identical_bytes_and_release_graph_before_close(tmp_path, monkeypatch, outcome):
    probe = experiment.probe
    out = tmp_path / "out"
    directory = out / "reports/section-visibility-probe"
    for name, value in {"OUT": out, "DIRECTORY": directory, "REPORT": directory / "report.json", "JOURNAL": directory / "calls.jsonl", "DRAWING": out / probe.INPUT_NAMES[0]}.items():
        monkeypatch.setattr(probe, name, value)
    monkeypatch.setattr(probe._seat_forensics, "OUT_FAILURES", out / "failures")
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(probe._telemetry, "info", lambda message: None)
    hashes = {probe.INPUT_NAMES[0]: experiment.FINAL_DRAWING_SHA, **probe.MODEL_HASHES}
    monkeypatch.setattr(probe, "digest", lambda path: probe.SOURCE_HASHES[Path(path).name] if Path(path).name in probe.SOURCE_HASHES else hashes[Path(path).relative_to(out).as_posix()])
    events = []
    refs = []

    class Token:
        pass

    def raw(app, journal, record, persist):
        token = Token()
        refs.append(weakref.ref(token))
        return {"token": token} if record["case"] != "raw_frame_ended" else None

    def sparse(app, journal, record, persist):
        events.append(record["case"])
        assert (refs[-1]() is not None) == (record["case"] != "raw_frame_ended")
        if outcome == "getter-error":
            raise RuntimeError("native getter failed")
        record["status"] = "observed"

    def close(title):
        assert refs[-1]() is None
        events.append("closed")

    monkeypatch.setattr(experiment, "raw_show", raw)
    monkeypatch.setattr(experiment, "sparse_after", sparse)
    app = SimpleNamespace(OpenDoc6=lambda *args: (SimpleNamespace(GetTitle=lambda: "drawing.SLDDRW"), 0, 0), CloseDoc=close)
    if outcome == "complete":
        asyncio.run(experiment.build(SimpleNamespace(swApp=app)))
        assert events == [event for case in experiment.CASES for event in (case, "closed")]
    else:
        with pytest.raises(RuntimeError, match="native getter failed"):
            asyncio.run(experiment.build(SimpleNamespace(swApp=app)))
        assert events == ["raw_frame_ended", "closed"]
    report = json.loads(probe.REPORT.read_text())
    assert report == json.loads((out / "failures/section-visibility-probe/report.json").read_text())
    assert all(case["input_sha256_after"] == hashes for case in report["cases"])
